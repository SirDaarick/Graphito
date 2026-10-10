"""Evaluation of a selected CharCNN v2 checkpoint: val-only calibration, then test scored once.

`evaluate_run` (design D11-D13, D16) runs after model selection:

1. load `best.pth` from the run directory;
2. score the val representatives, fit Platt calibration on them only (`build_calibration` refuses
   any non-val entry), write `calibration.json` and record it in `config.json`;
3. score the test files exactly once (representatives plus every non-broken test file, so the
   secondary view needs no second pass) and apply the frozen calibration;
4. write the headline metrics (test representatives) in the run root and the secondary view (all
   non-broken test files) in `test_all/`, both with CI95 bootstrapped by `dup_group`, per-group
   breakdowns (lang, course, length bucket), per-generator breakdowns (each model/profile versus
   all humans) and abstention counts;
5. write `scores_val.csv`, `scores_test.csv` and `shortcuts.json`, and extend `report.md`.

Every file is scored; abstention (`effective_length < min_non_ws_chars`) is only counted.
"""

import csv
import io
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import numpy as np
import torch
import torch.nn as nn

from models.char_cnn.v2.checkpoint import load_checkpoint, load_v2_model
from models.char_cnn.v2.config import ALPHABET, UNK_IDX
from models.char_cnn.v2.data import EncodedSet
from models.char_cnn.v2.scoring import score_arrays
from models.char_cnn.v2.shortcuts import LENGTH_BUCKETS, length_bucket, render_markdown
from models.evaluation import metrics as M
from models.evaluation.calibration import ScoredSet, build_calibration, load_calibration, save_calibration
from models.evaluation.manifest import SplitManifest
from models.evaluation.provenance import atomic_write_bytes
from models.evaluation.report import RunContext, compute_metrics, operating_points_from_calibration

__all__ = [
    "CHANNEL",
    "SCORE_NAME",
    "LOW_SUPPORT_MIN",
    "GROUP_KEYS",
    "GENERATOR_KEYS",
    "EvaluationResult",
    "score_split",
    "complete_per_group",
    "per_generator",
    "abstention_counts",
    "update_run_config",
    "evaluate_run",
]

CHANNEL = "char_cnn"
SCORE_NAME = "p_synthetic_raw"
LOW_SUPPORT_MIN = 30  # positives (and, per group, negatives) below this are flagged
GROUP_KEYS = ("lang", "course", "length_bucket")
GENERATOR_KEYS = ("model", "profile")
TEST_VIEWS = {
    "test": ("representatives", "headline: test representatives (one file per dup group)"),
    "test_all": ("all_files", "secondary: all non-broken test files (CI95 by dup_group)"),
}
_SPACE_IDX = ALPHABET.index(" ") + 2
_NEWLINE_IDX = ALPHABET.index("\n") + 2


def _key(value: Any) -> str:
    # Same convention as `models.evaluation.report` group keys.
    return "<none>" if value is None else str(value)


def score_split(
    model: nn.Module, encoded: EncodedSet, device: "str | torch.device", batch_size: int, *, name: str
) -> np.ndarray:
    """Raw windowed p(synthetic) of every sample of one split (`name` labels the pass)."""
    p_synth, _, _ = score_arrays(model, encoded.arrays, device, batch_size)
    return np.asarray(p_synth, dtype=np.float64)


def complete_per_group(per_group: Mapping[str, Mapping], expected: Mapping[str, Iterable[Any]]) -> Dict:
    """Add absent expected groups (`n=0`, null metrics) and a `low_support` flag to every entry.

    A group is low-support when either class has fewer than `LOW_SUPPORT_MIN` files in it.
    """
    out: Dict[str, Dict] = {}
    for name, tables in per_group.items():
        keys = [_key(k) for k in expected.get(name, ())]
        out[name] = {}
        for metric, table in tables.items():
            entries = {g: dict(v) for g, v in table.items()}
            for g in keys:
                entries.setdefault(g, {"n": 0, "n_pos": 0, "value": None, "reason": "empty"})
            for entry in entries.values():
                entry["low_support"] = min(entry["n_pos"], entry["n"] - entry["n_pos"]) < LOW_SUPPORT_MIN
            # Expected groups keep their given order (length buckets ascend); extras follow sorted.
            order = keys + sorted(set(entries) - set(keys))
            out[name][metric] = {g: entries[g] for g in order}
    return out


def per_generator(
    samples: Sequence, y: np.ndarray, scores: np.ndarray, operating_points: Mapping[str, Mapping],
    expected: Mapping[str, Iterable[Any]],
) -> Dict[str, Any]:
    """Each generator group's AI files versus all human files (D13).

    Humans have no model/profile, so a plain per-group AUC would be single-class; here each group
    is (its AI files) + (every human file). Recall is the share of the group's AI files at or
    above each operating point. `low_support` when the group has fewer than 30 AI files.
    """
    y = np.asarray(y)
    scores = np.asarray(scores, dtype=np.float64)
    human = y == 0
    out: Dict[str, Any] = {"comparison": "AI files of the group vs all human files of the view"}
    for key in GENERATOR_KEYS:
        values = np.array([_key(getattr(s, key)) for s in samples], dtype=object)
        groups = sorted({_key(v) for v in expected.get(key, ())} | set(values[y == 1].tolist()))
        table = {}
        for group in groups:
            pos = (y == 1) & (values == group)
            sel = pos | human
            n_pos = int(pos.sum())
            roc = M.roc_auc(y[sel], scores[sel]) if n_pos else None
            ap = M.average_precision(y[sel], scores[sel]) if n_pos else None
            recall = {
                point: (
                    float(np.mean(scores[pos] >= p["threshold"]))
                    if n_pos and p.get("threshold") is not None
                    else None
                )
                for point, p in operating_points.items()
            }
            table[group] = {
                "n_pos": n_pos,
                "n_neg": int(human.sum()),
                "roc_auc": roc,
                "pr_auc": ap,
                "reason": None if roc is not None else ("empty" if n_pos == 0 else M.undefined_reason(y[sel])),
                "recall": recall,
                "low_support": n_pos < LOW_SUPPORT_MIN,
            }
        out[key] = table
    return out


def _effective_lengths(encoded: EncodedSet) -> np.ndarray:
    # Normalized text is pure ALPHABET, so every non-space/newline position is a real character;
    # an empty text is encoded as [UNK] and has effective length 0.
    return np.array(
        [int(np.count_nonzero((a != UNK_IDX) & (a != _SPACE_IDX) & (a != _NEWLINE_IDX))) for a in encoded.arrays],
        dtype=np.int64,
    )


def abstention_counts(encoded: EncodedSet, min_non_ws_chars: int) -> Dict[str, int]:
    """Files the deployment policy would abstain on, per class (they are still scored, D16)."""
    abstained = _effective_lengths(encoded) < min_non_ws_chars
    ai = int(np.count_nonzero(abstained & (encoded.y == 1)))
    human = int(np.count_nonzero(abstained & (encoded.y == 0)))
    return {"human": human, "ai": ai, "total": human + ai, "n": len(encoded)}


def _union(*views: EncodedSet) -> EncodedSet:
    seen, samples, arrays = set(), [], []
    for view in views:
        for sample, array in zip(view.samples, view.arrays):
            if sample.id not in seen:
                seen.add(sample.id)
                samples.append(sample)
                arrays.append(array)
    return EncodedSet.build(samples, arrays)


def _write_csv(path: Path, header: Sequence[str], rows: Iterable[Sequence[Any]]) -> None:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    atomic_write_bytes(path, out.getvalue().encode("utf-8"))


def _write_json(path: Path, doc: Mapping[str, Any]) -> None:
    text = json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    atomic_write_bytes(path, (text + "\n").encode("utf-8"))


def update_run_config(ctx: RunContext, **fields: Any) -> RunContext:
    """Rewrite the run's `config.json` with extra top-level fields (provenance completion, D12)."""
    doc = {**ctx.config, **fields}
    _write_json(ctx.path / "config.json", doc)
    return replace(ctx, config=doc)


def _append_report(path: Path, sections: Sequence[str]) -> None:
    text = path.read_text(encoding="utf-8") + "\n" + "\n".join(sections)
    atomic_write_bytes(path, text.encode("utf-8"))


def _fmt(value: Optional[float]) -> str:
    return "null" if value is None else f"{value:.4f}"


def _view_section(metrics: Mapping[str, Any]) -> str:
    view = metrics["test_view"]
    lines = ["## Test view", "", f"- {view['label']} (n={metrics['n']}, n_pos={metrics['n_pos']})"]
    lines.append(f"- Scores: Platt-calibrated `{SCORE_NAME}` (calibration fitted on val only)")
    flagged = [
        f"{name}={group} (n={entry['n']}, n_pos={entry['n_pos']})"
        for name, tables in metrics["per_group"].items()
        for group, entry in tables["roc_auc"].items()
        if entry["low_support"]
    ]
    lines.append(f"- Low-support groups (< {LOW_SUPPORT_MIN} per class): " + (", ".join(flagged) or "none"))
    return "\n".join(lines) + "\n"


def _generator_section(metrics: Mapping[str, Any]) -> str:
    points = list(metrics["operating_points"])
    lines = [
        "## Per generator (vs all humans)",
        "",
        f"Each group's AI files against every human file of the view; low_support when n_pos < {LOW_SUPPORT_MIN}.",
        "",
        "| Breakdown | Group | n_pos | n_neg | ROC-AUC | PR-AUC | " + " | ".join(f"recall@{p}" for p in points)
        + " | Support |",
        "|---|---|---|---|---|---|" + "---|" * len(points) + "---|",
    ]
    for key in GENERATOR_KEYS:
        for group, e in metrics["per_generator"][key].items():
            recalls = " | ".join(_fmt(e["recall"][p]) for p in points)
            support = "low_support" if e["low_support"] else "ok"
            lines.append(
                f"| {key} | {group} | {e['n_pos']} | {e['n_neg']} | {_fmt(e['roc_auc'])} | {_fmt(e['pr_auc'])} "
                f"| {recalls} | {support} |"
            )
    return "\n".join(lines) + "\n"


def _abstention_section(n_abstained: Mapping[str, Mapping[str, int]], min_non_ws_chars: int) -> str:
    lines = [
        "## Abstention (reported only)",
        "",
        f"Files with fewer than {min_non_ws_chars} non-whitespace normalized chars; they are still scored.",
        "",
        "| Split | n | human | ai | total |",
        "|---|---|---|---|---|",
    ]
    for split, c in n_abstained.items():
        lines.append(f"| {split} | {c['n']} | {c['human']} | {c['ai']} | {c['total']} |")
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class EvaluationResult:
    run: RunContext
    calibration_path: Path
    calibration_sha256: str
    headline: Dict[str, Any]
    secondary: Dict[str, Any]


def evaluate_run(
    ctx: RunContext,
    manifest: SplitManifest,
    views: Mapping[str, EncodedSet],
    device: "str | torch.device",
    *,
    seed: int,
    n_boot: int = 1000,
    batch_size: int = 32,
    shortcuts: Optional[Mapping[str, Any]] = None,
    data_summary: Optional[Mapping[str, Any]] = None,
) -> EvaluationResult:
    """Calibrate on val, then score test once and write every report artifact (see module doc)."""
    run_dir = ctx.path
    checkpoint = load_checkpoint(run_dir / "best.pth", map_location=device)
    model = load_v2_model(checkpoint, device)
    min_non_ws = model.config.min_non_ws_chars

    # Calibration: val representatives only.
    val = views["val"]
    p_val = score_split(model, val, device, batch_size, name="val")
    scored = ScoredSet.from_samples(val.samples, p_val, val.y, manifest_sha256=manifest.sha256)
    artifact, _ = build_calibration(
        scored, channel=CHANNEL, score_name=SCORE_NAME, seed=seed, method="platt", manifest=manifest
    )
    calibration_path = run_dir / "calibration.json"
    save_calibration(artifact, calibration_path)
    calibration = load_calibration(calibration_path)
    points = operating_points_from_calibration(calibration)
    ctx = update_run_config(
        ctx,
        calibration_path=calibration_path.as_posix(),
        calibration_sha256=calibration.sha256,
        threshold_source=f"calibration:{calibration.sha256}",
    )
    _write_csv(
        run_dir / "scores_val.csv",
        ("id", "y", "raw", "calibrated"),
        zip(val.ids, val.y.tolist(), p_val.tolist(), calibration.apply(p_val).tolist()),
    )

    # Test: one scoring pass over every test file, after calibration exists.
    test_files = _union(views["test"], views["test_all"])
    raw_by_id = dict(zip(test_files.ids, score_split(model, test_files, device, batch_size, name="test").tolist()))
    representatives = set(views["test"].ids)
    raw_test = np.array([raw_by_id[i] for i in test_files.ids], dtype=np.float64)
    _write_csv(
        run_dir / "scores_test.csv",
        ("id", "y", "raw", "calibrated", "representative"),
        zip(
            test_files.ids, test_files.y.tolist(), raw_test.tolist(), calibration.apply(raw_test).tolist(),
            [int(i in representatives) for i in test_files.ids],
        ),
    )

    population = manifest.samples()  # non-broken, non-excluded entries of every split
    expected_groups = {
        "lang": sorted({s.lang for s in population}),
        "course": sorted({s.course for s in population}),
        "length_bucket": list(LENGTH_BUCKETS),
    }
    ai_population = [s for s in population if s.source == "ai"]
    expected_generators = {key: sorted({_key(getattr(s, key)) for s in ai_population}) for key in GENERATOR_KEYS}
    n_abstained = {
        name: abstention_counts(views[name], min_non_ws) for name in ("val", "test", "test_all")
    }

    written: Dict[str, Dict[str, Any]] = {}
    for name, (mode, label) in TEST_VIEWS.items():
        view = views[name]
        raw = np.array([raw_by_id[i] for i in view.ids], dtype=np.float64)
        calibrated = calibration.apply(raw)
        metrics = compute_metrics(
            view.y,
            calibrated,
            channel=CHANNEL,
            split="test",
            mode=mode,
            seed=seed,
            operating_points=points,
            groups={
                "lang": [s.lang for s in view.samples],
                "course": [s.course for s in view.samples],
                "length_bucket": [length_bucket(int(n)) for n in view.lengths],
            },
            bootstrap_groups=[s.dup_group or s.id for s in view.samples],
            bootstrap_unit="dup_group",
            n_boot=n_boot,
        )
        metrics["per_group"] = complete_per_group(metrics["per_group"], expected_groups)
        metrics["per_generator"] = per_generator(view.samples, view.y, calibrated, points, expected_generators)
        metrics["test_view"] = {"name": name, "label": label}
        metrics["n_abstained"] = {**n_abstained, "min_non_ws_chars": min_non_ws}
        metrics["selected_epoch"] = checkpoint["config"].get("epoch")
        if data_summary is not None:
            metrics["data_summary"] = dict(data_summary)

        target = ctx if name == "test" else RunContext(
            path=run_dir / name, channel=ctx.channel, config={**ctx.config, "mode": mode}
        )
        target.path.mkdir(exist_ok=True)
        written[name] = target.write(view.y, calibrated, metrics)
        _append_report(
            target.path / "report.md",
            [_view_section(metrics), _generator_section(metrics), _abstention_section(n_abstained, min_non_ws)],
        )

    if shortcuts is not None:
        _write_json(run_dir / "shortcuts.json", shortcuts)
        _append_report(run_dir / "report.md", [render_markdown(shortcuts)])

    return EvaluationResult(
        run=ctx,
        calibration_path=calibration_path,
        calibration_sha256=calibration.sha256,
        headline=written["test"],
        secondary=written["test_all"],
    )

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

`python -m models.char_cnn.v2.evaluate --run-dir <run>` re-runs steps 2-5 from an existing run's
`best.pth` without retraining (same manifest, data root, seed and `--limit-per-class` as the
run). It refuses (exit 1, nothing written) a run whose status is not `complete` or `failed` during
`evaluate` (a `running` run is never touched), a `best.pth` whose sha256 differs from the run's
recorded `best_sha256`, a run that already has calibration or metrics unless `--force` is given,
and a run whose manifest or data cannot be loaded. Every file of the run (except `best.pth`) is
snapshotted first; when the evaluation then fails, the snapshot is restored, so no partial outputs
are left: a `complete` run keeps its previous outputs and status (exit 4), a run that had failed
during `evaluate` is marked failed again with the new reason (exit 3).
"""

import argparse
import csv
import io
import json
import logging
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np
import torch
import torch.nn as nn

from models.char_cnn.v2.checkpoint import load_checkpoint, load_v2_model
from models.char_cnn.v2.config import UNK_IDX, char_index
from models.char_cnn.v2.data import EncodedSet, data_summary, limit_per_class, load_views, view_samples
from models.char_cnn.v2.runs import (
    CHECKPOINT_NAME,
    DEFAULT_EVAL_BATCH_SIZE,
    DEFAULT_N_BOOT,
    PARTIAL_WRITE_EXIT,
    REFUSED_EXIT,
    RUN_FAILED_EXIT,
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_RUNNING,
    describe_error,
    resolve_device,
    set_run_status,
    write_json,
)
from models.char_cnn.v2.scoring import score_arrays
from models.char_cnn.v2.shortcuts import LENGTH_BUCKETS, ShortcutAudit, length_bucket, render_markdown
from models.evaluation import metrics as M
from models.evaluation.calibration import ScoredSet, build_calibration, load_calibration, save_calibration
from models.evaluation.manifest import Sample, SplitManifest, load_manifest
from models.evaluation.provenance import atomic_write_bytes, file_sha256
from models.evaluation.report import RunContext, compute_metrics, operating_points_from_calibration

__all__ = [
    "CHANNEL",
    "SCORE_NAME",
    "LOW_SUPPORT_MIN",
    "GROUP_KEYS",
    "GENERATOR_KEYS",
    "SHORTCUT_VIEWS",
    "STATUS_RUNNING",
    "STATUS_COMPLETE",
    "STATUS_FAILED",
    "REFUSED_EXIT",
    "RUN_FAILED_EXIT",
    "PARTIAL_WRITE_EXIT",
    "EVALUABLE_FAILURE_STAGE",
    "EvaluationResult",
    "resolve_device",
    "write_json",
    "write_csv",
    "append_report",
    "describe_error",
    "set_run_status",
    "score_split",
    "group_labels",
    "expected_groups",
    "expected_generators",
    "load_run_views",
    "complete_per_group",
    "per_generator",
    "abstention_counts",
    "render_generator_section",
    "update_run_config",
    "evaluate_run",
    "reevaluate",
    "main",
]

logger = logging.getLogger(__name__)

CHANNEL = "char_cnn"
SCORE_NAME = "p_synthetic_raw"
LOW_SUPPORT_MIN = 30  # positives (and, per group, negatives) below this are flagged
GROUP_KEYS = ("lang", "course", "length_bucket")
GENERATOR_KEYS = ("model", "profile")
SHORTCUT_VIEWS = ("train", "test")  # representatives audited for residual shortcuts
TEST_VIEWS = {
    "test": ("representatives", "headline: test representatives (one file per dup group)"),
    "test_all": ("all_files", "secondary: all non-broken test files (CI95 by dup_group)"),
}
# Status constants, exit codes and the JSON/status helpers live in `v2/runs.py`; they are
# imported above and stay importable from this module.
# Files whose presence means a run was already evaluated (re-evaluation needs --force).
EVALUATION_ARTIFACTS = ("calibration.json", "metrics.json")
# A failed run may be re-evaluated only when it failed in this stage (its checkpoint is final).
EVALUABLE_FAILURE_STAGE = "evaluate"
_SPACE_IDX = char_index(" ")
_NEWLINE_IDX = char_index("\n")


def _key(value: Any) -> str:
    # Same convention as `models.evaluation.report` group keys.
    return "<none>" if value is None else str(value)


def score_split(
    model: nn.Module, encoded: EncodedSet, device: "str | torch.device", batch_size: int, *, name: str
) -> np.ndarray:
    """Raw windowed p(synthetic) of every sample of one split (`name` labels the pass in the log)."""
    logger.info("scoring %s: %d files", name, len(encoded))
    p_synth, _, _ = score_arrays(model, encoded.arrays, device, batch_size)
    return np.asarray(p_synth, dtype=np.float64)


def group_labels(encoded: EncodedSet) -> Dict[str, List[str]]:
    """Per-sample labels of every `GROUP_KEYS` breakdown (length buckets on normalized length)."""
    labels = {
        "lang": [s.lang for s in encoded.samples],
        "course": [s.course for s in encoded.samples],
        "length_bucket": [length_bucket(int(n)) for n in encoded.lengths],
    }
    return {key: labels[key] for key in GROUP_KEYS}


def expected_groups(population: Sequence[Sample]) -> Dict[str, List[str]]:
    """Every group a `GROUP_KEYS` breakdown should list, so absent groups report `n=0`."""
    expected = {
        "lang": sorted({s.lang for s in population}),
        "course": sorted({s.course for s in population}),
        "length_bucket": list(LENGTH_BUCKETS),
    }
    return {key: expected[key] for key in GROUP_KEYS}


def expected_generators(population: Sequence[Sample]) -> Dict[str, List[str]]:
    """Every generator group (model/profile of the AI files) a per-generator table should list."""
    ai = [s for s in population if s.source == "ai"]
    return {key: sorted({_key(getattr(s, key)) for s in ai}) for key in GENERATOR_KEYS}


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
    above each operating point. `low_support` when the group has fewer than `LOW_SUPPORT_MIN`
    AI files. AI files without a model/profile form the `<none>` group.
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


def write_csv(path: Path, header: Sequence[str], rows: Iterable[Sequence[Any]]) -> None:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    atomic_write_bytes(path, out.getvalue().encode("utf-8"))


def update_run_config(ctx: RunContext, **fields: Any) -> RunContext:
    """Rewrite the run's `config.json` with extra top-level fields (provenance completion, D12)."""
    doc = {**ctx.config, **fields}
    write_json(ctx.path / "config.json", doc)
    return replace(ctx, config=doc)


def append_report(path: Path, sections: Sequence[str]) -> None:
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


def render_generator_section(metrics: Mapping[str, Any]) -> str:
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
    n_boot: int = DEFAULT_N_BOOT,
    batch_size: int = DEFAULT_EVAL_BATCH_SIZE,
    shortcuts: Optional[Mapping[str, Any]] = None,
    data_summary: Optional[Mapping[str, Any]] = None,
) -> EvaluationResult:
    """Calibrate on val, then score test once and write every report artifact (see module doc)."""
    run_dir = ctx.path
    checkpoint = load_checkpoint(run_dir / CHECKPOINT_NAME, map_location=device)
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
    write_csv(
        run_dir / "scores_val.csv",
        ("id", "y", "raw", "calibrated"),
        zip(val.ids, val.y.tolist(), p_val.tolist(), calibration.apply(p_val).tolist()),
    )

    # Test: one scoring pass over every test file, after calibration exists.
    test_files = _union(views["test"], views["test_all"])
    raw_by_id = dict(zip(test_files.ids, score_split(model, test_files, device, batch_size, name="test").tolist()))
    representatives = set(views["test"].ids)
    raw_test = np.array([raw_by_id[i] for i in test_files.ids], dtype=np.float64)
    write_csv(
        run_dir / "scores_test.csv",
        ("id", "y", "raw", "calibrated", "representative"),
        zip(
            test_files.ids, test_files.y.tolist(), raw_test.tolist(), calibration.apply(raw_test).tolist(),
            [int(i in representatives) for i in test_files.ids],
        ),
    )

    population = manifest.samples()  # non-broken, non-excluded entries of every split
    groups_expected = expected_groups(population)
    generators_expected = expected_generators(population)
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
            groups=group_labels(view),
            bootstrap_groups=[s.dup_group or s.id for s in view.samples],
            bootstrap_unit="dup_group",
            n_boot=n_boot,
        )
        metrics["per_group"] = complete_per_group(metrics["per_group"], groups_expected)
        metrics["per_generator"] = per_generator(view.samples, view.y, calibrated, points, generators_expected)
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
        append_report(
            target.path / "report.md",
            [_view_section(metrics), render_generator_section(metrics), _abstention_section(n_abstained, min_non_ws)],
        )

    if shortcuts is not None:
        write_json(run_dir / "shortcuts.json", shortcuts)
        append_report(run_dir / "report.md", [render_markdown(shortcuts)])

    return EvaluationResult(
        run=ctx,
        calibration_path=calibration_path,
        calibration_sha256=calibration.sha256,
        headline=written["test"],
        secondary=written["test_all"],
    )


# --- re-evaluation of an existing run (CLI) -------------------------------------------------------


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_run_views(
    manifest: SplitManifest, root: "str | Path", limit: Optional[int] = None
) -> "tuple[Dict[str, EncodedSet], ShortcutAudit]":
    """Encode every view as the trainer did (one pass, shortcut audit fed in it), then apply the
    run's debug `--limit-per-class` when it had one."""
    audit = ShortcutAudit({view: [s.id for s in view_samples(manifest, view)] for view in SHORTCUT_VIEWS})
    views = load_views(manifest, root=root, on_text=audit)
    if limit is not None:
        views = {name: limit_per_class(view, limit) for name, view in views.items()}
    return views, audit


def reevaluate(
    run_dir: Path,
    manifest: SplitManifest,
    views: Mapping[str, EncodedSet],
    audit: ShortcutAudit,
    device: "str | torch.device",
    *,
    n_boot: Optional[int] = None,
    batch_size: Optional[int] = None,
) -> EvaluationResult:
    """Re-run `evaluate_run` on a finished run's `best.pth` with the run's own seed and settings.

    The run is marked `running` first (and `best_sha256` recorded when the run had none); the
    caller marks it `complete` or restores it on failure.
    """
    run_dir = Path(run_dir)
    doc = _read_json(run_dir / "config.json")
    hyperparams = doc.get("config", {}).get("hyperparams", {})
    ctx = RunContext(path=run_dir, channel=doc["channel"], config=doc)
    ctx = update_run_config(
        ctx,
        status=STATUS_RUNNING,
        failure=None,
        best_sha256=doc.get("best_sha256") or file_sha256(run_dir / CHECKPOINT_NAME),
        last_evaluation={"by": "models.char_cnn.v2.evaluate", "at": datetime.now(timezone.utc).isoformat()},
    )
    return evaluate_run(
        ctx,
        manifest,
        views,
        device,
        seed=doc["seed"],
        n_boot=n_boot or hyperparams.get("n_boot", DEFAULT_N_BOOT),
        batch_size=batch_size or hyperparams.get("eval_batch_size", DEFAULT_EVAL_BATCH_SIZE),
        shortcuts=audit.to_dict(),
        data_summary=data_summary(views),
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m models.char_cnn.v2.evaluate",
        description="Re-run val calibration and the single test evaluation from an existing run's best.pth.",
    )
    p.add_argument("--run-dir", type=Path, required=True, help="run directory holding config.json and best.pth")
    p.add_argument("--force", action="store_true", help="recompute even if calibration/metrics already exist")
    p.add_argument("--device", default=None, help="torch device (default: cuda if available, else cpu)")
    p.add_argument("--manifest", type=Path, default=None, help="manifest path (default: the run's; sha256 must match)")
    p.add_argument("--root", type=Path, default=None, help="corpus root (default: the run's data_root)")
    p.add_argument("--n-boot", type=int, default=None, help="bootstrap resamples (default: the run's)")
    p.add_argument("--batch-size", type=int, default=None, help="windows per scoring batch (default: the run's)")
    return p


def _refuse(message: str) -> int:
    print(f"REFUSED: {message}", file=sys.stderr)
    return REFUSED_EXIT


def _status_refusal(doc: Mapping[str, Any]) -> Optional[str]:
    """Why a run's status forbids re-evaluation, or None when it is `complete` or failed in `evaluate`."""
    status = doc.get("status")
    if status == STATUS_COMPLETE:
        return None
    stage = (doc.get("failure") or {}).get("stage")
    if status == STATUS_FAILED and stage == EVALUABLE_FAILURE_STAGE:
        return None
    if status == STATUS_FAILED:
        return (
            f"the run has status {status!r} in stage {stage!r}, not {EVALUABLE_FAILURE_STAGE!r}; retrain instead"
        )
    return f"the run has status {status!r}; only a complete run or one that failed during evaluation can be re-evaluated"


@dataclass(frozen=True)
class _Snapshot:
    """Every file of a run directory except `best.pth`, plus its directories, held in memory."""

    files: Dict[Path, bytes]
    dirs: frozenset

    @classmethod
    def take(cls, run_dir: Path) -> "_Snapshot":
        files, dirs = {}, set()
        for path in run_dir.rglob("*"):
            rel = path.relative_to(run_dir)
            if path.is_dir():
                dirs.add(rel)
            elif rel != Path(CHECKPOINT_NAME):
                files[rel] = path.read_bytes()
        return cls(files=files, dirs=frozenset(dirs))

    def restore(self, run_dir: Path) -> None:
        """Delete what the failed evaluation created and rewrite every file it changed."""
        for path in sorted(run_dir.rglob("*"), reverse=True):  # children before their directory
            rel = path.relative_to(run_dir)
            if path.is_dir():
                if rel not in self.dirs:
                    path.rmdir()
            elif rel != Path(CHECKPOINT_NAME) and rel not in self.files:
                path.unlink()
        for rel, data in self.files.items():
            path = run_dir / rel
            if not path.is_file() or path.read_bytes() != data:
                atomic_write_bytes(path, data)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Exit 0 when evaluated, else `REFUSED_EXIT`, `PARTIAL_WRITE_EXIT` or `RUN_FAILED_EXIT` (module doc)."""
    parser = build_parser()
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    for name in ("n_boot", "batch_size"):
        value = getattr(args, name)
        if value is not None and value < 1:
            parser.error(f"--{name.replace('_', '-')} must be >= 1 (got {value})")
    run_dir = Path(args.run_dir)
    for required in ("config.json", CHECKPOINT_NAME):
        if not (run_dir / required).is_file():
            return _refuse(f"{run_dir / required} does not exist; nothing to evaluate")
    try:
        doc = _read_json(run_dir / "config.json")
    except (OSError, ValueError) as exc:
        return _refuse(f"cannot read {run_dir / 'config.json'}: {describe_error(exc)}")
    refusal = _status_refusal(doc)
    if refusal is not None:
        return _refuse(f"{run_dir}: {refusal}")
    recorded = doc.get("best_sha256")
    if recorded and file_sha256(run_dir / CHECKPOINT_NAME) != recorded:
        return _refuse(f"{run_dir / CHECKPOINT_NAME} does not match the run's recorded best_sha256 {recorded}")
    existing = [name for name in EVALUATION_ARTIFACTS if (run_dir / name).exists()]
    if existing and not args.force:
        return _refuse(f"{run_dir} already has {existing}; pass --force to recompute them")
    try:
        manifest = load_manifest(args.manifest or doc["manifest_path"], doc["manifest_sha256"])
    except (OSError, ValueError, KeyError) as exc:
        return _refuse(f"cannot load the run's manifest: {describe_error(exc)}")

    run_config = doc.get("config", {})
    root = args.root or run_config.get("data_root")
    if root is None:
        return _refuse("the run records no data_root; pass --root")
    try:
        views, audit = load_run_views(manifest, root, run_config.get("hyperparams", {}).get("limit_per_class"))
    except (OSError, ValueError) as exc:
        return _refuse(f"cannot load the run's data: {describe_error(exc)} (run left unchanged)")

    snapshot = _Snapshot.take(run_dir)
    try:
        reevaluate(
            run_dir, manifest, views, audit, resolve_device(args.device), n_boot=args.n_boot,
            batch_size=args.batch_size,
        )
    except BaseException as exc:  # restore the previous outputs instead of leaving partial ones
        return _evaluation_failed(run_dir, doc, snapshot, exc)
    set_run_status(run_dir, STATUS_COMPLETE)
    print(f"evaluated: {run_dir}")
    return 0


def _evaluation_failed(run_dir: Path, doc: Mapping[str, Any], snapshot: _Snapshot, exc: BaseException) -> int:
    """Restore the run, then mark it failed unless it was `complete`; re-raises non-`Exception`s."""
    reason = describe_error(exc)
    try:
        snapshot.restore(run_dir)
    except Exception as restore_exc:  # outputs may be partial: say so in config.json
        reason = f"{reason}; restoring the previous outputs failed: {describe_error(restore_exc)}"
        set_run_status(run_dir, STATUS_FAILED, stage=EVALUABLE_FAILURE_STAGE, reason=reason)
        print(f"ERROR: evaluation failed: {reason}; {run_dir / 'config.json'} marked failed", file=sys.stderr)
        if not isinstance(exc, Exception):
            raise exc
        return RUN_FAILED_EXIT
    if not isinstance(exc, Exception):  # KeyboardInterrupt and friends: restored, then propagated
        raise exc
    if doc.get("status") == STATUS_COMPLETE:
        print(f"ERROR: evaluation failed: {reason}; previous outputs and status of {run_dir} restored", file=sys.stderr)
        return PARTIAL_WRITE_EXIT
    set_run_status(run_dir, STATUS_FAILED, stage=EVALUABLE_FAILURE_STAGE, reason=reason)
    print(
        f"ERROR: evaluation failed: {reason}; previous outputs restored, {run_dir / 'config.json'} marked failed",
        file=sys.stderr,
    )
    return RUN_FAILED_EXIT


if __name__ == "__main__":
    sys.exit(main())

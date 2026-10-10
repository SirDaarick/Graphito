#!/usr/bin/env python3
"""Benchmark suite: channel A (semantic), channel B (stylometry) and a provisional fused decision.

Reads a golden manifest built by data/golden_set/build_manifest.py from the TEST split of the
split manifest, scores every submission with the selected engine (stub|real) and writes one run
directory per channel through `models.evaluation` (metrics with bootstrap CI95, curves, plots,
report.md, provenance in config.json):

    runs/benchmark/<ts>/config.json, summary.json, [calibration_<channel>.json]
    runs/benchmark/<ts>/{channel_a,channel_b,fused}/<ts>/{config,metrics}.json, report.md, ...

Samples (BS1): every golden sample must be tagged `test` AND its split id must be among the
`load_split("test")` entries of the split manifest whose sha256 the golden manifest records;
anything else raises naming the id.

Scores:
    channel_a : raw cosine similarity of the engine embeddings to the best reference of the same
                problem (in-memory top-1), label = label_copy. Not the backend sigmoid.
    channel_b : ai_prob, label = label_ai.
    fused     : label = copy OR ai, score = max of the calibrated channel scores. Provisional
                decision = OR of the calibrated channel decisions (production fusion: SDD-4).

Modes (thresholds always come from calibration files, never from constants):
    calibrated-fit-in-run : score the VAL golden set (--val-manifest), fit one calibration per
                            channel on it, write calibration_<channel>.json into the run dir,
                            reload it frozen, then score the test set.
    calibrated-frozen     : load existing calibration_<channel>.json (--calibration-dir or
                            --calibration-a/-b); missing files fail with the calibration step.
    uncalibrated          : threshold-free metrics only (no operating points, no fused run).

Default calibrators: channel A = isotonic, because raw cosine lies in [-1, 1] while temperature
and Platt need scores in [0, 1]; channel B = platt (ai_prob is a probability). Override with
--method-a / --method-b.

Results on the stub engine or on synthetic fixtures are NOT evidence about the real models.

Usage:
    python scripts/benchmark_suite.py --manifest data/golden_set/manifest.json \\
        --calibrate --val-manifest data/golden_set/manifest_val.json --engine stub
    python scripts/benchmark_suite.py --manifest data/golden_set/manifest.json \\
        --mode calibrated-frozen --calibration-dir runs/benchmark/<ts>
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

from models.evaluation import metrics as M  # noqa: E402
from models.evaluation.calibration import (  # noqa: E402
    ScoredSet,
    build_calibration,
    load_calibration,
    save_calibration,
)
from models.evaluation.dedup import UnionFind  # noqa: E402
from models.evaluation.manifest import DEFAULT_MANIFEST, load_manifest, load_split  # noqa: E402
from models.evaluation.report import (  # noqa: E402
    RunContext,
    compute_metrics,
    operating_points_from_calibration,
)

CHANNELS = ("channel_a", "channel_b")
FUSED = "fused"
MODES = ("calibrated-fit-in-run", "calibrated-frozen", "uncalibrated")
DEFAULT_METHODS = {"channel_a": "isotonic", "channel_b": "platt"}
SCORE_NAMES = {"channel_a": "raw_cosine", "channel_b": "ai_prob"}
LABELS = {"channel_a": "label_copy", "channel_b": "label_ai"}
DECISION_TRUE = 1  # fused operating points threshold the 0/1 OR decision at "true"
CALIBRATION_STEP = (
    "run the calibration step first: python scripts/benchmark_suite.py --mode calibrated-fit-in-run "
    "--manifest <test golden manifest> --val-manifest <val golden manifest> (it writes "
    "calibration_<channel>.json into its run dir), then pass --calibration-dir <that run dir> "
    "or --calibration-a/--calibration-b"
)


class BenchmarkError(Exception):
    """An actionable usage error (missing calibration, missing val manifest, hash mismatch)."""


# --------------------------------------------------------------------------- scoring
def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Raw cosine similarity in [-1, 1] (0 for a zero vector); no clipping, no calibration."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / denom) if denom else float(0)


def make_engine(name: str):
    if name == "stub":
        from app.infrastructure.inference.stub_engine import StubInferenceEngine

        return StubInferenceEngine()
    from app.infrastructure.inference.real_engine import RealBimodalInferenceEngine

    return RealBimodalInferenceEngine()


async def score_manifest(golden: Mapping[str, Any], root: Path, engine) -> List[Dict[str, Any]]:
    """One scored record per submission: raw cosine to the best reference (None when the
    problem has no reference), ai_prob, labels and split metadata."""
    samples = golden["samples"]
    refs_by_problem: Dict[str, List[List[float]]] = {}
    for s in samples:
        if s["role"] == "reference":
            code = (Path(root) / s["path"]).read_text(encoding="utf-8", errors="replace")
            emb = await engine.extract_semantic_embedding(code, lang=s["lang"])
            refs_by_problem.setdefault(s["problem_id"], []).append(emb)

    scored: List[Dict[str, Any]] = []
    for s in samples:
        if s["role"] != "submission":
            continue
        code = (Path(root) / s["path"]).read_text(encoding="utf-8", errors="replace")
        emb = await engine.extract_semantic_embedding(code, lang=s["lang"])
        ai_prob = await engine.predict_synthetic_prob(code)
        refs = refs_by_problem.get(s["problem_id"], [])
        scored.append(
            {
                **{k: s.get(k) for k in ("id", "split_id", "split", "problem_id", "lang", "model",
                                         "dup_group", "cluster_id")},
                "label_copy": bool(s["label_copy"]),
                "label_ai": bool(s["label_ai"]),
                "sim": max((cosine(emb, r) for r in refs), default=None),
                "ai_prob": float(ai_prob),
            }
        )
    return scored


def fuse(cal_a: np.ndarray, cal_b: np.ndarray, t_a: float, t_b: float):
    """Provisional fusion: score = max of calibrated scores, decision = OR of channel decisions."""
    cal_a, cal_b = np.asarray(cal_a, dtype=np.float64), np.asarray(cal_b, dtype=np.float64)
    return np.maximum(cal_a, cal_b), (cal_a >= t_a) | (cal_b >= t_b)


# --------------------------------------------------------------------------- split gate
def require_split(samples: Sequence[Mapping], split: str, split_manifest_path: Path, sha256: Optional[str]) -> None:
    """Raise naming the first sample that is not an included `split` entry of the manifest."""
    for s in samples:
        if s.get("split") != split:
            raise ValueError(
                f"golden sample {s['id']} (split id {s.get('split_id')}) is {s.get('split')!r}; "
                f"this step accepts {split!r} only"
            )
    allowed = {e.id for e in load_split(split, path=split_manifest_path, expected_sha256=sha256)}
    for s in samples:
        if s.get("split_id") not in allowed:
            raise ValueError(
                f"golden sample {s['id']} has split id {s.get('split_id')}, which is not an included "
                f"{split!r} entry of {split_manifest_path}"
            )


def _source_sha(golden: Mapping, which: str) -> str:
    sha = golden.get("source_manifest_sha256")
    if not sha:
        raise ValueError(
            f"{which} golden manifest has no source_manifest_sha256; rebuild it with "
            "data/golden_set/build_corpus.py and build_manifest.py from the split manifest"
        )
    return sha


# --------------------------------------------------------------------------- calibration
def resolve_calibrations(paths: Mapping[str, Optional[Path]], manifest_sha256: str) -> Dict[str, Any]:
    """Load frozen calibrations; missing or mismatched files raise `BenchmarkError`."""
    loaded = {}
    for channel in CHANNELS:
        path = paths.get(channel)
        if path is None or not Path(path).is_file():
            shown = path if path is not None else f"calibration_{channel}.json (no path given)"
            raise BenchmarkError(f"missing calibration for {channel}: {shown}; {CALIBRATION_STEP}")
        cal = load_calibration(path)
        if cal.artifact["channel"] != channel:
            raise BenchmarkError(f"{path} is a calibration for {cal.artifact['channel']}, not {channel}")
        if cal.artifact["manifest"]["sha256"] != manifest_sha256:
            raise BenchmarkError(
                f"{path} was fitted on split manifest sha256 {cal.artifact['manifest']['sha256']}, "
                f"but the golden set comes from {manifest_sha256}; {CALIBRATION_STEP}"
            )
        loaded[channel] = cal
    return loaded


def _channel_rows(rows: List[Dict], channel: str) -> List[Dict]:
    """Channel A needs a reference in the problem; channel B scores every submission."""
    return [r for r in rows if r["sim"] is not None] if channel != "channel_b" else rows


def _raw_scores(rows: List[Dict], channel: str) -> np.ndarray:
    return np.array([r["sim"] if channel == "channel_a" else r["ai_prob"] for r in rows], dtype=np.float64)


def _labels(rows: List[Dict], key: str) -> np.ndarray:
    return np.array([int(r[key]) for r in rows], dtype=np.int64)


def fit_calibrations(val_rows, manifest, split_manifest_path, out_dir: Path, methods, seed) -> Dict[str, Any]:
    """Fit each channel on val scores only, write calibration_<channel>.json, reload it frozen."""
    loaded = {}
    for channel in CHANNELS:
        rows = _channel_rows(val_rows, channel)
        data = ScoredSet(
            [r["split_id"] for r in rows], _raw_scores(rows, channel), _labels(rows, LABELS[channel]),
            "val", manifest.sha256, [r["split"] for r in rows],
        )
        artifact, _ = build_calibration(
            data, channel=channel, score_name=SCORE_NAMES[channel], seed=seed, method=methods[channel],
            manifest=manifest, manifest_path=split_manifest_path,
        )
        path = out_dir / f"calibration_{channel}.json"
        save_calibration(artifact, path)
        loaded[channel] = load_calibration(path)
    return loaded


# --------------------------------------------------------------------------- evaluation
def atomic_units(rows: List[Dict]) -> np.ndarray:
    """Bootstrap units: records sharing a dup group or a GT cluster resample together."""
    uf = UnionFind(range(len(rows)))
    first: Dict[tuple, int] = {}
    for i, r in enumerate(rows):
        for key in ("dup_group", "cluster_id"):
            if r.get(key) is not None:
                uf.union(first.setdefault((key, r[key]), i), i)
    return np.array([uf.find(i) for i in range(len(rows))], dtype=np.int64)


def _groups(rows: List[Dict]) -> Dict[str, List]:
    return {
        "lang": [r["lang"] for r in rows],
        "course": [r["problem_id"].split("_", 1)[0] for r in rows],
        "model": [r["model"] for r in rows],
    }


def _evaluate(ctx: RunContext, rows, y, s, *, mode, seed, n_boot, points, manifest) -> Dict:
    metrics = compute_metrics(
        y, s, channel=ctx.channel, split="test", mode=mode, seed=seed, operating_points=points,
        groups=_groups(rows), bootstrap_groups=atomic_units(rows), bootstrap_unit="atomic", n_boot=n_boot,
    )
    return ctx.write(y, s, metrics, manifest_stats=manifest.stats)


def _fused_points(y, cal_a, cal_b, calibrations, *, seed, n_boot, rows) -> Dict[str, Dict]:
    """OR-decision operating points, one per FPR key both calibrations share."""
    a_art, b_art = calibrations["channel_a"].artifact, calibrations["channel_b"].artifact
    points = {}
    primary = a_art["primary"]
    for key in sorted(a_art["thresholds"], key=lambda k: k != primary):  # primary first
        if key not in b_art["thresholds"]:
            continue
        ta, tb = a_art["thresholds"][key], b_art["thresholds"][key]
        point = {
            "rule": "or",
            "primary": key == primary,
            "source": "provisional OR of calibrated channel decisions (production fusion: SDD-4)",
            "target_fpr": ta["target_fpr"],
            "channel_thresholds": {"channel_a": ta["threshold"], "channel_b": tb["threshold"]},
            "low_support": bool(ta["low_support"] or tb["low_support"]),
            "unachievable": ta["threshold"] is None or tb["threshold"] is None,
            "reason": ta["reason"] or tb["reason"],
            "threshold": None,
        }
        name = f"or_{key}"
        if point["unachievable"]:
            points[name] = point
            continue
        _, decision = fuse(cal_a, cal_b, ta["threshold"], tb["threshold"])
        point["threshold"] = DECISION_TRUE
        on_decision = compute_metrics(
            y, decision.astype(np.float64), channel=FUSED, split="test", mode="decision", seed=seed,
            operating_points={name: point}, bootstrap_groups=atomic_units(rows), n_boot=n_boot,
        )
        points[name] = on_decision["operating_points"][name]
    return points


def run_suite(
    *,
    golden: Mapping[str, Any],
    root: Path,
    split_manifest_path: Path,
    engine,
    engine_name: str,
    mode: str,
    seed: int,
    n_boot: int,
    runs_root: Path,
    val_golden: Optional[Mapping[str, Any]] = None,
    val_root: Optional[Path] = None,
    calibration_paths: Optional[Mapping[str, Optional[Path]]] = None,
    methods: Optional[Mapping[str, str]] = None,
    argv: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    if mode not in MODES:
        raise BenchmarkError(f"unknown mode {mode!r} (want one of {MODES})")
    methods = {**DEFAULT_METHODS, **(methods or {})}
    sha = _source_sha(golden, "test")
    calibrations = resolve_calibrations(calibration_paths or {}, sha) if mode == "calibrated-frozen" else {}
    if mode == "calibrated-fit-in-run" and val_golden is None:
        raise BenchmarkError("calibrated-fit-in-run needs --val-manifest (golden manifest of the val corpus)")

    manifest = load_manifest(split_manifest_path, expected_sha256=sha)
    require_split(golden["samples"], "test", split_manifest_path, sha)
    if val_golden is not None and mode == "calibrated-fit-in-run":
        if _source_sha(val_golden, "val") != sha:
            raise BenchmarkError("the val and test golden manifests come from different split manifests")
        require_split(val_golden["samples"], "val", split_manifest_path, sha)

    synthetic = bool(golden.get("synthetic")) or engine_name == "stub"
    now = datetime.now(timezone.utc)
    shared = {
        "engine": engine_name,
        "synthetic": synthetic,
        "golden_manifest": golden.get("source_manifest_path"),
        "golden_root": Path(root).as_posix(),
        "methods": methods if mode == "calibrated-fit-in-run" else None,
        "n_boot": n_boot,
    }
    top = RunContext.create(
        "benchmark", seed=seed, split="test", mode=mode, manifest_path=split_manifest_path,
        manifest_sha256=sha, config=shared, argv=argv, root=runs_root, now=now,
    )

    if mode == "calibrated-fit-in-run":
        val_rows = asyncio.run(score_manifest(val_golden, val_root, engine))
        calibrations = fit_calibrations(val_rows, manifest, split_manifest_path, top.path, methods, seed)
    rows = asyncio.run(score_manifest(golden, root, engine))

    summary: Dict[str, Any] = {
        "mode": mode, "manifest_sha256": sha, "run_dir": top.path.as_posix(), "synthetic": synthetic,
        "channels": {}, "skipped": {},
    }
    calibrated: Dict[str, np.ndarray] = {}
    for channel in CHANNELS:
        ch_rows = _channel_rows(rows, channel)
        y, raw = _labels(ch_rows, LABELS[channel]), _raw_scores(ch_rows, channel)
        cal = calibrations.get(channel)
        points = operating_points_from_calibration(cal) if cal else {}
        s = cal.apply(raw) if cal else raw
        ctx = RunContext.create(
            channel, seed=seed, split="test", mode=mode, manifest_path=split_manifest_path, manifest_sha256=sha,
            calibration_path=cal.path if cal else None,
            thresholds={k: p["threshold"] for k, p in points.items()},
            config={**shared, "score": SCORE_NAMES[channel], "label": LABELS[channel],
                    "dropped_without_reference": len(rows) - len(ch_rows)},
            argv=argv, root=top.path, now=now,
        )
        metrics = _evaluate(ctx, ch_rows, y, s, mode=mode, seed=seed, n_boot=n_boot, points=points, manifest=manifest)
        summary["channels"][channel] = _summary(ctx, metrics)
        if cal:
            calibrated[channel] = cal.apply(_raw_scores(_channel_rows(rows, "channel_a"), channel))

    if not calibrations:
        summary["skipped"][FUSED] = "uncalibrated mode: the fused decision needs calibrated channel thresholds"
    else:
        fused_rows = _channel_rows(rows, "channel_a")
        y = np.array([int(r["label_copy"] or r["label_ai"]) for r in fused_rows], dtype=np.int64)
        s = np.maximum(calibrated["channel_a"], calibrated["channel_b"])  # fused ranking score
        points = _fused_points(y, calibrated["channel_a"], calibrated["channel_b"], calibrations,
                               seed=seed, n_boot=n_boot, rows=fused_rows)
        ctx = RunContext.create(
            FUSED, seed=seed, split="test", mode=mode, manifest_path=split_manifest_path, manifest_sha256=sha,
            config={**shared, "score": "max(calibrated channel_a, calibrated channel_b)", "label": "copy OR ai",
                    "decision": "OR of calibrated channel decisions (provisional; production fusion: SDD-4)",
                    "calibrations": {c: {"path": cal.path.as_posix(), "sha256": cal.sha256}
                                     for c, cal in calibrations.items()},
                    "channel_thresholds": {k: p["channel_thresholds"] for k, p in points.items()}},
            argv=argv, root=top.path, now=now,
        )
        metrics = _evaluate(ctx, fused_rows, y, s, mode=mode, seed=seed, n_boot=n_boot, points=points,
                            manifest=manifest)
        summary["channels"][FUSED] = _summary(ctx, metrics)

    text = json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    (top.path / "summary.json").write_text(text, encoding="utf-8", newline="\n")
    return summary


def _summary(ctx: RunContext, metrics: Mapping) -> Dict[str, Any]:
    tf = metrics["threshold_free"]
    return {
        "run_dir": ctx.path.as_posix(),
        "n": metrics["n"],
        "n_pos": metrics["n_pos"],
        "roc_auc": {k: tf["roc_auc"][k] for k in ("value", "ci95")},
        "pr_auc": {k: tf["pr_auc"][k] for k in ("value", "ci95")},
        "operating_points": {
            k: {"threshold": p.get("threshold"), "unachievable": p.get("unachievable"),
                "low_support": p.get("low_support"),
                "observed": {m: p["observed"][m]["value"] for m in ("precision", "recall", "fpr", "f1")}
                if "observed" in p else None}
            for k, p in metrics["operating_points"].items()
        },
    }


def print_table(summary: Mapping[str, Any]) -> None:
    def fmt(v):
        return "null" if v is None else f"{v:.3f}"

    print(f"mode={summary['mode']} synthetic={summary['synthetic']} manifest_sha256={summary['manifest_sha256']}")
    print(f"{'channel':<10} {'n':>5} {'n_pos':>5} | {'ROC-AUC':>7} {'PR-AUC':>7} | operating points")
    for channel, m in summary["channels"].items():
        ops = ", ".join(
            f"{k}: t={fmt(p['threshold']) if isinstance(p['threshold'], float) else p['threshold']}"
            + (f" fpr={fmt(p['observed']['fpr'])} recall={fmt(p['observed']['recall'])}" if p["observed"] else "")
            for k, p in m["operating_points"].items()
        ) or "-"
        print(f"{channel:<10} {m['n']:>5} {m['n_pos']:>5} | {fmt(m['roc_auc']['value']):>7} "
              f"{fmt(m['pr_auc']['value']):>7} | {ops}")
    for name, reason in summary["skipped"].items():
        print(f"{name:<10} skipped: {reason}")


def _read_golden(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True, help="Golden manifest of the TEST corpus")
    parser.add_argument("--root", type=Path, default=None, help="Test corpus root (default: manifest['root'])")
    parser.add_argument("--split-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--engine", choices=["stub", "real"], default="stub")
    parser.add_argument("--mode", choices=MODES, default="calibrated-frozen")
    parser.add_argument("--calibrate", action="store_true", help="Shorthand for --mode calibrated-fit-in-run")
    parser.add_argument("--val-manifest", type=Path, default=None, help="Golden manifest of the VAL corpus")
    parser.add_argument("--val-root", type=Path, default=None, help="Val corpus root (default: its manifest root)")
    parser.add_argument("--calibration-dir", type=Path, default=None,
                        help="Directory holding calibration_channel_a.json and calibration_channel_b.json")
    parser.add_argument("--calibration-a", type=Path, default=None)
    parser.add_argument("--calibration-b", type=Path, default=None)
    parser.add_argument("--method-a", choices=["temperature", "platt", "isotonic"], default=DEFAULT_METHODS["channel_a"])
    parser.add_argument("--method-b", choices=["temperature", "platt", "isotonic"], default=DEFAULT_METHODS["channel_b"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-boot", type=int, default=1000)
    parser.add_argument("--runs-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--charcnn-checkpoint", type=Path, default=None,
                        help="Evaluate this CharCNN checkpoint instead of the deployed one (real engine only)")
    args = parser.parse_args(argv)
    mode = "calibrated-fit-in-run" if args.calibrate else args.mode

    def calibration_path(channel: str, explicit: Optional[Path]) -> Optional[Path]:
        if explicit is not None:
            return explicit
        return args.calibration_dir / f"calibration_{channel}.json" if args.calibration_dir else None

    try:
        golden = _read_golden(args.manifest)
        val_golden = _read_golden(args.val_manifest) if args.val_manifest else None
        engine = make_engine(args.engine)
        if args.charcnn_checkpoint:
            if args.engine != "real":
                parser.error("--charcnn-checkpoint requires --engine real")
            from models.char_cnn.inference import CharCNNInference

            engine.charcnn_engine = CharCNNInference(checkpoint_path=args.charcnn_checkpoint)
        summary = run_suite(
            golden=golden,
            root=args.root or Path(golden["root"]),
            split_manifest_path=args.split_manifest,
            engine=engine,
            engine_name=args.engine,
            mode=mode,
            seed=args.seed,
            n_boot=args.n_boot,
            runs_root=args.runs_root,
            val_golden=val_golden,
            val_root=args.val_root or (Path(val_golden["root"]) if val_golden else None),
            calibration_paths={
                "channel_a": calibration_path("channel_a", args.calibration_a),
                "channel_b": calibration_path("channel_b", args.calibration_b),
            },
            methods={"channel_a": args.method_a, "channel_b": args.method_b},
            argv=sys.argv if argv is None else ["scripts/benchmark_suite.py", *argv],
        )
    except BenchmarkError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print_table(summary)
    print(f"Run: {summary['run_dir']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

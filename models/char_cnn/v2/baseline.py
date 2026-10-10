"""Legacy baseline (CT8): a legacy (v1) checkpoint scored on the split_v1 test views.

`python -m models.char_cnn.v2.baseline [--checkpoint models/char_cnn/best_model.pth]`

The checkpoint is loaded through the inference facade (legacy branch) and `predict_text(raw)` is
run on every test file (raw = file bytes decoded as UTF-8 with `errors="replace"`, line endings
kept). The headline view is the test representatives (run root), the secondary view every
non-broken test file (`test_all/`), both with CI95 bootstrapped by `dup_group`, the v2 per-group
and per-generator breakdowns (length buckets use the v2-normalized length, as in v2 runs) and
the legacy abstention counts. Scores are the served `prob_sintetico`, so abstained files carry
the legacy 0.05 placeholder.

The result is labelled `contaminated: true`: the legacy checkpoint was trained on a split that
overlaps split_v1 test and its preprocessing differs from v2. It is never calibrated; its only
operating point is `argmax_0.5` (`source: "manual"`). The checkpoint is read-only: its sha256
is recorded before and after the run and a difference fails the run. Output goes to
`<runs-root>/char_cnn_legacy/<ts>/`.

Exit codes (`v2/runs.py`): 0 complete; 1 refused before anything was written (missing or
non-legacy checkpoint, unloadable manifest); 3 when the run is marked failed after its directory
exists (status `failed` in `config.json`).
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

import numpy as np
import torch

from models.char_cnn.inference import CharCNNInference
from models.char_cnn.v2.checkpoint import LEGACY_VERSION
from models.char_cnn.v2.data import EncodedSet, load_views
from models.char_cnn.v2.evaluate import (
    TEST_VIEWS,
    append_report,
    complete_per_group,
    expected_generators,
    expected_groups,
    group_labels,
    per_generator,
    render_generator_section,
    update_run_config,
    write_csv,
)
from models.char_cnn.v2.runs import (
    DEFAULT_N_BOOT,
    REFUSED_EXIT,
    RUN_FAILED_EXIT,
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_RUNNING,
    describe_error,
    resolve_device,
    set_run_status,
)
from models.evaluation.manifest import DEFAULT_MANIFEST, ROOT, SplitManifest, load_manifest
from models.evaluation.provenance import file_sha256
from models.evaluation.report import RunContext, compute_metrics

__all__ = [
    "CHANNEL",
    "MODE",
    "POINT_KEY",
    "MANUAL_POINT",
    "CONTAMINATION_NOTE",
    "REFUSED_EXIT",
    "RUN_FAILED_EXIT",
    "build_parser",
    "main",
]

CHANNEL = "char_cnn_legacy"
MODE = "legacy_contaminated"
SCORE_NAME = "prob_sintetico"
POINT_KEY = "argmax_0.5"
CONTAMINATION_NOTE = (
    "contaminated: the legacy checkpoint was trained on a split that overlaps split_v1 test, and its "
    "preprocessing (v1) differs from preprocess v2; these numbers are not comparable to a v2 run"
)
MANUAL_POINT: Dict[str, Any] = {
    "threshold": 0.5,
    "primary": True,
    "source": "manual",
    "target_fpr": None,
    "low_support": False,
    "unachievable": False,
    "reason": None,
    "rule": "prob_sintetico >= 0.5 (the legacy argmax, except at an exact 0.5 tie)",
}


class _Refused(RuntimeError):
    """A check before the run directory exists failed; nothing was written."""


def _load_legacy(checkpoint: Path, device: torch.device) -> CharCNNInference:
    try:
        engine = CharCNNInference(checkpoint, device=device)
    except Exception as exc:
        raise _Refused(f"cannot load {checkpoint} through the inference facade: {describe_error(exc)}") from exc
    if engine.arch_version != LEGACY_VERSION:
        raise _Refused(
            f"{checkpoint} is a v{engine.arch_version} checkpoint; the baseline evaluates legacy (v1) "
            "checkpoints only (evaluate v2 runs with models.char_cnn.v2.evaluate)"
        )
    return engine


def _abstention(view: EncodedSet, abstained: Mapping[str, bool]) -> Dict[str, int]:
    flags = np.array([abstained[i] for i in view.ids], dtype=bool)
    ai = int(np.count_nonzero(flags & (view.y == 1)))
    human = int(np.count_nonzero(flags & (view.y == 0)))
    return {"human": human, "ai": ai, "total": human + ai, "n": len(view)}


def _baseline_section(config: Mapping[str, Any], metrics: Mapping[str, Any]) -> str:
    counts = metrics["n_abstained"]
    lines = [
        "## Legacy baseline (contaminated)",
        "",
        f"- {CONTAMINATION_NOTE}; not comparable to the legacy 96% claim either.",
        f"- Checkpoint: `{config['config']['checkpoint']}` (sha256 `{config['config']['checkpoint_sha256_before']}`,"
        " unchanged by the run).",
        f"- {metrics['test_view']['label']} (n={metrics['n']}, n_pos={metrics['n_pos']}).",
        f"- Scores: uncalibrated `{SCORE_NAME}` from the legacy facade; operating point `{POINT_KEY}` is manual.",
        f"- Legacy abstention (`insufficient_length`, scored with the 0.05 placeholder): "
        + ", ".join(f"{split} {c['total']}/{c['n']} (human {c['human']}, ai {c['ai']})" for split, c in counts.items()
                    if isinstance(c, dict)),
    ]
    return "\n".join(lines) + "\n"


def _write_view_metrics(
    ctx: RunContext,
    manifest: SplitManifest,
    views: Mapping[str, EncodedSet],
    scores: Mapping[str, float],
    abstained: Mapping[str, bool],
    *,
    seed: int,
    n_boot: int,
) -> None:
    population = manifest.samples()
    groups_expected = expected_groups(population)
    generators_expected = expected_generators(population)
    points = {POINT_KEY: dict(MANUAL_POINT)}
    n_abstained = {name: _abstention(views[name], abstained) for name in TEST_VIEWS}
    for name, (mode, label) in TEST_VIEWS.items():
        view = views[name]
        s = np.array([scores[i] for i in view.ids], dtype=np.float64)
        metrics = compute_metrics(
            view.y,
            s,
            channel=CHANNEL,
            split="test",
            mode=mode,
            seed=seed,
            operating_points=points,
            groups=group_labels(view),
            bootstrap_groups=[smp.dup_group or smp.id for smp in view.samples],
            bootstrap_unit="dup_group",
            n_boot=n_boot,
        )
        metrics["per_group"] = complete_per_group(metrics["per_group"], groups_expected)
        metrics["per_generator"] = per_generator(view.samples, view.y, s, points, generators_expected)
        metrics["test_view"] = {"name": name, "label": label}
        metrics["contaminated"] = True
        metrics["contamination_note"] = CONTAMINATION_NOTE
        metrics["warnings"] = [CONTAMINATION_NOTE, *metrics["warnings"]]
        metrics["score"] = {"name": SCORE_NAME, "calibrated": False}
        metrics["n_abstained"] = {**n_abstained, "rule": "legacy insufficient_length"}

        target = ctx if name == "test" else RunContext(path=ctx.path / name, channel=ctx.channel, config=ctx.config)
        target.path.mkdir(exist_ok=True)
        written = target.write(view.y, s, metrics)
        append_report(
            target.path / "report.md", [_baseline_section(ctx.config, written), render_generator_section(written)]
        )


def _write_scores(path: Path, views: Mapping[str, EncodedSet], scores, abstained) -> None:
    representatives = set(views["test"].ids)
    rows, seen = [], set()
    for view in (views["test_all"], views["test"]):
        for sample_id, label in zip(view.ids, view.y.tolist()):
            if sample_id not in seen:
                seen.add(sample_id)
                rows.append(
                    (sample_id, label, scores[sample_id], int(abstained[sample_id]), int(sample_id in representatives))
                )
    write_csv(path, ("id", "y", "p_synthetic", "abstained", "representative"), rows)


def run_baseline(args: argparse.Namespace, argv: Sequence[str]) -> "tuple[int, Optional[Path]]":
    """Execute the baseline; returns (exit code, run directory or None when refused)."""
    checkpoint = Path(args.checkpoint)
    if not checkpoint.is_file():
        raise _Refused(f"{checkpoint} does not exist")
    sha_before = file_sha256(checkpoint)
    device = resolve_device(args.device)
    engine = _load_legacy(checkpoint, device)
    try:
        manifest = load_manifest(args.manifest, args.expected_sha256)
    except (OSError, ValueError) as exc:
        raise _Refused(f"cannot load the manifest: {describe_error(exc)}") from exc

    ckpt_config = engine.checkpoint.get("config") or {}
    ctx = RunContext.create(
        CHANNEL,
        seed=args.seed,
        split="test",
        mode=MODE,
        manifest_path=manifest.path,
        manifest_sha256=manifest.sha256,
        thresholds={POINT_KEY: MANUAL_POINT["threshold"]},
        config={
            "contaminated": True,
            "contamination_note": CONTAMINATION_NOTE,
            "checkpoint": checkpoint.resolve().as_posix(),
            "checkpoint_sha256_before": sha_before,
            "arch_version": engine.arch_version,
            "preproc_version": engine.preproc_version,
            "legacy_config": {
                key: ckpt_config.get(key) for key in ("seq_length", "whitespace_mode", "strip_comments")
            },
            "score": SCORE_NAME,
            "calibrated": False,
            "n_boot": args.n_boot,
            "device": str(device),
            "torch_version": str(torch.__version__),
            "data_root": Path(args.root).as_posix(),
        },
        argv=list(argv),
        root=args.runs_root,
    )
    ctx = update_run_config(ctx, status=STATUS_RUNNING, failure=None)
    stage = "score"
    try:
        scores: Dict[str, float] = {}
        abstained: Dict[str, bool] = {}

        def on_text(sample, raw: str, normalized: str) -> None:
            result = engine.predict_text(raw)
            scores[sample.id] = float(result["prob_sintetico"])
            abstained[sample.id] = bool(result["insufficient_length"])

        views = load_views(manifest, views=tuple(TEST_VIEWS), root=args.root, on_text=on_text)

        stage = "verify_checkpoint"
        sha_after = file_sha256(checkpoint)
        ctx = update_run_config(ctx, checkpoint_sha256_after=sha_after)
        if sha_after != sha_before:
            raise RuntimeError(f"{checkpoint} changed during the run ({sha_before} -> {sha_after})")

        stage = "evaluate"
        _write_scores(ctx.path / "scores_test.csv", views, scores, abstained)
        _write_view_metrics(ctx, manifest, views, scores, abstained, seed=args.seed, n_boot=args.n_boot)
    except Exception as exc:  # recorded in config.json instead of leaving a silent half-written run
        reason = describe_error(exc)
        set_run_status(ctx.path, STATUS_FAILED, stage=stage, reason=reason)
        print(f"ERROR: baseline failed during {stage}: {reason}; see {ctx.path / 'config.json'}", file=sys.stderr)
        return RUN_FAILED_EXIT, ctx.path
    set_run_status(ctx.path, STATUS_COMPLETE)
    return 0, ctx.path


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1 (got {value})")
    return value


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m models.char_cnn.v2.baseline",
        description="Score a legacy CharCNN checkpoint on split_v1 test (labelled contaminated; read-only).",
    )
    p.add_argument("--checkpoint", type=Path, default=ROOT / "models" / "char_cnn" / "best_model.pth")
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="split manifest (.json or .json.gz)")
    p.add_argument("--expected-sha256", default=None, help="refuse the manifest unless its sha256 matches")
    p.add_argument("--root", type=Path, default=ROOT, help="corpus root; files are read at <root>/<id>")
    p.add_argument("--runs-root", type=Path, default=ROOT / "runs", help="output goes to <runs-root>/char_cnn_legacy/")
    p.add_argument("--device", default=None, help="torch device (default: cuda if available, else cpu)")
    p.add_argument("--seed", type=int, default=42, help="bootstrap seed")
    p.add_argument("--n-boot", type=_positive_int, default=DEFAULT_N_BOOT, help="bootstrap resamples for the CI95")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    try:
        code, run_dir = run_baseline(args, ["-m", "models.char_cnn.v2.baseline", *argv])
    except _Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return REFUSED_EXIT
    if code == 0:
        print(f"run directory: {run_dir}")
    return code


if __name__ == "__main__":
    sys.exit(main())

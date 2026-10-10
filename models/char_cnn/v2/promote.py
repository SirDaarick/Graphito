"""Guarded promotion of a v2 run checkpoint to the deployed path (CT9).

`python -m models.char_cnn.v2.promote <run>/best.pth [--target models/char_cnn/best_model.pth]
[--force] [--dry-run]`

Checks, in order (any failure refuses with `REFUSED_EXIT` and writes nothing):

1. the source loads with `weights_only=True` and carries `arch_version == preproc_version == 2`
   (an unversioned legacy checkpoint is refused);
2. its run directory holds `config.json` with `status: "complete"`, `metrics.json` and
   `calibration.json` (an unevaluated or failed run cannot be promoted);
3. `git status --porcelain -- <target>` is empty: a modified, staged or untracked target, or a
   failing git call, is refused unless `--force` is given.

Then the source bytes are copied atomically onto the target and `<target stem>.provenance.json`
is written next to it (run id and directory, source/target/previous/config/calibration sha256,
headline AUCs, forced flag, git status, timestamp). `--dry-run` runs every check and prints the
plan without writing. The trainer, baseline and tests never promote onto the real target; the
git runner is injectable so tests use a fake one on temporary targets.
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from models.char_cnn.v2.checkpoint import LEGACY_VERSION, checkpoint_versions, load_checkpoint
from models.char_cnn.v2.evaluate import STATUS_COMPLETE, describe_error, write_json
from models.evaluation.manifest import ROOT
from models.evaluation.provenance import atomic_write_bytes, file_sha256

__all__ = [
    "PROVENANCE_SCHEMA",
    "DEFAULT_TARGET",
    "REFUSED_EXIT",
    "PromoteRefused",
    "GitRunner",
    "run_git",
    "provenance_path",
    "plan_promotion",
    "promote",
    "build_parser",
    "main",
]

PROVENANCE_SCHEMA = "graphito.charcnn_promotion/v1"
DEFAULT_TARGET = ROOT / "models" / "char_cnn" / "best_model.pth"
REFUSED_EXIT = 1
REQUIRED_RUN_FILES = ("config.json", "metrics.json", "calibration.json")

GitRunner = Callable[[Sequence[str], Path], subprocess.CompletedProcess]


class PromoteRefused(RuntimeError):
    """A promotion check failed; nothing was written."""


def run_git(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess:
    """Default git runner (`git <args>` in `cwd`, text output, 10 s timeout)."""
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10, check=False)


def provenance_path(target: Path) -> Path:
    """The sidecar next to the target, e.g. `best_model.pth` -> `best_model.provenance.json`."""
    return target.with_name(f"{target.stem}.provenance.json")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_source(source: Path) -> Dict[str, Any]:
    """The source checkpoint config, refused unless it is a v2 checkpoint."""
    if not source.is_file():
        raise PromoteRefused(f"{source} does not exist")
    try:
        checkpoint = load_checkpoint(source, map_location="cpu")
        config = checkpoint.get("config") or {}
        versions = checkpoint_versions(config)
    except Exception as exc:  # unreadable, unsafe or unknown-version checkpoints are all refused
        raise PromoteRefused(f"{source} is not a loadable CharCNN checkpoint: {describe_error(exc)}") from exc
    if "arch_version" not in config or "preproc_version" not in config or versions[0] == LEGACY_VERSION:
        raise PromoteRefused(
            f"{source} lacks the v2 version fields (arch_version/preproc_version); only v2 run "
            "checkpoints can be promoted"
        )
    return config


def _check_run(run_dir: Path) -> Dict[str, Any]:
    """`config.json` of the source's run, refused unless the run finished and was evaluated."""
    missing = [name for name in REQUIRED_RUN_FILES if not (run_dir / name).is_file()]
    if missing:
        raise PromoteRefused(f"run {run_dir} lacks {missing}; promote only an evaluated run")
    config = _read_json(run_dir / "config.json")
    if config.get("status") != STATUS_COMPLETE:
        raise PromoteRefused(f"run {run_dir} has status {config.get('status')!r}, expected {STATUS_COMPLETE!r}")
    return config


def _git_status(target: Path, git: GitRunner) -> "tuple[Optional[str], Optional[str]]":
    """(porcelain output, error); an error means the target state is unknown."""
    try:
        done = git(["status", "--porcelain", "--", target.name], target.parent)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, describe_error(exc)
    if done.returncode != 0:
        detail = (done.stderr or "").strip().splitlines()
        return None, f"git exited {done.returncode}" + (f": {detail[0]}" if detail else "")
    return done.stdout.rstrip("\n"), None


@dataclass(frozen=True)
class Plan:
    source: Path
    target: Path
    run_dir: Path
    forced: bool
    provenance: Dict[str, Any]


def plan_promotion(source: Path, target: Path, *, force: bool, git: GitRunner = run_git) -> Plan:
    """Run every check and build the provenance document; raises `PromoteRefused`."""
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target:
        raise PromoteRefused("source and target are the same file")
    checkpoint_config = _check_source(source)
    run_dir = source.parent
    run_config = _check_run(run_dir)

    status, error = _git_status(target, git)
    if error is not None and not force:
        raise PromoteRefused(f"cannot check {target} with git ({error}); pass --force to promote anyway")
    if status and not force:
        raise PromoteRefused(f"{target} has uncommitted changes ({status!r}); pass --force to overwrite it")

    metrics = _read_json(run_dir / "metrics.json")
    headline = metrics.get("threshold_free", {})
    provenance = {
        "schema": PROVENANCE_SCHEMA,
        "run_id": run_config.get("run_id", checkpoint_config.get("run_id")),
        "run_dir": run_dir.as_posix(),
        "source": source.as_posix(),
        "source_sha256": file_sha256(source),
        "target": target.as_posix(),
        "previous_sha256": file_sha256(target) if target.is_file() else None,
        "config_sha256": file_sha256(run_dir / "config.json"),
        "calibration_path": (run_dir / "calibration.json").as_posix(),
        "calibration_sha256": file_sha256(run_dir / "calibration.json"),
        "headline": {
            "split": metrics.get("split"),
            "mode": metrics.get("mode"),
            "n": metrics.get("n"),
            "roc_auc": headline.get("roc_auc", {}).get("value"),
            "pr_auc": headline.get("pr_auc", {}).get("value"),
        },
        "arch_version": checkpoint_config["arch_version"],
        "preproc_version": checkpoint_config["preproc_version"],
        "run_git_sha": checkpoint_config.get("git_sha"),
        "forced": bool(force),
        "git_status": status if error is None else f"unknown: {error}",
    }
    return Plan(source=source, target=target, run_dir=run_dir, forced=bool(force), provenance=provenance)


def promote(plan: Plan) -> Dict[str, Any]:
    """Copy the source onto the target atomically, then write the provenance sidecar."""
    data = plan.source.read_bytes()
    atomic_write_bytes(plan.target, data)
    provenance = {
        **plan.provenance,
        "target_sha256": file_sha256(plan.target),
        "promoted_at": datetime.now(timezone.utc).isoformat(),
    }
    if provenance["target_sha256"] != provenance["source_sha256"]:
        raise RuntimeError(f"{plan.target} does not match the source after the copy")
    write_json(provenance_path(plan.target), provenance)
    return provenance


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m models.char_cnn.v2.promote",
        description="Copy an evaluated v2 run checkpoint onto the deployed path, with a provenance sidecar.",
    )
    p.add_argument("source", type=Path, help="<runs-root>/char_cnn/<ts>/best.pth")
    p.add_argument("--target", type=Path, default=DEFAULT_TARGET, help="deployed checkpoint path")
    p.add_argument("--force", action="store_true", help="overwrite a modified/untracked target or skip a failing git check")
    p.add_argument("--dry-run", action="store_true", help="run every check and print the plan; write nothing")
    return p


def main(argv: Optional[Sequence[str]] = None, *, git: GitRunner = run_git) -> int:
    """Exit 0 when promoted (or a dry run passed), `REFUSED_EXIT` when a check refused."""
    args = build_parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        plan = plan_promotion(args.source, args.target, force=args.force, git=git)
    except PromoteRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return REFUSED_EXIT
    if args.dry_run:
        print(f"dry run: would copy {plan.source} -> {plan.target} (forced={plan.forced}); nothing written")
        print(json.dumps(plan.provenance, indent=2, sort_keys=True))
        return 0
    provenance = promote(plan)
    print(f"promoted {plan.source} -> {plan.target}; provenance: {provenance_path(plan.target)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

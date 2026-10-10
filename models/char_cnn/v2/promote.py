"""Guarded promotion of a v2 run checkpoint to the deployed path (CT9).

`python -m models.char_cnn.v2.promote <run>/best.pth [--target models/char_cnn/best_model.pth]
[--force] [--dry-run]`

Checks, in order (any failure refuses with `REFUSED_EXIT` and writes nothing):

1. the source loads with `weights_only=True` and carries `arch_version == preproc_version == 2`
   (an unversioned legacy checkpoint is refused);
2. its run directory holds `config.json` with `status: "complete"`, `metrics.json` and
   `calibration.json` (an unevaluated or failed run cannot be promoted);
3. the source is that run's `best.pth` and its sha256 equals the run's recorded `best_sha256`;
4. `git status --porcelain --ignored -- <target>` is empty: a modified, staged, untracked or
   ignored target, or a failing git call, is refused unless `--force` is given. An ignored entry
   counts as clean only when the file is tracked and identical to `HEAD` (`git diff --quiet HEAD`).

Writing is verify-before-write: the source bytes are read once and their in-memory sha256 must
equal the plan's `source_sha256` (and the target must still hold the planned previous bytes),
otherwise the promotion is refused with nothing written. The provenance sidecar
`<target stem>.provenance.json` (run id and directory, source/target/previous/config/calibration
sha256, headline AUCs, forced flag, git status, timestamp) is staged in a temp file before the
target is replaced atomically, then moved into place. When anything fails after the target was
touched, the previous target bytes and sidecar (kept in memory) are restored and the CLI exits
`PARTIAL_WRITE_EXIT` with an `ERROR:` line. `--dry-run` runs every check and prints the plan
without writing. The trainer, baseline and tests never promote onto the real target; the git
runner is injectable so tests use a fake one on temporary targets.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from models.char_cnn.v2.checkpoint import LEGACY_VERSION, checkpoint_versions, load_checkpoint
from models.char_cnn.v2.runs import (
    CHECKPOINT_NAME,
    PARTIAL_WRITE_EXIT,
    REFUSED_EXIT,
    STATUS_COMPLETE,
    describe_error,
)
from models.evaluation.manifest import ROOT
from models.evaluation.provenance import atomic_write_bytes, file_sha256

__all__ = [
    "PROVENANCE_SCHEMA",
    "DEFAULT_TARGET",
    "REFUSED_EXIT",
    "PARTIAL_WRITE_EXIT",
    "PromoteRefused",
    "PromoteFailed",
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
REQUIRED_RUN_FILES = ("config.json", "metrics.json", "calibration.json")
IGNORED_PREFIX = "!! "  # `git status --porcelain --ignored` marker of an ignored path

GitRunner = Callable[[Sequence[str], Path], subprocess.CompletedProcess]


class PromoteRefused(RuntimeError):
    """A promotion check failed; nothing was written."""


class PromoteFailed(RuntimeError):
    """A write failed after the target was touched; `restored` says whether the previous state is back."""

    def __init__(self, message: str, *, restored: bool):
        super().__init__(message)
        self.restored = restored


def run_git(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess:
    """Default git runner (`git <args>` in `cwd`, text output, 10 s timeout)."""
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10, check=False)


def provenance_path(target: Path) -> Path:
    """The sidecar next to the target, e.g. `best_model.pth` -> `best_model.provenance.json`."""
    return target.with_name(f"{target.stem}.provenance.json")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    try:
        config = _read_json(run_dir / "config.json")
    except (OSError, ValueError) as exc:
        raise PromoteRefused(f"cannot read {run_dir / 'config.json'}: {describe_error(exc)}") from exc
    if config.get("status") != STATUS_COMPLETE:
        raise PromoteRefused(f"run {run_dir} has status {config.get('status')!r}, expected {STATUS_COMPLETE!r}")
    return config


def _check_binding(source: Path, run_config: Dict[str, Any]) -> str:
    """The source sha256, refused unless the source is the run's recorded `best.pth`."""
    if source.name != CHECKPOINT_NAME:
        raise PromoteRefused(f"{source} is not the run's {CHECKPOINT_NAME}; promote only a run's selected checkpoint")
    recorded = run_config.get("best_sha256")
    if not recorded:
        raise PromoteRefused(
            f"run {source.parent} records no best_sha256; re-run models.char_cnn.v2.evaluate --force to record it"
        )
    actual = file_sha256(source)
    if actual != recorded:
        raise PromoteRefused(f"{source} sha256 {actual} does not match the run's best_sha256 {recorded}")
    return actual


def _git(git: GitRunner, args: Sequence[str], cwd: Path) -> Tuple[Optional[subprocess.CompletedProcess], Optional[str]]:
    try:
        return git(list(args), cwd), None
    except (OSError, subprocess.SubprocessError) as exc:
        return None, describe_error(exc)


def _git_failure(done: subprocess.CompletedProcess) -> str:
    detail = (done.stderr or "").strip().splitlines()
    return f"git exited {done.returncode}" + (f": {detail[0]}" if detail else "")


def _git_status(target: Path, git: GitRunner) -> Tuple[str, bool, Optional[str]]:
    """(porcelain output, dirty, error); an error means the target state is unknown.

    Any entry is dirty, except an ignored (`!!`) one whose file is tracked and identical to
    `HEAD`. An ignored path that is untracked (the usual case) is therefore dirty.
    """
    name, cwd = target.name, target.parent
    done, error = _git(git, ["status", "--porcelain", "--ignored", "--", name], cwd)
    if error is not None:
        return "", True, error
    if done.returncode != 0:
        return "", True, _git_failure(done)
    status = done.stdout.rstrip("\n")
    lines = [line for line in status.splitlines() if line.strip()]
    if not lines:
        return status, False, None
    if any(not line.startswith(IGNORED_PREFIX) for line in lines):
        return status, True, None
    tracked, error = _git(git, ["ls-files", "--error-unmatch", "--", name], cwd)
    if error is not None:
        return status, True, error
    if tracked.returncode != 0:  # untracked and ignored: not in HEAD, so it cannot be identical
        return status, True, None
    diff, error = _git(git, ["diff", "--quiet", "HEAD", "--", name], cwd)
    if error is not None:
        return status, True, error
    if diff.returncode not in (0, 1):
        return status, True, _git_failure(diff)
    return status, diff.returncode == 1, None


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
    source_sha256 = _check_binding(source, run_config)

    status, dirty, error = _git_status(target, git)
    if error is not None and not force:
        raise PromoteRefused(f"cannot check {target} with git ({error}); pass --force to promote anyway")
    if dirty and error is None and not force:
        raise PromoteRefused(
            f"{target} is modified, untracked or ignored ({status!r}); pass --force to overwrite it"
        )

    try:
        metrics = _read_json(run_dir / "metrics.json")
    except (OSError, ValueError) as exc:
        raise PromoteRefused(f"cannot read {run_dir / 'metrics.json'}: {describe_error(exc)}") from exc
    headline = metrics.get("threshold_free", {})
    provenance = {
        "schema": PROVENANCE_SCHEMA,
        "run_id": run_config.get("run_id", checkpoint_config.get("run_id")),
        "run_dir": run_dir.as_posix(),
        "source": source.as_posix(),
        "source_sha256": source_sha256,
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


def _staged_path(sidecar: Path) -> Path:
    """The pid-unique temp file the sidecar is written to before `_commit_sidecar` moves it."""
    return sidecar.with_name(f".{sidecar.name}.{os.getpid()}.staged")


def _commit_sidecar(staged: Path, sidecar: Path) -> None:
    os.replace(staged, sidecar)


def _restore(target: Path, previous: Optional[bytes], sidecar: Path, previous_sidecar: Optional[bytes]) -> bool:
    """Put the previous target and sidecar back (or remove them when there were none)."""
    try:
        for path, data in ((target, previous), (sidecar, previous_sidecar)):
            if data is None:
                path.unlink(missing_ok=True)
            elif not path.is_file() or path.read_bytes() != data:
                atomic_write_bytes(path, data)
        return True
    except OSError:
        return False


def promote(plan: Plan) -> Dict[str, Any]:
    """Verify the source in memory, then replace the target and its sidecar (see module doc).

    Raises `PromoteRefused` (nothing written) when the source or target changed since the plan,
    and `PromoteFailed` when a write failed after the target was touched.
    """
    data = plan.source.read_bytes()  # read once: these exact bytes are hashed and written
    if _sha256(data) != plan.provenance["source_sha256"]:
        raise PromoteRefused(f"{plan.source} changed since the checks (sha256 differs); nothing written")
    target, sidecar = plan.target, provenance_path(plan.target)
    previous = target.read_bytes() if target.is_file() else None
    if (None if previous is None else _sha256(previous)) != plan.provenance["previous_sha256"]:
        raise PromoteRefused(f"{target} changed since the checks; nothing written")
    previous_sidecar = sidecar.read_bytes() if sidecar.is_file() else None

    provenance = {
        **plan.provenance,
        "target_sha256": plan.provenance["source_sha256"],
        "promoted_at": datetime.now(timezone.utc).isoformat(),
    }
    payload = (json.dumps(provenance, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    staged = _staged_path(sidecar)
    try:
        staged.write_bytes(payload)  # the sidecar is on disk before the target is touched
        atomic_write_bytes(target, data)
        written = _sha256(target.read_bytes())
        if written != provenance["target_sha256"]:
            raise RuntimeError(f"{target} does not match the source after the copy ({written})")
        _commit_sidecar(staged, sidecar)
    except BaseException as exc:
        restored = _restore(target, previous, sidecar, previous_sidecar)
        staged.unlink(missing_ok=True)
        if not isinstance(exc, Exception):
            raise
        raise PromoteFailed(f"promotion failed after writing {target}: {describe_error(exc)}", restored=restored) from exc
    return provenance


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m models.char_cnn.v2.promote",
        description="Copy an evaluated v2 run checkpoint onto the deployed path, with a provenance sidecar.",
    )
    p.add_argument("source", type=Path, help="<runs-root>/char_cnn/<ts>/best.pth")
    p.add_argument("--target", type=Path, default=DEFAULT_TARGET, help="deployed checkpoint path")
    p.add_argument(
        "--force", action="store_true", help="overwrite a modified/untracked/ignored target or skip a failing git check"
    )
    p.add_argument("--dry-run", action="store_true", help="run every check and print the plan; write nothing")
    return p


def main(argv: Optional[Sequence[str]] = None, *, git: GitRunner = run_git) -> int:
    """Exit 0 when promoted (or a dry run passed), `REFUSED_EXIT` when nothing was written,
    `PARTIAL_WRITE_EXIT` when a write failed after the target was touched (previous state restored)."""
    args = build_parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        plan = plan_promotion(args.source, args.target, force=args.force, git=git)
        if args.dry_run:
            print(f"dry run: would copy {plan.source} -> {plan.target} (forced={plan.forced}); nothing written")
            print(json.dumps(plan.provenance, indent=2, sort_keys=True))
            return 0
        promote(plan)
    except PromoteRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return REFUSED_EXIT
    except PromoteFailed as exc:
        outcome = (
            "the previous target and sidecar were restored"
            if exc.restored
            else "RESTORE FAILED: check the target and its sidecar by hand"
        )
        print(f"ERROR: {exc}; {outcome}", file=sys.stderr)
        return PARTIAL_WRITE_EXIT
    except Exception as exc:  # every write happens inside `promote`'s guarded block, so none happened
        print(f"REFUSED: unexpected error before writing: {describe_error(exc)}", file=sys.stderr)
        return REFUSED_EXIT
    print(f"promoted {plan.source} -> {plan.target}; provenance: {provenance_path(plan.target)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

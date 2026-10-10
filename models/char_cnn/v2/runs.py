"""Shared run-directory contract of the CharCNN v2 CLIs (train, evaluate, baseline, promote).

Exit codes (every CLI uses the same meaning; argparse usage errors also exit 2, before anything is
written):

| Code | Constant | Meaning |
|---|---|---|
| 0 | - | success |
| 1 | `REFUSED_EXIT` | refused by a check; nothing was written (or the run is left unchanged) |
| 2 | `LEAK_GUARD_EXIT` | train only: the leak guard failed (`leak_guard.json` written, run marked failed) |
| 3 | `RUN_FAILED_EXIT` | the run directory's `config.json` is marked `failed` (stage and reason recorded) |
| 4 | `PARTIAL_WRITE_EXIT` | a write failed part-way; the previous files (and run status) were restored |

`config.json` records `status` (`running` -> `complete` | `failed`) and, when failed,
`failure: {stage, reason}`.
"""

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import torch

from models.evaluation.provenance import atomic_write_bytes

__all__ = [
    "STATUS_RUNNING",
    "STATUS_COMPLETE",
    "STATUS_FAILED",
    "REFUSED_EXIT",
    "LEAK_GUARD_EXIT",
    "RUN_FAILED_EXIT",
    "PARTIAL_WRITE_EXIT",
    "CHECKPOINT_NAME",
    "DEFAULT_N_BOOT",
    "DEFAULT_EVAL_BATCH_SIZE",
    "write_json",
    "set_run_status",
    "describe_error",
    "resolve_device",
]

STATUS_RUNNING = "running"
STATUS_COMPLETE = "complete"
STATUS_FAILED = "failed"

REFUSED_EXIT = 1
LEAK_GUARD_EXIT = 2
RUN_FAILED_EXIT = 3
PARTIAL_WRITE_EXIT = 4

CHECKPOINT_NAME = "best.pth"  # the selected checkpoint of a v2 run (its sha256 is `best_sha256`)
DEFAULT_N_BOOT = 1000  # bootstrap resamples for the CI95
DEFAULT_EVAL_BATCH_SIZE = 32  # windows per scoring batch


def write_json(path: Path, doc: Mapping[str, Any]) -> None:
    """Atomic, sorted, NaN-free UTF-8 JSON (the run directory's JSON writer)."""
    text = json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    atomic_write_bytes(path, (text + "\n").encode("utf-8"))


def describe_error(exc: BaseException) -> str:
    """One-line `Type: message` for `config.json` and the `ERROR:` line."""
    message = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


def set_run_status(
    run_dir: Path, status: str, *, stage: Optional[str] = None, reason: Optional[str] = None
) -> Dict[str, Any]:
    """Record the run status in `config.json`, re-read from disk so no earlier update is lost."""
    path = Path(run_dir) / "config.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["status"] = status
    doc["failure"] = {"stage": stage, "reason": reason} if status == STATUS_FAILED else None
    write_json(path, doc)
    return doc


def resolve_device(name: Optional[str]) -> torch.device:
    """The requested device, else CUDA when available, else CPU."""
    return torch.device(name or ("cuda" if torch.cuda.is_available() else "cpu"))

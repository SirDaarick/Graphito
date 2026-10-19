"""Provenance helpers shared by split manifests, calibration files and run reports (stdlib only).

Git state is best effort: when git is missing, times out or the directory is not a checkout,
the sha and dirty flag are the string `"unknown"` and callers keep going.
"""

import hashlib
import os
import platform
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path
from typing import Dict, Iterable, Optional, Union

ROOT = Path(__file__).resolve().parents[2]
GIT = "git"
UNKNOWN = "unknown"
DEFAULT_PACKAGES = ("numpy", "scikit-learn", "scipy", "matplotlib", "torch")


def _git(args, cwd: Path) -> str:
    done = subprocess.run(
        [GIT, *args], cwd=cwd, capture_output=True, text=True, timeout=10, check=True
    )
    return done.stdout.strip()


def git_info(cwd: Optional[Union[str, Path]] = None) -> Dict[str, Union[str, bool]]:
    """`{"git_sha", "dirty"}` for the checkout at `cwd` (repo root by default).

    `dirty` ignores untracked files. Both values are `"unknown"` when git is unavailable.
    """
    cwd = Path(cwd) if cwd is not None else ROOT
    try:
        sha = _git(["rev-parse", "HEAD"], cwd)
        dirty = bool(_git(["status", "--porcelain", "--untracked-files=no"], cwd))
    except (OSError, subprocess.SubprocessError):
        return {"git_sha": UNKNOWN, "dirty": UNKNOWN}
    return {"git_sha": sha, "dirty": dirty}


def file_sha256(path: Union[str, Path], chunk_size: int = 1 << 20) -> str:
    """Hex sha256 of a file's bytes, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: Union[str, Path], data: bytes) -> Path:
    """Write `data` to `path` atomically and return the path.

    The bytes go to a pid-unique sibling temp file that `os.replace` moves onto `path`, so a
    failed or interrupted write leaves any previous file intact; the temp file is removed on
    any failure (including `KeyboardInterrupt`). Parent directories are created."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        tmp.write_bytes(data)
        max_attempts = 15 if os.name == "nt" else 1
        for attempt in range(max_attempts):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == max_attempts - 1:
                    raise
                time.sleep(0.05 * (attempt + 1))
    except BaseException:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise
    return path


def package_versions(names: Iterable[str] = DEFAULT_PACKAGES) -> Dict[str, Optional[str]]:
    """Installed distribution versions (None when a package is absent); imports nothing."""
    out = {}
    for name in names:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


def runtime_info() -> Dict:
    """Python version, platform and package versions."""
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "versions": package_versions(),
    }

"""Repository configuration for the evaluation foundation: gitignore, gitattributes, dev deps."""

import shutil
import subprocess
from pathlib import Path
from typing import Dict

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not available")


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


@pytest.fixture(scope="module", autouse=True)
def _inside_work_tree():
    probe = _git("rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0:
        pytest.skip("not running inside a git work tree")


def _is_ignored(path: str) -> bool:
    return _git("check-ignore", "-q", "--no-index", path).returncode == 0


def _attrs(path: str, *names: str) -> Dict[str, str]:
    out = _git("check-attr", *names, "--", path).stdout
    result = {}
    for line in out.splitlines():
        _, attr, value = line.rsplit(": ", 2)
        result[attr] = value.strip()
    return result


def test_runs_directory_is_fully_ignored():
    assert _is_ignored("runs/char_cnn/x/roc.png")
    assert _is_ignored("runs/char_cnn/x/metrics.json")


def test_split_manifest_is_not_ignored():
    assert not _is_ignored("data/splits/split_v1.json")


def test_split_manifest_attributes_protect_byte_identity():
    attrs = _attrs("data/splits/split_v1.json", "diff", "eol", "linguist-generated")
    assert attrs["diff"] == "unset"
    assert attrs["eol"] == "lf"
    assert attrs["linguist-generated"] == "set"


def test_existing_gitattributes_rule_is_preserved():
    assert _attrs("Documentacion/main.tex", "linguist-vendored")["linguist-vendored"] == "set"


def test_matplotlib_is_a_dev_only_dependency():
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").split()
    assert "matplotlib" in dev
    backend = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "matplotlib" not in backend

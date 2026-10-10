"""Seeding helpers: torch-optional global seeding and sha256-derived RNG streams."""

import hashlib
import os
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from models.evaluation.seed import seed_everything, stable_rng

ROOT = Path(__file__).resolve().parent.parent


def _draw() -> tuple:
    return random.random(), float(np.random.rand())


def test_seed_everything_without_torch_seeds_random_and_numpy(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)  # makes `import torch` raise ImportError
    assert seed_everything(123) == 123
    first = _draw()
    assert seed_everything(123) == 123
    assert _draw() == first
    seed_everything(124)
    assert _draw() != first


def test_deterministic_flag_does_not_require_torch(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    assert seed_everything(5, deterministic_torch=True) == 5


def test_seed_everything_seeds_torch_when_installed():
    torch = pytest.importorskip("torch")
    seed_everything(7)
    first = torch.rand(3).tolist()
    seed_everything(7)
    assert torch.rand(3).tolist() == first


def test_stable_rng_is_deterministic_and_keyed():
    a = [stable_rng(42, "A:0").random() for _ in range(2)]
    assert a[0] == a[1]
    assert stable_rng(42, "A:1").random() != a[0]
    assert stable_rng(43, "A:0").random() != a[0]


def test_stable_rng_ignores_global_random_state():
    random.seed(1)
    first = stable_rng(9, "k").random()
    random.seed(2)
    assert stable_rng(9, "k").random() == first


def test_stable_rng_matches_the_golden_set_derivation():
    digest = hashlib.sha256(b"42:A:0").hexdigest()
    assert stable_rng(42, "A:0").random() == random.Random(int(digest[:16], 16)).random()


def test_package_imports_without_torch():
    code = (
        "import sys; sys.modules['torch'] = None\n"
        "import models.evaluation as ev\n"
        "assert callable(ev.seed_everything) and callable(ev.stable_rng)\n"
    )
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr

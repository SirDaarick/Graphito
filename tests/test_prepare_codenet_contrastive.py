"""Pure helpers of `scripts/prepare_codenet_contrastive.py` (F0 of the contrastive CodeNet guide).

No CodeNet data, tokenizer or model is read: the helpers take plain ids, hash arrays and counts.
"""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("prepare_codenet", ROOT / "scripts" / "prepare_codenet_contrastive.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prep = _load()


def test_split_problems_is_deterministic_and_disjoint():
    ids = [f"p{i:05d}" for i in range(100)]
    a = prep.split_problems(ids, seed=0)
    b = prep.split_problems(list(reversed(ids)), seed=0)
    assert a == b  # input order does not matter
    assert set(a) == set(ids)
    assert set(a.values()) == {"train", "val", "test"}


def test_split_problems_fractions_and_seed():
    ids = [f"p{i:05d}" for i in range(1000)]
    split = prep.split_problems(ids, seed=0)
    counts = {s: sum(v == s for v in split.values()) for s in ("train", "val", "test")}
    assert counts == {"train": 800, "val": 100, "test": 100}
    assert prep.split_problems(ids, seed=1) != split


def test_split_problems_tiny_input_keeps_every_split_non_empty_when_possible():
    split = prep.split_problems(["a", "b", "c"], seed=0)
    assert sorted(split.values()) == ["test", "train", "val"]


def test_near_duplicate_detects_overlap_above_threshold():
    base = np.arange(10, dtype=np.uint64)
    same = np.arange(10, dtype=np.uint64)
    disjoint = np.arange(100, 110, dtype=np.uint64)
    assert prep.near_duplicate(base, [disjoint, same], threshold=0.9)
    assert not prep.near_duplicate(base, [disjoint], threshold=0.9)
    assert not prep.near_duplicate(base, [], threshold=0.9)


def test_near_duplicate_threshold_is_inclusive_or_exclusive_as_documented():
    a = np.arange(10, dtype=np.uint64)
    b = np.arange(2, 12, dtype=np.uint64)  # |inter|=8, |union|=12 -> 0.666...
    assert prep.max_similarity(a, [b]) == pytest.approx(8 / 12)
    assert prep.near_duplicate(a, [b], threshold=8 / 12)  # >= threshold
    assert not prep.near_duplicate(a, [b], threshold=0.7)


def test_max_similarity_empty_reference_is_zero():
    assert prep.max_similarity(np.arange(3, dtype=np.uint64), []) == 0.0


def test_canonicalize_or_raw_uses_the_canonicalizer():
    code, ok = prep.canonicalize_or_raw("int x;", lambda c, lang: c.upper())
    assert (code, ok) == ("INT X;", True)


def test_canonicalize_or_raw_falls_back_to_raw_code_when_it_raises():
    def boom(code, lang):
        raise RuntimeError("unparsable")

    assert prep.canonicalize_or_raw("int x;", boom) == ("int x;", False)


def test_real_canonicalizer_makes_identifier_renaming_invisible():
    a = "int suma(int a, int b) { int total = a + b; return total; }\nint main() { return suma(1, 2); }\n"
    b = "int add(int x, int y) { int acc = x + y; return acc; }\nint main() { return add(1, 2); }\n"
    ca, ok_a = prep.canonicalize_or_raw(a)
    cb, ok_b = prep.canonicalize_or_raw(b)
    assert ok_a and ok_b
    assert ca == cb
    assert "total" not in ca and "main" in ca


@pytest.mark.parametrize(
    "kept, total, dfg_kept, dfg_total, expected",
    [(100, 100, 20, 20, True), (99, 100, 20, 20, False), (100, 100, 19, 20, False), (0, 0, 0, 0, True)],
)
def test_fits_one_window_requires_no_truncation(kept, total, dfg_kept, dfg_total, expected):
    f = {"n_code_kept": kept, "n_code_subtokens": total, "n_dfg_kept": dfg_kept, "n_dfg": dfg_total}
    assert prep.fits_one_window(f) is expected

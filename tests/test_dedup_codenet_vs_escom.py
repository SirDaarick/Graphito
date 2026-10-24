"""Pure helpers of `scripts/dedup_codenet_vs_escom.py` (cross-corpus near-duplicate check).

Synthetic signatures and hash sets only: no CodeNet or ESCOM data is read.
"""

import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("dedup_cn", ROOT / "scripts" / "dedup_codenet_vs_escom.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dd = _load()


def _sig(*values):
    return np.asarray(values, dtype=np.uint64)


def test_band_candidates_finds_signatures_sharing_a_whole_band():
    ref = np.stack([_sig(1, 2, 3, 4), _sig(9, 9, 9, 9), _sig(5, 6, 7, 8)])
    query = np.stack([_sig(1, 2, 0, 0), _sig(0, 0, 0, 0)])  # first band equals ref[0]'s first band
    cands = dd.band_candidates(query, ref, bands=2, rows=2)
    assert cands == {0: {0}, 1: set()}


def test_band_candidates_ignores_partial_band_agreement():
    ref = np.stack([_sig(1, 2, 3, 4)])
    query = np.stack([_sig(1, 9, 3, 9)])  # one row of each band agrees, never a whole band
    assert dd.band_candidates(query, ref, bands=2, rows=2) == {0: set()}


def test_band_candidates_rejects_oversized_bands():
    import pytest

    with pytest.raises(ValueError):
        dd.band_candidates(np.zeros((1, 4), dtype=np.uint64), np.zeros((1, 4), dtype=np.uint64), bands=3, rows=2)


def test_exact_matches_keeps_only_candidates_at_or_above_threshold():
    a = np.arange(10, dtype=np.uint32)
    refs = [np.arange(10, dtype=np.uint32), np.arange(5, 15, dtype=np.uint32), np.arange(100, 110, dtype=np.uint32)]
    hits = dd.exact_matches(a, {0, 1, 2}, refs, threshold=0.8)
    assert hits == {0: 1.0}
    assert dd.exact_matches(a, set(), refs, threshold=0.8) == {}


def test_filter_manifest_drops_flagged_rows_and_problems_with_too_few_accepted():
    rows = [
        {"problem": "p1", "role": "accepted", "submission_id": "a"},
        {"problem": "p1", "role": "accepted", "submission_id": "b"},
        {"problem": "p1", "role": "wrong_answer", "submission_id": "w"},
        {"problem": "p2", "role": "accepted", "submission_id": "c"},
        {"problem": "p2", "role": "accepted", "submission_id": "d"},
    ]
    kept, dropped_problems = dd.filter_rows(rows, flagged={("p2", "c")}, min_accepted=2)
    assert [r["submission_id"] for r in kept] == ["a", "b", "w"]
    assert dropped_problems == ["p2"]

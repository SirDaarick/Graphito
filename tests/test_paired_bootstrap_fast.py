"""`paired_bootstrap(..., fast_grouped=True)` must reproduce the resampling implementation exactly.

The grouped bootstrap only changes how many times each group's pairs count, so the AUC of every
resample can be read from per-group counts of negatives below/tied with each positive after ONE sort per
column. These tests compare it with the original implementation on data with ties and several groups.
"""

import numpy as np
import pytest

from models.robustness.scoring import paired_bootstrap


def _dataset(seed: int, n: int = 600, n_groups: int = 6, n_methods: int = 3, tie_digits: int = 2):
    rng = np.random.default_rng(seed)
    groups = rng.integers(0, n_groups, n)
    y = (rng.random(n) < 0.15).astype(np.int64)
    scores = {}
    for m in range(n_methods):
        for cond in ("T0", "T1", "T2"):
            base = rng.normal(size=n) + 1.2 * y * (1.0 - 0.1 * m)
            scores[(f"m{m}", cond)] = np.round(base, tie_digits)  # rounding creates many ties
    return y, scores, groups


def _assert_same(a, b, tol=1e-9):
    assert set(a) == set(b)
    for name in a:
        ra, rb = a[name], b[name]
        assert ra["n_valid"] == rb["n_valid"], name
        assert ra["skipped_resamples"] == rb["skipped_resamples"], name
        for key in ("value", "lo", "hi"):
            if ra[key] is None or rb[key] is None:
                assert ra[key] is rb[key], (name, key)
            else:
                assert ra[key] == pytest.approx(rb[key], abs=tol), (name, key)
        assert ra["reason"] == rb["reason"], name


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_fast_grouped_matches_the_original_on_tied_scores(seed):
    y, scores, groups = _dataset(seed)
    slow = paired_bootstrap(y, scores, groups=groups, n_boot=200, seed=42)
    fast = paired_bootstrap(y, scores, groups=groups, n_boot=200, seed=42, fast_grouped=True)
    _assert_same(slow, fast)


def test_fast_grouped_matches_with_few_resamples_single_worker_path():
    y, scores, groups = _dataset(3)
    slow = paired_bootstrap(y, scores, groups=groups, n_boot=40, seed=7)
    fast = paired_bootstrap(y, scores, groups=groups, n_boot=40, seed=7, fast_grouped=True, min_valid=1)
    _assert_same(paired_bootstrap(y, scores, groups=groups, n_boot=40, seed=7, min_valid=1), fast)
    assert set(slow) == set(fast)


def test_fast_grouped_handles_resamples_without_positives():
    # positives live in a single group: resamples that skip that group are undefined and skipped
    rng = np.random.default_rng(5)
    n, groups = 300, rng.integers(0, 5, 300)
    y = ((groups == 0) & (rng.random(n) < 0.3)).astype(np.int64)
    scores = {("a", "T0"): np.round(rng.normal(size=n) + y, 2), ("a", "T1"): np.round(rng.normal(size=n) + y, 2)}
    slow = paired_bootstrap(y, scores, groups=groups, n_boot=120, seed=1)
    fast = paired_bootstrap(y, scores, groups=groups, n_boot=120, seed=1, fast_grouped=True)
    assert any(r["skipped_resamples"] > 0 for r in slow.values())
    _assert_same(slow, fast)


def test_fast_grouped_requires_groups():
    y, scores, _ = _dataset(0, n=100)
    with pytest.raises(ValueError):
        paired_bootstrap(y, scores, groups=None, n_boot=10, seed=1, fast_grouped=True)


def test_fast_grouped_matches_with_explicit_contrasts():
    y, scores, groups = _dataset(4)
    contrasts = {"did_T1_m0_m1": ("T1", "m0", "m1")}
    slow = paired_bootstrap(y, scores, groups=groups, n_boot=120, seed=3, contrasts=contrasts)
    fast = paired_bootstrap(y, scores, groups=groups, n_boot=120, seed=3, contrasts=contrasts, fast_grouped=True)
    _assert_same(slow, fast)

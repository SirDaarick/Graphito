"""Unit tests for robustness scoring and paired bootstrap metrics."""

from typing import Dict, List
import numpy as np
import pytest

from models.evaluation import metrics as M
from models.graphcodebert.v2.baselines import SetSimilarity
from models.graphcodebert.v2.pairs import embedding_similarity
from models.robustness.scoring import (
    CrossSetSimilarity,
    cross_embedding_similarity,
    paired_bootstrap,
)


def test_cross_set_similarity_parity_with_baseline():
    """When orig_sets == trans_sets, CrossSetSimilarity must match SetSimilarity bit-for-bit."""
    rng = np.random.default_rng(42)
    # Generate 15 synthetic hash sets with varying sizes and overlap
    sets: List[np.ndarray] = []
    for i in range(15):
        if i % 4 == 0:
            sets.append(np.empty(0, dtype=np.uint64))
        else:
            k = rng.integers(5, 30)
            vals = np.unique(rng.integers(0, 100, size=k)).astype(np.uint64)
            sets.append(vals)

    sim_baseline = SetSimilarity(sets)
    sim_cross = CrossSetSimilarity(sets, sets)

    # Full block comparison
    base_mat = sim_baseline(0, len(sets))
    cross_mat = sim_cross(0, len(sets))
    assert np.allclose(base_mat, cross_mat, atol=1e-12)

    # Sub-block comparisons
    for start, stop in [(0, 5), (5, 10), (3, 12), (10, 15)]:
        b_sub = sim_baseline(start, stop)
        c_sub = sim_cross(start, stop)
        assert np.allclose(b_sub, c_sub, atol=1e-12)


def test_cross_set_similarity_asymmetric():
    """Test CrossSetSimilarity with distinct sets and empty edges."""
    orig_sets = [
        np.array([1, 2, 3], dtype=np.uint64),
        np.array([4, 5], dtype=np.uint64),
        np.empty(0, dtype=np.uint64),
    ]
    trans_sets = [
        np.array([2, 3, 4], dtype=np.uint64),
        np.array([10, 20], dtype=np.uint64),
        np.empty(0, dtype=np.uint64),
    ]
    cross = CrossSetSimilarity(orig_sets, trans_sets)
    mat = cross(0, 3)

    assert mat.shape == (3, 3)
    # orig[0] = {1, 2, 3}, trans[0] = {2, 3, 4} -> inter={2, 3} (2), union={1, 2, 3, 4} (4) -> 0.5
    assert mat[0, 0] == pytest.approx(2.0 / 4.0)
    # orig[0] = {1, 2, 3}, trans[1] = {10, 20} -> inter=0
    assert mat[0, 1] == 0.0
    # Empty orig or trans gives 0
    assert mat[2, 0] == 0.0
    assert mat[0, 2] == 0.0
    assert mat[2, 2] == 0.0


def test_cross_embedding_similarity_parity_with_baseline():
    """When E_orig == E_trans, cross_embedding_similarity must equal embedding_similarity."""
    rng = np.random.default_rng(123)
    e = rng.normal(size=(20, 64))
    # Add a zero row (representing failed embedding)
    e[5] = 0.0

    base_sim = embedding_similarity(e)
    cross_sim = cross_embedding_similarity(e, e)

    base_mat = base_sim(0, 20)
    cross_mat = cross_sim(0, 20)
    assert np.allclose(base_mat, cross_mat, atol=1e-12)

    # Sub-block check
    assert np.allclose(base_sim(2, 10), cross_sim(2, 10), atol=1e-12)


def test_cross_embedding_similarity_different():
    """Verify cosine properties when E_orig != E_trans."""
    rng = np.random.default_rng(321)
    e_orig = rng.normal(size=(10, 32))
    e_trans = rng.normal(size=(10, 32))
    e_orig[2] = 0.0  # Zero vector

    sim_fn = cross_embedding_similarity(e_orig, e_trans)
    mat = sim_fn(0, 10)

    assert mat.shape == (10, 10)
    assert mat[2, 0] == 0.0
    assert np.all(mat >= -1.0 - 1e-6) and np.all(mat <= 1.0 + 1e-6)


def test_paired_bootstrap_identical_columns():
    """Verify delta against T0 and DiD calculations with identical columns give 0 and CI [0, 0]."""
    rng = np.random.default_rng(42)
    n = 200
    y = rng.integers(0, 2, size=n)
    # Ensure both classes are present
    y[0] = 0
    y[1] = 1

    s_base = rng.uniform(0.0, 1.0, size=n)

    # Nested dictionary with identical scores for T0 and T1 across methods
    scores_dict = {
        "jaccard": {"T0": s_base, "T1": s_base},
        "v2": {"T0": s_base, "T1": s_base},
    }

    res = paired_bootstrap(y, scores_dict, n_boot=50, seed=42)

    # Delta for jaccard under T1 vs T0
    assert "delta__jaccard__T1" in res
    assert res["delta__jaccard__T1"]["value"] == 0.0
    assert res["delta__jaccard__T1"]["ci95"] == [0.0, 0.0]

    # Delta for v2 under T1 vs T0
    assert "delta__v2__T1" in res
    assert res["delta__v2__T1"]["value"] == 0.0
    assert res["delta__v2__T1"]["ci95"] == [0.0, 0.0]

    # DiD between jaccard and v2 under T1
    did_key = "did__T1__jaccard__v2"
    assert did_key in res
    assert res[did_key]["value"] == 0.0
    assert res[did_key]["ci95"] == [0.0, 0.0]


def test_paired_bootstrap_with_groups():
    """Paired bootstrap respects cluster/assignment groups without error."""
    rng = np.random.default_rng(99)
    n = 100
    y = np.array([0, 1] * (n // 2))
    groups = np.repeat(np.arange(10), n // 10)
    s0 = rng.uniform(0.1, 0.9, size=n)
    s1 = s0 + 0.05 * rng.uniform(-1, 1, size=n)

    scores_dict = {
        "jaccard": {"T0": s0, "T7@1.0": s1},
        "v2": {"T0": s0, "T7@1.0": s1},
    }

    res = paired_bootstrap(y, scores_dict, groups=groups, n_boot=50, seed=42)
    assert "delta__jaccard__T7@1.0" in res
    assert res["delta__jaccard__T7@1.0"]["unit"] == "group"
    assert res["delta__jaccard__T7@1.0"]["n_units"] == 10

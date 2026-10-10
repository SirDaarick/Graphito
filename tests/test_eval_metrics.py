"""Vectorized evaluation metrics: rank AUC, AP, threshold views, MAP@R, ECE and bootstrap CIs."""

import random

import numpy as np
import pytest
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.metrics import roc_curve as sk_roc_curve

from models.evaluation import metrics as M


# --- 7.1 threshold-free metrics -------------------------------------------------------------


@pytest.mark.parametrize(
    "scores, labels, expected",
    [
        ([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0], 1.0),
        ([0.9, 0.8, 0.2, 0.1], [0, 0, 1, 1], 0.0),
        ([0.5, 0.5, 0.5, 0.5], [1, 0, 1, 0], 0.5),
        ([0.5, 0.5, 0.9, 0.1], [1, 0, 1, 0], 0.875),
    ],
)
def test_roc_auc_known_values(scores, labels, expected):
    assert M.roc_auc(labels, scores) == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_auc_and_ap_match_sklearn_on_tie_heavy_data(seed):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 2, 400)
    s = np.round(rng.random(400) * 0.6 + 0.3 * y, 1)  # few distinct values -> many ties
    w = rng.random(400) + 0.1
    assert M.roc_auc(y, s) == pytest.approx(roc_auc_score(y, s), abs=1e-12)
    assert M.roc_auc(y, s, sample_weight=w) == pytest.approx(
        roc_auc_score(y, s, sample_weight=w), abs=1e-12
    )
    assert M.average_precision(y, s) == pytest.approx(average_precision_score(y, s), abs=1e-12)


def test_roc_curve_matches_sklearn_points():
    rng = np.random.default_rng(5)
    y = rng.integers(0, 2, 200)
    s = np.round(rng.random(200), 1)
    fpr, tpr, thr = M.roc_curve(y, s)
    sk_fpr, sk_tpr, sk_thr = sk_roc_curve(y, s, drop_intermediate=False)
    np.testing.assert_allclose(fpr, sk_fpr)
    np.testing.assert_allclose(tpr, sk_tpr)
    assert np.isinf(thr[0]) and np.allclose(thr[1:], sk_thr[1:])


def test_pr_curve_ends_at_full_recall():
    precision, recall, thresholds = M.pr_curve([1, 0, 1, 0], [0.9, 0.8, 0.7, 0.1])
    assert recall[-1] == 1.0 and precision[0] == 1.0
    assert len(precision) == len(recall) == len(thresholds)


@pytest.mark.parametrize("labels", [[0, 0, 0, 0], [1, 1, 1, 1]])
def test_single_class_returns_none_with_reason(labels):
    s = [0.1, 0.4, 0.6, 0.9]
    assert M.roc_auc(labels, s) is None
    assert M.average_precision(labels, s) is None
    assert M.roc_curve(labels, s) is None and M.pr_curve(labels, s) is None
    assert M.undefined_reason(labels) == "single_class"
    assert M.metric_entry(M.roc_auc, labels, s) == {"value": None, "reason": "single_class"}
    assert M.metric_entry(M.average_precision, labels, s) == {"value": None, "reason": "single_class"}


def test_empty_input_reason():
    assert M.undefined_reason([]) == "empty"
    assert M.roc_auc([], []) is None


def test_large_random_auc_is_near_half():
    rng = np.random.default_rng(42)
    y = rng.integers(0, 2, 20000)
    s = rng.random(20000)
    assert abs(M.roc_auc(y, s) - 0.5) < 0.02


def test_non_binary_labels_are_rejected():
    with pytest.raises(ValueError, match="binary"):
        M.roc_auc([1, 0, -1], [0.2, 0.3, 0.4])
    with pytest.raises(ValueError, match="length"):
        M.roc_auc([1, 0], [0.2])


def test_validate_labels_is_public_and_strict():
    y = M.validate_labels([0, 1, True, np.int8(0)])
    assert y.dtype == np.int64 and y.tolist() == [0, 1, 1, 0]
    assert M.validate_labels([]).size == 0
    with pytest.raises(ValueError, match="binary"):
        M.validate_labels([0, -1])
    with pytest.raises(ValueError, match="1-D"):
        M.validate_labels([[0, 1]])
    assert not hasattr(M, "_labels")


# --- 7.2 threshold metrics, views and groups -----------------------------------------------


def test_threshold_metrics_known_counts():
    m = M.threshold_metrics([1, 1, 0, 0, 0], [0.9, 0.4, 0.8, 0.1, 0.2], 0.5)
    assert (m["tp"], m["fp"], m["tn"], m["fn"]) == (1, 1, 2, 1)
    assert m["precision"] == pytest.approx(0.5)
    assert m["recall"] == m["tpr"] == pytest.approx(0.5)
    assert m["fpr"] == pytest.approx(1 / 3)
    assert m["f1"] == pytest.approx(0.5)
    assert M.threshold_metrics([1, 0], [0.5, 0.2], 0.5)["tp"] == 1  # decision is s >= t


def test_precision_null_without_predicted_positives():
    m = M.threshold_metrics([1, 0, 1, 0], [0.1, 0.2, 0.3, 0.4], 0.9)
    assert m["precision"] is None and m["f1"] is None
    assert m["recall"] == 0.0 and m["fpr"] == 0.0


def test_recall_null_without_positives():
    m = M.threshold_metrics([0, 0, 0], [0.1, 0.6, 0.9], 0.5)
    assert m["recall"] is None and m["tpr"] is None
    assert m["fpr"] == pytest.approx(2 / 3)
    assert m["precision"] == 0.0


def test_prevalence_weights_reach_target_prevalence():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    np.testing.assert_array_equal(M.prevalence_weights(y), np.ones(10))
    for pi in (0.5, 0.1):
        w = M.prevalence_weights(y, pi)
        assert w.sum() == pytest.approx(10)
        assert w[y == 1].sum() / w.sum() == pytest.approx(pi)
    assert M.prevalence_weights(np.zeros(4, dtype=int), 0.5) is None


def test_views_observed_and_balanced_always_natural_only_when_configured():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    s = np.array([0.9, 0.8, 0.7, 0.6, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
    views = M.threshold_views(y, s, 0.5)
    assert set(views) == {"observed", "balanced"}
    assert views["observed"]["view"] == "observed" and views["balanced"]["view"] == "balanced"
    assert views["observed"]["precision"] == pytest.approx(0.5)
    assert views["balanced"]["precision"] == pytest.approx(0.8)
    assert views["balanced"]["prevalence"] == pytest.approx(0.5)
    for key in ("tpr", "fpr"):  # prevalence-invariant
        assert views["observed"][key] == pytest.approx(views["balanced"][key])

    natural = M.threshold_views(y, s, 0.5, natural_prevalence=0.1)
    assert set(natural) == {"observed", "balanced", "natural"}
    assert natural["natural"]["view"] == "natural"
    assert natural["natural"]["precision"] == pytest.approx(1 / (1 + 2.25))


def test_reweighted_views_on_single_class_are_null_for_precision():
    views = M.threshold_views([0, 0, 0], [0.1, 0.6, 0.9], 0.5)
    assert views["balanced"]["precision"] is None
    assert views["balanced"]["reason"] == "single_class"
    assert views["balanced"]["fpr"] == pytest.approx(2 / 3)


def test_per_group_reports_empty_and_single_class_groups():
    y = np.array([1, 0, 1, 0, 0, 0])
    s = np.array([0.9, 0.1, 0.8, 0.2, 0.3, 0.4])
    g = np.array(["c", "c", "cpp", "cpp", "solo", "solo"])
    out = M.per_group(M.roc_auc, y, s, g, keys=["c", "cpp", "solo", "missing"])
    assert out["c"] == {"n": 2, "n_pos": 1, "value": 1.0, "reason": None}
    assert out["solo"]["value"] is None and out["solo"]["reason"] == "single_class"
    assert out["missing"] == {"n": 0, "n_pos": 0, "value": None, "reason": "empty"}


# --- 7.3 retrieval and calibration error ----------------------------------------------------


def test_ap_at_r_toy_cases():
    assert M.ap_at_r([1, 0, 1, 0], 2) == pytest.approx(0.5)
    assert M.ap_at_r([1, 1, 0, 0], 2) == pytest.approx(1.0)


def _brute_map_at_r(sim, labels):
    aps, excluded = [], 0
    for q in range(len(labels)):
        r = sum(1 for j in range(len(labels)) if j != q and labels[j] is not None and labels[j] == labels[q])
        if labels[q] is None or r == 0:
            excluded += 1
            continue
        cands = sorted((j for j in range(len(labels)) if j != q), key=lambda j: (-sim[q][j], j))
        hits, total = 0, 0.0
        for i, j in enumerate(cands[:r], start=1):
            if labels[j] == labels[q]:
                hits += 1
                total += hits / i
        aps.append(total / r)
    return aps, excluded


def test_map_at_r_matches_musgrave_toy_and_brute_force():
    labels = ["a", "a", "a", "b", None]
    sim = np.zeros((5, 5))
    sim[0, [1, 3, 2, 4]] = [0.9, 0.8, 0.7, 0.6]  # query 0 ranking: rel, non, rel, non
    sim = np.maximum(sim, sim.T)
    out = M.map_at_r(sim, labels)
    aps, excluded = _brute_map_at_r(sim, labels)
    assert aps[0] == pytest.approx(0.5)
    assert out["n_queries"] == 3 and out["n_excluded"] == excluded == 2
    assert out["value"] == pytest.approx(np.mean(aps))

    rng = np.random.default_rng(3)
    for _ in range(5):
        labels = [None if v < 0 else int(v) for v in rng.integers(-1, 4, 12)]
        sim = np.round(rng.random((12, 12)), 1)
        aps, excluded = _brute_map_at_r(sim, labels)
        out = M.map_at_r(sim, labels)
        assert out["n_excluded"] == excluded and out["n_queries"] == len(aps)
        if aps:
            assert out["value"] == pytest.approx(np.mean(aps))
        else:
            assert out["value"] is None


def test_map_at_r_all_excluded_is_null_and_mean_is_query_macro():
    assert M.map_at_r(np.zeros((2, 2)), [None, None])["value"] is None
    first = M.map_at_r(np.array([[0, 1, 0], [1, 0, 0], [0, 0, 0]]), ["x", "x", None])
    second = M.map_at_r(np.array([[0, 0.1, 0.9], [0.1, 0, 0.9], [0.9, 0.9, 0]]), ["y", "y", "z"])
    total = M.mean_map_at_r([first, second])
    assert first["value"] == 1.0 and second["value"] == 0.0
    assert total["n_queries"] == 4 and total["n_excluded"] == 2
    assert total["value"] == pytest.approx(0.5)


@pytest.mark.parametrize("n_pos, expected", [(8, 0.0), (5, 0.3)])
def test_ece_known_values(n_pos, expected):
    y = np.array([1] * n_pos + [0] * (10 - n_pos))
    p = np.full(10, 0.8)
    assert M.ece(y, p) == pytest.approx(expected, abs=1e-12)
    rel = M.reliability_bins(y, p, n_bins=15)
    assert rel["n_bins"] == 15 and len(rel["bins"]) == 15
    assert [b["n"] for b in rel["bins"] if b["n"]] == [10]
    assert rel["ece"] == pytest.approx(expected, abs=1e-12)


def test_ece_edges_and_invalid_probabilities():
    assert M.ece([1, 0], [1.0, 0.0]) == pytest.approx(0.0)
    assert M.ece([], []) is None
    with pytest.raises(ValueError, match="probabilit"):
        M.ece([1, 0], [1.2, 0.1])


# --- 7.4 bootstrap -----------------------------------------------------------------------------


def _data(n=300, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 2, n)
    return y, rng.random(n) + 0.4 * y


def test_bootstrap_is_seed_reproducible_and_brackets_point():
    y, s = _data()
    a = M.bootstrap_ci(M.roc_auc, y, s, n_boot=200, seed=11)
    b = M.bootstrap_ci(M.roc_auc, y, s, n_boot=200, seed=11)
    assert a == b
    assert a["value"] == pytest.approx(M.roc_auc(y, s))
    assert a["lo"] <= a["value"] <= a["hi"]
    assert a["ci95"] == [a["lo"], a["hi"]]
    assert a["n_boot"] == 200 and a["n_valid"] == 200 and a["skipped_resamples"] == 0
    assert a["unit"] == "sample"


def test_bootstrap_leaves_global_rng_state_untouched():
    y, s = _data()
    np_state, py_state = np.random.get_state(), random.getstate()
    M.bootstrap_ci(M.roc_auc, y, s, n_boot=50, seed=1)
    after = np.random.get_state()
    assert py_state == random.getstate()
    assert all(np.array_equal(x, z) if isinstance(x, np.ndarray) else x == z for x, z in zip(np_state, after))


def test_bootstrap_skips_undefined_resamples():
    y = np.array([1, 1] + [0] * 98)
    s = np.linspace(0, 1, 100)
    out = M.bootstrap_ci(M.roc_auc, y, s, n_boot=300, seed=0)
    assert out["skipped_resamples"] > 0
    assert out["n_valid"] + out["skipped_resamples"] == 300
    assert out["ci95"] is None or out["lo"] <= out["hi"]
    strict = M.bootstrap_ci(M.roc_auc, y, s, n_boot=300, seed=0, min_valid=300)
    assert strict["ci95"] is None and strict["lo"] is None and strict["reason"] == "too_few_valid_resamples"


def test_bootstrap_point_undefined_gives_null_ci():
    out = M.bootstrap_ci(M.roc_auc, [0, 0, 0], [0.1, 0.2, 0.3], n_boot=20, seed=0)
    assert out["value"] is None and out["ci95"] is None and out["reason"] == "single_class"


def test_grouped_bootstrap_resamples_whole_units():
    sizes = {1: 1, 2: 2, 3: 3, 4: 4}
    groups = np.repeat(list(sizes), list(sizes.values()))
    s = groups.astype(float)
    y = np.tile([1, 0], 5)

    def whole_units(_y, ss):
        return float(all(np.sum(ss == g) % size == 0 for g, size in sizes.items()))

    grouped = M.bootstrap_ci(whole_units, y, s, n_boot=200, seed=2, groups=groups)
    assert grouped["unit"] == "group" and grouped["n_units"] == 4
    assert grouped["lo"] == grouped["hi"] == 1.0
    flat = M.bootstrap_ci(whole_units, y, s, n_boot=200, seed=2)
    assert flat["lo"] == 0.0


def test_bootstrap_many_shares_resamples():
    y, s = _data()
    many = M.bootstrap_many({"auc": M.roc_auc, "ap": M.average_precision}, y, s, n_boot=100, seed=4)
    assert many["auc"] == M.bootstrap_ci(M.roc_auc, y, s, n_boot=100, seed=4)
    assert many["ap"]["value"] == pytest.approx(M.average_precision(y, s))

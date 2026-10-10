"""Vectorized evaluation metrics (numpy only).

Conventions shared by every function:
- `y` holds binary labels (0/1; anything else raises `ValueError`), `s` holds scores where
  higher means "more positive". A threshold decision is `s >= t`.
- A metric that is undefined for the input (no samples, or a single class for ROC/PR) returns
  `None`, never a number and never an exception; `undefined_reason` names why
  (`empty` | `single_class`) and `metric_entry` bundles `{value, reason}`.
- Randomness (bootstrap) uses a local seeded `np.random.Generator`; global RNG state is never
  touched.
"""

import math
from typing import Callable, Dict, Hashable, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

MetricFn = Callable[[np.ndarray, np.ndarray], Optional[float]]

VIEWS = ("observed", "balanced", "natural")


def validate_labels(y) -> np.ndarray:
    """1-D binary 0/1 labels as int64; raises `ValueError` on any other shape or value."""
    y = np.asarray(y)
    if y.ndim != 1:
        raise ValueError(f"labels must be 1-D, got shape {y.shape}")
    if y.size and not np.isin(y, (0, 1)).all():
        raise ValueError("labels must be binary 0/1 (filter ambiguous -1 labels first)")
    return y.astype(np.int64)


def _prepare(y, s, sample_weight=None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    y = validate_labels(y)
    s = np.asarray(s, dtype=np.float64)
    if s.shape != y.shape:
        raise ValueError(f"labels and scores differ in length: {y.shape} vs {s.shape}")
    if sample_weight is None:
        w = np.ones(y.size, dtype=np.float64)
    else:
        w = np.asarray(sample_weight, dtype=np.float64)
        if w.shape != y.shape:
            raise ValueError(f"labels and weights differ in length: {y.shape} vs {w.shape}")
    return y, s, w


def _float(value) -> Optional[float]:
    return None if value is None else float(value)


def undefined_reason(y) -> Optional[str]:
    """`empty` without samples, `single_class` when only one label occurs, else None."""
    y = validate_labels(y)
    if y.size == 0:
        return "empty"
    if y.min() == y.max():
        return "single_class"
    return None


def metric_entry(fn: Callable, y, s, **kwargs) -> Dict:
    """`{"value", "reason"}` for a metric; `reason` is set only when the value is None."""
    value = fn(y, s, **kwargs)
    reason = None if value is not None else (undefined_reason(y) or "undefined")
    return {"value": _float(value), "reason": reason}


# --- threshold-free metrics -------------------------------------------------------------------


def roc_auc(y, s, sample_weight=None) -> Optional[float]:
    """ROC-AUC by the rank (Mann-Whitney) statistic with midranks for ties.

    Scores are sorted once and grouped into tie blocks; each positive scores the negative
    weight strictly below its block plus half the negative weight inside it, which is the
    midrank formula aggregated per block. O(n log n), no pair loops. None for a single class.
    """
    y, s, w = _prepare(y, s, sample_weight)
    if undefined_reason(y):
        return None
    order = np.argsort(s, kind="stable")
    s_sorted, y_sorted, w_sorted = s[order], y[order], w[order]
    starts = np.r_[0, np.flatnonzero(np.diff(s_sorted)) + 1]
    pos = np.add.reduceat(w_sorted * y_sorted, starts)
    neg = np.add.reduceat(w_sorted * (1 - y_sorted), starts)
    total_pos, total_neg = pos.sum(), neg.sum()
    if total_pos <= 0 or total_neg <= 0:
        return None
    neg_below = np.cumsum(neg) - neg
    return float(np.sum(pos * (neg_below + 0.5 * neg)) / (total_pos * total_neg))


def _descending_counts(y: np.ndarray, s: np.ndarray):
    """Cumulative (tp, fp) at each distinct threshold, thresholds in descending order."""
    order = np.argsort(-s, kind="stable")
    s_desc, y_desc = s[order], y[order]
    last = np.r_[np.flatnonzero(np.diff(s_desc)), y.size - 1]
    tps = np.cumsum(y_desc)[last].astype(np.float64)
    fps = (last + 1) - tps
    return tps, fps, s_desc[last]


def roc_curve(y, s):
    """`(fpr, tpr, thresholds)` over every distinct threshold (descending), starting at
    `(0, 0, inf)`; None for a single class."""
    y, s, _ = _prepare(y, s)
    if undefined_reason(y):
        return None
    tps, fps, thresholds = _descending_counts(y, s)
    return (
        np.r_[0.0, fps / fps[-1]],
        np.r_[0.0, tps / tps[-1]],
        np.r_[np.inf, thresholds],
    )


def pr_curve(y, s):
    """`(precision, recall, thresholds)` over every distinct threshold (descending, so recall
    is non-decreasing); None for a single class."""
    y, s, _ = _prepare(y, s)
    if undefined_reason(y):
        return None
    tps, fps, thresholds = _descending_counts(y, s)
    return tps / (tps + fps), tps / tps[-1], thresholds


def average_precision(y, s) -> Optional[float]:
    """Step-wise AP (scikit-learn definition): sum over thresholds of delta-recall x precision."""
    curve = pr_curve(y, s)
    if curve is None:
        return None
    precision, recall, _ = curve
    return float(np.sum(np.diff(np.r_[0.0, recall]) * precision))


# --- threshold metrics and prevalence views ---------------------------------------------------


def threshold_metrics(y, s, t: float, sample_weight=None) -> Dict:
    """Confusion counts and rates at `s >= t`.

    Precision is None without predicted positives, recall/TPR None without positives, FPR
    None without negatives; F1 is None when precision or recall is. Counts are weighted
    (floats) when `sample_weight` is given; `n`, `n_pos`, `n_neg` are always raw counts.
    """
    y, s, w = _prepare(y, s, sample_weight)
    pred = s >= t
    pos = y == 1
    tp, fp = w[pred & pos].sum(), w[pred & ~pos].sum()
    fn, tn = w[~pred & pos].sum(), w[~pred & ~pos].sum()
    if sample_weight is None:
        tp, fp, fn, tn = int(tp), int(fp), int(fn), int(tn)
    precision = tp / (tp + fp) if tp + fp > 0 else None
    recall = tp / (tp + fn) if tp + fn > 0 else None
    fpr = fp / (fp + tn) if fp + tn > 0 else None
    if precision is None or recall is None:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
    return {
        "threshold": float(t),
        "n": int(y.size),
        "n_pos": int(pos.sum()),
        "n_neg": int((~pos).sum()),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": _float(precision),
        "recall": _float(recall),
        "tpr": _float(recall),
        "fpr": _float(fpr),
        "f1": _float(f1),
    }


def prevalence_weights(y, pi: Optional[float] = None) -> Optional[np.ndarray]:
    """Per-sample weights that reweight the classes to prevalence `pi` (sum stays n).

    `pi=None` is the observed view (all ones). None when a class is absent, since no
    reweighting can create it. AUC is invariant to these weights; precision/F1 are not.
    """
    y = validate_labels(y)
    if pi is None:
        return np.ones(y.size, dtype=np.float64)
    if not 0.0 < pi < 1.0:
        raise ValueError(f"prevalence must be in (0, 1), got {pi}")
    if undefined_reason(y):
        return None
    observed = y.mean()
    return np.where(y == 1, pi / observed, (1.0 - pi) / (1.0 - observed))


def threshold_views(y, s, t: float, natural_prevalence: Optional[float] = None) -> Dict[str, Dict]:
    """Threshold metrics under the `observed` and `balanced` (pi=0.5) views, plus `natural`
    only when a prevalence is configured. Each entry is labelled with `view` and `prevalence`.

    A reweighted view on single-class data keeps the prevalence-invariant rates (TPR, FPR)
    and reports precision/F1 as None with reason `single_class`.
    """
    y, s, _ = _prepare(y, s)
    observed = threshold_metrics(y, s, t)
    out = {
        "observed": {
            **observed,
            "view": "observed",
            "prevalence": float(y.mean()) if y.size else None,
            "reason": undefined_reason(y) if y.size == 0 else None,
        }
    }
    targets = [("balanced", 0.5)]
    if natural_prevalence is not None:
        targets.append(("natural", float(natural_prevalence)))
    for view, pi in targets:
        weights = prevalence_weights(y, pi)
        if weights is None:
            entry = {**observed, "precision": None, "f1": None, "reason": undefined_reason(y)}
        else:
            entry = {**threshold_metrics(y, s, t, sample_weight=weights), "reason": None}
        out[view] = {**entry, "view": view, "prevalence": pi}
    return out


def per_group(
    fn: MetricFn, y, s, groups, keys: Optional[Iterable[Hashable]] = None
) -> Dict[Hashable, Dict]:
    """`{group: {n, n_pos, value, reason}}`. Requested `keys` with no rows give `n=0`,
    `value=None`, reason `empty`; undefined values carry their reason."""
    y, s, _ = _prepare(y, s)
    groups = np.asarray(groups, dtype=object)
    if groups.shape != y.shape:
        raise ValueError(f"labels and groups differ in length: {y.shape} vs {groups.shape}")
    if keys is None:
        keys = sorted(set(groups.tolist()), key=str)
    out = {}
    for key in keys:
        mask = groups == key
        yy, ss = y[mask], s[mask]
        value = fn(yy, ss) if yy.size else None
        reason = None if value is not None else (undefined_reason(yy) or "undefined")
        out[key] = {"n": int(yy.size), "n_pos": int(yy.sum()), "value": _float(value), "reason": reason}
    return out


# --- retrieval: MAP@R -------------------------------------------------------------------------


def ap_at_r(relevant_ranked: Sequence, r: int) -> float:
    """AP@R (Musgrave et al.): (1/R) * sum over the top R ranks of P(i) * rel(i)."""
    if r <= 0:
        raise ValueError("R must be positive")
    rel = np.asarray(relevant_ranked, dtype=np.float64)[:r]
    hits = np.cumsum(rel)
    return float(np.sum(hits / np.arange(1, rel.size + 1) * rel) / r)


def map_at_r(sim, labels: Sequence[Optional[Hashable]]) -> Dict:
    """MAP@R for one assignment.

    `sim` is an n x n similarity matrix, `labels[i]` the cluster of item i (None = no
    cluster). Queries are items with R >= 1 other members of their cluster; candidates are all
    other items (the diagonal is excluded), ranked by similarity with ties in stable index
    order. Items with R = 0 are excluded and counted. Returns
    `{value, n_queries, n_excluded, ap_sum}` (`value` None without queries).
    """
    sim = np.asarray(sim, dtype=np.float64)
    n = len(labels)
    if sim.shape != (n, n):
        raise ValueError(f"similarity matrix must be {n}x{n}, got {sim.shape}")
    index: Dict[Hashable, int] = {}
    codes = np.array(
        [-(i + 1) if lab is None else index.setdefault(lab, len(index)) for i, lab in enumerate(labels)],
        dtype=np.int64,
    )
    same = codes[:, None] == codes[None, :]
    np.fill_diagonal(same, False)
    r = same.sum(axis=1)
    queries = np.flatnonzero(r > 0)
    if queries.size == 0:
        return {"value": None, "n_queries": 0, "n_excluded": n, "ap_sum": 0.0}
    order = np.argsort(-sim[queries], axis=1, kind="stable")
    order = order[order != queries[:, None]].reshape(queries.size, n - 1)
    rq = r[queries]
    ranks = np.arange(1, n)
    rel = same[queries[:, None], order] & (ranks[None, :] <= rq[:, None])
    precision = np.cumsum(rel, axis=1) / ranks[None, :]
    ap = np.sum(precision * rel, axis=1) / rq
    return {
        "value": float(ap.mean()),
        "n_queries": int(queries.size),
        "n_excluded": int(n - queries.size),
        "ap_sum": float(ap.sum()),
    }


def mean_map_at_r(results: Iterable[Mapping]) -> Dict:
    """Macro mean over every query of several `map_at_r` results (e.g. one per assignment)."""
    n_queries = n_excluded = 0
    ap_sum = 0.0
    for res in results:
        n_queries += res["n_queries"]
        n_excluded += res["n_excluded"]
        ap_sum += res["ap_sum"]
    return {
        "value": ap_sum / n_queries if n_queries else None,
        "n_queries": n_queries,
        "n_excluded": n_excluded,
        "ap_sum": ap_sum,
    }


# --- calibration error ------------------------------------------------------------------------


def reliability_bins(y, p, n_bins: int = 15) -> Dict:
    """Equal-width reliability bins on [0, 1] and the ECE they imply.

    Returns `{n_bins, n, ece, bins: [{lo, hi, n, mean_pred, frac_pos}]}`; ECE is the
    count-weighted mean |frac_pos - mean_pred| (None without samples).
    """
    y, p, _ = _prepare(y, p)
    if p.size and (np.nanmin(p) < 0.0 or np.nanmax(p) > 1.0 or np.isnan(p).any()):
        raise ValueError("ECE needs probabilities in [0, 1]")
    idx = np.minimum((p * n_bins).astype(np.int64), n_bins - 1)
    counts = np.bincount(idx, minlength=n_bins)
    sum_p = np.bincount(idx, weights=p, minlength=n_bins)
    sum_y = np.bincount(idx, weights=y.astype(np.float64), minlength=n_bins)
    bins = []
    for b in range(n_bins):
        c = int(counts[b])
        bins.append(
            {
                "lo": b / n_bins,
                "hi": (b + 1) / n_bins,
                "n": c,
                "mean_pred": float(sum_p[b] / c) if c else None,
                "frac_pos": float(sum_y[b] / c) if c else None,
            }
        )
    ece_value = float(np.abs(sum_y - sum_p).sum() / p.size) if p.size else None
    return {"n_bins": n_bins, "n": int(p.size), "ece": ece_value, "bins": bins}


def ece(y, p, n_bins: int = 15) -> Optional[float]:
    """Expected calibration error with `n_bins` equal-width bins (None without samples)."""
    return reliability_bins(y, p, n_bins)["ece"]


# --- bootstrap --------------------------------------------------------------------------------


def _is_valid(value) -> bool:
    return value is not None and math.isfinite(value)


def bootstrap_many(
    fns: Mapping[str, MetricFn],
    y,
    s,
    *,
    n_boot: int = 1000,
    seed: int,
    groups=None,
    alpha: float = 0.05,
    min_valid: Optional[int] = None,
) -> Dict[str, Dict]:
    """Percentile bootstrap CIs for several metrics over the same resamples.

    With `groups`, whole units (e.g. atomic units or blocks) are resampled with replacement;
    otherwise single samples are. Resamples where a metric is None/NaN are skipped and counted
    (`skipped_resamples`); with fewer than `min_valid` valid resamples (default half of
    `n_boot`) the CI is null with reason `too_few_valid_resamples`. A local
    `np.random.default_rng(seed)` drives the draws, so results depend only on the inputs and
    the seed, and global RNG state is untouched.
    """
    y = np.asarray(y)
    s = np.asarray(s)
    n = y.shape[0]
    if s.shape[0] != n:
        raise ValueError(f"labels and scores differ in length: {y.shape} vs {s.shape}")
    if min_valid is None:
        min_valid = max(1, n_boot // 2)
    rng = np.random.default_rng(seed)
    if groups is None:
        unit, n_units = "sample", n
    else:
        groups = np.asarray(groups, dtype=object)
        if groups.shape[0] != n:
            raise ValueError(f"labels and groups differ in length: {n} vs {groups.shape[0]}")
        _, codes = np.unique(groups.astype(str), return_inverse=True)
        by_group = np.argsort(codes, kind="stable")
        group_of_sorted = codes[by_group]
        unit, n_units = "group", int(codes.max()) + 1 if n else 0

    stats: Dict[str, List[float]] = {name: [] for name in fns}
    skipped = {name: 0 for name in fns}
    for _ in range(n_boot if n else 0):
        if groups is None:
            idx = rng.integers(0, n, n)
        else:
            counts = np.bincount(rng.integers(0, n_units, n_units), minlength=n_units)
            idx = np.repeat(by_group, counts[group_of_sorted])
        yy, ss = y[idx], s[idx]
        for name, fn in fns.items():
            value = fn(yy, ss)
            if _is_valid(value):
                stats[name].append(float(value))
            else:
                skipped[name] += 1

    out = {}
    for name, fn in fns.items():
        point = fn(y, s) if n else None
        result = {
            "value": float(point) if _is_valid(point) else None,
            "reason": None,
            "lo": None,
            "hi": None,
            "ci95": None,
            "alpha": alpha,
            "n_boot": n_boot,
            "n_valid": len(stats[name]),
            "skipped_resamples": skipped[name],
            "unit": unit,
            "n_units": n_units,
            "seed": seed,
        }
        if result["value"] is None:
            try:
                result["reason"] = undefined_reason(y) or "undefined"
            except ValueError:
                result["reason"] = "undefined"
        elif len(stats[name]) < min_valid:
            result["reason"] = "too_few_valid_resamples"
        else:
            lo, hi = np.quantile(np.asarray(stats[name]), [alpha / 2, 1 - alpha / 2])
            result.update(lo=float(lo), hi=float(hi), ci95=[float(lo), float(hi)])
        out[name] = result
    return out


def bootstrap_ci(
    fn: MetricFn,
    y,
    s,
    *,
    n_boot: int = 1000,
    seed: int,
    groups=None,
    alpha: float = 0.05,
    min_valid: Optional[int] = None,
) -> Dict:
    """Percentile bootstrap CI for one metric; see `bootstrap_many`."""
    return bootstrap_many(
        {"metric": fn}, y, s, n_boot=n_boot, seed=seed, groups=groups, alpha=alpha, min_valid=min_valid
    )["metric"]

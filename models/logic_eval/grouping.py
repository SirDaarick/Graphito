"""E1 evaluation metrics: MAP@R, Recall@1, ROC-AUC, Silhouette, and confusion matrix."""

from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
from sklearn.metrics import silhouette_score

from models.evaluation.metrics import map_at_r, roc_auc


def compute_map_at_r(sim: np.ndarray, labels: Sequence[Any]) -> Dict[str, Any]:
    """Compute MAP@R across all queries where at least one other peer exists."""
    return map_at_r(sim, labels)


def compute_recall_at_1(sim: np.ndarray, labels: Sequence[Any]) -> Optional[float]:
    """Fraction of queries whose nearest neighbor (excluding self) belongs to the same cluster."""
    sim = np.asarray(sim, dtype=np.float64)
    n = len(labels)
    if n <= 1:
        return None

    labels_arr = np.array(labels)
    # Mask out diagonal
    masked_sim = sim.copy()
    np.fill_diagonal(masked_sim, -np.inf)

    # Find nearest neighbor for each item
    nn_indices = np.argmax(masked_sim, axis=1)

    # Consider only items that have at least one other member with the same label
    has_peer = np.zeros(n, dtype=bool)
    for i in range(n):
        if np.sum(labels_arr == labels_arr[i]) > 1:
            has_peer[i] = True

    if not np.any(has_peer):
        return None

    correct = labels_arr[nn_indices[has_peer]] == labels_arr[has_peer]
    return float(np.mean(correct))


def random_baseline_map_at_r(
    labels: Sequence[Any], seed: int = 42, n_permutations: int = 50
) -> float:
    """Compute expected MAP@R under random similarity ordering."""
    n = len(labels)
    rng = np.random.default_rng(seed)
    scores = []
    for _ in range(n_permutations):
        # Generate random symmetric similarity matrix
        rand_sim = rng.standard_normal((n, n))
        rand_sim = rand_sim + rand_sim.T
        res = compute_map_at_r(rand_sim, labels)
        if res["value"] is not None:
            scores.append(res["value"])
    return float(np.mean(scores)) if scores else 0.0


def compute_cosine_silhouette(
    sim: np.ndarray, labels: Sequence[Any]
) -> Optional[float]:
    """Compute Silhouette score on precomputed cosine distance (1 - sim)."""
    labels_arr = np.array(labels)
    unique_labels = np.unique(labels_arr)
    n = len(labels)
    if len(unique_labels) < 2 or len(unique_labels) >= n:
        return None

    # Distance = clip(1 - sim, 0, 2)
    dist = np.clip(1.0 - np.asarray(sim, dtype=np.float64), 0.0, 2.0)
    np.fill_diagonal(dist, 0.0)
    try:
        score = silhouette_score(dist, labels_arr, metric="precomputed")
        return float(score)
    except Exception:
        return None


def compute_pairwise_roc_auc(
    sim: np.ndarray,
    labels: Sequence[Any],
    courses: Optional[Sequence[Any]] = None,
) -> Optional[float]:
    """Compute pairwise ROC-AUC (same cluster vs different cluster).

    If courses is given, pairs are restricted to pairs within the same course.
    """
    sim = np.asarray(sim, dtype=np.float64)
    labels_arr = np.array(labels)
    n = len(labels_arr)
    if n <= 1:
        return None

    # Upper triangular indices
    i_idx, j_idx = np.triu_indices(n, k=1)

    if courses is not None:
        courses_arr = np.array(courses)
        course_mask = courses_arr[i_idx] == courses_arr[j_idx]
        i_idx = i_idx[course_mask]
        j_idx = j_idx[course_mask]

    if len(i_idx) == 0:
        return None

    y = (labels_arr[i_idx] == labels_arr[j_idx]).astype(np.int64)
    scores = sim[i_idx, j_idx]

    return roc_auc(y, scores)


def compute_assignment_confusion(
    sim: np.ndarray, labels: Sequence[Any]
) -> Dict[str, Dict[str, int]]:
    """Compute confusion counts between assignments when nearest neighbor belongs to another assignment."""
    sim = np.asarray(sim, dtype=np.float64)
    labels_arr = np.array(labels)
    n = len(labels_arr)
    masked_sim = sim.copy()
    np.fill_diagonal(masked_sim, -np.inf)

    nn_indices = np.argmax(masked_sim, axis=1)

    confusion: Dict[str, Dict[str, int]] = {}
    for i in range(n):
        true_lbl = str(labels_arr[i])
        pred_lbl = str(labels_arr[nn_indices[i]])
        if true_lbl != pred_lbl:
            confusion.setdefault(true_lbl, {}).setdefault(pred_lbl, 0)
            confusion[true_lbl][pred_lbl] += 1

    return confusion


def compute_per_assignment_map_at_r(
    sim: np.ndarray, labels: Sequence[Any], query_to_assignment: Sequence[str]
) -> Dict[str, Dict[str, Any]]:
    """Compute MAP@R partitioned by assignment block against the full candidate pool."""
    sim = np.asarray(sim, dtype=np.float64)
    n = len(labels)
    index: Dict[Any, int] = {}
    codes = np.array(
        [-(i + 1) if lab is None else index.setdefault(lab, len(index)) for i, lab in enumerate(labels)],
        dtype=np.int64,
    )
    same = codes[:, None] == codes[None, :]
    np.fill_diagonal(same, False)
    r = same.sum(axis=1)
    queries = np.flatnonzero(r > 0)

    unique_assigns = sorted(set(query_to_assignment))
    per_assign: Dict[str, Dict[str, Any]] = {
        assign: {"n_queries": 0, "n_excluded": 0, "ap_sum": 0.0, "value": None}
        for assign in unique_assigns
    }

    if queries.size == 0:
        return per_assign

    order = np.argsort(-sim[queries], axis=1, kind="stable")
    order = order[order != queries[:, None]].reshape(queries.size, n - 1)
    rq = r[queries]
    ranks = np.arange(1, n)
    rel = same[queries[:, None], order] & (ranks[None, :] <= rq[:, None])
    precision = np.cumsum(rel, axis=1) / ranks[None, :]
    ap = np.sum(precision * rel, axis=1) / rq

    for q_idx, q in enumerate(queries):
        assign = query_to_assignment[q]
        per_assign[assign]["n_queries"] += 1
        per_assign[assign]["ap_sum"] += float(ap[q_idx])

    for assign, res in per_assign.items():
        if res["n_queries"] > 0:
            res["value"] = float(res["ap_sum"] / res["n_queries"])

    return per_assign


def bootstrap_metric_difference(
    metric_a: np.ndarray,
    metric_b: np.ndarray,
    n_boot: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Compute paired bootstrap difference (a - b) over assignment units."""
    diff = np.asarray(metric_a) - np.asarray(metric_b)
    n = len(diff)
    if n == 0:
        return {"mean_diff": None, "ci95": None}

    rng = np.random.default_rng(seed)
    boot_means = []
    for _ in range(n_boot):
        sample = rng.choice(diff, size=n, replace=True)
        boot_means.append(float(np.mean(sample)))

    lo, hi = np.quantile(boot_means, [alpha / 2.0, 1.0 - alpha / 2.0])
    return {
        "mean_diff": float(np.mean(diff)),
        "ci95": [float(lo), float(hi)],
    }

"""E2 evaluation metrics: leave-one-out reference evaluation, AUC, and Spearman."""

from typing import Any, Dict, List, Optional, Sequence
import numpy as np
from scipy.stats import spearmanr

from models.evaluation.metrics import roc_auc


def evaluate_assignment_leave_one_out(
    sim: np.ndarray,
    pass_rates: Sequence[float],
    assignment_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Leave-one-out reference evaluation across all passing solutions for an assignment.

    Args:
        sim: n x n similarity matrix between solutions of the assignment.
        pass_rates: pass rate in [0, 1] for each solution (1.0 = pass, <1.0 = fail).
        assignment_name: Optional identifier of the assignment.

    Returns:
        Dict with n_pass, n_fail, mean AUC, mean Spearman, and per-reference results.
    """
    sim = np.asarray(sim, dtype=np.float64)
    rates = np.asarray(pass_rates, dtype=np.float64)
    n = len(rates)

    pass_indices = np.flatnonzero(rates == 1.0)
    fail_indices = np.flatnonzero(rates < 1.0)

    n_pass = int(len(pass_indices))
    n_fail = int(len(fail_indices))

    if n_pass == 0 or n_fail == 0:
        return {
            "assignment": assignment_name,
            "n_total": n,
            "n_pass": n_pass,
            "n_fail": n_fail,
            "auc": None,
            "spearman": None,
            "per_reference": [],
        }

    aucs: List[float] = []
    spearmans: List[float] = []
    per_ref: List[Dict[str, Any]] = []

    for r_idx in pass_indices:
        # Candidate set: all other solutions
        cand_indices = np.array([idx for idx in range(n) if idx != r_idx], dtype=np.int64)
        cand_sims = sim[r_idx, cand_indices]
        cand_rates = rates[cand_indices]
        cand_labels = (cand_rates == 1.0).astype(np.int64)

        # Binary ROC-AUC (pass vs fail)
        val_auc = roc_auc(cand_labels, cand_sims)
        if val_auc is not None:
            aucs.append(val_auc)

        # Spearman rank correlation (similarity vs pass_rate)
        if len(np.unique(cand_sims)) > 1 and len(np.unique(cand_rates)) > 1:
            res = spearmanr(cand_sims, cand_rates)
            val_spearman = float(res.correlation) if not np.isnan(res.correlation) else 0.0
        else:
            val_spearman = 0.0
        spearmans.append(val_spearman)

        per_ref.append({
            "ref_index": int(r_idx),
            "auc": val_auc,
            "spearman": val_spearman,
        })

    mean_auc = float(np.mean(aucs)) if aucs else None
    mean_spearman = float(np.mean(spearmans)) if spearmans else None

    return {
        "assignment": assignment_name,
        "n_total": n,
        "n_pass": n_pass,
        "n_fail": n_fail,
        "auc": mean_auc,
        "spearman": mean_spearman,
        "per_reference": per_ref,
    }


def macro_evaluate_e2(
    assignment_results: Sequence[Dict[str, Any]],
    n_boot: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Compute macro averages and bootstrap 95% CIs over assignments for E2."""
    valid_aucs = [r["auc"] for r in assignment_results if r.get("auc") is not None]
    valid_spearmans = [r["spearman"] for r in assignment_results if r.get("spearman") is not None]

    n_assignments = len(assignment_results)
    rng = np.random.default_rng(seed)

    def bootstrap_ci(vals: List[float]) -> Optional[List[float]]:
        if len(vals) < 2:
            return None
        arr = np.array(vals)
        boot_means = []
        for _ in range(n_boot):
            sample = rng.choice(arr, size=len(arr), replace=True)
            boot_means.append(float(np.mean(sample)))
        lo, hi = np.quantile(boot_means, [alpha / 2.0, 1.0 - alpha / 2.0])
        return [float(lo), float(hi)]

    macro_auc = float(np.mean(valid_aucs)) if valid_aucs else None
    macro_spearman = float(np.mean(valid_spearmans)) if valid_spearmans else None

    return {
        "n_assignments": n_assignments,
        "n_valid_auc": len(valid_aucs),
        "macro_auc": macro_auc,
        "auc_ci95": bootstrap_ci(valid_aucs) if valid_aucs else None,
        "macro_spearman": macro_spearman,
        "spearman_ci95": bootstrap_ci(valid_spearmans) if valid_spearmans else None,
        "per_assignment": list(assignment_results),
    }

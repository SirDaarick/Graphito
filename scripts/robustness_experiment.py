#!/usr/bin/env python3
"""Channel A Robustness Experiment CLI and evaluation pipeline."""

import argparse
import concurrent.futures
import dataclasses
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np

# Ensure repository root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.evaluation.calibration import load_calibration
from models.evaluation.manifest import DEFAULT_MANIFEST, ManifestError, SplitManifest, load_manifest
from models.evaluation import metrics as M
from models.evaluation.provenance import atomic_write_bytes, package_versions
from models.evaluation.report import RunContext, compute_metrics
from models.graphcodebert.v2.baselines import (
    SetSimilarity,
    V2FileEmbedder,
    jaccard_set,
    load_legacy,
    winnowing_set,
)
from models.graphcodebert.v2.cache import CachedEmbedder, EmbeddingCache, FileEmbedding
from models.graphcodebert.v2.config import GCBV2Config
from models.graphcodebert.v2.evaluate import (
    FileRecord,
    Refused,
    load_embedders,
    load_files,
    operating_points,
)
from models.graphcodebert.v2.pairs import (
    VIEWS,
    EvalPairs,
    ScoredPairs,
    embedding_similarity,
    map_at_r_ci,
    score_pairs,
    stack_embeddings,
)
from models.graphcodebert.v2.runs import (
    DEFAULT_N_BOOT,
    REFUSED_EXIT,
    RUN_FAILED_EXIT,
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_RUNNING,
    describe_error,
    resolve_device,
    set_run_status,
    write_json,
)
from models.robustness.scoring import (
    CrossSetSimilarity,
    cross_embedding_similarity,
    paired_bootstrap,
    texts_for_method,
)
from models.robustness.transforms import (
    TRANSFORMS,
    TransformResult,
    apply_condition,
    derive_seed,
)
from models.robustness.validity import (
    abstract_edit_ratio,
    count_error_nodes,
    syntax_check,
    token_edit_ratio,
)
from models.graphcodebert.v2.adapter import (
    AdapterFileEmbedder,
    adapter_sha256,
    build_embedder,
    is_adapter_method,
    parse_adapter_specs,
)
from models.graphcodebert.v2.dfg import parse_source

CHANNEL = "robustness"
ALL_METHODS = ("jaccard", "winnowing", "v2", "v2_nodfg", "legacy", "v2_norm")
LEXICAL_METHODS = ("jaccard", "winnowing")
EMBEDDING_METHODS = ("v2", "v2_nodfg", "legacy", "v2_norm")
# v2_norm reuses the v2 embedder (same cache key); only the text fed to it differs.
EMBEDDER_ALIAS = {"v2_norm": "v2"}


def _text_keyed(method: str) -> bool:
    """Canonicalized-text methods (v2_norm and the `ft_<name>` adapters) are cached by the sha256 of the
    text actually embedded, not by the file sha."""
    return method in EMBEDDER_ALIAS or is_adapter_method(method)


LEXICAL_FNS: Dict[str, Callable[[str], np.ndarray]] = {
    "jaccard": jaccard_set,
    "winnowing": winnowing_set,
}
DEFAULT_CONDITIONS = "T0,T1,T2,T3,T4,T5,T6,T7@0.25,T7@0.5,T7@1.0"
DEFAULT_METHODS = "jaccard,winnowing,v2,v2_nodfg"
DEFAULT_MODEL = "microsoft/graphcodebert-base"
VERSION_PACKAGES = (
    "torch", "transformers", "tree-sitter", "tree-sitter-c", "tree-sitter-cpp", "numpy", "scipy", "scikit-learn",
)


def _log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def _plain(value: Any) -> Any:
    """JSON-safe copy."""
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_plain(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path: Path, doc: Any) -> None:
    atomic_write_bytes(path, json.dumps(doc, indent=2).encode("utf-8"))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Channel A robustness evaluation under structural obfuscation.")
    p.add_argument("--manifest", default=DEFAULT_MANIFEST, help="Path to split manifest.")
    p.add_argument(
        "--expected-sha256",
        default="e835362d2e7a4153ef97204d4b30e769759a0f8f54f7db67b9e1fb2639e5238f",
        help="Expected manifest sha256.",
    )
    p.add_argument("--split", default="val", choices=["train", "val", "test"], help="Dataset split to evaluate.")
    p.add_argument("--confirm-test", action="store_true", help="Explicit confirmation required to evaluate on test.")
    p.add_argument(
        "--source-run",
        default="runs/graphcodebert/20261011-082155",
        help="Reference run directory for selection and val thresholds.",
    )
    p.add_argument(
        "--deploy-calibration",
        default="models/deploy/channel_a/calibration.json",
        help="Deployed isotonic calibration for Jaccard.",
    )
    p.add_argument("--methods", default=DEFAULT_METHODS, help="Comma-separated methods to evaluate.")
    p.add_argument("--conditions", default=DEFAULT_CONDITIONS, help="Comma-separated conditions.")
    p.add_argument(
        "--stage",
        default="all",
        choices=["all", "transform", "embed", "score", "report"],
        help="Execution stage.",
    )
    p.add_argument("--resume", default=None, help="Directory of a previous run to continue.")
    p.add_argument("--seed", type=int, default=42, help="Random seed for bootstrap.")
    p.add_argument("--n-boot", type=int, default=1000, help="Bootstrap draws for primary contrasts (H1, H2, H3).")
    p.add_argument("--n-boot-secondary", type=int, default=200, help="Bootstrap draws for exploratory conditions.")
    p.add_argument("--device", default="cuda", help="PyTorch device.")
    p.add_argument("--batch-size", type=int, default=16, help="Embedder batch size.")
    p.add_argument("--cache-dir", default="runs/graphcodebert/_cache", help="Embeddings cache root.")
    p.add_argument("--limit-assignments", type=int, default=None, help="Limit to first N assignments.")
    p.add_argument("--local-files-only", action="store_true", default=True, help="Disallow network HF downloads.")
    p.add_argument("--root", default=str(ROOT), help="Repository root.")
    p.add_argument("--runs-root", default="runs", help="Root directory for runs.")
    p.add_argument("--skip-validity", action="store_true", help="Skip parse/compile/edit-ratio validity metrics (scores are unaffected).")
    p.add_argument("--prefill-shard", default=None, help="K/N: only warm the embedding cache for shard K of N, then exit.")
    p.add_argument("--run-dir", default=None, help="Exact output directory for a fresh run (default: <runs-root>/robustness/<timestamp>).")
    p.add_argument("--reference-run", default="runs/robustness/20261012-050941", help="Earlier robustness run for the v2_norm reproduction check.")
    p.add_argument(
        "--adapter",
        action="append",
        default=[],
        metavar="ft_NAME=PATH",
        help="LoRA adapter to score as an extra method named ft_NAME (also list it in --methods). Repeatable.",
    )
    return p


# --- Transformation & Validation Worker ---------------------------------------------------------


def _transform_one_file(
    sample_id: str,
    text: str,
    lang: str,
    cond: str,
    base_seed: int,
    skip_validity: bool = False,
) -> Dict[str, Any]:
    orig_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    t_seed = derive_seed(base_seed, orig_sha, cond, 1.0)
    res = apply_condition(text, lang, cond, seed=t_seed)
    trans_sha = hashlib.sha256(res.code.encode("utf-8")).hexdigest()
    if skip_validity:
        return {
            "id": sample_id, "condition": cond, "sha256_in": orig_sha, "sha256_out": trans_sha,
            "code_out": res.code, "n_eligible": res.n_eligible, "n_applied": res.n_applied,
            "parse_ok": True, "compile_ok": None, "edit_tokens": 0.0, "edit_abstract": 0.0,
        }

    # Parse validity check
    orig_tree = parse_source(text.encode("utf-8"), lang)
    trans_tree = parse_source(res.code.encode("utf-8"), lang)
    orig_err = count_error_nodes(orig_tree.root_node)
    trans_err = count_error_nodes(trans_tree.root_node)
    parse_ok = trans_err <= orig_err

    # Compiler syntax check (if compiler available)
    compile_ok = syntax_check(res.code, lang)

    # Edit magnitude metrics
    e_tokens = token_edit_ratio(text, res.code)
    e_abstract = abstract_edit_ratio(text, res.code)

    return {
        "id": sample_id,
        "condition": cond,
        "sha256_in": orig_sha,
        "sha256_out": trans_sha,
        "code_out": res.code,
        "n_eligible": res.n_eligible,
        "n_applied": res.n_applied,
        "parse_ok": parse_ok,
        "compile_ok": compile_ok,
        "edit_tokens": e_tokens,
        "edit_abstract": e_abstract,
    }


def _compute_single_method_views(
    cond: str,
    m: str,
    score_file_str: str,
    y_all: np.ndarray,
    assignments: np.ndarray,
    masks: Dict[str, np.ndarray],
    n_boot_cond: int,
    seed: int,
    split: str,
    val_th: Optional[float],
    jaccard_cal_path: Optional[str],
) -> Tuple[str, str, Dict[str, Any]]:
    data = np.load(score_file_str)
    raw_s = data["scores"]
    jaccard_cal = load_calibration(Path(jaccard_cal_path)) if jaccard_cal_path else None

    views_doc: Dict[str, Any] = {}
    for view in ("all", "no_identical"):
        mask = masks[view]
        yy = y_all[mask]
        ss = raw_s[mask]
        grp = assignments[mask]

        ops = {}
        if m == "jaccard" and jaccard_cal is not None:
            decisions = jaccard_cal.decide(ss)
            tp = int((decisions & (yy == 1)).sum())
            fp = int((decisions & (yy == 0)).sum())
            fn = int((~decisions & (yy == 1)).sum())
            tn = int((~decisions & (yy == 0)).sum())
            ops["deployed"] = {
                "threshold": jaccard_cal.threshold()["threshold"],
                "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                "tpr": float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0,
                "fpr": float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0,
            }
        elif val_th is not None:
            decisions = ss >= val_th
            tp = int((decisions & (yy == 1)).sum())
            fp = int((decisions & (yy == 0)).sum())
            fn = int((~decisions & (yy == 1)).sum())
            tn = int((~decisions & (yy == 0)).sum())
            ops["deployed"] = {
                "threshold": val_th,
                "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                "tpr": float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0,
                "fpr": float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0,
            }

        met = compute_metrics(
            yy, ss,
            channel=CHANNEL,
            split=split,
            mode="robustness",
            n_boot=n_boot_cond,
            seed=seed,
            bootstrap_groups=grp,
            operating_points=ops,
        )
        views_doc[view] = {
            **met,
            "roc_auc": met["threshold_free"]["roc_auc"],
            "pr_auc": met["threshold_free"]["pr_auc"],
        }

    return cond, m, views_doc


# --- Plotting Helpers ---------------------------------------------------------------------------


def _plot_degradation(path: Path, metrics: Mapping, active_methods: Sequence[str]) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(6, 4.5), dpi=120)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(1, 1, 1)
    ax.set_title("ROC-AUC Degradation under T7 Obfuscation")
    ax.set_xlabel("T7 Intensity")
    ax.set_ylabel("ROC-AUC (view: all)")

    intensities = [0.0, 0.25, 0.5, 1.0]
    cond_keys = ["T0", "T7@0.25", "T7@0.5", "T7@1.0"]
    colors = {"jaccard": "#1f77b4", "winnowing": "#2ca02c", "v2": "#d62728", "v2_nodfg": "#ff7f0e", "legacy": "#7f7f7f"}

    for m in active_methods:
        ys, y_err_lo, y_err_hi = [], [], []
        x_points = []
        for x, c in zip(intensities, cond_keys):
            if c in metrics and m in metrics[c]:
                res = metrics[c][m]["views"]["all"]["roc_auc"]
                val = res.get("value")
                ci = res.get("ci95")
                if val is not None:
                    x_points.append(x)
                    ys.append(val)
                    if ci and len(ci) == 2 and ci[0] is not None:
                        y_err_lo.append(val - ci[0])
                        y_err_hi.append(ci[1] - val)
                    else:
                        y_err_lo.append(0.0)
                        y_err_hi.append(0.0)

        if len(ys) > 1:
            c_color = colors.get(m, "#333333")
            ax.errorbar(
                x_points, ys, yerr=[y_err_lo, y_err_hi],
                label=m, color=c_color, marker="o", capsize=3, linewidth=1.8,
            )

    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(0.4, 1.02)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="lower left", framealpha=0.9)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    atomic_write_bytes(path, buf.getvalue())


def _plot_delta_by_transform(path: Path, contrasts: Mapping, active_methods: Sequence[str]) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(7, 4.5), dpi=120)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(1, 1, 1)
    ax.set_title("Delta ROC-AUC vs T0 by Transformation")
    ax.set_xlabel("Condition")
    ax.set_ylabel("Δ ROC-AUC")

    conditions = ["T1", "T2", "T3", "T4", "T5", "T6", "T7@1.0"]
    present_conds = [c for c in conditions if any(f"delta__{m}__{c}" in contrasts for m in active_methods)]
    if not present_conds:
        return

    n_m = len(active_methods)
    width = 0.8 / max(1, n_m)
    x_indices = np.arange(len(present_conds))
    colors = {"jaccard": "#1f77b4", "winnowing": "#2ca02c", "v2": "#d62728", "v2_nodfg": "#ff7f0e", "legacy": "#7f7f7f"}

    for idx_m, m in enumerate(active_methods):
        deltas = []
        errs = []
        for c in present_conds:
            key = f"delta__{m}__{c}"
            if key in contrasts and contrasts[key].get("value") is not None:
                val = contrasts[key]["value"]
                deltas.append(val)
                ci = contrasts[key].get("ci95")
                if ci and len(ci) == 2 and ci[0] is not None:
                    errs.append((ci[1] - ci[0]) / 2.0)
                else:
                    errs.append(0.0)
            else:
                deltas.append(0.0)
                errs.append(0.0)

        offset = (idx_m - n_m / 2 + 0.5) * width
        ax.bar(
            x_indices + offset, deltas, width,
            yerr=errs, label=m, color=colors.get(m, "#333333"), capsize=2, alpha=0.85,
        )

    ax.axhline(0, color="black", linestyle="--", linewidth=1)
    ax.set_xticks(x_indices)
    ax.set_xticklabels(present_conds)
    ax.legend(loc="lower left", framealpha=0.9)
    ax.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    atomic_write_bytes(path, buf.getvalue())


def _plot_positive_drop(
    path: Path,
    t0_scores: Mapping[str, np.ndarray],
    tk_scores: Mapping[str, np.ndarray],
    pos_mask: np.ndarray,
    active_methods: Sequence[str],
) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(6, 4.5), dpi=120)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(1, 1, 1)
    ax.set_title("Score Drop on Positive Pairs (T0 - T7@1.0)")
    ax.set_xlabel("Method")
    ax.set_ylabel("Score Drop (s_T0 - s_T7@1.0)")

    data = []
    labels = []
    for m in active_methods:
        if m in t0_scores and m in tk_scores:
            s0 = t0_scores[m][pos_mask]
            sk = tk_scores[m][pos_mask]
            drops = s0 - sk
            data.append(drops)
            labels.append(m)

    if data:
        ax.boxplot(data, tick_labels=labels, showmeans=True)
        ax.axhline(0, color="gray", linestyle="--", linewidth=1)
        ax.grid(True, linestyle=":", alpha=0.5)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        atomic_write_bytes(path, buf.getvalue())


# --- Markdown Report Generator ------------------------------------------------------------------


def _generate_report_markdown(
    config: Mapping,
    transform_summary: Mapping,
    metrics: Mapping,
    contrasts: Mapping,
    methods: Sequence[str],
    conditions: Sequence[str],
) -> str:
    lines = [
        "# Channel A Robustness Evaluation Report: Structural Obfuscation",
        "",
        f"- **Run ID:** `{config.get('run_id')}`",
        f"- **Split:** `{config.get('split')}`",
        f"- **Manifest SHA256:** `{config.get('manifest_sha256')}`",
        f"- **Seed:** `{config.get('seed')}`",
        f"- **Primary N_boot:** `{config.get('n_boot')}`",
        "",
        "## 1. Pre-Registered Hypotheses Verdicts",
        "",
        "| Hypothesis | Statement | Contrast Statistic | Estimate [CI95] | Verdict |",
        "|---|---|---|---|---|",
    ]

    # H1 verdict
    h1_key = "did__T7@1.0__jaccard__v2"
    if h1_key in contrasts and contrasts[h1_key].get("value") is not None:
        val = contrasts[h1_key]["value"]
        ci = contrasts[h1_key].get("ci95")
        ci_str = f"[{ci[0]:.4f}, {ci[1]:.4f}]" if ci else "N/A"
        if ci and ci[1] < 0:
            v_h1 = "**CONFIRMED** (jaccard drops more than v2)"
        elif ci and ci[0] > 0:
            v_h1 = "**REFUTED** (v2 drops more than jaccard)"
        else:
            v_h1 = "**INCONCLUSIVE** (CI contains 0)"
        lines.append(f"| **H1** | Jaccard degrades more than v2 under T7@1.0 | `DiD(T7@1.0; jaccard, v2)` | {val:.4f} {ci_str} | {v_h1} |")
    else:
        lines.append("| **H1** | Jaccard degrades more than v2 under T7@1.0 | `DiD(T7@1.0; jaccard, v2)` | N/A | Not evaluated |")

    # H2 verdict
    h2_key = "delta__jaccard__T1"
    if h2_key in contrasts and contrasts[h2_key].get("value") is not None:
        val = contrasts[h2_key]["value"]
        ci = contrasts[h2_key].get("ci95")
        ci_str = f"[{ci[0]:.4f}, {ci[1]:.4f}]" if ci else "N/A"
        if abs(val) < 1e-9:
            v_h2 = "**CONFIRMED** (exact zero drop, control intact)"
        else:
            v_h2 = f"**FAILED** (nonzero drop {val:.6f}; implementation bug)"
        lines.append(f"| **H2** | T1 acts as invariant control for Jaccard | `ΔROC-AUC_jaccard(T1)` | {val:.4f} {ci_str} | {v_h2} |")
    else:
        lines.append("| **H2** | T1 acts as invariant control for Jaccard | `ΔROC-AUC_jaccard(T1)` | N/A | Not evaluated |")

    # H3 verdict
    h3_entry = None
    h3_sign = 1.0
    if "did__T3__v2_nodfg__v2" in contrasts:
        h3_entry = contrasts["did__T3__v2_nodfg__v2"]
    elif "did__T3__v2__v2_nodfg" in contrasts:
        h3_entry = contrasts["did__T3__v2__v2_nodfg"]
        h3_sign = -1.0

    if h3_entry is not None and h3_entry.get("value") is not None:
        val = h3_entry["value"] * h3_sign
        raw_ci = h3_entry.get("ci95")
        ci = sorted([raw_ci[0] * h3_sign, raw_ci[1] * h3_sign]) if raw_ci else None
        ci_str = f"[{ci[0]:.4f}, {ci[1]:.4f}]" if ci else "N/A"
        if ci and ci[1] < 0:
            v_h3 = "**CONFIRMED** (v2_nodfg drops more than v2 under reordering)"
        elif ci and ci[0] > 0:
            v_h3 = "**REFUTED** (DFG hurts under reordering)"
        else:
            v_h3 = "**INCONCLUSIVE** (DFG invariance not statistically significant)"
        lines.append(f"| **H3** | DFG confers robustness under reordering T3 | `DiD(T3; v2_nodfg, v2)` | {val:.4f} {ci_str} | {v_h3} |")
    else:
        lines.append("| **H3** | DFG confers robustness under reordering T3 | `DiD(T3; v2_nodfg, v2)` | N/A | Not evaluated |")

    lines.extend([
        "",
        "## 2. Transformation Validity & Edit Magnitude",
        "",
        "| Condition | Applied Files | Applied Rate | Parse OK Rate | Mean Token Edit | Mean Abstract Edit |",
        "|---|---|---|---|---|---|",
    ])

    cond_stats = transform_summary.get("conditions", transform_summary)
    for c, stat in cond_stats.items():
        n_files = stat.get("n_files", 0)
        n_app = stat.get("n_applied_gt_0", 0)
        app_rate = (n_app / n_files * 100) if n_files else 0.0
        p_ok = (stat.get("parse_ok_rate", 1.0) or 1.0) * 100
        m_tok = stat.get("mean_edit_tokens", 0.0)
        m_abs = stat.get("mean_edit_abstract", 0.0)
        lines.append(f"| `{c}` | {n_app}/{n_files} | {app_rate:.1f}% | {p_ok:.1f}% | {m_tok:.4f} | {m_abs:.4f} |")

    lines.extend([
        "",
        "## 3. Method Performance by Condition (View: all)",
        "",
    ])

    header_cols = ["Condition"] + list(methods) + (["DiD (jac - v2)"] if "jaccard" in methods and "v2" in methods else [])
    lines.append("| " + " | ".join(header_cols) + " |")
    lines.append("|" + "|".join(["---"] * len(header_cols)) + "|")

    for c in conditions:
        row = [f"`{c}`"]
        for m in methods:
            if c in metrics and m in metrics[c]:
                auc_res = metrics[c][m]["views"]["all"]["roc_auc"]
                val = auc_res.get("value")
                ci = auc_res.get("ci95")
                if val is not None:
                    if ci and len(ci) == 2 and ci[0] is not None:
                        row.append(f"{val:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]")
                    else:
                        row.append(f"{val:.3f}")
                else:
                    row.append("N/A")
            else:
                row.append("—")

        if "jaccard" in methods and "v2" in methods:
            did_k = f"did__{c}__jaccard__v2"
            if did_k in contrasts and contrasts[did_k].get("value") is not None:
                did_val = contrasts[did_k]["value"]
                did_ci = contrasts[did_k].get("ci95")
                if did_ci and len(did_ci) == 2 and did_ci[0] is not None:
                    row.append(f"{did_val:+.3f} [{did_ci[0]:+.3f}, {did_ci[1]:+.3f}]")
                else:
                    row.append(f"{did_val:+.3f}")
            else:
                row.append("—")

        lines.append("| " + " | ".join(row) + " |")

    lines.extend([
        "",
        "## 4. Figures",
        "",
        "- [Degradation Curve](plots/degradation_curve.png)",
        "- [Delta by Transform](plots/delta_by_transform.png)",
        "- [Positive Drop Distribution](plots/positive_drop.png)",
        "",
    ])

    return "\n".join(lines)


# --- v2_norm study (identifier canonicalization) -------------------------------------------------

V2NORM_REFERENCE_RUN = "runs/robustness/20261012-050941"
V2NORM_REPRO_TOL = 0.002
V2NORM_SANITY_N = 200


def _auc_of(metrics: Mapping, cond: str, method: str) -> Tuple[Optional[float], Optional[List[float]]]:
    res = metrics.get(cond, {}).get(method, {}).get("views", {}).get("all", {}).get("roc_auc", {})
    return res.get("value"), res.get("ci95")


def v2norm_reproduction_check(metrics: Mapping, reference_run: Path) -> Dict[str, Any]:
    """Compare v2/jaccard ROC-AUC (view all) at T0 and T1 against the earlier robustness run."""
    ref = json.loads((Path(reference_run) / "metrics.json").read_text(encoding="utf-8"))
    rows, ok = [], True
    for method in ("v2", "jaccard"):
        for cond in ("T0", "T1"):
            new, _ = _auc_of(metrics, cond, method)
            old, _ = _auc_of(ref, cond, method)
            diff = None if new is None or old is None else new - old
            passed = diff is not None and abs(diff) <= V2NORM_REPRO_TOL
            ok = ok and passed
            rows.append({"method": method, "condition": cond, "new": new, "reference": old, "diff": diff, "ok": passed})
    return {"tolerance": V2NORM_REPRO_TOL, "reference_run": str(reference_run), "ok": ok, "rows": rows}


def v2norm_sanity_check(ep, files, transformed_records, seed: int, n: int = V2NORM_SANITY_N) -> Dict[str, Any]:
    """Fraction of sampled positive pairs whose file b satisfies canon(T1(b)) == canon(b)."""
    from models.logic_eval.canonical import canonicalize_code

    pos = np.flatnonzero(ep.pairs.label == 1)
    rng = np.random.default_rng(seed)
    pick = rng.choice(pos, size=min(n, pos.size), replace=False)
    n_match, mismatches, n_applied = 0, [], 0
    for pi in pick:
        s = ep.samples[int(ep.pairs.b[pi])]
        rec = transformed_records[(s.id, "T1")]
        n_applied += int(rec["n_applied"] > 0)
        ca = canonicalize_code(files[s.id].text, s.lang)
        t1_code = rec["code_out"] if "code_out" in rec else apply_condition(
            files[s.id].text, s.lang, "T1", seed=derive_seed(seed, rec["sha256_in"], "T1", 1.0)
        ).code
        cb = canonicalize_code(t1_code, s.lang)
        if ca == cb:
            n_match += 1
        else:
            al, bl = ca.splitlines(), cb.splitlines()
            first = next((i for i, (x, y) in enumerate(zip(al, bl)) if x != y), min(len(al), len(bl)))
            mismatches.append({
                "id": s.id, "lang": s.lang, "line": first + 1,
                "canon_orig": al[first] if first < len(al) else None,
                "canon_t1": bl[first] if first < len(bl) else None,
            })
    return {
        "n_sampled": int(pick.size), "n_equal": n_match, "fraction_equal": n_match / max(1, pick.size),
        "n_t1_applied": n_applied, "n_mismatch": len(mismatches), "mismatches": mismatches,
    }


def v2norm_level_contrasts(y, scores_by_cond_method, mask, groups, conds, n_boot: int, seed: int) -> Dict[str, Any]:
    """Paired bootstrap of AUC_v2_norm(c) - AUC_v2(c): pseudo-method with T0=v2 and T1=v2_norm."""
    sd = {
        f"lvl{i}": {"T0": scores_by_cond_method[c]["v2"][mask], "T1": scores_by_cond_method[c]["v2_norm"][mask]}
        for i, c in enumerate(conds)
    }
    raw = paired_bootstrap(y, sd, groups=groups, n_boot=n_boot, seed=seed)
    return {c: raw[f"delta__lvl{i}__T1"] for i, c in enumerate(conds)}


def _fmt_ci(ci) -> str:
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci and ci[0] is not None else "n/d"


def _plot_v2norm(path: Path, metrics: Mapping, conds: Sequence[str]) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    labels = {"T0": "T0\n(original)", "T1": "T1\n(renombrar identif.)", "T5": "T5\n(código muerto)", "T7@1.0": "T7@1.0\n(combinado)"}
    series = [("v2", "v2 (GraphCodeBERT)", "#d62728"), ("v2_norm", "v2_norm (renombrado canónico)", "#2ca02c"), ("jaccard", "Jaccard (referencia)", "#1f77b4")]
    fig = Figure(figsize=(8, 4.8), dpi=130)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(1, 1, 1)
    width = 0.26
    x = np.arange(len(conds))
    for k, (m, name, color) in enumerate(series):
        vals, lo, hi = [], [], []
        for c in conds:
            v, ci = _auc_of(metrics, c, m)
            vals.append(v if v is not None else 0.0)
            lo.append(v - ci[0] if v is not None and ci and ci[0] is not None else 0.0)
            hi.append(ci[1] - v if v is not None and ci and ci[0] is not None else 0.0)
        ax.bar(x + (k - 1) * width, vals, width, yerr=[lo, hi], capsize=3, label=name, color=color, alpha=0.88)
    ax.set_xticks(x)
    ax.set_xticklabels([labels.get(c, c) for c in conds])
    ax.set_ylim(0.5, 1.0)
    ax.set_ylabel("ROC-AUC (vista: todos), IC95%")
    ax.set_title("Robustez de v2 con y sin renombrado canónico de identificadores")
    ax.grid(True, axis="y", linestyle=":", alpha=0.5)
    ax.legend(loc="lower left", framealpha=0.9, fontsize=8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    atomic_write_bytes(path, buf.getvalue())


def write_v2norm_outputs(
    run_dir: Path,
    config: Mapping,
    metrics: Mapping,
    contrasts: Mapping,
    levels: Mapping,
    sanity: Mapping,
    repro: Mapping,
    conds: Sequence[str],
) -> None:
    """report.md (Spanish), v2norm_robustez.png and a machine-readable verdict summary."""
    _plot_v2norm(run_dir / "v2norm_robustez.png", metrics, conds)

    def c(key):
        return contrasts.get(key, {})

    d_v2, d_nm = c("delta__v2__T1"), c("delta__v2_norm__T1")
    did = c("did__T1__v2__v2_norm")  # (v2 drop) - (v2_norm drop)
    primary_v = None if did.get("value") is None else -did["value"]
    pci = did.get("ci95")
    primary_ci = [-pci[1], -pci[0]] if pci and pci[0] is not None else None
    h1_ok = d_nm.get("value") is not None and abs(d_nm["value"]) < 0.01
    l0 = levels.get("T0", {})
    h2_ok = l0.get("value") is not None and abs(l0["value"]) < 0.02
    verdicts = {
        "primary_delta": {"value": primary_v, "ci95": primary_ci},
        "H1": {"v2_norm_drop_T1": d_nm.get("value"), "ci95": d_nm.get("ci95"), "confirmed": bool(h1_ok)},
        "H2": {"v2_norm_minus_v2_T0": l0.get("value"), "ci95": l0.get("ci95"), "confirmed": bool(h2_ok)},
        "H3": {k: {"value": levels[k].get("value"), "ci95": levels[k].get("ci95")} for k in levels if k in ("T5", "T7@1.0")},
    }
    write_json(run_dir / "verdicts.json", _plain(verdicts))
    write_json(run_dir / "sanity_t1.json", _plain(sanity))
    write_json(run_dir / "reproduction.json", _plain(repro))
    write_json(run_dir / "contrasts_levels.json", _plain(levels))

    L = [
        "# Robustez de v2 con renombrado canónico de identificadores (`v2_norm`)",
        "",
        f"- **Corrida:** `{config.get('run_id', run_dir.name)}`",
        f"- **Partición:** `{config.get('split')}` (manifiesto `{config.get('manifest_sha256')}`)",
        f"- **Semilla:** `{config.get('seed')}`; bootstrap estratificado por asignación; n_boot = {config.get('n_boot')} "
        f"(contrastes primarios) y {config.get('n_boot_secondary')} en las métricas por condición secundarias.",
        "- **Pregunta:** ¿el renombrado canónico elimina la vulnerabilidad de v2 al renombrado de identificadores (T1) y qué cuesta frente a las demás transformaciones?",
        "",
        "## 1. Verificación de reproducción",
        "",
        f"Se contrastó el ROC-AUC (vista `all`) de esta corrida con la corrida `{repro['reference_run']}` (tolerancia ±{repro['tolerance']}).",
        "",
        "| Método | Condición | Anterior | Actual | Diferencia | Resultado |",
        "|---|---|---|---|---|---|",
    ]
    for r in repro["rows"]:
        L.append(f"| {r['method']} | {r['condition']} | {r['reference']:.4f} | {r['new']:.4f} | {r['diff']:+.4f} | {'OK' if r['ok'] else 'FALLA'} |")
    L += ["", f"Reproducción: **{'exitosa' if repro['ok'] else 'fallida'}**.", "", "## 2. ROC-AUC por método y condición (vista `all`, IC95%)", ""]
    methods = [m for m in ("v2", "v2_norm", "jaccard") if m in config.get("methods", [])]
    L.append("| Condición | " + " | ".join(methods) + " |")
    L.append("|---|" + "---|" * len(methods))
    for cnd in conds:
        cells = []
        for m in methods:
            v, ci = _auc_of(metrics, cnd, m)
            cells.append("n/d" if v is None else f"{v:.3f} {_fmt_ci(ci)}")
        L.append(f"| `{cnd}` | " + " | ".join(cells) + " |")
    L += ["", "Cambio respecto de T0 (ΔAUC) con IC95% por bootstrap pareado:", "", "| Condición | " + " | ".join(methods) + " |", "|---|" + "---|" * len(methods)]
    for cnd in conds:
        if cnd == "T0":
            continue
        cells = []
        for m in methods:
            d = c(f"delta__{m}__{cnd}")
            cells.append("n/d" if d.get("value") is None else f"{d['value']:+.3f} {_fmt_ci(d.get('ci95'))}")
        L.append(f"| `{cnd}` | " + " | ".join(cells) + " |")
    L += [
        "", "## 3. Contraste primario y veredictos preregistrados", "",
        "Contraste primario: Δ = [AUC_v2_norm(T1) − AUC_v2_norm(T0)] − [AUC_v2(T1) − AUC_v2(T0)], es decir, la fracción de la caída de v2 por renombrado que v2_norm elimina.",
        "",
    ]
    if primary_v is not None:
        L.append(f"**Δ = {primary_v:+.4f} {_fmt_ci(primary_ci)}** (caída de v2 en T1: {d_v2['value']:+.4f} {_fmt_ci(d_v2.get('ci95'))}; "
                 f"caída de v2_norm en T1: {d_nm['value']:+.4f} {_fmt_ci(d_nm.get('ci95'))}).")
    L += [
        "",
        "| Hipótesis | Enunciado (preregistro) | Estimación [IC95%] | Veredicto |",
        "|---|---|---|---|",
        f"| H1 | La caída de v2_norm en T1 es ≈ 0 (|ΔAUC_v2_norm(T1)| < 0,01) | {d_nm.get('value', float('nan')):+.4f} {_fmt_ci(d_nm.get('ci95'))} | **{'CONFIRMADA' if h1_ok else 'REFUTADA'}** |",
        f"| H2 | v2_norm en T0 está a menos de 0,02 de v2 en T0 | {l0.get('value', float('nan')):+.4f} {_fmt_ci(l0.get('ci95'))} | **{'CONFIRMADA' if h2_ok else 'REFUTADA'}** |",
    ]
    for k in ("T5", "T7@1.0"):
        lv = levels.get(k, {})
        if lv.get("value") is not None:
            L.append(f"| H3 (exploratoria) | v2_norm − v2 en {k}, sin expectativa previa | {lv['value']:+.4f} {_fmt_ci(lv.get('ci95'))} | Descriptivo |")
    L += [
        "", "Diferencia de nivel v2_norm − v2 por condición (bootstrap pareado, mismo remuestreo):", "",
        "| Condición | AUC_v2_norm − AUC_v2 [IC95%] |", "|---|---|",
    ]
    for k, lv in levels.items():
        if lv.get("value") is not None:
            L.append(f"| `{k}` | {lv['value']:+.4f} {_fmt_ci(lv.get('ci95'))} |")
    L += [
        "", "## 4. Verificación de sanidad: canon(T1(b)) = canon(b)", "",
        f"Sobre {sanity['n_sampled']} segundos archivos de pares positivos muestreados (semilla {config.get('seed')}), "
        f"la igualdad byte a byte se cumple en **{sanity['n_equal']}/{sanity['n_sampled']} ({sanity['fraction_equal']*100:.1f}%)**; "
        f"T1 modificó el archivo en {sanity['n_t1_applied']}/{sanity['n_sampled']} casos.",
        "",
    ]
    if sanity["mismatches"]:
        L += ["Discrepancias (primera línea que difiere):", "", "| Archivo | Lenguaje | Línea | Original canónico | T1 canónico |", "|---|---|---|---|---|"]
        for mm in sanity["mismatches"][:15]:
            a = (mm["canon_orig"] or "").strip().replace("|", "\\|")
            b = (mm["canon_t1"] or "").strip().replace("|", "\\|")
            L.append(f"| `{mm['id']}` | {mm['lang']} | {mm['line']} | `{a}` | `{b}` |")
        L.append("")
    L += [
        "## 5. Limitaciones", "",
        "- No se recalcula la TPR al umbral desplegado para v2_norm: no existe un umbral calibrado de v2_norm; solo se informa una métrica independiente del umbral (ROC-AUC).",
        "- La canonicalización se aplica después de la transformación y a ambos lados del par; no se evalúa un atacante que conozca la normalización.",
        "- Solo se evalúan T0, T1, T5 y T7@1.0; no se extrapola a T2, T3, T4 ni T6.",
        "- La transformación se aplica al segundo archivo de cada par y, como en la corrida previa, a todos los archivos del conjunto de prueba; hay pocos positivos (n_pos ≈ 338), por lo que los IC son amplios.",
        "",
        "## 6. Figura", "", "![ROC-AUC por condición](v2norm_robustez.png)", "",
    ]
    atomic_write_bytes(run_dir / "report.md", "\n".join(L).encode("utf-8"))

# --- Main Pipeline ------------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    argv_list = list(sys.argv[1:] if argv is None else argv)

    # 1. Split validation & confirmation gate
    if args.split == "test" and not args.confirm_test:
        print("ERROR: evaluating on 'test' requires explicit --confirm-test flag", file=sys.stderr)
        return REFUSED_EXIT

    try:
        adapters = parse_adapter_specs(args.adapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return REFUSED_EXIT
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    for m in methods:
        if m not in ALL_METHODS and m not in adapters:
            print(f"ERROR: unknown method {m!r} (must be among {ALL_METHODS} or a --adapter name)", file=sys.stderr)
            return REFUSED_EXIT

    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    if "T0" not in conditions:
        conditions = ["T0"] + conditions

    # Load resume config upfront if resuming
    resume_config = None
    if args.resume:
        resume_dir = Path(args.resume)
        if not resume_dir.is_dir():
            print(f"ERROR: resume directory {resume_dir} does not exist", file=sys.stderr)
            return REFUSED_EXIT
        config_path = resume_dir / "config.json"
        if not config_path.is_file():
            print(f"ERROR: config.json not found in {resume_dir}", file=sys.stderr)
            return REFUSED_EXIT
        resume_config = json.loads(config_path.read_text(encoding="utf-8"))
        if resume_config.get("manifest_sha256") and args.expected_sha256:
            if resume_config["manifest_sha256"] != args.expected_sha256:
                print("ERROR: resume manifest_sha256 does not match current manifest", file=sys.stderr)
                return REFUSED_EXIT
        cfg_inner = resume_config.get("config", resume_config)
        if "split" in cfg_inner and not any(arg.startswith("--split") for arg in argv_list):
            args.split = cfg_inner["split"]
        if "methods" in cfg_inner and not any(arg.startswith("--methods") for arg in argv_list):
            methods = cfg_inner["methods"]
        if "conditions" in cfg_inner and not any(arg.startswith("--conditions") for arg in argv_list):
            conditions = cfg_inner["conditions"]
        if "seed" in cfg_inner and not any(arg.startswith("--seed") for arg in argv_list):
            args.seed = cfg_inner["seed"]
        if "n_boot" in cfg_inner and not any(arg.startswith("--n-boot") for arg in argv_list):
            args.n_boot = cfg_inner["n_boot"]
        if "n_boot_secondary" in cfg_inner and not any(arg.startswith("--n-boot-secondary") for arg in argv_list):
            args.n_boot_secondary = cfg_inner["n_boot_secondary"]
        if "limit_assignments" in cfg_inner and args.limit_assignments is None and not any(arg.startswith("--limit-assignments") for arg in argv_list):
            args.limit_assignments = cfg_inner["limit_assignments"]
        elif args.limit_assignments is None and not any(arg.startswith("--limit-assignments") for arg in argv_list):
            if "limit_assignments" in resume_config:
                args.limit_assignments = resume_config["limit_assignments"]
            elif "argv" in resume_config and isinstance(resume_config["argv"], list):
                r_argv = resume_config["argv"]
                if "--limit-assignments" in r_argv:
                    idx = r_argv.index("--limit-assignments")
                    if idx + 1 < len(r_argv):
                        try:
                            args.limit_assignments = int(r_argv[idx + 1])
                        except ValueError:
                            pass

    # 2. Load manifest & dataset pairs
    try:
        manifest = load_manifest(args.manifest, expected_sha256=args.expected_sha256)
    except (ManifestError, OSError) as exc:
        print(f"ERROR loading manifest: {exc}", file=sys.stderr)
        return REFUSED_EXIT

    _log(f"Manifest verified: sha256={manifest.sha256}")
    ep = EvalPairs.from_manifest(manifest, args.split, limit_assignments=args.limit_assignments)
    _log(f"Loaded {len(ep.samples)} samples across {len(ep.blocks)} assignments for split {args.split}")

    files = load_files(Path(args.root), ep.samples)

    # 3. Load operating points & calibration
    deploy_cal = Path(args.deploy_calibration)
    jaccard_cal = load_calibration(deploy_cal) if deploy_cal.is_file() else None

    source_run = Path(args.source_run)
    thresholds_val_path = source_run / "thresholds_val.json"
    selection_path = source_run / "selection.json"

    val_thresholds: Dict[str, float] = {}
    poolings: Dict[str, str] = {}
    if thresholds_val_path.is_file():
        t_data = json.loads(thresholds_val_path.read_text(encoding="utf-8"))
        for m, m_info in t_data.get("methods", {}).items():
            primary = m_info.get("primary", "fpr_0.05")
            th = m_info.get("thresholds", {}).get(primary, {}).get("threshold")
            if th is not None:
                val_thresholds[m] = float(th)

    if selection_path.is_file():
        s_data = json.loads(selection_path.read_text(encoding="utf-8"))
        for m, m_info in s_data.get("methods", {}).items():
            if m_info.get("pooling"):
                poolings[m] = m_info["pooling"]
    # Defaults
    poolings.setdefault("v2", "mean")
    poolings.setdefault("v2_nodfg", "mean")
    poolings.setdefault("legacy", "cls")
    poolings.setdefault("v2_norm", poolings["v2"])
    for m in methods:
        if is_adapter_method(m):
            poolings[m] = "mean"  # the adapters were trained and selected with mean pooling

    # 4. Prepare Embedders if neural methods selected
    embedding_methods_active = [m for m in methods if m in EMBEDDING_METHODS or is_adapter_method(m)]
    embedders, statuses = {}, {}
    device = resolve_device(args.device) if embedding_methods_active else "cpu"
    if embedding_methods_active:
        embedders, statuses = load_embedders(
            sorted({EMBEDDER_ALIAS.get(m, m) for m in embedding_methods_active if not is_adapter_method(m)}),
            model_name=DEFAULT_MODEL,
            local_files_only=args.local_files_only,
            device=device,
            batch_size=args.batch_size,
        )
        for m_alias, m_base in EMBEDDER_ALIAS.items():
            if m_alias in embedding_methods_active:
                embedders[m_alias] = embedders[m_base]
        adapter_shas: Dict[str, str] = {}
        for m in embedding_methods_active:
            if is_adapter_method(m):
                adapter_shas[m] = adapter_sha256(adapters[m])
                embedders[m] = AdapterFileEmbedder(
                    build_embedder(adapters[m], device=device, batch_size=args.batch_size, local_files_only=args.local_files_only),
                    adapter_shas[m],
                )
                _log(f"Adapter {m}: {adapters[m]} sha256={adapter_shas[m][:16]}")

    # 5. Initialize or Resume Run Context
    cache_root = Path(args.cache_dir)
    if resume_config is not None:
        run_dir = Path(args.resume)
        run_config = resume_config
    else:
        run_config = {
            "channel": CHANNEL,
            "split": args.split,
            "mode": "robustness",
            "seed": args.seed,
            "n_boot": args.n_boot,
            "n_boot_secondary": args.n_boot_secondary,
            "methods": methods,
            "adapters": {m: {"path": str(p), "sha256": adapter_sha256(p)} for m, p in adapters.items() if m in methods},
            "conditions": conditions,
            "poolings": poolings,
            "val_thresholds": val_thresholds,
            "limit_assignments": args.limit_assignments,
            "manifest_sha256": manifest.sha256,
            "deploy_calibration_sha256": jaccard_cal.sha256 if jaccard_cal else None,
            "versions": package_versions(VERSION_PACKAGES),
            "device": str(device),
        }
        ctx = RunContext.create(
            CHANNEL,
            seed=args.seed,
            split=args.split,
            mode="robustness",
            manifest_path=args.manifest,
            manifest_sha256=manifest.sha256,
            calibration_path=args.deploy_calibration if jaccard_cal else None,
            config=_plain(run_config),
            argv=argv_list,
            root=args.runs_root,
            run_dir=args.run_dir,
        )
        run_dir = ctx.path
        set_run_status(run_dir, STATUS_RUNNING)

    _log(f"Run directory: {run_dir}")
    scores_dir = run_dir / "scores"
    plots_dir = run_dir / "plots"
    scores_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    # 6. STAGE: Transform
    transforms_jl_path = run_dir / "transforms.jsonl"
    transform_summary_path = run_dir / "transform_summary.json"

    # Map: (sample_id, cond) -> transformed_record
    transformed_records: Dict[Tuple[str, str], Dict[str, Any]] = {}
    if transforms_jl_path.is_file() and args.stage != "transform":
        _log(f"Reading existing transformations from {transforms_jl_path}")
        with open(transforms_jl_path, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                transformed_records[(rec["id"], rec["condition"])] = rec

    tasks_to_run = []
    for cond in conditions:
        for s in ep.samples:
            if (s.id, cond) not in transformed_records:
                tasks_to_run.append((s.id, files[s.id].text, s.lang, cond, args.seed, args.skip_validity))

    if tasks_to_run:
        _log(f"Applying {len(tasks_to_run)} transformations across {len(conditions)} conditions...")
        t0_trans = time.perf_counter()
        # Run transformations in thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as executor:
            futures = [executor.submit(_transform_one_file, *t) for t in tasks_to_run]
            for fut in concurrent.futures.as_completed(futures):
                rec = fut.result()
                transformed_records[(rec["id"], rec["condition"])] = rec
        _log(f"Transformations finished in {time.perf_counter() - t0_trans:.1f}s")

        # Write transforms.jsonl
        with open(transforms_jl_path, "w", encoding="utf-8") as f:
            for cond in conditions:
                for s in ep.samples:
                    rec = transformed_records[(s.id, cond)]
                    # Omit code_out in jsonl to keep line compact
                    out_rec = {k: v for k, v in rec.items() if k != "code_out"}
                    f.write(json.dumps(out_rec) + "\n")

    # Generate transform_summary.json
    summary_by_cond: Dict[str, Dict[str, Any]] = {}
    for cond in conditions:
        recs = [transformed_records[(s.id, cond)] for s in ep.samples]
        n_files = len(recs)
        n_applied = sum(r["n_applied"] > 0 for r in recs)
        p_ok = sum(bool(r["parse_ok"]) for r in recs) / n_files if n_files else 1.0
        c_recs = [r["compile_ok"] for r in recs if r["compile_ok"] is not None]
        c_ok = (sum(c_recs) / len(c_recs)) if c_recs else None
        m_tok = float(np.mean([r["edit_tokens"] for r in recs])) if recs else 0.0
        m_abs = float(np.mean([r["edit_abstract"] for r in recs])) if recs else 0.0
        summary_by_cond[cond] = {
            "n_files": n_files,
            "n_applied_gt_0": n_applied,
            "parse_ok_rate": p_ok,
            "compile_ok_rate": c_ok,
            "mean_edit_tokens": m_tok,
            "mean_edit_abstract": m_abs,
        }
    write_json(transform_summary_path, {"conditions": summary_by_cond})

    if args.stage == "transform":
        set_run_status(run_dir, STATUS_COMPLETE)
        _log("Stage 'transform' complete.")
        return 0

    # 7. STAGE: Embeddings & Sets
    cached_embedders: Dict[str, CachedEmbedder] = {}
    for m in embedding_methods_active:
        cached_embedders[m] = CachedEmbedder(embedders[m], EmbeddingCache(cache_root, embedders[m].key_fields()))

    if args.prefill_shard:
        # Cache warm-up for one shard of the unique texts (run several shards in parallel processes).
        k_s, n_s = (int(x) for x in args.prefill_shard.split("/"))
        todo: Dict[str, Tuple[str, str, str]] = {}
        for i_s, s in enumerate(ep.samples):
            if i_s % n_s != k_s:
                continue
            orig_txt = files[s.id].text
            for m in embedding_methods_active:
                for cond in conditions:
                    r = transformed_records[(s.id, cond)]
                    t_txt = r["code_out"] if "code_out" in r else orig_txt
                    o_t, t_t = texts_for_method(m, [orig_txt], [t_txt], [s.lang])
                    for txt in (o_t[0], t_t[0]):
                        sh = hashlib.sha256(txt.encode("utf-8")).hexdigest()
                        todo[f"{m}:{sh}"] = (m, txt, s.lang)
        _log(f"Prefill shard {k_s}/{n_s}: {len(todo)} unique texts")
        for i, (key, (m, txt, lg)) in enumerate(todo.items()):
            cached_embedders[m].embed(key.split(":", 1)[1] if _text_keyed(m) else hashlib.sha256(txt.encode("utf-8")).hexdigest(), txt, lg)
            if i % 100 == 0:
                _log(f"  prefill {i}/{len(todo)}")
        _log("Prefill shard done.")
        return 0
    # 8. STAGE: Scoring
    # Store scores: scores_matrix[cond][method] -> 1D array of pair scores
    scores_by_cond_method: Dict[str, Dict[str, np.ndarray]] = {c: {} for c in conditions}

    # Original sets / embeddings for orig side
    orig_records = [files[s.id] for s in ep.samples]
    orig_lexical = {m: [LEXICAL_FNS[m](r.text) for r in orig_records] for m in methods if m in LEXICAL_METHODS}

    orig_embeddings: Dict[str, np.ndarray] = {}
    for m in embedding_methods_active:
        pool = poolings[m]
        cached = cached_embedders[m]
        o_texts, _ = texts_for_method(m, [r.text for r in orig_records], [r.text for r in orig_records], [r.lang for r in orig_records])
        if _text_keyed(m):
            o_shas = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in o_texts]
        else:
            o_shas = [r.sha256 for r in orig_records]
        entries = [cached.embed(sh, t, r.lang) for sh, t, r in zip(o_shas, o_texts, orig_records)]
        stacked, _ = stack_embeddings(entries, pool)
        orig_embeddings[m] = stacked

    for cond in conditions:
        _log(f"Scoring condition {cond}...")
        # Check if all scores for this condition are already cached
        if args.stage != "score" and all((scores_dir / f"{cond}__{m}.npz").is_file() for m in methods):
            for m in methods:
                data = np.load(scores_dir / f"{cond}__{m}.npz")
                scores_by_cond_method[cond][m] = data["scores"]
            continue

        trans_records = [transformed_records[(s.id, cond)] for s in ep.samples]
        # Transformed texts
        trans_texts = []
        for s, r in zip(ep.samples, trans_records):
            if "code_out" in r:
                trans_texts.append(r["code_out"])
            elif cond == "T0":
                trans_texts.append(files[s.id].text)
            else:
                t_seed = derive_seed(args.seed, r["sha256_in"], cond, 1.0)
                trans_texts.append(apply_condition(files[s.id].text, s.lang, cond, seed=t_seed).code)

        for m in methods:
            score_file = scores_dir / f"{cond}__{m}.npz"
            if score_file.is_file() and args.stage != "score":
                data = np.load(score_file)
                scores_by_cond_method[cond][m] = data["scores"]
                continue

            if m in LEXICAL_METHODS:
                fn = LEXICAL_FNS[m]
                trans_sets = [fn(t) for t in trans_texts]
                sim_fn = CrossSetSimilarity(orig_lexical[m], trans_sets)
            else:
                pool = poolings[m]
                cached = cached_embedders[m]
                _, m_texts = texts_for_method(
                    m, [files[s.id].text for s in ep.samples], trans_texts, [s.lang for s in ep.samples]
                )
                if _text_keyed(m):
                    m_shas = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in m_texts]
                else:
                    m_shas = [r["sha256_out"] for r in trans_records]
                entries = [
                    cached.embed(sh, t, s.lang)
                    for s, sh, t in zip(ep.samples, m_shas, m_texts)
                ]
                trans_stacked, _ = stack_embeddings(entries, pool)
                sim_fn = cross_embedding_similarity(orig_embeddings[m], trans_stacked)

            scored = score_pairs(sim_fn, ep, views=("all", "no_identical"))
            scores_by_cond_method[cond][m] = scored.scores
            np.savez_compressed(
                score_file,
                scores=scored.scores,
                pairs_a=ep.pairs.a,
                pairs_b=ep.pairs.b,
                label=ep.pairs.label,
            )

    y_all = ep.pairs.label.astype(np.int64)
    assignments = ep.assignments
    mask_all = ep.view_mask("all")

    metrics_path = run_dir / "metrics.json"
    contrasts_path = run_dir / "contrasts.json"
    if args.stage == "report" and metrics_path.is_file() and contrasts_path.is_file():
        _log("Loading existing metrics.json and contrasts.json for stage 'report'...")
        metrics_doc = json.loads(metrics_path.read_text(encoding="utf-8"))
        contrasts_doc = json.loads(contrasts_path.read_text(encoding="utf-8"))
    else:
        # 9. STAGE: Compute Metrics & Bootstrap
        _log("Computing metrics and bootstrap confidence intervals...")

        metrics_partial_path = run_dir / "metrics_partial.json"
        metrics_doc: Dict[str, Any] = {}
        if metrics_partial_path.is_file():
            try:
                metrics_doc = json.loads(metrics_partial_path.read_text(encoding="utf-8"))
                n_res = sum(len(v) for v in metrics_doc.values() if isinstance(v, dict))
                _log(f"Resumed {n_res} completed condition-method entries from metrics_partial.json")
            except Exception:
                metrics_doc = {}

        tasks = []
        masks = {"all": ep.view_mask("all"), "no_identical": ep.view_mask("no_identical")}
        j_cal_str = str(deploy_cal) if jaccard_cal is not None else None

        for cond in conditions:
            metrics_doc.setdefault(cond, {})
            n_boot_cond = args.n_boot if cond in ("T0", "T1", "T3", "T7@1.0") else min(args.n_boot, args.n_boot_secondary)
            for m in methods:
                if m in metrics_doc[cond]:
                    continue  # already computed!
                score_file = scores_dir / f"{cond}__{m}.npz"
                val_th = val_thresholds.get(m)
                tasks.append((
                    cond, m, str(score_file), y_all, assignments, masks,
                    n_boot_cond, args.seed, args.split, val_th, j_cal_str
                ))

        if tasks:
            _log(f"Computing metrics for {len(tasks)} tasks across parallel processes...")
            n_workers = min(10, os.cpu_count() or 4)
            with concurrent.futures.ProcessPoolExecutor(max_workers=n_workers) as executor:
                futures = {executor.submit(_compute_single_method_views, *t): (t[0], t[1]) for t in tasks}
                for fut in concurrent.futures.as_completed(futures):
                    cond_res, m_res, views_res = fut.result()
                    metrics_doc[cond_res][m_res] = {"views": views_res}
                    _log(f"Completed metrics: condition={cond_res}, method={m_res}")
                    metrics_partial_path.write_text(json.dumps(_plain(metrics_doc), indent=2), encoding="utf-8")

        # 10. STAGE: Paired Bootstrap Contrasts (H1, H2, H3, deltas)
        _log("Computing paired bootstrap contrasts...")
        # Mask view all
        mask_all = ep.view_mask("all")
        y_sub = y_all[mask_all]
        grp_sub = assignments[mask_all]

        scores_for_boot: Dict[Tuple[str, str], np.ndarray] = {}
        for c in conditions:
            for m in methods:
                scores_for_boot[(m, c)] = scores_by_cond_method[c][m][mask_all]

        contrasts_doc = paired_bootstrap(
            y_sub,
            scores_for_boot,
            groups=grp_sub,
            n_boot=args.n_boot,
            seed=args.seed,
        )

        write_json(metrics_path, _plain(metrics_doc))
        write_json(contrasts_path, _plain(contrasts_doc))

    # 11. STAGE: Plots & Report
    _log("Generating plots...")
    _plot_degradation(plots_dir / "degradation_curve.png", metrics_doc, methods)
    _plot_delta_by_transform(plots_dir / "delta_by_transform.png", contrasts_doc, methods)

    pos_mask = (y_all == 1) & mask_all
    if "T7@1.0" in conditions:
        _plot_positive_drop(
            plots_dir / "positive_drop.png",
            scores_by_cond_method["T0"],
            scores_by_cond_method["T7@1.0"],
            pos_mask,
            methods,
        )

    _log("Writing Markdown report...")
    report_content = _generate_report_markdown(
        run_config,
        summary_by_cond,
        metrics_doc,
        contrasts_doc,
        methods,
        conditions,
    )
    if "v2_norm" in methods and "v2" in methods and "T1" in conditions:
        generic = run_dir / "report_generic.md"
        atomic_write_bytes(generic, report_content.encode("utf-8"))
        ref_run = Path(args.reference_run)
        if not ref_run.is_absolute():
            ref_run = Path(args.root) / ref_run
        repro = v2norm_reproduction_check(metrics_doc, ref_run)
        _log(f"Reproduction check ok={repro['ok']}")
        sanity = v2norm_sanity_check(ep, files, transformed_records, args.seed)
        _log(f"Sanity canon(T1(b))==canon(b): {sanity['n_equal']}/{sanity['n_sampled']}")
        lvl_conds = [x for x in ("T0", "T1", "T5", "T7@1.0") if x in conditions]
        lvl_path = run_dir / "contrasts_levels.json"
        if lvl_path.is_file():
            levels = json.loads(lvl_path.read_text(encoding="utf-8"))
        else:
            levels = v2norm_level_contrasts(
                y_all[mask_all], scores_by_cond_method, mask_all, assignments[mask_all], lvl_conds, args.n_boot, args.seed
            )
        write_v2norm_outputs(run_dir, run_config, metrics_doc, contrasts_doc, levels, sanity, repro, lvl_conds)
    else:
        atomic_write_bytes(run_dir / "report.md", report_content.encode("utf-8"))
    set_run_status(run_dir, STATUS_COMPLETE)
    _log(f"Experiment completed successfully! Artifacts written to {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

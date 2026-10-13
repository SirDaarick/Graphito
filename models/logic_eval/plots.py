"""Plotting functions for logic grouping evaluation (G1 to G5)."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.manifold import TSNE


def plot_g1_heatmap(
    sim_matrices: Dict[str, np.ndarray],
    labels: Sequence[str],
    out_path: Path,
    max_items: int = 250,
) -> None:
    """G1: Heatmap of cosine similarities ordered by assignment blocks."""
    labels_arr = np.array(labels)
    # Sort indices by assignment label
    order = np.argsort(labels_arr, kind="stable")
    if len(order) > max_items:
        order = order[:max_items]

    sorted_labels = labels_arr[order]
    methods = list(sim_matrices.keys())
    n_methods = len(methods)
    if n_methods == 0:
        return

    fig, axes = plt.subplots(1, n_methods, figsize=(5 * n_methods, 4.5), squeeze=False)
    # Find boundary indices where label changes
    change_indices = np.flatnonzero(sorted_labels[:-1] != sorted_labels[1:]) + 1

    for idx, method in enumerate(methods):
        ax = axes[0, idx]
        sim = sim_matrices[method]
        sub_sim = sim[np.ix_(order, order)]

        im = ax.imshow(sub_sim, cmap="viridis", vmin=0.0, vmax=1.0, origin="upper")
        ax.set_title(f"Similarity: {method}")
        ax.set_xlabel("Solutions (grouped by assignment)")
        if idx == 0:
            ax.set_ylabel("Solutions (grouped by assignment)")

        for ci in change_indices:
            ax.axhline(ci - 0.5, color="white", linewidth=0.6, alpha=0.7)
            ax.axvline(ci - 0.5, color="white", linewidth=0.6, alpha=0.7)

    fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.7, label="Cosine Similarity")
    plt.suptitle("G1: Similarity Heatmap Ordered by Assignment", fontsize=13)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_g2_projection(
    embeddings_by_method: Dict[str, np.ndarray],
    labels: Sequence[str],
    out_path: Path,
    reference_mask: Optional[np.ndarray] = None,
    seed: int = 42,
) -> None:
    """G2: 2D t-SNE projection of embeddings (e.g. side-by-side v2 vs v2_norm)."""
    labels_arr = np.array(labels)
    unique_labels = sorted(set(labels_arr))
    color_map = {lbl: idx for idx, lbl in enumerate(unique_labels)}
    colors = [color_map[lbl] for lbl in labels_arr]

    methods = [m for m in embeddings_by_method if embeddings_by_method[m].ndim == 2]
    if len(methods) == 0:
        return

    n_methods = min(len(methods), 2)
    selected_methods = methods[:n_methods]
    fig, axes = plt.subplots(1, n_methods, figsize=(6 * n_methods, 5.5), squeeze=False)

    n_samples = len(labels_arr)
    perplexity = min(30, max(2, (n_samples - 1) // 3))

    cmap = plt.get_cmap("tab10" if len(unique_labels) <= 10 else "tab20")

    for idx, m in enumerate(selected_methods):
        ax = axes[0, idx]
        emb = embeddings_by_method[m]

        if emb.shape[0] < 4:
            ax.text(0.5, 0.5, "Too few samples for t-SNE", ha="center")
            continue

        tsne = TSNE(n_components=2, metric="cosine", perplexity=perplexity, random_state=seed, init="pca")
        proj = tsne.fit_transform(emb)

        scatter = ax.scatter(
            proj[:, 0],
            proj[:, 1],
            c=colors,
            cmap=cmap,
            alpha=0.7,
            s=25,
            edgecolors="none",
        )

        if reference_mask is not None and np.any(reference_mask):
            ref_idx = np.flatnonzero(reference_mask)
            ax.scatter(
                proj[ref_idx, 0],
                proj[ref_idx, 1],
                c="gold",
                marker="*",
                s=120,
                edgecolors="black",
                linewidths=0.8,
                label="Reference (E2)",
            )

        ax.set_title(f"t-SNE Projection: {m}")
        ax.set_xticks([])
        ax.set_yticks([])

    plt.suptitle("G2: 2D Projection of Program Embeddings", fontsize=13)
    fig.text(
        0.5,
        0.01,
        "Note: 2D projections distort distances; distances between clusters are not interpretable.\n"
        "Conclusions rely on MAP@R and Silhouette computed in original embedding space.",
        ha="center",
        fontsize=8,
        style="italic",
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_g3_map_at_r(
    metrics_by_method: Dict[str, Dict[str, Any]],
    random_baseline: float,
    out_path: Path,
) -> None:
    """G3: MAP@R bar chart by method with 95% confidence intervals."""
    methods = list(metrics_by_method.keys())
    if not methods:
        return

    values = []
    yerr_lower = []
    yerr_upper = []

    for m in methods:
        data = metrics_by_method[m]
        v = data.get("value") or 0.0
        values.append(v)
        ci = data.get("ci95")
        if ci and len(ci) == 2 and ci[0] is not None and ci[1] is not None:
            yerr_lower.append(max(0.0, v - ci[0]))
            yerr_upper.append(max(0.0, ci[1] - v))
        else:
            yerr_lower.append(0.0)
            yerr_upper.append(0.0)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x_pos = np.arange(len(methods))
    ax.bar(
        x_pos,
        values,
        yerr=[yerr_lower, yerr_upper],
        capsize=4,
        color="#3470a3",
        edgecolor="#1f4b70",
        alpha=0.85,
    )
    ax.axhline(
        random_baseline,
        color="crimson",
        linestyle="--",
        linewidth=1.5,
        label=f"Random baseline ({random_baseline:.3f})",
    )

    ax.set_xticks(x_pos)
    ax.set_xticklabels(methods, rotation=15, ha="right")
    ax.set_ylabel("MAP@R")
    ax.set_ylim(0.0, 1.05)
    ax.set_title("G3: MAP@R by Representation Method (E1-H1, E1-H2, E1-H3)")
    ax.legend(loc="upper left")
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_g4_correctness(
    correctness_data_by_method: Union[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]],
    out_path: Path,
) -> None:
    """G4: Similarity to reference grouped by test outcome (pass all / partial / fail all).

    Supports either a list of dicts (single method) or dict of method -> list of dicts.
    """
    if isinstance(correctness_data_by_method, list):
        data_dict = {"v2": correctness_data_by_method}
    else:
        data_dict = correctness_data_by_method

    methods_to_plot = [m for m in ["jaccard", "v2", "v2_norm"] if m in data_dict]
    if not methods_to_plot:
        methods_to_plot = list(data_dict.keys())[:3]

    n_panels = len(methods_to_plot)
    fig, axes = plt.subplots(1, n_panels, figsize=(5.5 * n_panels, 4.5), squeeze=False)
    rng = np.random.default_rng(42)

    for p_idx, method in enumerate(methods_to_plot):
        ax = axes[0, p_idx]
        items = data_dict.get(method, [])
        groups: Dict[str, List[float]] = {
            "Pass all (1.0)": [],
            "Partial (<1.0, >0)": [],
            "Fail all (0.0)": [],
        }
        for item in items:
            sim = item.get("sim_to_ref")
            rate = item.get("pass_rate")
            if sim is None or rate is None:
                continue
            if rate == 1.0:
                groups["Pass all (1.0)"].append(sim)
            elif rate == 0.0:
                groups["Fail all (0.0)"].append(sim)
            else:
                groups["Partial (<1.0, >0)"].append(sim)

        box_data = [groups["Pass all (1.0)"], groups["Partial (<1.0, >0)"], groups["Fail all (0.0)"]]
        labels = [
            f"Pass ({len(box_data[0])})",
            f"Partial ({len(box_data[1])})",
            f"Fail ({len(box_data[2])})",
        ]
        valid_boxes = [d if len(d) > 0 else [0.0] for d in box_data]
        try:
            ax.boxplot(valid_boxes, tick_labels=labels, patch_artist=True, boxprops=dict(facecolor="#c4d8e8"))
        except TypeError:
            ax.boxplot(valid_boxes, labels=labels, patch_artist=True, boxprops=dict(facecolor="#c4d8e8"))

        for idx, vals in enumerate(box_data):
            if vals:
                jitter = rng.uniform(-0.1, 0.1, size=len(vals))
                ax.scatter(np.ones(len(vals)) * (idx + 1) + jitter, vals, alpha=0.5, s=15, color="#1f4b70")

        ax.set_ylabel("Similarity to Reference Solution")
        ax.set_title(f"G4 ({method}): Outcome vs. Similarity")
        ax.grid(axis="y", linestyle=":", alpha=0.6)

    fig.suptitle("G4: Similarity to Reference by Unit Test Outcome (E2)", fontsize=13, y=1.02)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)



def plot_g5_teacher_view(
    ranked_submissions: List[Dict[str, Any]],
    assignment_name: str,
    out_path: Path,
    max_items: int = 35,
) -> None:
    """G5: Ranked teacher view for an assignment ordered by similarity to reference."""
    if not ranked_submissions:
        return

    items = ranked_submissions[:max_items]
    fig, ax = plt.subplots(figsize=(8, max(4.0, len(items) * 0.25)))

    sims = [it["sim"] for it in items]
    pass_flags = [it.get("pasa", False) for it in items]
    colors = ["#2ca02c" if p else "#d62728" for p in pass_flags]
    labels = [f"{it.get('student', it.get('id', 'sub'))} ({it.get('last_test_results', '')})" for it in items]

    y_pos = np.arange(len(items))
    ax.barh(y_pos, sims, color=colors, alpha=0.8, edgecolor="black", linewidth=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Similarity to Reference Solution")
    ax.set_xlim(0.0, 1.05)
    ax.set_title(f"G5: Teacher Inspection Ranking — {assignment_name}")
    ax.grid(axis="x", linestyle=":", alpha=0.6)

    # Custom legend
    import matplotlib.patches as mpatches
    green_patch = mpatches.Patch(color="#2ca02c", label="Passing")
    red_patch = mpatches.Patch(color="#d62728", label="Failing")
    ax.legend(handles=[green_patch, red_patch], loc="lower right")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

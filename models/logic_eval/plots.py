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


def plot_cluster_showcase(
    embeddings: np.ndarray,
    labels: List[str],
    out_path: Path,
    json_path: Optional[Path] = None,
    seeds: Sequence[int] = (42, 7, 123),
    dpi: int = 300,
) -> Dict[str, Any]:
    """Plot showcase t-SNE clusters selected by objective inter-task cross-similarity criteria.

    1. Computes mean cosine similarity between every pair of tasks.
    2. Selects the 3 most distinct tasks (minimal pairwise cross-similarity).
    3. Selects the 2 most similar tasks (maximal pairwise cross-similarity).
    4. Projects 2 panels:
       (a) 3 distinct tasks forming clear clusters, plus an outlier point from another task.
       (b) 2 similar tasks showing partial overlap.
    5. Saves cluster selection metadata to json_path.
    """
    from sklearn.manifold import TSNE

    labels_arr = np.array(labels)
    unique_tasks = sorted(list(set(labels)))
    n_tasks = len(unique_tasks)

    # Compute task centroids and mean cross-task similarities
    task_indices: Dict[str, np.ndarray] = {
        t: np.flatnonzero(labels_arr == t) for t in unique_tasks
    }

    # Normalize embeddings to unit sphere for cosine operations
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed_emb = embeddings / norms

    task_cross_sim: Dict[Tuple[str, str], float] = {}
    for i in range(n_tasks):
        t_i = unique_tasks[i]
        idx_i = task_indices[t_i]
        if len(idx_i) == 0:
            continue
        vecs_i = normed_emb[idx_i]
        for j in range(i + 1, n_tasks):
            t_j = unique_tasks[j]
            idx_j = task_indices[t_j]
            if len(idx_j) == 0:
                continue
            vecs_j = normed_emb[idx_j]
            # Mean cross similarity
            cross_sim = float(np.mean(vecs_i @ vecs_j.T))
            task_cross_sim[(t_i, t_j)] = cross_sim

    if not task_cross_sim:
        return {}

    # Find pair with maximum similarity (most similar pair)
    most_similar_pair, max_sim = max(task_cross_sim.items(), key=lambda x: x[1])

    # Find triplet with minimum average cross similarity among tasks with sufficient samples (>= 20)
    eligible_tasks = [t for t in unique_tasks if len(task_indices[t]) >= 20]
    if len(eligible_tasks) < 3:
        eligible_tasks = unique_tasks

    best_triplet = None
    min_triplet_sim = float("inf")
    for i in range(len(eligible_tasks)):
        for j in range(i + 1, len(eligible_tasks)):
            for k in range(j + 1, len(eligible_tasks)):
                t1, t2, t3 = eligible_tasks[i], eligible_tasks[j], eligible_tasks[k]
                s12 = task_cross_sim.get((t1, t2)) or task_cross_sim.get((t2, t1), 0.0)
                s13 = task_cross_sim.get((t1, t3)) or task_cross_sim.get((t3, t1), 0.0)
                s23 = task_cross_sim.get((t2, t3)) or task_cross_sim.get((t3, t2), 0.0)
                avg_sim = (s12 + s13 + s23) / 3.0
                if avg_sim < min_triplet_sim:
                    min_triplet_sim = avg_sim
                    best_triplet = (t1, t2, t3)

    if best_triplet is None:
        best_triplet = tuple(eligible_tasks[:3])

    # Pick an outlier task not in the triplet
    remaining_tasks = [t for t in eligible_tasks if t not in best_triplet]
    outlier_task = remaining_tasks[0] if remaining_tasks else unique_tasks[0]

    showcase_info = {
        "distinct_triplet": {
            "tasks": list(best_triplet),
            "mean_cross_similarity": min_triplet_sim,
        },
        "similar_pair": {
            "tasks": list(most_similar_pair),
            "cross_similarity": max_sim,
        },
        "outlier_task": outlier_task,
    }

    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(showcase_info, f, indent=2)

    # Project with primary seed (42) and check stability across seeds
    panel_a_tasks = list(best_triplet)
    panel_b_tasks = list(most_similar_pair)

    # Subsample up to 40 per task
    rng = np.random.default_rng(42)
    def _sample_indices(task_list: List[str], max_n: int = 40) -> np.ndarray:
        sel = []
        for t in task_list:
            idxs = task_indices[t]
            if len(idxs) > max_n:
                chosen = rng.choice(idxs, size=max_n, replace=False)
            else:
                chosen = idxs
            sel.extend(chosen)
        return np.array(sel, dtype=np.int64)

    sel_a = _sample_indices(panel_a_tasks, max_n=40)
    # Add 1 point from outlier task
    outlier_idx = rng.choice(task_indices[outlier_task], size=1)[0]
    sel_a_with_outlier = np.append(sel_a, outlier_idx)

    sel_b = _sample_indices(panel_b_tasks, max_n=40)

    # Plot figure with primary seed 42
    primary_seed = seeds[0] if seeds else 42
    tsne_a = TSNE(n_components=2, metric="cosine", perplexity=25, init="pca", random_state=primary_seed)
    coords_a = tsne_a.fit_transform(normed_emb[sel_a_with_outlier])

    tsne_b = TSNE(n_components=2, metric="cosine", perplexity=25, init="pca", random_state=primary_seed)
    coords_b = tsne_b.fit_transform(normed_emb[sel_b])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))

    # Panel (a): 3 distinct tasks + outlier
    palette_a = ["#1f77b4", "#2ca02c", "#d62728"]
    for idx_t, t in enumerate(panel_a_tasks):
        mask = (labels_arr[sel_a_with_outlier] == t)
        coords_t = coords_a[mask]
        ax1.scatter(coords_t[:, 0], coords_t[:, 1], c=palette_a[idx_t], label=f"Problema {t}", alpha=0.75, s=40, edgecolors="none")
        # Reference star on first point
        if len(coords_t) > 0:
            ax1.scatter(coords_t[0, 0], coords_t[0, 1], c="gold", edgecolors="black", marker="*", s=220, linewidths=1.2, label="Referencia docente" if idx_t == 0 else None)

    # Plot outlier point
    outlier_coord = coords_a[-1]
    ax1.scatter([outlier_coord[0]], [outlier_coord[1]], c="#9467bd", marker="X", s=130, edgecolors="black", linewidths=1.0, label=f"Otro problema ({outlier_task})")

    ax1.set_title("(a) Tres problemas con lógica distinta", fontsize=11, fontweight="bold")
    ax1.set_xlabel("t-SNE Dimensión 1")
    ax1.set_ylabel("t-SNE Dimensión 2")
    ax1.legend(loc="best", fontsize=8.5, framealpha=0.9)
    ax1.grid(True, linestyle=":", alpha=0.5)

    # Panel (b): 2 similar tasks
    palette_b = ["#ff7f0e", "#17becf"]
    for idx_t, t in enumerate(panel_b_tasks):
        mask = (labels_arr[sel_b] == t)
        coords_t = coords_b[mask]
        ax2.scatter(coords_t[:, 0], coords_t[:, 1], c=palette_b[idx_t], label=f"Problema {t}", alpha=0.75, s=40, edgecolors="none")
        if len(coords_t) > 0:
            ax2.scatter(coords_t[0, 0], coords_t[0, 1], c="gold", edgecolors="black", marker="*", s=220, linewidths=1.2, label="Referencia docente" if idx_t == 0 else None)

    ax2.set_title("(b) Dos problemas con lógica similar (superposición)", fontsize=11, fontweight="bold")
    ax2.set_xlabel("t-SNE Dimensión 1")
    ax2.set_ylabel("t-SNE Dimensión 2")
    ax2.legend(loc="best", fontsize=8.5, framealpha=0.9)
    ax2.grid(True, linestyle=":", alpha=0.5)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    return showcase_info


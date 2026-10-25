"""Plotting functions for logic grouping evaluation (G1 to G5)."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.manifold import TSNE


# Figure text per language. "en" is the default and must stay unchanged (run artifacts);
# "es" is used for the thesis document.
LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "g1_title": "Similarity: {method}",
        "g1_axis": "Solutions (grouped by assignment)",
        "g1_colorbar": "Cosine Similarity",
        "g1_suptitle": "G1: Similarity Heatmap Ordered by Assignment",
        "g2_too_few": "Too few samples for t-SNE",
        "g2_reference": "Reference (E2)",
        "g2_title": "t-SNE Projection: {method}",
        "g2_suptitle": "G2: 2D Projection of Program Embeddings",
        "g2_note": (
            "Note: 2D projections distort distances; distances between clusters are not interpretable.\n"
            "Conclusions rely on MAP@R and Silhouette computed in original embedding space."
        ),
        "g3_baseline": "Random baseline ({value:.3f})",
        "g3_title": "G3: MAP@R by Representation Method (E1-H1, E1-H2, E1-H3)",
        "g4_pass": "Pass ({n})",
        "g4_partial": "Partial ({n})",
        "g4_fail": "Fail ({n})",
        "sim_to_ref": "Similarity to Reference Solution",
        "g4_title": "G4 ({method}): Outcome vs. Similarity",
        "g4_suptitle": "G4: Similarity to Reference by Unit Test Outcome (E2)",
        "g5_title": "G5: Teacher Inspection Ranking — {assignment}",
        "g5_passing": "Passing",
        "g5_failing": "Failing",
    },
    "es": {
        "g1_title": "Similitud: {method}",
        "g1_axis": "Soluciones (agrupadas por tarea)",
        "g1_colorbar": "Similitud coseno",
        "g1_suptitle": "G1: Mapa de calor de similitud ordenado por tarea",
        "g2_too_few": "Muy pocas muestras para t-SNE",
        "g2_reference": "Referencia (E2)",
        "g2_title": "Proyección t-SNE: {method}",
        "g2_suptitle": "G2: Proyección 2D de los embeddings de programas",
        "g2_note": (
            "Nota: las proyecciones 2D distorsionan las distancias; las distancias entre grupos no son interpretables.\n"
            "Las conclusiones se basan en MAP@R y Silhouette calculados en el espacio original de los embeddings."
        ),
        "g3_baseline": "Línea base aleatoria ({value:.3f})",
        "g3_title": "G3: MAP@R por método de representación (E1-H1, E1-H2, E1-H3)",
        "g4_pass": "Pasa todas ({n})",
        "g4_partial": "Parcial ({n})",
        "g4_fail": "Falla todas ({n})",
        "sim_to_ref": "Similitud con la solución de referencia",
        "g4_title": "G4 ({method}): resultado vs. similitud",
        "g4_suptitle": "G4: Similitud con la referencia según el resultado de las pruebas unitarias (E2)",
        "g5_title": "G5: Ranking de inspección docente — {assignment}",
        "g5_passing": "Pasa las pruebas",
        "g5_failing": "No pasa las pruebas",
    },
}


def _t(lang: str, key: str, **fmt: Any) -> str:
    """Localized figure text; raises KeyError on an unknown language."""
    text = LABELS[lang][key]
    return text.format(**fmt) if fmt else text


def plot_g1_heatmap(
    sim_matrices: Dict[str, np.ndarray],
    labels: Sequence[str],
    out_path: Path,
    max_items: int = 250,
    lang: str = "en",
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
        ax.set_title(_t(lang, "g1_title", method=method))
        ax.set_xlabel(_t(lang, "g1_axis"))
        if idx == 0:
            ax.set_ylabel(_t(lang, "g1_axis"))

        for ci in change_indices:
            ax.axhline(ci - 0.5, color="white", linewidth=0.6, alpha=0.7)
            ax.axvline(ci - 0.5, color="white", linewidth=0.6, alpha=0.7)

    fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.7, label=_t(lang, "g1_colorbar"))
    plt.suptitle(_t(lang, "g1_suptitle"), fontsize=13)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_g2_projection(
    embeddings_by_method: Dict[str, np.ndarray],
    labels: Sequence[str],
    out_path: Path,
    reference_mask: Optional[np.ndarray] = None,
    seed: int = 42,
    lang: str = "en",
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
            ax.text(0.5, 0.5, _t(lang, "g2_too_few"), ha="center")
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
                label=_t(lang, "g2_reference"),
            )

        ax.set_title(_t(lang, "g2_title", method=m))
        ax.set_xticks([])
        ax.set_yticks([])

    plt.suptitle(_t(lang, "g2_suptitle"), fontsize=13)
    fig.text(
        0.5,
        0.01,
        _t(lang, "g2_note"),
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
    lang: str = "en",
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
        label=_t(lang, "g3_baseline", value=random_baseline),
    )

    ax.set_xticks(x_pos)
    ax.set_xticklabels(methods, rotation=15, ha="right")
    ax.set_ylabel("MAP@R")
    ax.set_ylim(0.0, 1.05)
    ax.set_title(_t(lang, "g3_title"))
    ax.legend(loc="upper left")
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_g4_correctness(
    correctness_data_by_method: Union[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]],
    out_path: Path,
    lang: str = "en",
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
            _t(lang, "g4_pass", n=len(box_data[0])),
            _t(lang, "g4_partial", n=len(box_data[1])),
            _t(lang, "g4_fail", n=len(box_data[2])),
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

        ax.set_ylabel(_t(lang, "sim_to_ref"))
        ax.set_title(_t(lang, "g4_title", method=method))
        ax.grid(axis="y", linestyle=":", alpha=0.6)

    fig.suptitle(_t(lang, "g4_suptitle"), fontsize=13, y=1.02)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)



def plot_g5_teacher_view(
    ranked_submissions: List[Dict[str, Any]],
    assignment_name: str,
    out_path: Path,
    max_items: int = 35,
    lang: str = "en",
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
    ax.set_xlabel(_t(lang, "sim_to_ref"))
    ax.set_xlim(0.0, 1.05)
    ax.set_title(_t(lang, "g5_title", assignment=assignment_name))
    ax.grid(axis="x", linestyle=":", alpha=0.6)

    # Custom legend
    import matplotlib.patches as mpatches
    green_patch = mpatches.Patch(color="#2ca02c", label=_t(lang, "g5_passing"))
    red_patch = mpatches.Patch(color="#d62728", label=_t(lang, "g5_failing"))
    ax.legend(handles=[green_patch, red_patch], loc="lower right")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)



EXTERNAL_RULE = (
    "Among E1 tasks not in panel (a), choose the task with the lowest mean cosine "
    "similarity (original v2 space) to the union of the panel (a) tasks; then choose "
    "the single solution of that task with the lowest mean similarity to that union. "
    "Ties are broken by task name and then by lowest index."
)


def select_external_point(
    sim: np.ndarray,
    labels: Sequence[str],
    panel_tasks: Sequence[str],
) -> Dict[str, Any]:
    """Objectively pick the 'external problem' point shown next to panel (a).

    Args:
        sim: Full (N, N) cosine similarity matrix in the original embedding space.
        labels: Task label per row of ``sim``.
        panel_tasks: Tasks drawn in panel (a); they are never eligible.

    Returns:
        Dict with the chosen ``task``, its ``mean_similarity_to_panel``, the chosen
        row ``index`` and that point's mean similarity (``point_mean_similarity``).
    """
    labels_arr = np.asarray(list(labels))
    panel_mask = np.isin(labels_arr, list(panel_tasks))
    panel_idx = np.flatnonzero(panel_mask)
    candidates = sorted(set(labels_arr[~panel_mask].tolist()))
    if len(panel_idx) == 0 or not candidates:
        raise ValueError("Need at least one panel task and one non-panel task.")

    best_task, best_score = None, float("inf")
    for task in candidates:  # sorted -> deterministic tie-break by name
        idx = np.flatnonzero(labels_arr == task)
        score = float(np.mean(sim[np.ix_(idx, panel_idx)]))
        if score < best_score:
            best_task, best_score = task, score

    idx = np.flatnonzero(labels_arr == best_task)
    per_point = np.asarray(sim[np.ix_(idx, panel_idx)]).mean(axis=1)
    best_pos = int(np.argmin(per_point))  # first minimum -> lowest index
    return {
        "task": str(best_task),
        "mean_similarity_to_panel": best_score,
        "index": int(idx[best_pos]),
        "point_mean_similarity": float(per_point[best_pos]),
    }


def plot_cluster_showcase(
    embeddings: np.ndarray,
    labels: List[str],
    out_path: Path,
    json_path: Optional[Path] = None,
    seeds: Sequence[int] = (42, 7, 123),
    dpi: int = 300,
    passing: Optional[Sequence[bool]] = None,
    fixed_selection: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Plot showcase t-SNE clusters selected by objective inter-task criteria.

    1. Computes mean cosine similarity between every pair of tasks.
    2. Selects the 3 most distinct tasks (minimal mean pairwise cross-similarity).
    3. Selects the 2 most similar tasks (maximal pairwise cross-similarity).
    4. Selects one external point with ``select_external_point`` (objective rule).
    5. Projects 2 panels with t-SNE (cosine, perplexity 30, PCA init, seed 42):
       (a) 3 distinct tasks plus the external point.
       (b) 2 similar tasks showing partial overlap.
    6. Saves selection metadata to json_path.

    ``passing`` optionally flags, per row, whether the solution passes its tests; the
    reference star of each task is the first sampled passing solution (fallback: the
    first sampled one, recorded in the metadata).

    ``fixed_selection`` (``panel_a_tasks``, ``panel_b_tasks``, ``external_index``) skips the
    objective selection and draws exactly those tasks and that external point, so a figure
    in another embedding space stays comparable with an earlier one; the similarity values
    stored in the metadata are then measured in the current space.
    """
    from matplotlib.lines import Line2D

    labels_arr = np.array(labels)
    unique_tasks = sorted(set(labels))
    n_tasks = len(unique_tasks)
    task_indices: Dict[str, np.ndarray] = {
        t: np.flatnonzero(labels_arr == t) for t in unique_tasks
    }

    # Unit-normalise: dot products are cosine similarities in the original space.
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed_emb = embeddings / norms
    full_sim = normed_emb @ normed_emb.T

    task_cross_sim: Dict[Tuple[str, str], float] = {}
    for i in range(n_tasks):
        idx_i = task_indices[unique_tasks[i]]
        for j in range(i + 1, n_tasks):
            idx_j = task_indices[unique_tasks[j]]
            if len(idx_i) == 0 or len(idx_j) == 0:
                continue
            task_cross_sim[(unique_tasks[i], unique_tasks[j])] = float(
                np.mean(full_sim[np.ix_(idx_i, idx_j)])
            )

    if not task_cross_sim:
        return {}

    most_similar_pair, max_sim = max(task_cross_sim.items(), key=lambda x: x[1])
    if fixed_selection is not None:
        most_similar_pair = tuple(fixed_selection["panel_b_tasks"])
        max_sim = task_cross_sim[tuple(sorted(most_similar_pair))]

    eligible_tasks = [t for t in unique_tasks if len(task_indices[t]) >= 20]
    if len(eligible_tasks) < 3:
        eligible_tasks = unique_tasks

    best_triplet = None
    min_triplet_sim = float("inf")
    for i in range(len(eligible_tasks)):
        for j in range(i + 1, len(eligible_tasks)):
            for k in range(j + 1, len(eligible_tasks)):
                t1, t2, t3 = eligible_tasks[i], eligible_tasks[j], eligible_tasks[k]
                s12 = task_cross_sim.get((t1, t2), 0.0)
                s13 = task_cross_sim.get((t1, t3), 0.0)
                s23 = task_cross_sim.get((t2, t3), 0.0)
                avg_sim = (s12 + s13 + s23) / 3.0
                if avg_sim < min_triplet_sim:
                    min_triplet_sim = avg_sim
                    best_triplet = (t1, t2, t3)
    if best_triplet is None:
        best_triplet = tuple(eligible_tasks[:3])

    if fixed_selection is not None:
        best_triplet = tuple(fixed_selection["panel_a_tasks"])
        a, b, c = best_triplet
        min_triplet_sim = float(np.mean([
            task_cross_sim[tuple(sorted(p))] for p in ((a, b), (a, c), (b, c))
        ]))

    panel_a_tasks = list(best_triplet)
    panel_b_tasks = list(most_similar_pair)

    external = select_external_point(full_sim, labels, panel_a_tasks)
    if fixed_selection is not None:
        ext_i = int(fixed_selection["external_index"])
        ext_task = str(labels_arr[ext_i])
        panel_idx = np.flatnonzero(np.isin(labels_arr, panel_a_tasks))
        ext_idx = np.flatnonzero(labels_arr == ext_task)
        external = {
            "task": ext_task,
            "mean_similarity_to_panel": float(np.mean(full_sim[np.ix_(ext_idx, panel_idx)])),
            "index": ext_i,
            "point_mean_similarity": float(np.mean(full_sim[ext_i, panel_idx])),
        }
    external_task = external["task"]
    external_idx = external["index"]

    # Subsample up to 40 per task (fixed seed, sorted for stable ordering).
    rng = np.random.default_rng(42)

    def _sample_indices(task_list: List[str], max_n: int = 40) -> np.ndarray:
        sel: List[int] = []
        for t in task_list:
            idxs = task_indices[t]
            if len(idxs) > max_n:
                idxs = np.sort(rng.choice(idxs, size=max_n, replace=False))
            sel.extend(int(v) for v in idxs)
        return np.array(sel, dtype=np.int64)

    sel_a = _sample_indices(panel_a_tasks)
    sel_a_with_ext = np.append(sel_a, external_idx)
    sel_b = _sample_indices(panel_b_tasks)

    passing_arr = None if passing is None else np.asarray(passing, dtype=bool)
    references: Dict[str, Dict[str, Any]] = {}

    def _reference_pos(sel: np.ndarray, task: str) -> int:
        """Position (within ``sel``) of the reference solution of ``task``."""
        positions = [p for p, gi in enumerate(sel) if labels_arr[gi] == task]
        verified = False
        chosen = positions[0]
        if passing_arr is not None:
            for p in positions:
                if passing_arr[sel[p]]:
                    chosen, verified = p, True
                    break
        references.setdefault(task, {"index": int(sel[chosen]), "verified_passing": verified})
        return chosen

    primary_seed = seeds[0] if seeds else 42

    def _tsne(x: np.ndarray) -> np.ndarray:
        return TSNE(
            n_components=2, metric="cosine", perplexity=30, init="pca",
            random_state=primary_seed,
        ).fit_transform(x)

    coords_a = _tsne(normed_emb[sel_a_with_ext])
    coords_b = _tsne(normed_emb[sel_b])

    star_size = 280
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))

    def _draw_panel(ax, sel, coords, tasks, palette, n_points):
        for idx_t, t in enumerate(tasks):
            mask = np.array([labels_arr[g] == t for g in sel[:n_points]])
            ct = coords[:n_points][mask]
            ax.scatter(ct[:, 0], ct[:, 1], c=palette[idx_t], label=f"Problema {t}",
                       alpha=0.75, s=40, edgecolors="none")
            rp = _reference_pos(sel[:n_points], t)
            ax.scatter(coords[rp, 0], coords[rp, 1], c=palette[idx_t], edgecolors="black",
                       marker="*", s=star_size, linewidths=1.4, zorder=5)

    palette_a = ["#1f77b4", "#2ca02c", "#d62728"]
    _draw_panel(ax1, sel_a_with_ext, coords_a, panel_a_tasks, palette_a, len(sel_a))
    ext_coord = coords_a[-1]
    ax1.scatter([ext_coord[0]], [ext_coord[1]], c="#9467bd", marker="X", s=130,
                edgecolors="black", linewidths=1.0, zorder=6,
                label=f"Problema externo ({external_task})")

    palette_b = ["#ff7f0e", "#17becf"]
    _draw_panel(ax2, sel_b, coords_b, panel_b_tasks, palette_b, len(sel_b))

    star_handle = Line2D([0], [0], marker="*", color="none", markerfacecolor="#cccccc",
                         markeredgecolor="black", markersize=14,
                         label="Solución de referencia (ejemplo de alumno)")
    for ax, title in (
        (ax1, "(a) Tres problemas con lógica distinta"),
        (ax2, "(b) Dos problemas con lógica similar (superposición)"),
    ):
        handles, lbls = ax.get_legend_handles_labels()
        ax.legend(handles + [star_handle], lbls + [star_handle.get_label()],
                  loc="best", fontsize=8.5, framealpha=0.9)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_xlabel("t-SNE Dimensión 1")
        ax.set_ylabel("t-SNE Dimensión 2")
        ax.grid(True, linestyle=":", alpha=0.5)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    showcase_info = {
        "distinct_triplet": {
            "tasks": panel_a_tasks,
            "mean_cross_similarity": min_triplet_sim,
        },
        "similar_pair": {
            "tasks": panel_b_tasks,
            "cross_similarity": max_sim,
        },
        "external_point": {
            "rule": EXTERNAL_RULE,
            "task": external_task,
            "mean_similarity_to_panel_a": external["mean_similarity_to_panel"],
            "solution_index": external_idx,
            "solution_mean_similarity_to_panel_a": external["point_mean_similarity"],
        },
        "reference_solutions": references,
        "tsne": {"metric": "cosine", "perplexity": 30, "init": "pca", "random_state": primary_seed},
    }
    if fixed_selection is not None:
        showcase_info["selection"] = "reused"
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(showcase_info, f, indent=2)
    return showcase_info

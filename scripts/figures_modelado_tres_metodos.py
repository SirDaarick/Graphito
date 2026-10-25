"""Thesis figures that compare Jaccard, zero-shot `v2_norm` and the contrastive adapter B_s1 on ESCOM.

Two stages, so the drawing never needs a GPU:

    python scripts/figures_modelado_tres_metodos.py compute --work DIR   # embeds E1/E2 files, checks the numbers
    python scripts/figures_modelado_tres_metodos.py draw --work DIR      # writes the Spanish PNGs

`compute` refuses to continue when MAP@R (E1) or the per-assignment AUC (E2) differ from the frozen F4
results in `runs/contrastivo_codenet/f4/`, so the figures can only show numbers that were already reported.
The robustness figures read `runs/contrastivo_codenet/f4/robustness_summary.json` directly.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

DATA_REPO = Path(r"C:\Users\edani\OneDrive\Documents\Proyectos\Graphito")  # holds the gitignored ESCOM data
ADAPTER = Path(r"C:\Users\edani\datasets\codenet\f3\B_s1\adapter")
F4 = ROOT / "runs" / "contrastivo_codenet" / "f4"
SHOWCASE = DATA_REPO.parent / "Graphito-worktrees" / "doc-v2norm" / "runs" / "logic_eval" / "20261013-152644" / "cluster_showcase_v2norm.json"
FIG_DIR = ROOT / "Documentacion" / "Documento" / "figuras"
SEED = 42
METHODS = ("jaccard", "v2_norm", "ft_B_s1")
NAMES = {"jaccard": "Jaccard (texto)", "v2_norm": "GraphCodeBERT sin ajuste (v2_norm)", "ft_B_s1": "GraphCodeBERT ajustado (modelo usado)"}
SHORT = {"jaccard": "Jaccard", "v2_norm": "v2_norm", "ft_B_s1": "Ajustado"}
COLORS = {"jaccard": "#555555", "v2_norm": "#D55E00", "ft_B_s1": "#0072B2"}
MARKERS = {"jaccard": "s", "v2_norm": "o", "ft_B_s1": "D"}


def compute(work: Path) -> None:
    import torch

    from f4_eval import cosine_matrix, embed_mean
    from models.graphcodebert.v2.adapter import build_embedder
    from models.graphcodebert.v2.baselines import SetSimilarity, jaccard_set
    from models.logic_eval.correctness import evaluate_assignment_leave_one_out
    from models.logic_eval.data import load_e1_sample, load_e2_stats, load_manifest_data
    from models.logic_eval.grouping import compute_map_at_r

    work.mkdir(parents=True, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    models = {"v2_norm": build_embedder(None, device=device), "ft_B_s1": build_embedder(ADAPTER, device=device)}
    frozen_e1 = json.loads((F4 / "e1.json").read_text(encoding="utf-8"))["methods"]
    frozen_e2 = json.loads((F4 / "e2.json").read_text(encoding="utf-8"))["methods"]

    sample = load_e1_sample(DATA_REPO / "data" / "splits" / "split_v1.json.gz", max_per_block=60, seed=SEED)
    codes = [(DATA_REPO / it["id"]).read_text(encoding="utf-8", errors="replace") for it in sample]
    langs = [it.get("lang", "c") for it in sample]
    labels = [it.get("block") or it.get("assignment") for it in sample]
    passing = [bool(it.get("pasa")) for it in sample]
    embs = {}
    sims = {"jaccard": SetSimilarity([jaccard_set(c) for c in codes])(0, len(codes))}
    for name, embedder in models.items():
        print(f"[E1] embedding with {name}", flush=True)
        embs[name] = embed_mean(embedder, codes, langs)
        sims[name] = cosine_matrix(embs[name])
    for name in METHODS:
        got, want = compute_map_at_r(sims[name], labels)["value"], frozen_e1[name]["map_at_r"]
        if abs(got - want) > 1e-6:
            raise SystemExit(f"E1 MAP@R of {name} is {got}, the frozen F4 result is {want}; refusing to draw")
        print(f"[E1] {name} MAP@R {got:.6f} reproduces F4", flush=True)
    np.savez_compressed(work / "e1.npz", labels=np.array(labels), v2_norm=embs["v2_norm"], ft_B_s1=embs["ft_B_s1"])
    (work / "e1_meta.json").write_text(json.dumps({"ids": [it["id"] for it in sample], "labels": labels}), encoding="utf-8")

    manifest = load_manifest_data(DATA_REPO / "data" / "splits" / "split_v1.json.gz")
    entries = [e for e in manifest.get("entries", []) if e.get("source") == "human" and not e.get("excluded", False)]
    qualified = load_e2_stats(entries, stats_dir=DATA_REPO / "data" / "raw" / "stats", min_pass=5, min_fail=3, seed=SEED)
    points: Dict[str, List[Dict[str, Any]]] = {m: [] for m in METHODS}
    for a_idx, assign in enumerate(sorted(qualified)):
        subs = qualified[assign]
        scodes = [(DATA_REPO / s["id"]).read_text(encoding="utf-8", errors="replace") for s in subs]
        slangs = [s.get("lang", "c") for s in subs]
        rates = [s["pass_rate"] for s in subs]
        print(f"[E2] {a_idx + 1}/{len(qualified)} {assign}: {len(subs)} submissions", flush=True)
        s_sims = {"jaccard": SetSimilarity([jaccard_set(c) for c in scodes])(0, len(scodes))}
        for name, embedder in models.items():
            s_sims[name] = cosine_matrix(embed_mean(embedder, scodes, slangs))
        for name in METHODS:
            auc = evaluate_assignment_leave_one_out(s_sims[name], rates, assignment_name=assign)["auc"]
            want = {r["assignment"]: r["auc"] for r in frozen_e2[name]["per_assignment"]}[assign]
            if (auc is None) != (want is None) or (auc is not None and abs(auc - want) > 2e-3):
                raise SystemExit(f"E2 AUC of {name} in {assign} is {auc}, the frozen F4 result is {want}; refusing to draw")
        pass_idxs = [i for i, r in enumerate(rates) if r == 1.0]
        if not pass_idxs:
            continue
        ref = pass_idxs[0]
        for name in METHODS:
            for idx, s in enumerate(subs):
                if idx != ref:
                    points[name].append({"assignment": assign, "pass_rate": s["pass_rate"], "sim_to_ref": float(s_sims[name][ref, idx])})
    (work / "e2_points.json").write_text(json.dumps(points), encoding="utf-8")
    print("compute done", flush=True)


def _style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "serif", "axes.spines.top": False, "axes.spines.right": False})
    return plt


def draw_e1(work: Path, plt) -> None:
    frozen = json.loads((F4 / "e1.json").read_text(encoding="utf-8"))["methods"]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for i, m in enumerate(METHODS):
        v, (lo, hi) = frozen[m]["map_at_r"], frozen[m]["ci95"]
        ax.bar(i, v, color=COLORS[m], width=0.6, yerr=[[v - lo], [hi - v]], capsize=5, error_kw={"lw": 1.5})
        ax.text(i, hi + 0.012, f"{v:.3f}", ha="center", fontsize=11)
    ax.axhline(0.002, color="crimson", ls="--", lw=1.2, label="Azar (0.002)")
    ax.set_xticks(range(3), [NAMES[m].replace(" (", "\n(") for m in METHODS], fontsize=9)
    ax.set_ylabel("MAP@R (IC 95 %)")
    ax.set_ylim(0, 0.6)
    ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "comparacion_map_at_r.png", dpi=200)
    plt.close(fig)


def draw_heatmap(work: Path, plt) -> None:
    from models.graphcodebert.v2.baselines import SetSimilarity, jaccard_set
    from f4_eval import cosine_matrix

    data = np.load(work / "e1.npz")
    meta = json.loads((work / "e1_meta.json").read_text(encoding="utf-8"))
    labels = np.array(meta["labels"])
    order = np.argsort(labels, kind="stable")
    sorted_labels = labels[order]
    bounds = np.flatnonzero(sorted_labels[:-1] != sorted_labels[1:]) + 1
    codes = [(DATA_REPO / i).read_text(encoding="utf-8", errors="replace") for i in meta["ids"]]
    sims = {
        "jaccard": SetSimilarity([jaccard_set(c) for c in codes])(0, len(codes)),
        "v2_norm": cosine_matrix(data["v2_norm"]),
        "ft_B_s1": cosine_matrix(data["ft_B_s1"]),
    }
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    for ax, m in zip(axes, METHODS):
        sim = sims[m][np.ix_(order, order)]
        im = ax.imshow(sim, cmap="viridis", interpolation="nearest", aspect="equal")
        for b in bounds:
            ax.axhline(b - 0.5, color="white", lw=0.2, alpha=0.5)
            ax.axvline(b - 0.5, color="white", lw=0.2, alpha=0.5)
        ax.set_title(NAMES[m], fontsize=11)
        ax.set_xlabel("Entregas ordenadas por tarea")
        ax.set_xticks([])
        ax.set_yticks([])
        cb = fig.colorbar(im, ax=ax, shrink=0.75, pad=0.02)
        cb.set_label("Similitud (escala propia de cada método)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "comparacion_mapa_calor.png", dpi=150)
    plt.close(fig)


def draw_correctness(work: Path, plt) -> None:
    points = json.loads((work / "e2_points.json").read_text(encoding="utf-8"))
    rng = np.random.default_rng(SEED)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    for ax, m in zip(axes, METHODS):
        groups = {"Pasa todas": [], "Parcial": [], "Falla todas": []}
        for p in points[m]:
            key = "Pasa todas" if p["pass_rate"] == 1.0 else "Falla todas" if p["pass_rate"] == 0.0 else "Parcial"
            groups[key].append(p["sim_to_ref"])
        data = list(groups.values())
        ax.boxplot(data, widths=0.5, showfliers=False, medianprops={"color": "black"}, boxprops={"color": COLORS[m]}, whiskerprops={"color": COLORS[m]}, capprops={"color": COLORS[m]})
        for i, vals in enumerate(data, start=1):
            ax.scatter(i + rng.uniform(-0.15, 0.15, len(vals)), vals, s=8, alpha=0.35, color=COLORS[m])
        ax.set_xticks(range(1, 4), [f"{k} ({len(v)})" for k, v in groups.items()])
        ax.set_title(NAMES[m], fontsize=11)
        ax.set_ylabel("Similitud con la solución de referencia")
        ax.grid(axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "comparacion_correccion.png", dpi=170)
    plt.close(fig)


def draw_clusters(work: Path) -> None:
    from logic_grouping_eval import passing_flags
    from models.logic_eval.data import load_e1_sample
    from models.logic_eval.plots import plot_cluster_showcase

    data = np.load(work / "e1.npz")
    meta = json.loads((work / "e1_meta.json").read_text(encoding="utf-8"))
    sample = load_e1_sample(DATA_REPO / "data" / "splits" / "split_v1.json.gz", max_per_block=60, seed=SEED)
    if [it["id"] for it in sample] != meta["ids"]:
        raise SystemExit("E1 sample changed since `compute`; rerun it")
    ref = json.loads(SHOWCASE.read_text(encoding="utf-8"))
    info = plot_cluster_showcase(
        embeddings=data["ft_B_s1"],
        labels=meta["labels"],
        out_path=FIG_DIR / "clusters_canal_a_ajustado.png",
        json_path=work / "cluster_showcase_ajustado.json",
        seeds=(42, 7, 123),
        dpi=300,
        passing=passing_flags(sample, DATA_REPO / "data" / "raw" / "stats"),
        fixed_selection={
            "panel_a_tasks": ref["distinct_triplet"]["tasks"],
            "panel_b_tasks": ref["similar_pair"]["tasks"],
            "external_index": ref["external_point"]["solution_index"],
        },
    )
    print(json.dumps(info, ensure_ascii=False)[:300])


CONDITIONS = ["T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7@0.25", "T7@0.5", "T7@1.0"]
COND_LABELS = {
    "T0": "Original", "T1": "T1 Renombrar\nidentificadores", "T2": "T2 for ↔ while", "T3": "T3 Reordenar\nsentencias",
    "T4": "T4 Operadores\nequivalentes", "T5": "T5 Código\nmuerto", "T6": "T6 Invertir\nif/else",
    "T7@0.25": "T7 combinado\n25 %", "T7@0.5": "T7 combinado\n50 %", "T7@1.0": "T7 combinado\n100 %",
}


def draw_robustness(plt) -> None:
    s = json.loads((F4 / "robustness_summary.json").read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(CONDITIONS))
    for m in METHODS:
        y = np.array([s["auc"][c][m] for c in CONDITIONS])
        lo = np.array([s["auc_ci95"][c][m][0] for c in CONDITIONS])
        hi = np.array([s["auc_ci95"][c][m][1] for c in CONDITIONS])
        ax.plot(x, y, marker=MARKERS[m], color=COLORS[m], lw=2, label=NAMES[m])
        ax.fill_between(x, lo, hi, color=COLORS[m], alpha=0.12)
    ax.set_xticks(x, [COND_LABELS[c] for c in CONDITIONS], rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("ROC-AUC en pares de plagio (IC 95 %)")
    ax.set_ylim(0.5, 1.0)
    ax.grid(axis="y", ls=":", alpha=0.5)
    ax.legend(loc="lower left", frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "comparacion_robustez_lineas.png", dpi=200)
    plt.close(fig)

    keys = ["T0", "T1", "T5", "T7@1.0"]
    names = ["T0\n(original)", "T1\n(renombrar identif.)", "T5\n(código muerto)", "T7@1.0\n(combinado)"]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    width = 0.26
    for j, m in enumerate(METHODS):
        y = np.array([s["auc"][c][m] for c in keys])
        lo = np.array([s["auc_ci95"][c][m][0] for c in keys])
        hi = np.array([s["auc_ci95"][c][m][1] for c in keys])
        ax.bar(np.arange(4) + (j - 1) * width, y, width, color=COLORS[m], yerr=[y - lo, hi - y], capsize=3, label=NAMES[m], error_kw={"lw": 1.2})
    ax.set_xticks(range(4), names)
    ax.set_ylabel("ROC-AUC (IC 95 %)")
    ax.set_ylim(0.5, 1.0)
    ax.grid(axis="y", ls=":", alpha=0.5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3, frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "comparacion_robustez_barras.png", dpi=200)
    plt.close(fig)


def draw(work: Path) -> None:
    plt = _style()
    draw_e1(work, plt)
    draw_robustness(plt)
    draw_heatmap(work, plt)
    draw_correctness(work, plt)
    draw_clusters(work)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["compute", "draw"])
    ap.add_argument("--work", required=True, type=Path)
    args = ap.parse_args()
    compute(args.work) if args.stage == "compute" else draw(args.work)


if __name__ == "__main__":
    main()

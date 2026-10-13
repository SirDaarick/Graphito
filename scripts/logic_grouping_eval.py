import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import numpy as np
import torch

from models.evaluation.manifest import manifest_sha256
from models.graphcodebert.v2.baselines import (
    SetSimilarity,
    V2FileEmbedder,
    jaccard_set,
    winnowing_set,
)
from models.graphcodebert.v2.cache import CachedEmbedder, EmbeddingCache
from models.graphcodebert.v2.embed import GraphCodeBERTV2Embedder
from models.graphcodebert.v2.pairs import map_at_r_ci
from models.logic_eval.canonical import canonicalize_code
from models.logic_eval.correctness import evaluate_assignment_leave_one_out, macro_evaluate_e2
from models.logic_eval.data import load_e1_sample, load_e2_stats, load_manifest_data
from models.logic_eval.grouping import (
    bootstrap_metric_difference,
    compute_assignment_confusion,
    compute_cosine_silhouette,
    compute_map_at_r,
    compute_pairwise_roc_auc,
    compute_per_assignment_map_at_r,
    compute_recall_at_1,
    random_baseline_map_at_r,
)
from models.logic_eval.plots import (
    plot_g1_heatmap,
    plot_g2_projection,
    plot_g3_map_at_r,
    plot_g4_correctness,
    plot_g5_teacher_view,
)


def get_git_info() -> Dict[str, Any]:
    try:
        import subprocess
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        status = subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        return {"git_sha": sha, "dirty": len(status) > 0}
    except Exception:
        return {"git_sha": "unknown", "dirty": False}


def cosine_sim_matrix(embeddings: np.ndarray) -> np.ndarray:
    emb = np.asarray(embeddings, dtype=np.float64)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    unit = np.divide(emb, norms, out=np.zeros_like(emb), where=norms > 0)
    return unit @ unit.T


def read_file_text(root: Path, file_path_str: str) -> str:
    path = root / file_path_str
    return path.read_text(encoding="utf-8", errors="replace")


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate logical grouping for Canal A.")
    parser.add_argument("--split", default="data/splits/split_v1.json.gz", help="Path to split manifest")
    parser.add_argument(
        "--methods",
        default="jaccard,winnowing,v2,v2_nodfg,v2_norm",
        help="Comma-separated list of methods to evaluate",
    )
    parser.add_argument("--per-assignment", type=int, default=60, help="Max items per assignment block for E1")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--n-boot", type=int, default=1000, help="Number of bootstrap iterations")
    parser.add_argument("--smoke", action="store_true", help="Run fast smoke test (5 blocks, 10 items each)")
    parser.add_argument("--out", default="runs/logic_eval", help="Output directory")
    parser.add_argument("--stats-dir", default="data/raw/stats", help="Directory containing student stats")
    parser.add_argument("--cache-dir", default="data/cache/embeddings", help="Embedding cache directory")
    return parser.parse_args()


def main():
    start_time = time.time()
    args = parse_args()
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]

    repo_root = Path.cwd()
    manifest_path = repo_root / args.split

    # Create run directory
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out)
    if "smoke" in args.out or args.smoke:
        # In smoke mode, write directly into out_dir or out_dir/timestamp
        run_dir = out_dir if out_dir.name == "logic_eval_smoke" else out_dir / timestamp
    else:
        run_dir = out_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = run_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    max_per_block = 10 if args.smoke else args.per_assignment
    smoke_blocks = 5 if args.smoke else None
    n_boot = min(50, args.n_boot) if args.smoke else args.n_boot

    print(f"=== Logic Grouping Evaluation ===")
    print(f"Output directory: {run_dir}")
    print(f"Methods: {methods}")
    print(f"Mode: {'SMOKE' if args.smoke else 'FULL'} (max_per_block={max_per_block}, n_boot={n_boot})")

    # 1. Load E1 Sample
    print(f"Loading E1 sample from {manifest_path}...")
    e1_sample = load_e1_sample(
        manifest_path,
        max_per_block=max_per_block,
        seed=args.seed,
        smoke_blocks=smoke_blocks,
    )
    print(f"Loaded {len(e1_sample)} sample items across {len(set(e.get('block') or e.get('assignment') for e in e1_sample))} blocks.")

    # Read raw code
    codes: List[str] = []
    canon_codes: List[str] = []
    labels: List[str] = []
    courses: List[str] = []
    blocks: List[str] = []

    for item in e1_sample:
        c = read_file_text(repo_root, item["id"])
        codes.append(c)
        labels.append(item.get("block") or item.get("assignment"))
        courses.append(item.get("course", ""))
        blocks.append(item.get("block") or item.get("assignment"))

    # Prepare canonical code if v2_norm is requested
    if any("norm" in m for m in methods):
        print("Canonicalizing code for norm methods...")
        for idx, (item, c) in enumerate(zip(e1_sample, codes)):
            c_norm = canonicalize_code(c, lang=item.get("lang", "c"))
            canon_codes.append(c_norm)

    # 2. Setup embedder / models if needed
    needs_gcb = any(m.startswith("v2") for m in methods)
    v2_embedder = None
    cached_v2_dfg = None
    cached_v2_nodfg = None

    if needs_gcb:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading GraphCodeBERT v2 on {device}...")
        v2_embedder = GraphCodeBERTV2Embedder.from_pretrained(
            "microsoft/graphcodebert-base",
            device=device,
            local_files_only=True,
        )
        file_embedder_dfg = V2FileEmbedder(v2_embedder, use_dfg=True)
        file_embedder_nodfg = V2FileEmbedder(v2_embedder, use_dfg=False)

        cache_path = Path(args.cache_dir)
        cache_dfg = EmbeddingCache(cache_path, file_embedder_dfg.key_fields())
        cache_nodfg = EmbeddingCache(cache_path, file_embedder_nodfg.key_fields())

        cached_v2_dfg = CachedEmbedder(file_embedder_dfg, cache_dfg)
        cached_v2_nodfg = CachedEmbedder(file_embedder_nodfg, cache_nodfg)

    # 3. Compute representations and similarity matrices for E1
    sim_matrices: Dict[str, np.ndarray] = {}
    embeddings_by_method: Dict[str, np.ndarray] = {}
    e1_metrics: Dict[str, Dict[str, Any]] = {}

    for method in methods:
        print(f"Evaluating representation method: {method}...")
        if method == "jaccard":
            sets = [jaccard_set(c) for c in codes]
            sim = SetSimilarity(sets)(0, len(codes))
            sim_matrices["jaccard"] = sim

        elif method == "winnowing":
            sets = [winnowing_set(c) for c in codes]
            sim = SetSimilarity(sets)(0, len(codes))
            sim_matrices["winnowing"] = sim

        elif method in ("v2", "v2_nodfg", "v2_norm", "v2_norm_nodfg"):
            use_dfg = not ("nodfg" in method)
            use_norm = "norm" in method
            cached_emb = cached_v2_dfg if use_dfg else cached_v2_nodfg

            vectors = []
            for item, orig_c, norm_c in zip(
                e1_sample,
                codes,
                canon_codes if canon_codes else ["" for _ in codes],
            ):
                code_to_use = norm_c if use_norm else orig_c
                sha = hashlib.sha256(code_to_use.encode("utf-8")).hexdigest()
                lang = item.get("lang", "c")
                res = cached_emb.embed(sha, code_to_use, lang)
                vec = res.vectors.get("mean")
                if vec is None:
                    vec = np.zeros(768, dtype=np.float32)
                vectors.append(vec)

            emb_mat = np.stack(vectors, axis=0)
            embeddings_by_method[method] = emb_mat
            sim = cosine_sim_matrix(emb_mat)
            sim_matrices[method] = sim
        else:
            print(f"Warning: unknown method {method}, skipping.")
            continue

        # Compute E1 metrics
        sim = sim_matrices[method]
        m_map = compute_map_at_r(sim, labels)
        rec1 = compute_recall_at_1(sim, labels)
        auc = compute_pairwise_roc_auc(sim, labels, courses=courses)
        sil = compute_cosine_silhouette(sim, labels)
        per_assign = compute_per_assignment_map_at_r(sim, labels, blocks)
        ci_res = map_at_r_ci(per_assign, n_boot=n_boot, seed=args.seed)

        e1_metrics[method] = {
            "value": m_map.get("value"),
            "ci95": ci_res.get("ci95"),
            "recall_at_1": rec1,
            "roc_auc": auc,
            "silhouette": sil,
            "n_queries": m_map.get("n_queries"),
            "per_assignment": per_assign,
        }

    # Baseline MAP@R
    print("Computing random baseline MAP@R...")
    rnd_baseline = random_baseline_map_at_r(labels, seed=args.seed, n_permutations=min(50, n_boot))
    print(f"Random baseline MAP@R: {rnd_baseline:.4f}")

    # Contrasts (E1-H2, E1-H3)
    contrasts: Dict[str, Any] = {}
    if "v2_norm" in e1_metrics and "v2" in e1_metrics:
        assign_keys = sorted(set(e1_metrics["v2"]["per_assignment"]) & set(e1_metrics["v2_norm"]["per_assignment"]))
        v2_vals = np.array([e1_metrics["v2"]["per_assignment"][k]["value"] or 0.0 for k in assign_keys])
        v2_norm_vals = np.array([e1_metrics["v2_norm"]["per_assignment"][k]["value"] or 0.0 for k in assign_keys])
        contrasts["v2_norm - v2"] = bootstrap_metric_difference(v2_norm_vals, v2_vals, n_boot=n_boot, seed=args.seed)

    if "v2" in e1_metrics and "jaccard" in e1_metrics:
        assign_keys = sorted(set(e1_metrics["v2"]["per_assignment"]) & set(e1_metrics["jaccard"]["per_assignment"]))
        v2_vals = np.array([e1_metrics["v2"]["per_assignment"][k]["value"] or 0.0 for k in assign_keys])
        jaccard_vals = np.array([e1_metrics["jaccard"]["per_assignment"][k]["value"] or 0.0 for k in assign_keys])
        contrasts["v2 - jaccard"] = bootstrap_metric_difference(v2_vals, jaccard_vals, n_boot=n_boot, seed=args.seed)

    # Confusion matrix
    primary_method = "v2" if "v2" in sim_matrices else methods[0]
    confusion = compute_assignment_confusion(sim_matrices[primary_method], labels)

    # 4. Evaluation 2: Correctness & Reference Solution
    print("Evaluating E2: Correctness and reference similarity...")
    manifest_data = load_manifest_data(manifest_path)
    all_human_entries = [
        e for e in manifest_data.get("entries", [])
        if e.get("source") == "human" and not e.get("excluded", False)
    ]
    # 4. Evaluate E2: Correctness and reference similarity across methods (Leave-One-Out)
    print("Evaluating E2: Correctness and reference similarity across methods...")
    min_pass = 5
    min_fail = 3
    e2_qualified = load_e2_stats(
        all_human_entries,
        stats_dir=args.stats_dir,
        min_pass=min_pass,
        min_fail=min_fail,
        seed=args.seed,
    )
    print(f"Found {len(e2_qualified)} qualifying assignments for E2.")

    if args.smoke and len(e2_qualified) > 3:
        e2_keys = sorted(e2_qualified.keys())[:3]
        e2_qualified = {k: e2_qualified[k][:12] for k in e2_keys}


    e2_results_by_method: Dict[str, Dict[str, Any]] = {}
    correctness_points_by_method: Dict[str, List[Dict[str, Any]]] = {m: [] for m in methods}
    first_assignment_ranking_for_g5: List[Dict[str, Any]] = []
    first_assignment_name: str = ""

    # Pre-cache canonical code for E2 submissions if v2_norm is present
    canon_e2_cache: Dict[str, str] = {}
    if "v2_norm" in methods:
        for assign_name, submissions in e2_qualified.items():
            for s in submissions:
                sid = s["id"]
                if sid not in canon_e2_cache:
                    scode = read_file_text(repo_root, sid)
                    canon_e2_cache[sid] = canonicalize_code(scode, lang=s.get("lang", "c"))

    # Compute per-method assignment evaluations
    # To compute paired contrasts across tasks, we track per-task AUC lists aligned by assignment
    assignment_names_sorted = sorted(e2_qualified.keys())
    per_method_task_aucs: Dict[str, List[float]] = {m: [] for m in methods}

    for method in methods:
        print(f"  Evaluating E2 for method: {method}...")
        assign_eval_list: List[Dict[str, Any]] = []

        for a_idx, assign_name in enumerate(assignment_names_sorted):
            submissions = e2_qualified[assign_name]
            raw_codes = [read_file_text(repo_root, s["id"]) for s in submissions]
            pass_rates = [s["pass_rate"] for s in submissions]
            n_sub = len(submissions)

            # Compute similarity matrix for this method
            if method == "jaccard":
                sets = [jaccard_set(c) for c in raw_codes]
                sub_sim = SetSimilarity(sets)(0, n_sub)
            elif method == "winnowing":
                sets = [winnowing_set(c) for c in raw_codes]
                sub_sim = SetSimilarity(sets)(0, n_sub)
            elif method == "v2":
                sub_vecs = []
                for s, scode in zip(submissions, raw_codes):
                    sha = s.get("sha256") or hashlib.sha256(scode.encode("utf-8")).hexdigest()
                    res = cached_v2_dfg.embed(sha, scode, s.get("lang", "c"))
                    vec = res.vectors.get("mean") if res.vectors.get("mean") is not None else np.zeros(768, dtype=np.float32)
                    sub_vecs.append(vec)
                sub_sim = cosine_sim_matrix(np.stack(sub_vecs, axis=0))
            elif method == "v2_nodfg":
                sub_vecs = []
                for s, scode in zip(submissions, raw_codes):
                    sha = s.get("sha256") or hashlib.sha256(scode.encode("utf-8")).hexdigest()
                    res = cached_v2_nodfg.embed(sha, scode, s.get("lang", "c"))
                    vec = res.vectors.get("mean") if res.vectors.get("mean") is not None else np.zeros(768, dtype=np.float32)
                    sub_vecs.append(vec)
                sub_sim = cosine_sim_matrix(np.stack(sub_vecs, axis=0))
            elif method == "v2_norm":
                sub_vecs = []
                for s in submissions:
                    c_norm = canon_e2_cache[s["id"]]
                    sha = hashlib.sha256(c_norm.encode("utf-8")).hexdigest()
                    res = cached_v2_dfg.embed(sha, c_norm, s.get("lang", "c"))
                    vec = res.vectors.get("mean") if res.vectors.get("mean") is not None else np.zeros(768, dtype=np.float32)
                    sub_vecs.append(vec)
                sub_sim = cosine_sim_matrix(np.stack(sub_vecs, axis=0))
            else:
                sets = [jaccard_set(c) for c in raw_codes]
                sub_sim = SetSimilarity(sets)(0, n_sub)

            eval_res = evaluate_assignment_leave_one_out(sub_sim, pass_rates, assignment_name=assign_name)
            assign_eval_list.append(eval_res)
            per_method_task_aucs[method].append(eval_res["auc"] if eval_res["auc"] is not None else 0.5)

            # Collect points for G4 plot using the first passing reference
            pass_idxs = [i for i, r in enumerate(pass_rates) if r == 1.0]
            if pass_idxs:
                ref_idx = pass_idxs[0]
                for idx, s in enumerate(submissions):
                    if idx != ref_idx:
                        correctness_points_by_method[method].append({
                            "assignment": assign_name,
                            "pass_rate": s["pass_rate"],
                            "pasa": s["pasa"],
                            "sim_to_ref": float(sub_sim[ref_idx, idx]),
                        })

            # For G5, capture ranking for first assignment using v2 if available, else first method
            if (method == "v2" or (not first_assignment_ranking_for_g5 and method == methods[0])) and not first_assignment_ranking_for_g5 and pass_idxs:
                first_assignment_name = assign_name
                ref_idx = pass_idxs[0]
                ranked = []
                for idx, s in enumerate(submissions):
                    if idx != ref_idx:
                        ranked.append({
                            "student": s.get("student", s["id"]),
                            "last_test_results": s.get("last_test_results", ""),
                            "pasa": s["pasa"],
                            "sim": float(sub_sim[ref_idx, idx]),
                        })
                ranked.sort(key=lambda x: x["sim"], reverse=True)
                first_assignment_ranking_for_g5 = ranked

        macro_res = macro_evaluate_e2(assign_eval_list, n_boot=n_boot, seed=args.seed)
        e2_results_by_method[method] = macro_res

    # Paired bootstrap contrasts on Macro-AUC across assignments
    e2_contrasts: Dict[str, Dict[str, Any]] = {}
    e2_pairs = [("v2 - jaccard", "v2", "jaccard"), ("v2_norm - v2", "v2_norm", "v2")]
    for name, m_a, m_b in e2_pairs:
        if m_a in per_method_task_aucs and m_b in per_method_task_aucs:
            arr_a = np.array(per_method_task_aucs[m_a], dtype=np.float64)
            arr_b = np.array(per_method_task_aucs[m_b], dtype=np.float64)
            diffs = arr_a - arr_b
            mean_diff = float(np.mean(diffs))

            rng = np.random.default_rng(args.seed)
            boot_diffs = []
            n_tasks = len(diffs)
            for _ in range(n_boot):
                idx = rng.integers(0, n_tasks, size=n_tasks)
                boot_diffs.append(float(np.mean(diffs[idx])))
            ci_low = float(np.percentile(boot_diffs, 2.5))
            ci_high = float(np.percentile(boot_diffs, 97.5))
            e2_contrasts[name] = {
                "mean_diff": mean_diff,
                "ci95": [ci_low, ci_high],
            }

    # 5. Generate Plots (G1 to G5)
    print("Generating plots (G1 - G5)...")
    plot_g1_heatmap(sim_matrices, labels, plots_dir / "g1_heatmap.png")
    plot_g2_projection(embeddings_by_method, labels, plots_dir / "g2_projection.png", seed=args.seed)
    plot_g3_map_at_r(e1_metrics, rnd_baseline, plots_dir / "g3_map_at_r.png")
    plot_g4_correctness(correctness_points_by_method, plots_dir / "g4_correctness.png")
    plot_g5_teacher_view(first_assignment_ranking_for_g5, first_assignment_name or "A2016/Z1/Z1", plots_dir / "g5_teacher_view.png")

    # 6. Save Artifacts and Results
    print("Writing result files...")
    # config.json
    config_doc = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git": get_git_info(),
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha256(manifest_path),
        "methods": methods,
        "mode": "smoke" if args.smoke else "full",
        "per_assignment": max_per_block,
        "seed": args.seed,
        "n_boot": n_boot,
        "random_baseline": rnd_baseline,
    }
    with open(run_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config_doc, f, indent=2)

    # sample.json
    sample_doc = {
        "e1_sample_ids": [e["id"] for e in e1_sample],
        "e2_assignments": {k: [s["id"] for s in v] for k, v in e2_qualified.items()},
    }
    with open(run_dir / "sample.json", "w", encoding="utf-8") as f:
        json.dump(sample_doc, f, indent=2)

    # e1_metrics.json
    with open(run_dir / "e1_metrics.json", "w", encoding="utf-8") as f:
        json.dump(e1_metrics, f, indent=2)

    # e1_contrasts.json
    with open(run_dir / "e1_contrasts.json", "w", encoding="utf-8") as f:
        json.dump(contrasts, f, indent=2)

    # e1_confusion.json
    with open(run_dir / "e1_confusion.json", "w", encoding="utf-8") as f:
        json.dump(confusion, f, indent=2)

    # e2_metrics.json
    with open(run_dir / "e2_metrics.json", "w", encoding="utf-8") as f:
        json.dump(e2_results_by_method, f, indent=2)

    # e2_contrasts.json
    with open(run_dir / "e2_contrasts.json", "w", encoding="utf-8") as f:
        json.dump(e2_contrasts, f, indent=2)

    # report.md
    # Check hypotheses
    h1_verdict = "INCONCLUSIVE"
    if "v2" in e1_metrics and e1_metrics["v2"].get("ci95"):
        ci = e1_metrics["v2"]["ci95"]
        if ci[0] > rnd_baseline:
            h1_verdict = "CONFIRMED"
        elif ci[0] <= rnd_baseline <= ci[1]:
            h1_verdict = "REFUTED"

    h2_verdict = "INCONCLUSIVE"
    if "v2_norm - v2" in contrasts and contrasts["v2_norm - v2"].get("ci95"):
        ci = contrasts["v2_norm - v2"]["ci95"]
        if ci[0] > 0:
            h2_verdict = "CONFIRMED"
        else:
            h2_verdict = "REFUTED"

    h3_verdict = "INCONCLUSIVE"
    if "v2 - jaccard" in contrasts and contrasts["v2 - jaccard"].get("ci95"):
        ci = contrasts["v2 - jaccard"]["ci95"]
        if ci[0] >= 0:
            h3_verdict = "CONFIRMED"
        elif ci[1] < 0:
            h3_verdict = "REFUTED"

    h4_verdict = "INCONCLUSIVE"
    v2_e2 = e2_results_by_method.get("v2", {})
    if v2_e2.get("auc_ci95"):
        ci = v2_e2["auc_ci95"]
        if ci[0] > 0.5:
            h4_verdict = "CONFIRMED"
        elif ci[0] <= 0.5 <= ci[1]:
            h4_verdict = "REFUTED"

    report_md = f"""# Evaluación de Agrupamiento Lógico (Canal A)

**Fecha:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}  
**Modo:** {'Smoke run' if args.smoke else 'Full run'}  
**Muestra E1:** {len(e1_sample)} entregas  
**Línea base aleatoria MAP@R:** {rnd_baseline:.4f}  

## 1. Verificación de Hipótesis Pre-registradas

| ID | Hipótesis | Criterio de confirmación | Resultado | Veredicto |
|---|---|---|---|---|
| **E1-H1** | Embeddings agrupan por tarea | MAP@R(v2) > Random, IC95 separado | MAP@R={e1_metrics.get('v2', {}).get('value', 'N/A')}, CI={e1_metrics.get('v2', {}).get('ci95', 'N/A')} | **{h1_verdict}** |
| **E1-H2** | Renombrado canónico mejora v2 | ΔMAP@R(v2_norm − v2) > 0, IC95 excluye 0 | Δ={contrasts.get('v2_norm - v2', {}).get('mean_diff', 'N/A')}, CI={contrasts.get('v2_norm - v2', {}).get('ci95', 'N/A')} | **{h2_verdict}** |
| **E1-H3** | GraphCodeBERT ≥ Jaccard | ΔMAP@R(v2 − jaccard) ≥ 0 | Δ={contrasts.get('v2 - jaccard', {}).get('mean_diff', 'N/A')}, CI={contrasts.get('v2 - jaccard', {}).get('ci95', 'N/A')} | **{h3_verdict}** |
| **E2-H1** | Parecido a correcta indica corrección | AUC > 0.5 con IC95 que excluye 0.5 | Macro AUC(v2)={v2_e2.get('macro_auc', 'N/A')}, CI={v2_e2.get('auc_ci95', 'N/A')} | **{h4_verdict}** |

## 2. Métricas E1 por Método

| Método | MAP@R (IC95) | Recall@1 | ROC-AUC | Silhouette |
|---|---|---|---|---|
"""
    for m, vals in e1_metrics.items():
        v = vals.get("value")
        v_str = f"{v:.4f}" if v is not None else "N/A"
        ci = vals.get("ci95")
        ci_str = f"[{ci[0]:.4f}, {ci[1]:.4f}]" if ci and ci[0] is not None else "N/A"
        r1 = vals.get("recall_at_1")
        r1_str = f"{r1:.4f}" if r1 is not None else "N/A"
        auc_v = vals.get("roc_auc")
        auc_str = f"{auc_v:.4f}" if auc_v is not None else "N/A"
        sil_v = vals.get("silhouette")
        sil_str = f"{sil_v:.4f}" if sil_v is not None else "N/A"
        report_md += f"| `{m}` | {v_str} {ci_str} | {r1_str} | {auc_str} | {sil_str} |\n"

    report_md += """
## 3. Resultados E2 (Leave-One-Out Reference Evaluation)

| Método | Macro AUC (IC95) | Macro Spearman (IC95) |
|---|---|---|
"""
    for m, mres in e2_results_by_method.items():
        auc_v = mres.get("macro_auc")
        auc_str = f"{auc_v:.4f}" if auc_v is not None else "N/A"
        auc_ci = mres.get("auc_ci95")
        auc_ci_str = f"[{auc_ci[0]:.4f}, {auc_ci[1]:.4f}]" if auc_ci and auc_ci[0] is not None else "N/A"
        sp_v = mres.get("macro_spearman")
        sp_str = f"{sp_v:.4f}" if sp_v is not None else "N/A"
        sp_ci = mres.get("spearman_ci95")
        sp_ci_str = f"[{sp_ci[0]:.4f}, {sp_ci[1]:.4f}]" if sp_ci and sp_ci[0] is not None else "N/A"
        report_md += f"| `{m}` | {auc_str} {auc_ci_str} | {sp_str} {sp_ci_str} |\n"

    report_md += """
### Contrastes Pareados E2 (Macro-AUC sobre tareas)
"""
    for cname, cvals in e2_contrasts.items():
        mdiff = cvals.get("mean_diff")
        mdiff_str = f"{mdiff:.4f}" if mdiff is not None else "N/A"
        ci = cvals.get("ci95")
        ci_str = f"[{ci[0]:.4f}, {ci[1]:.4f}]" if ci and ci[0] is not None else "N/A"
        report_md += f"- **{cname}:** Δ={mdiff_str}, IC95={ci_str}\n"

    report_md += f"""
## 4. Gráficas Generadas

- `plots/g1_heatmap.png`: Mapa de calor de similitud coseno agrupado por tarea.
- `plots/g2_projection.png`: Proyección 2D t-SNE de embeddings (v2 vs v2_norm).
- `plots/g3_map_at_r.png`: Barras comparativas de MAP@R con IC95 y baseline aleatorio.
- `plots/g4_correctness.png`: Similitud a la referencia según resultado de pruebas.
- `plots/g5_teacher_view.png`: Vista priorizada de inspección docente para `{first_assignment_name}`.
"""
    with open(run_dir / "report.md", "w", encoding="utf-8") as f:
        f.write(report_md)

    duration = time.time() - start_time
    print(f"\nExecution finished cleanly in {duration:.2f} seconds.")
    print(f"Results saved to: {run_dir}")


if __name__ == "__main__":
    main()

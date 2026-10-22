"""F4 of the contrastive CodeNet experiment: the single final evaluation on ESCOM of the frozen adapters.

Evaluates the zero-shot `v2_norm` baseline, Jaccard and the four F3 adapters (B_s1 is the pre-registered
headline, see `odd/tasks/contrastivo-codenet-f3.md`) on:

- E1: MAP@R of the assignment grouping (`logic_grouping_eval.py` sample and seed);
- E2: Macro-AUC of "similarity to a passing reference predicts passing" (leave-one-out references);
- robustness: T0-T7 obfuscations on the `split_v1` test pairs (`robustness_experiment.py`, run as a subprocess).

Hypotheses (guide, section 1; H1-H3 are drawn from the headline adapter only, every other adapter is reported):
H1 = E2 Macro-AUC gain over zero-shot `v2_norm` with a CI95 that excludes 0; H2 = E1 MAP@R gain likewise;
H3 = no condition where the adapter loses more than `v2_norm` under T1-T7 (difference-in-differences CI95
entirely below 0 refutes it). Nothing is retrained or recalibrated after seeing results.

    python scripts/f4_eval.py plan          # validates adapters and prints sizes and commands; no model results
    python scripts/f4_eval.py run           # the evaluation; refuses to start twice (use --resume to continue)
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

F3 = Path(r"C:\Users\edani\datasets\codenet\f3")
DEFAULT_REPO = Path(r"C:\Users\edani\OneDrive\Documents\Proyectos\Graphito")  # holds the gitignored ESCOM data
HEADLINE = "ft_B_s1"
ADAPTERS = {
    "ft_B_s1": F3 / "B_s1" / "adapter",
    "ft_B_s0": F3 / "B_s0" / "adapter",
    "ft_A_s0": F3 / "A_s0" / "adapter",
    "ft_A_s1": F3 / "A_s1" / "adapter",
}
BASELINE = "v2_norm"
N_BOOT, SEED = 1000, 42
CONDITIONS = "T0,T1,T2,T3,T4,T5,T6,T7@0.25,T7@0.5,T7@1.0"
# Earlier ESCOM runs the zero-shot numbers must reproduce before any adapter number is trusted.
REFERENCE_LOGIC_RUN = "runs/logic_eval/20261013-152644"
REFERENCE_ROBUSTNESS_RUN = "runs/robustness_v2norm/20261019-222018"
REPRO_TOL, REPRO_TOL_AUC = 1e-6, 2e-3


# --- pure helpers (tested) ----------------------------------------------------------------------


def improvement_verdict(ci: Optional[List[float]]) -> str:
    """confirmed when the CI95 lies above 0, refuted when it lies below, inconclusive otherwise."""
    if not ci or ci[0] is None:
        return "inconclusive"
    if ci[0] > 0:
        return "confirmed"
    if ci[1] < 0:
        return "refuted"
    return "inconclusive"


def non_regression_verdict(did_by_condition: Mapping[str, Optional[Mapping]]) -> Dict[str, Any]:
    """H3: refuted when some condition has a difference-in-differences CI95 entirely below 0
    (the adapter loses more than `v2_norm`); otherwise confirmed. Conditions without data are listed."""
    refuted, missing = [], []
    for cond, res in did_by_condition.items():
        if not res or not res.get("ci95") or res["ci95"][0] is None:
            missing.append(cond)
        elif res["ci95"][1] < 0:
            refuted.append(cond)
    return {
        "verdict": "refuted" if refuted else "confirmed",
        "refuted_conditions": refuted,
        "missing_conditions": missing,
        "conditions": dict(did_by_condition),
    }


def reproduces(value: Optional[float], reference: float, tol: float) -> bool:
    return value is not None and abs(value - reference) <= tol


def paired_difference(a: Mapping[str, Optional[float]], b: Mapping[str, Optional[float]], n_boot: int = N_BOOT, seed: int = SEED) -> Dict[str, Any]:
    """Paired bootstrap of mean(a - b) over the keys present in both (None counts as 0.0, as in
    `logic_grouping_eval.py`)."""
    from models.logic_eval.grouping import bootstrap_metric_difference

    keys = sorted(set(a) & set(b))
    va = np.array([a[k] or 0.0 for k in keys], dtype=np.float64)
    vb = np.array([b[k] or 0.0 for k in keys], dtype=np.float64)
    res = bootstrap_metric_difference(va, vb, n_boot=n_boot, seed=seed)
    return {**res, "n_units": len(keys)}


def check_frozen(out: Path, frozen: Mapping[str, Any], resume: bool) -> str:
    """The evaluation happens once: the frozen record (adapter hashes, headline) is written before any
    number exists, a second start is refused, and a resume must match it exactly."""
    path = out / "f4_frozen.json"
    if path.exists():
        if not resume:
            raise SystemExit(f"{path} exists: F4 already started. Use --resume to continue the same run.")
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("adapters") != frozen["adapters"] or old.get("headline") != frozen["headline"]:
            raise SystemExit("the adapters or headline differ from the frozen record: refusing to resume")
        return "resumed"
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(frozen, indent=2), encoding="utf-8")
    return "created"


# --- stages -------------------------------------------------------------------------------------


def adapter_paths(args) -> Dict[str, Path]:
    """The frozen F3 adapters; `--adapter ft_NAME=PATH` replaces one (plumbing checks with a null adapter)."""
    from models.graphcodebert.v2.adapter import parse_adapter_specs

    paths = {n: Path(p) for n, p in ADAPTERS.items()}
    override = parse_adapter_specs(args.adapter)
    unknown = set(override) - set(paths)
    if unknown:
        raise SystemExit(f"unknown adapter names {sorted(unknown)}; expected {sorted(paths)}")
    paths.update(override)
    return paths


def frozen_record(paths: Mapping[str, Path]) -> Dict[str, Any]:
    from models.graphcodebert.v2.adapter import adapter_sha256

    return {
        "headline": HEADLINE,
        "adapters": {n: adapter_sha256(p) for n, p in paths.items()},
        "baseline": BASELINE,
        "n_boot": N_BOOT,
        "seed": SEED,
        "conditions": CONDITIONS,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def load_baseline(device) -> Dict[str, Any]:
    from models.graphcodebert.v2.adapter import build_embedder

    return {BASELINE: build_embedder(None, device=device)}


def load_adapters(paths: Mapping[str, Path], device) -> Dict[str, Any]:
    from models.graphcodebert.v2.adapter import build_embedder

    return {name: build_embedder(path, device=device) for name, path in paths.items()}


def embed_mean(embedder, codes: List[str], langs: List[str]) -> np.ndarray:
    """`mean`-pooled v2 vectors of identifier-canonicalized code (zeros on failure, counted by the caller)."""
    from models.logic_eval.canonical import canonicalize_code

    dim = embedder.encoder.hidden_size
    out = np.zeros((len(codes), dim), dtype=np.float64)
    for i, (code, lang) in enumerate(zip(codes, langs)):
        res = embedder.embed(canonicalize_code(code, lang=lang), lang)
        if res.success:
            out[i] = res.mean
    return out


def cosine_matrix(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    unit = np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 0)
    return unit @ unit.T


def e1_methods(models, repo: Path, smoke: bool, include_jaccard: bool) -> Dict[str, Any]:
    """E1 MAP@R of each embedding model (and Jaccard) on the `logic_grouping_eval.py` sample."""
    from models.graphcodebert.v2.baselines import SetSimilarity, jaccard_set
    from models.graphcodebert.v2.pairs import map_at_r_ci
    from models.logic_eval.data import load_e1_sample
    from models.logic_eval.grouping import compute_map_at_r, compute_per_assignment_map_at_r, compute_recall_at_1

    sample = load_e1_sample(repo / "data" / "splits" / "split_v1.json.gz", max_per_block=10 if smoke else 60, seed=SEED, smoke_blocks=3 if smoke else None)
    codes = [(repo / it["id"]).read_text(encoding="utf-8", errors="replace") for it in sample]
    langs = [it.get("lang", "c") for it in sample]
    labels = [it.get("block") or it.get("assignment") for it in sample]
    sims = {"jaccard": SetSimilarity([jaccard_set(c) for c in codes])(0, len(codes))} if include_jaccard else {}
    for name, embedder in models.items():
        print(f"[E1] embedding with {name}", flush=True)
        sims[name] = cosine_matrix(embed_mean(embedder, codes, langs))
    res: Dict[str, Any] = {"n_items": len(sample), "methods": {}}
    for name, sim in sims.items():
        per = compute_per_assignment_map_at_r(sim, labels, labels)
        res["methods"][name] = {
            "map_at_r": compute_map_at_r(sim, labels)["value"],
            "ci95": map_at_r_ci(per, n_boot=N_BOOT, seed=SEED).get("ci95"),
            "recall_at_1": compute_recall_at_1(sim, labels),
            "per_assignment": per,
        }
    return res


def e2_methods(models, repo: Path, smoke: bool, include_jaccard: bool) -> Dict[str, Any]:
    """E2 Macro-AUC (leave-one-out passing references) of each embedding model (and Jaccard)."""
    from models.graphcodebert.v2.baselines import SetSimilarity, jaccard_set
    from models.logic_eval.correctness import evaluate_assignment_leave_one_out, macro_evaluate_e2
    from models.logic_eval.data import load_e2_stats, load_manifest_data

    manifest = load_manifest_data(repo / "data" / "splits" / "split_v1.json.gz")
    entries = [e for e in manifest.get("entries", []) if e.get("source") == "human" and not e.get("excluded", False)]
    qualified = load_e2_stats(entries, stats_dir=repo / "data" / "raw" / "stats", min_pass=5, min_fail=3, seed=SEED)
    names = sorted(qualified)[:3] if smoke else sorted(qualified)
    per_method: Dict[str, List[Dict[str, Any]]] = {m: [] for m in ([*(["jaccard"] if include_jaccard else []), *models])}
    for a_idx, assign in enumerate(names):
        subs = qualified[assign][:12] if smoke else qualified[assign]
        codes = [(repo / s["id"]).read_text(encoding="utf-8", errors="replace") for s in subs]
        langs = [s.get("lang", "c") for s in subs]
        rates = [s["pass_rate"] for s in subs]
        print(f"[E2] {a_idx + 1}/{len(names)} {assign}: {len(subs)} submissions", flush=True)
        sims = {"jaccard": SetSimilarity([jaccard_set(c) for c in codes])(0, len(codes))} if include_jaccard else {}
        for name, embedder in models.items():
            sims[name] = cosine_matrix(embed_mean(embedder, codes, langs))
        for name, sim in sims.items():
            per_method[name].append(evaluate_assignment_leave_one_out(sim, rates, assignment_name=assign))
    return {"n_assignments": len(names), "methods": {n: macro_evaluate_e2(v, n_boot=N_BOOT, seed=SEED) for n, v in per_method.items()}}


def add_contrasts(res: Dict[str, Any], kind: str) -> Dict[str, Any]:
    """Paired bootstrap of every adapter against zero-shot `v2_norm` and Jaccard, over assignments."""
    if kind == "e1":
        vals = {n: {k: v["value"] for k, v in m["per_assignment"].items()} for n, m in res["methods"].items()}
    else:
        vals = {n: {r["assignment"]: (r["auc"] if r["auc"] is not None else 0.5) for r in m["per_assignment"]} for n, m in res["methods"].items()}
    res["contrasts"] = {
        f"{n} - {ref}": paired_difference(vals[n], vals[ref]) for n in res["methods"] if n not in (BASELINE, "jaccard") for ref in (BASELINE, "jaccard")
    }
    return res


def gate_zero_shot(base: Mapping[str, Any], repo: Path) -> Dict[str, Any]:
    """The zero-shot `v2_norm` numbers must reproduce the earlier ESCOM run before any adapter is scored."""
    e1_ref = json.loads((repo / REFERENCE_LOGIC_RUN / "e1_metrics.json").read_text(encoding="utf-8-sig"))["v2_norm"]["value"]
    e2_ref = json.loads((repo / REFERENCE_LOGIC_RUN / "e2_metrics.json").read_text(encoding="utf-8-sig"))["v2_norm"]["macro_auc"]
    gates = {
        "e1_v2_norm": {"new": base["e1"]["methods"][BASELINE]["map_at_r"], "reference": e1_ref},
        "e2_v2_norm": {"new": base["e2"]["methods"][BASELINE]["macro_auc"], "reference": e2_ref},
    }
    for g in gates.values():
        g["ok"] = reproduces(g["new"], g["reference"], REPRO_TOL)
    return gates


def robustness_command(paths: Mapping[str, Path], repo: Path, out: Path, smoke: bool, resume: bool, gate: bool = False) -> List[str]:
    """The robustness run as a subprocess. `gate=True` is the zero-shot-only pre-check (T0 and T1), run
    before any adapter is scored; its embeddings come from the shared cache."""
    run_dir = out / ("robustness_gate" if gate else "robustness")
    paths = {} if gate else paths
    methods = ",".join(["jaccard", BASELINE, *paths])
    cmd = [
        sys.executable, str(Path(__file__).resolve().parent / "robustness_experiment.py"),
        "--methods", methods, "--skip-validity", "--root", str(repo),
        "--manifest", str(repo / "data" / "splits" / "split_v1.json.gz"),
        "--cache-dir", str(repo / "runs" / "graphcodebert" / "_cache"),
        "--source-run", str(repo / "runs" / "graphcodebert" / "20261011-082155"),
        "--deploy-calibration", str(repo / "models" / "deploy" / "channel_a" / "calibration.json"),
        "--n-boot", str(N_BOOT), "--n-boot-secondary", str(N_BOOT),
    ]
    if smoke:
        cmd += ["--split", "val", "--conditions", "T0,T1", "--limit-assignments", "2", "--n-boot", "50", "--n-boot-secondary", "50"]
    else:
        cmd += ["--split", "test", "--confirm-test", "--conditions", "T0,T1" if gate else CONDITIONS]
    cmd += ["--resume", str(run_dir)] if resume and (run_dir / "config.json").is_file() else ["--run-dir", str(run_dir)]
    for name, path in paths.items():
        cmd += ["--adapter", f"{name}={path}"]
    return cmd


def robustness_summary(out: Path, repo: Path, run_name: str = "robustness") -> Dict[str, Any]:
    run = out / run_name
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8-sig"))
    contrasts = json.loads((run / "contrasts.json").read_text(encoding="utf-8-sig"))

    def auc(cond: str, method: str) -> Optional[float]:
        return metrics.get(cond, {}).get(method, {}).get("views", {}).get("all", {}).get("roc_auc", {}).get("value")

    conds = [c for c in metrics if c != "T0"]
    res: Dict[str, Any] = {"auc": {c: {m: auc(c, m) for m in metrics[c]} for c in metrics}}
    res["did_vs_v2_norm"] = {
        name: {c: contrasts.get(f"did__{c}__{name}__{BASELINE}") for c in conds} for name in ADAPTERS
    }
    ref = json.loads((repo / REFERENCE_ROBUSTNESS_RUN / "metrics.json").read_text(encoding="utf-8-sig"))
    res["reproduction"] = {
        c: {"new": auc(c, BASELINE), "reference": ref[c][BASELINE]["views"]["all"]["roc_auc"]["value"]} for c in ("T0", "T1") if c in metrics
    }
    res["reproduction_ok"] = all(reproduces(v["new"], v["reference"], REPRO_TOL_AUC) for v in res["reproduction"].values())
    return res


def write(path: Path, doc: Any) -> None:
    path.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")


def final_summary(out: Path, e1: Dict, e2: Dict, rob: Optional[Dict]) -> Dict[str, Any]:
    h = HEADLINE
    h1 = e2["contrasts"][f"{h} - {BASELINE}"]
    h2 = e1["contrasts"][f"{h} - {BASELINE}"]
    summary: Dict[str, Any] = {
        "headline": h,
        "H1": {"claim": "E2 Macro-AUC gain over zero-shot v2_norm", **h1, "verdict": improvement_verdict(h1.get("ci95"))},
        "H2": {"claim": "E1 MAP@R gain over zero-shot v2_norm", **h2, "verdict": improvement_verdict(h2.get("ci95"))},
        "e1_map_at_r": {n: m["map_at_r"] for n, m in e1["methods"].items()},
        "e2_macro_auc": {n: m["macro_auc"] for n, m in e2["methods"].items()},
    }
    if rob is not None:
        summary["H3"] = {"claim": "no condition where the adapter loses more than v2_norm", **non_regression_verdict(rob["did_vs_v2_norm"][h])}
    write(out / "f4_summary.json", summary)
    return summary


def run_plan(args) -> None:
    from models.graphcodebert.v2.adapter import adapter_sha256
    from models.logic_eval.data import load_e1_sample, load_e2_stats, load_manifest_data

    paths = adapter_paths(args)
    repo = args.repo_root
    print("adapters:")
    for n, p in paths.items():
        print(f"  {n}{' (headline)' if n == HEADLINE else ''}: {p}  sha256={adapter_sha256(p)[:16]}")
    manifest_path = repo / "data" / "splits" / "split_v1.json.gz"
    e1 = load_e1_sample(manifest_path, max_per_block=60, seed=SEED)
    manifest = load_manifest_data(manifest_path)
    entries = [e for e in manifest.get("entries", []) if e.get("source") == "human" and not e.get("excluded", False)]
    e2 = load_e2_stats(entries, stats_dir=repo / "data" / "raw" / "stats", min_pass=5, min_fail=3, seed=SEED)
    n_models = 1 + len(paths)
    print(f"E1: {len(e1)} files x {n_models} neural models")
    print(f"E2: {len(e2)} assignments, {sum(len(v) for v in e2.values())} submissions x {n_models} neural models")
    print("robustness command:\n  " + " ".join(f'"{c}"' if " " in c else c for c in robustness_command(paths, repo, args.out, smoke=False, resume=False)))
    print("reproduction gates before any adapter number is reported: "
          f"E1/E2 zero-shot vs {REFERENCE_LOGIC_RUN}, robustness zero-shot vs {REFERENCE_ROBUSTNESS_RUN}")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_robustness(cmd: List[str], log_path: Path) -> None:
    with open(log_path, "a", encoding="utf-8") as log:
        rc = subprocess.call(cmd, stdout=log, stderr=subprocess.STDOUT)
    if rc != 0:
        raise SystemExit(f"robustness_experiment.py exited with {rc}; see {log_path}")


def run_eval(args) -> None:
    import torch

    paths = adapter_paths(args)
    out, repo = args.out, args.repo_root
    state = check_frozen(out, frozen_record(paths), args.resume)
    print(f"F4 {state}; output {out}", flush=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    gating = not args.smoke  # smoke runs use subsets: their numbers cannot match the full-run references

    # 1. Zero-shot v2_norm and Jaccard only, then the reproduction gate (no adapter has been scored yet).
    base: Dict[str, Any] = {}
    baseline = None
    for stage, fn in (("e1", e1_methods), ("e2", e2_methods)):
        path = out / f"{stage}_base.json"
        if path.exists():
            base[stage] = load_json(path)
            continue
        baseline = baseline or load_baseline(device)
        base[stage] = fn(baseline, repo, args.smoke, include_jaccard=True)
        write(path, base[stage])
    gates = gate_zero_shot(base, repo)
    write(out / "gates.json", gates)
    if gating and not all(g["ok"] for g in gates.values()):
        raise SystemExit(f"zero-shot v2_norm does not reproduce {REFERENCE_LOGIC_RUN}: {gates}. Stop and investigate before scoring any adapter.")
    if gating and not args.skip_robustness:
        gate_dir = out / "robustness_gate"
        if not (gate_dir / "metrics.json").exists():
            print("[robustness gate] zero-shot T0/T1", flush=True)
            run_robustness(robustness_command(paths, repo, out, args.smoke, args.resume, gate=True), out / "robustness_gate.log")
        rgate = robustness_summary(out, repo, run_name="robustness_gate")
        write(out / "robustness_gate.json", rgate["reproduction"])
        if not rgate["reproduction_ok"]:
            raise SystemExit(f"zero-shot robustness does not reproduce {REFERENCE_ROBUSTNESS_RUN}: {rgate['reproduction']}")

    # 2. The adapters.
    stages: Dict[str, Any] = {}
    adapters = None
    for stage, fn in (("e1", e1_methods), ("e2", e2_methods)):
        path = out / f"{stage}.json"
        if path.exists():
            stages[stage] = load_json(path)
            print(f"[{stage}] already done, skipped", flush=True)
            continue
        adapters = adapters or load_adapters(paths, device)
        res = fn(adapters, repo, args.smoke, include_jaccard=False)
        res["methods"] = {**base[stage]["methods"], **res["methods"]}
        stages[stage] = add_contrasts(res, stage)
        write(path, stages[stage])

    # 3. Robustness of the adapters (T0-T7 on the test pairs).
    rob = None
    if not args.skip_robustness:
        if not (out / "robustness" / "metrics.json").exists():
            print("[robustness] starting", flush=True)
            run_robustness(robustness_command(paths, repo, out, args.smoke, args.resume), out / "robustness.log")
        rob = robustness_summary(out, repo)
        write(out / "robustness_summary.json", rob)
    summary = final_summary(out, stages["e1"], stages["e2"], rob)
    print(json.dumps({k: summary[k] for k in ("H1", "H2", "H3") if k in summary}, indent=2, default=float))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("--repo-root", type=Path, default=DEFAULT_REPO)
        p.add_argument("--out", type=Path, default=Path(r"C:\Users\edani\datasets\codenet\f4"))
        p.add_argument("--adapter", action="append", default=[], metavar="ft_NAME=PATH", help="override a frozen adapter (smoke tests only)")
    r = sub.choices["run"]
    r.add_argument("--resume", action="store_true", help="continue the frozen run; finished stages are skipped")
    r.add_argument("--smoke", action="store_true", help="tiny plumbing check (use a scratch --out); gates are not enforced")
    r.add_argument("--skip-robustness", action="store_true")
    args = ap.parse_args()
    run_plan(args) if args.cmd == "plan" else run_eval(args)


if __name__ == "__main__":
    main()

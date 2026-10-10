#!/usr/bin/env python3
"""Benchmark suite: AUC / F1 / FPR for channel A (semantic), channel B (stylometry) and fused.

Reads a manifest produced by data/golden_set/build_manifest.py, scores every submission with
the selected engine (stub|real) and reports metrics at several semantic thresholds.

Channel A : score = calibrated similarity to the best reference of the same problem
            (in-memory top-1, mirrors query_nearest(top_k=1)), label = label_copy.
Channel B : score = ai_prob, label = label_ai.
Fused     : pred = dictamen != SIN_ALERTAS, label = copy OR ai, AUC score = max(sim, ai).

AUC is null (None) when a split has a single class. Results on the stub engine or on the
synthetic fixture are NOT evidence about the real models.

Usage:
    python scripts/benchmark_suite.py --manifest data/golden_set/manifest.json --engine stub
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.application.orchestrator.analysis_orchestrator import AnalysisOrchestrator  # noqa: E402
from app.config import settings  # noqa: E402

DEFAULT_THRESHOLDS_SEM = (0.85, 0.70)


# --------------------------------------------------------------------------- metrics
def auc(scores: Sequence[float], labels: Sequence[bool]) -> Optional[float]:
    """Mann-Whitney AUC (ties count 0.5). None if only one class is present."""
    pos = [s for s, l in zip(scores, labels) if l]
    neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg:
        return None
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def confusion(preds: Sequence[bool], labels: Sequence[bool]) -> Dict[str, int]:
    tp = sum(1 for p, l in zip(preds, labels) if p and l)
    fp = sum(1 for p, l in zip(preds, labels) if p and not l)
    tn = sum(1 for p, l in zip(preds, labels) if not p and not l)
    fn = sum(1 for p, l in zip(preds, labels) if not p and l)
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def f1_from(c: Dict[str, int]) -> float:
    denom = 2 * c["tp"] + c["fp"] + c["fn"]
    return (2 * c["tp"] / denom) if denom else 0.0


def fpr_from(c: Dict[str, int]) -> Optional[float]:
    neg = c["fp"] + c["tn"]
    return (c["fp"] / neg) if neg else None


def channel_metrics(scores: Sequence[float], preds: Sequence[bool], labels: Sequence[bool]) -> Dict[str, Any]:
    c = confusion(preds, labels)
    a = auc(scores, labels)
    return {
        "auc": None if a is None else round(a, 4),
        "f1": round(f1_from(c), 4),
        "fpr": None if fpr_from(c) is None else round(fpr_from(c), 4),
        **c,
    }


# --------------------------------------------------------------------------- scoring
def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5 or 1.0
    nb = sum(y * y for y in b) ** 0.5 or 1.0
    return max(0.0, min(1.0, dot / (na * nb)))


def make_engine(name: str):
    if name == "stub":
        from app.infrastructure.inference.stub_engine import StubInferenceEngine

        return StubInferenceEngine()
    from app.infrastructure.inference.real_engine import RealBimodalInferenceEngine

    return RealBimodalInferenceEngine()


async def score_manifest(manifest: Dict[str, Any], root: Path, engine) -> List[Dict[str, Any]]:
    """Return one scored record per submission: calibrated sim, ai_prob and labels."""
    samples = manifest["samples"]
    refs_by_problem: Dict[str, List[List[float]]] = {}
    for s in samples:
        if s["role"] == "reference":
            code = (root / s["path"]).read_text(encoding="utf-8", errors="replace")
            emb = await engine.extract_semantic_embedding(code, lang=s["lang"])
            refs_by_problem.setdefault(s["problem_id"], []).append(emb)

    scored: List[Dict[str, Any]] = []
    for s in samples:
        if s["role"] != "submission":
            continue
        code = (root / s["path"]).read_text(encoding="utf-8", errors="replace")
        emb = await engine.extract_semantic_embedding(code, lang=s["lang"])
        ai_prob = await engine.predict_synthetic_prob(code)
        refs = refs_by_problem.get(s["problem_id"], [])
        raw = max((_cosine(emb, r) for r in refs), default=0.0)
        scored.append(
            {
                "id": s["id"],
                "problem_id": s["problem_id"],
                "split": s["split"],
                "label_copy": bool(s["label_copy"]),
                "label_ai": bool(s["label_ai"]),
                "sim": AnalysisOrchestrator.calibrate_semantic_similarity(raw),
                "ai_prob": float(ai_prob),
            }
        )
    return scored


def evaluate(scored: List[Dict[str, Any]], engine, threshold_sem: float, threshold_ai: float) -> List[Dict[str, Any]]:
    runs = []
    for split in ("all", "dev", "test"):
        rows = scored if split == "all" else [r for r in scored if r["split"] == split]
        if not rows:
            continue
        sims = [r["sim"] for r in rows]
        ais = [r["ai_prob"] for r in rows]
        lab_copy = [r["label_copy"] for r in rows]
        lab_ai = [r["label_ai"] for r in rows]
        lab_any = [c or a for c, a in zip(lab_copy, lab_ai)]
        fused_pred = [
            engine.compute_decision(
                semantic_similarity=r["sim"],
                synthetic_prob=r["ai_prob"],
                threshold_sem=threshold_sem,
                threshold_ai=threshold_ai,
            )["dictamen"]
            != "SIN_ALERTAS"
            for r in rows
        ]
        runs.append(
            {
                "threshold_sem": threshold_sem,
                "split": split,
                "n": len(rows),
                "channel_a": channel_metrics(sims, [s >= threshold_sem for s in sims], lab_copy),
                "channel_b": channel_metrics(ais, [a >= threshold_ai for a in ais], lab_ai),
                "fused": channel_metrics([max(s, a) for s, a in zip(sims, ais)], fused_pred, lab_any),
            }
        )
    return runs


def run_suite(
    manifest: Dict[str, Any],
    root: Path,
    engine,
    engine_name: str,
    thresholds_sem: Sequence[float] = DEFAULT_THRESHOLDS_SEM,
    threshold_ai: Optional[float] = None,
    manifest_label: str = "",
) -> Dict[str, Any]:
    threshold_ai = settings.THRESHOLD_AI if threshold_ai is None else threshold_ai
    scored = asyncio.run(score_manifest(manifest, root, engine))
    runs: List[Dict[str, Any]] = []
    for t in thresholds_sem:
        runs.extend(evaluate(scored, engine, t, threshold_ai))
    return {
        "engine": engine_name,
        "manifest": manifest_label,
        "synthetic": bool(manifest.get("synthetic", False)) or engine_name == "stub",
        "threshold_ai": threshold_ai,
        "runs": runs,
    }


def print_table(result: Dict[str, Any]) -> None:
    def fmt(v):
        return "null" if v is None else f"{v:.3f}"

    print(f"engine={result['engine']} synthetic={result['synthetic']} threshold_ai={result['threshold_ai']}")
    print(f"{'thr_sem':>7} {'split':>5} {'n':>4} | {'chan':<8} {'AUC':>6} {'F1':>6} {'FPR':>6}")
    for r in result["runs"]:
        for chan in ("channel_a", "channel_b", "fused"):
            m = r[chan]
            print(f"{r['threshold_sem']:>7.2f} {r['split']:>5} {r['n']:>4} | {chan:<8} "
                  f"{fmt(m['auc']):>6} {fmt(m['f1']):>6} {fmt(m['fpr']):>6}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=None, help="Corpus root (default: manifest['root'])")
    parser.add_argument("--engine", choices=["stub", "real"], default="stub")
    parser.add_argument("--out", type=Path, default=Path("benchmark_suite_results.json"))
    parser.add_argument("--threshold-ai", type=float, default=None, help="Default: settings.THRESHOLD_AI")
    parser.add_argument("--thresholds-sem", type=float, nargs="+", default=list(DEFAULT_THRESHOLDS_SEM))
    parser.add_argument("--charcnn-checkpoint", type=Path, default=None,
                        help="Evaluate this CharCNN checkpoint instead of the deployed one (real engine only)")
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    root = args.root or Path(manifest["root"])
    engine = make_engine(args.engine)
    if args.charcnn_checkpoint:
        if args.engine != "real":
            parser.error("--charcnn-checkpoint requires --engine real")
        from models.char_cnn.inference import CharCNNInference

        engine.charcnn_engine = CharCNNInference(checkpoint_path=args.charcnn_checkpoint)
    result = run_suite(
        manifest, root, engine, args.engine, args.thresholds_sem, args.threshold_ai, str(args.manifest)
    )
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print_table(result)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

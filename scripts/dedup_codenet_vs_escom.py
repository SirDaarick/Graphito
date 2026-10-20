"""Near-duplicate check of the F0 CodeNet samples against the ESCOM evaluation corpus.

`prepare_codenet_contrastive.py` only compared against the 124 catalog programs. The guide
(`Documentacion/guias_implementacion/entrenamiento_contrastivo_codenet.md`, section 2) requires the
check against the ESCOM corpus used by E1, E2 and T1-T7 (`data/raw/src`). This script does it with
MinHash band candidates followed by an exact Jaccard on the 5-token shingle sets, reads the F0 outputs
and, with `--apply`, removes the flagged samples from `manifest.jsonl` and the `cache_<split>.pkl` files
(a `*.before_escom_dedup` copy of each is kept).

    python scripts/dedup_codenet_vs_escom.py --escom-src <repo>/data/raw/src [--apply]
"""

import argparse
import json
import pickle
import shutil
import sys
import time
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.evaluation.dedup import jaccard, make_permutations, minhash  # noqa: E402

BANDS, ROWS = 32, 4  # 128 permutations; high recall at Jaccard 0.8, the exact check removes false candidates
THRESHOLD = 0.8
CODE_EXTENSIONS = (".c", ".cpp", ".cc", ".h", ".hpp")


# --- pure helpers (tested) ----------------------------------------------------------------------


def band_candidates(query_sigs: np.ndarray, ref_sigs: np.ndarray, bands: int = BANDS, rows: int = ROWS) -> dict[int, set[int]]:
    """For each query row, the reference rows agreeing with it on every row of at least one band."""
    if bands * rows > query_sigs.shape[1] or bands * rows > ref_sigs.shape[1]:
        raise ValueError(f"bands*rows={bands * rows} exceeds the signature length")
    out: dict[int, set[int]] = {i: set() for i in range(query_sigs.shape[0])}
    for band in range(bands):
        lo, hi = band * rows, (band + 1) * rows
        buckets: dict[bytes, list[int]] = {}
        for j in range(ref_sigs.shape[0]):
            buckets.setdefault(np.ascontiguousarray(ref_sigs[j, lo:hi]).tobytes(), []).append(j)
        for i in range(query_sigs.shape[0]):
            out[i].update(buckets.get(np.ascontiguousarray(query_sigs[i, lo:hi]).tobytes(), ()))
    return out


def exact_matches(shingles: np.ndarray, candidates: Iterable[int], refs: Sequence[np.ndarray], threshold: float) -> dict[int, float]:
    """Candidate index -> exact Jaccard, for the candidates at or above `threshold`."""
    hits = {}
    for j in candidates:
        sim = jaccard(shingles, refs[j])
        if sim >= threshold:
            hits[j] = sim
    return hits


def filter_rows(rows: Sequence[Mapping], flagged: set[tuple[str, str]], min_accepted: int = 2):
    """Drop flagged (problem, submission_id) rows, then every problem left with < `min_accepted`
    Accepted rows. Returns (kept rows in input order, sorted dropped problem ids)."""
    survivors = [r for r in rows if (r["problem"], r["submission_id"]) not in flagged]
    accepted: dict[str, int] = {}
    for r in survivors:
        if r["role"] == "accepted":
            accepted[r["problem"]] = accepted.get(r["problem"], 0) + 1
    problems = {r["problem"] for r in rows}
    dropped = sorted(p for p in problems if accepted.get(p, 0) < min_accepted)
    kept = [r for r in survivors if r["problem"] not in set(dropped)]
    return kept, dropped


# --- I/O ----------------------------------------------------------------------------------------


def signatures(shingle_sets: Sequence[np.ndarray]) -> np.ndarray:
    a, b = make_permutations()
    return np.stack([minhash(s, a, b) for s in shingle_sets])


def escom_files(src: Path, catalog: Path | None) -> list[Path]:
    roots = [src] + ([catalog] if catalog else [])
    return sorted(p for r in roots for p in r.rglob("*") if p.is_file() and p.suffix.lower() in CODE_EXTENSIONS)


def main() -> None:
    from models.graphcodebert.v2.baselines import jaccard_set

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--codenet-root", type=Path, default=Path(r"C:\Users\edani\datasets\codenet"))
    ap.add_argument("--escom-src", type=Path, required=True, help="ESCOM student corpus (data/raw/src)")
    ap.add_argument("--catalog", type=Path, default=None, help="optional Programas_ESCOM catalog folder")
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--apply", action="store_true", help="rewrite manifest and caches without the flagged samples")
    ap.add_argument("--reuse-report", action="store_true", help="take the flagged samples from dedup_escom_corpus.json")
    args = ap.parse_args()

    f0 = args.codenet_root / "f0"
    rows = [json.loads(line) for line in (f0 / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    t0 = time.time()
    report_path = f0 / "dedup_escom_corpus.json"

    if args.reuse_report:  # apply a previous dry run without recomputing the shingles (~14 min)
        saved = json.loads(report_path.read_text(encoding="utf-8"))
        if saved["codenet_samples"] != len(rows):
            raise SystemExit("the saved report was computed for a different manifest; rerun without --reuse-report")
        flagged = {tuple(x) for x in saved["flagged"]}
        report = {k: v for k, v in saved.items() if k not in ("flagged", "applied")}
    else:
        refs_files = escom_files(args.escom_src, args.catalog)
        print(f"ESCOM reference files: {len(refs_files)}", flush=True)
        refs = [jaccard_set(p.read_text(encoding="utf-8", errors="replace")) for p in refs_files]
        print(f"ESCOM shingles done ({time.time() - t0:.0f}s)", flush=True)
        queries = [jaccard_set((args.codenet_root / r["path"]).read_text(encoding="utf-8", errors="replace")) for r in rows]
        print(f"CodeNet shingles done ({time.time() - t0:.0f}s)", flush=True)

        cands = band_candidates(signatures(queries), signatures(refs))
        flagged, sims = set(), []
        for i, r in enumerate(rows):
            hits = exact_matches(queries[i], cands[i], refs, args.threshold)
            sims.append(max(hits.values(), default=0.0))
            if hits:
                flagged.add((r["problem"], r["submission_id"]))
        report = {
            "escom_files": len(refs_files),
            "codenet_samples": len(rows),
            "threshold": args.threshold,
            "flagged_samples": len(flagged),
            "candidate_pairs": int(sum(len(c) for c in cands.values())),
            "max_similarity_among_flagged": float(max(sims, default=0.0)),
            "elapsed_s": round(time.time() - t0, 1),
        }
    print(json.dumps(report, indent=2))
    report_path.write_text(
        json.dumps({**report, "flagged": sorted(map(list, flagged)), "applied": bool(args.apply and flagged)}, indent=2),
        encoding="utf-8",
    )
    if not (args.apply and flagged):
        return

    kept, dropped_problems = filter_rows(rows, flagged)
    keep_ids = {(r["problem"], r["submission_id"]) for r in kept}
    for name in ("manifest.jsonl", "cache_train.pkl", "cache_val.pkl", "cache_test.pkl"):
        shutil.copy2(f0 / name, f0 / f"{name}.before_escom_dedup")
    (f0 / "manifest.jsonl").write_text("\n".join(json.dumps(r) for r in kept) + "\n", encoding="utf-8")
    for split in ("train", "val", "test"):
        path = f0 / f"cache_{split}.pkl"
        data = pickle.loads(path.read_bytes())
        path.write_bytes(pickle.dumps([d for d in data if (d["problem"], d["submission_id"]) in keep_ids], protocol=pickle.HIGHEST_PROTOCOL))
    print(f"applied: kept={len(kept)} dropped_problems={dropped_problems}")


if __name__ == "__main__":
    main()

"""F0 of the contrastive CodeNet experiment: manifest and cached `v2` inputs.

Reads the extracted Project CodeNet C++1000 benchmark (Accepted) and the Wrong Answer sample, keeps
the programs that fit ONE `v2` window, removes near-duplicates (Wrong Answer vs Accepted of the same
problem, everything vs `Programas_ESCOM`), splits by problem and writes:

- `manifest.jsonl`: one row per kept sample (problem, split, role, submission id, relative path, sha256).
- `cache_<split>.pkl`: the upstream-format `v2` features of every sample (no attention mask; rebuild
  it with `models.graphcodebert.v2.encode.build_attention_mask`).
- `stats.json`: parameters, counts per stage and the ESCOM similarity distribution.

See `Documentacion/guias_implementacion/entrenamiento_contrastivo_codenet.md` (F0). Run from the repo root:

    python scripts/prepare_codenet_contrastive.py
"""

import argparse
import hashlib
import json
import pickle
import random
import sys
import time
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.evaluation.dedup import jaccard  # noqa: E402

SPLITS = ("train", "val", "test")
WA_VS_ACCEPTED_THRESHOLD = 0.9  # guide F3: a near-identical Wrong Answer is not learnable
ESCOM_THRESHOLD = 0.8  # guide section 2 fixes the check, not the value
MAX_ACCEPTED_SCANNED = 150  # bounds parse time on problems where most programs are long


# --- pure helpers (tested) ----------------------------------------------------------------------


def split_problems(problem_ids: Sequence[str], seed: int = 0, val_fraction: float = 0.1, test_fraction: float = 0.1) -> dict[str, str]:
    """Deterministic split by problem (never by submission). Input order does not matter."""
    ids = sorted(problem_ids)
    random.Random(seed).shuffle(ids)
    n = len(ids)
    n_val = max(1, round(n * val_fraction)) if n >= 3 else 0
    n_test = max(1, round(n * test_fraction)) if n >= 3 else 0
    out = {}
    for i, pid in enumerate(ids):
        out[pid] = "val" if i < n_val else "test" if i < n_val + n_test else "train"
    return out


def max_similarity(shingles: np.ndarray, references: Sequence[np.ndarray]) -> float:
    """Highest exact Jaccard between one shingle set and a collection (0.0 when empty)."""
    return max((jaccard(shingles, r) for r in references), default=0.0)


def near_duplicate(shingles: np.ndarray, references: Sequence[np.ndarray], threshold: float) -> bool:
    """True when some reference has Jaccard >= `threshold` with `shingles`."""
    return bool(references) and max_similarity(shingles, references) >= threshold


def fits_one_window(features: Mapping[str, int]) -> bool:
    """True when `build_features` truncated neither the code subtokens nor the DFG nodes."""
    return features["n_code_kept"] == features["n_code_subtokens"] and features["n_dfg_kept"] == features["n_dfg"]


# --- data access --------------------------------------------------------------------------------


def read_code(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def featurize(code: str, tokenizer, config):
    """`v2` features for one program, or None when it has no code tokens after comment stripping."""
    from models.graphcodebert.v2.dfg import extract_dfg_v2
    from models.graphcodebert.v2.encode import build_features

    df = extract_dfg_v2(code, "cpp")
    if not df.code_tokens:
        return None
    f = build_features(df.code_tokens, df.dfg, tokenizer, config.code_length, config.data_flow_length)
    f["input_ids"] = np.asarray(f["input_ids"], dtype=np.int32)
    f["position_idx"] = np.asarray(f["position_idx"], dtype=np.int32)
    f.pop("source_tokens")  # derivable from input_ids; keeps the cache small
    return f


def escom_shingles(root: Path) -> list[np.ndarray]:
    from models.graphcodebert.v2.baselines import jaccard_set

    files = [p for ext in ("*.c", "*.cpp", "*.cc") for p in root.rglob(ext)]
    return [jaccard_set(read_code(p)) for p in sorted(files)]


def build_sample(path: Path, problem: str, role: str, codenet_root: Path, tokenizer, config):
    """A kept-candidate record (with shingles) or None when empty or not single-window."""
    from models.graphcodebert.v2.baselines import jaccard_set

    code = read_code(path)
    f = featurize(code, tokenizer, config)
    if f is None or not fits_one_window(f):
        return None
    return {
        "problem": problem,
        "role": role,
        "submission_id": path.stem,
        "path": path.relative_to(codenet_root).as_posix(),
        "sha256": hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest(),
        "features": f,
        "shingles": jaccard_set(code),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--codenet-root", type=Path, default=Path(r"C:\Users\edani\datasets\codenet"))
    ap.add_argument("--escom-root", type=Path, default=Path("Programas_ESCOM"))
    ap.add_argument("--out", type=Path, default=None, help="default: <codenet-root>/f0")
    ap.add_argument("--accepted-per-problem", type=int, default=20)
    ap.add_argument("--wa-per-problem", type=int, default=10)
    ap.add_argument("--limit-problems", type=int, default=None, help="smoke runs")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    from transformers import RobertaTokenizer

    from models.graphcodebert.v2.config import GCBV2Config
    from models.graphcodebert.v2.model import DEFAULT_MODEL

    root = args.codenet_root
    out = args.out or root / "f0"
    out.mkdir(parents=True, exist_ok=True)
    accepted_dir = root / "cpp1000" / "Project_CodeNet_C++1000"
    wa_dir = root / "wa" / "Project_CodeNet" / "data"

    config = GCBV2Config()
    tokenizer = RobertaTokenizer.from_pretrained(DEFAULT_MODEL, local_files_only=True)
    rng = random.Random(args.seed)
    t0 = time.time()

    escom = escom_shingles(args.escom_root)
    print(f"ESCOM reference programs: {len(escom)}")

    problems = sorted(d.name for d in accepted_dir.iterdir() if d.is_dir())
    if args.limit_problems:
        problems = problems[: args.limit_problems]

    stats = {
        "params": {
            "accepted_per_problem": args.accepted_per_problem,
            "wa_per_problem": args.wa_per_problem,
            "seed": args.seed,
            "wa_vs_accepted_threshold": WA_VS_ACCEPTED_THRESHOLD,
            "escom_threshold": ESCOM_THRESHOLD,
            "max_accepted_scanned": MAX_ACCEPTED_SCANNED,
            "code_length": config.code_length,
            "data_flow_length": config.data_flow_length,
        },
        "problems_total": len(problems),
        "dropped": {"not_single_window_or_empty": 0, "escom_near_duplicate": 0, "wa_near_duplicate_of_accepted": 0},
        "problems_dropped_lt2_accepted": 0,
    }
    escom_max = []
    kept: dict[str, list[dict]] = {}

    for i, pid in enumerate(problems, 1):
        files = sorted((accepted_dir / pid).glob("*.cpp"))
        rng.shuffle(files)
        accepted = []
        for path in files[:MAX_ACCEPTED_SCANNED]:
            if len(accepted) >= args.accepted_per_problem:
                break
            s = build_sample(path, pid, "accepted", root, tokenizer, config)
            if s is None:
                stats["dropped"]["not_single_window_or_empty"] += 1
                continue
            sim = max_similarity(s["shingles"], escom)
            escom_max.append(sim)
            if sim >= ESCOM_THRESHOLD:
                stats["dropped"]["escom_near_duplicate"] += 1
                continue
            accepted.append(s)
        if len(accepted) < 2:
            stats["problems_dropped_lt2_accepted"] += 1
            continue

        wrong = []
        acc_sets = [s["shingles"] for s in accepted]
        for path in sorted((wa_dir / pid / "C++").glob("*.cpp")):
            if len(wrong) >= args.wa_per_problem:
                break
            s = build_sample(path, pid, "wrong_answer", root, tokenizer, config)
            if s is None:
                stats["dropped"]["not_single_window_or_empty"] += 1
                continue
            if near_duplicate(s["shingles"], acc_sets, WA_VS_ACCEPTED_THRESHOLD):
                stats["dropped"]["wa_near_duplicate_of_accepted"] += 1
                continue
            if near_duplicate(s["shingles"], escom, ESCOM_THRESHOLD):
                stats["dropped"]["escom_near_duplicate"] += 1
                continue
            wrong.append(s)
        kept[pid] = accepted + wrong
        if i % 50 == 0:
            print(f"[{i}/{len(problems)}] kept problems={len(kept)} elapsed={time.time() - t0:.0f}s", flush=True)

    split = split_problems(list(kept), seed=args.seed)
    cache = {s: [] for s in SPLITS}
    with open(out / "manifest.jsonl", "w", encoding="utf-8") as mf:
        for pid, samples in sorted(kept.items()):
            for s in samples:
                mf.write(json.dumps({
                    "problem": pid, "split": split[pid], "role": s["role"],
                    "submission_id": s["submission_id"], "path": s["path"], "sha256": s["sha256"],
                }) + "\n")
                cache[split[pid]].append({
                    "problem": pid, "role": s["role"], "submission_id": s["submission_id"], "features": s["features"],
                })
    for name, rows in cache.items():
        with open(out / f"cache_{name}.pkl", "wb") as fh:
            pickle.dump(rows, fh, protocol=pickle.HIGHEST_PROTOCOL)

    stats["problems_kept"] = len(kept)
    stats["by_split"] = {
        name: {
            "problems": sum(v == name for v in split.values()),
            "accepted": sum(r["role"] == "accepted" for r in rows),
            "wrong_answer": sum(r["role"] == "wrong_answer" for r in rows),
        }
        for name, rows in cache.items()
    }
    stats["escom_max_similarity_accepted"] = {
        "n": len(escom_max),
        "p50": float(np.percentile(escom_max, 50)) if escom_max else None,
        "p99": float(np.percentile(escom_max, 99)) if escom_max else None,
        "max": float(max(escom_max)) if escom_max else None,
    }
    stats["elapsed_s"] = round(time.time() - t0, 1)
    (out / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()

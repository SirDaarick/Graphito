#!/usr/bin/env python3
"""Assemble the golden-set corpus layout from the IEEE Plagiarism dataset and the LLM output.

Produces the layout consumed by build_manifest.py:

    <out>/<problem_id>/{reference,original,copy,ai}/*.c|*.cpp

with problem_id = "<course>_<assignment>_<task>" (e.g. A2016_Z1_Z1).

Class sources:
    copy      : students listed in ground-truth-static-anon.txt (code-similarity plagiarism)
    original  : students in NO ground-truth file (static or dynamic); dynamic-only students are
                excluded because their label is ambiguous for a code-similarity benchmark
    reference : one held-out honest original per problem (deterministic, not reused as original)
    ai        : LLM files from data/output (empty and "name (1).c" duplicates are skipped)

Only problems that have both LLM files and student sources are kept. Human classes are capped
per problem (seeded) so the benchmark stays tractable.

Usage:
    python data/golden_set/build_corpus.py --out data/golden_set/corpus --seed 42
"""

import argparse
import hashlib
import random
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Set

HERE = Path(__file__).resolve().parent
DATA = HERE.parent
EXTENSIONS = {".c", ".cpp"}
MIN_BYTES = 50
DUPLICATE_NAME = re.compile(r"\s\(\d+\)")


def parse_ground_truth(path: Path) -> Dict[str, Set[str]]:
    """Return {"A2016/Z1/Z1": {"student1", ...}} for every listed (grouped or single) student."""
    result: Dict[str, Set[str]] = {}
    current = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("- "):
            current = line[2:].strip()
            result.setdefault(current, set())
        elif current is not None:
            result[current].update(s.strip() for s in line.split(",") if s.strip())
    return result


def usable(f: Path) -> bool:
    return (
        f.is_file()
        and f.suffix.lower() in EXTENSIONS
        and f.stat().st_size >= MIN_BYTES
        and not DUPLICATE_NAME.search(f.stem)
    )


def pick(files: List[Path], cap: int, rng: random.Random) -> List[Path]:
    files = sorted(files)
    return files if len(files) <= cap else sorted(rng.sample(files, cap))


def stable_rng(seed: int, key: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def copy_files(files: List[Path], dest: Path, prefix: str = "") -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(f, dest / f"{prefix}{f.name}")


def build_corpus(src: Path, ai_root: Path, gt_dir: Path, out: Path, seed: int, cap: int) -> Dict[str, int]:
    static = parse_ground_truth(gt_dir / "ground-truth-static-anon.txt")
    full = parse_ground_truth(gt_dir / "ground-truth-anon.txt")
    dynamic = parse_ground_truth(gt_dir / "ground-truth-dynamic-anon.txt")

    totals = {"problems": 0, "reference": 0, "original": 0, "copy": 0, "ai": 0, "skipped_problems": 0}
    for ai_problem in sorted(p for p in ai_root.glob("*/*/*") if p.is_dir()):
        key = "/".join(ai_problem.relative_to(ai_root).parts)  # A2016/Z1/Z1
        student_dir = src / key
        ai_files = [f for f in ai_problem.iterdir() if usable(f)]
        if not student_dir.is_dir() or not ai_files:
            totals["skipped_problems"] += 1
            continue

        problem_id = key.replace("/", "_")
        rng = stable_rng(seed, problem_id)
        students = [f for f in student_dir.iterdir() if usable(f)]
        flagged = static.get(key, set()) | full.get(key, set()) | dynamic.get(key, set())
        copies = [f for f in students if f.stem in static.get(key, set())]
        honest = [f for f in students if f.stem not in flagged]

        reference = pick(honest, 1, rng)
        originals = pick([f for f in honest if f not in reference], cap, rng)
        copies = pick(copies, cap, rng)

        base = out / problem_id
        copy_files(reference, base / "reference")
        copy_files(originals, base / "original")
        copy_files(copies, base / "copy")
        copy_files(ai_files, base / "ai", prefix="")

        totals["problems"] += 1
        totals["reference"] += len(reference)
        totals["original"] += len(originals)
        totals["copy"] += len(copies)
        totals["ai"] += len(ai_files)
    return totals


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, default=DATA / "raw" / "src")
    parser.add_argument("--ai", type=Path, default=DATA / "output")
    parser.add_argument("--ground-truth", type=Path, default=DATA / "raw")
    parser.add_argument("--out", type=Path, default=HERE / "corpus")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cap", type=int, default=10, help="Max originals and max copies per problem")
    parser.add_argument("--force", action="store_true", help="Delete --out first if it exists")
    args = parser.parse_args(argv)

    if args.out.exists():
        if not args.force:
            print(f"{args.out} already exists; pass --force to rebuild", file=sys.stderr)
            return 1
        shutil.rmtree(args.out)

    totals = build_corpus(args.src, args.ai, args.ground_truth, args.out, args.seed, args.cap)
    print(f"Corpus: {args.out}")
    print(totals)
    return 0


if __name__ == "__main__":
    sys.exit(main())

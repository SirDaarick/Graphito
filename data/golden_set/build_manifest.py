#!/usr/bin/env python3
"""Build a golden-set manifest from a corpus directory.

Expected layout (one root, passed on the command line; nothing is hardcoded):

    <root>/<problem_id>/<class>/*.c|*.cpp      with class in: reference | original | copy | ai

Class -> labels:
    reference : role=reference,  label_copy=False, label_ai=False
    original  : role=submission, label_copy=False, label_ai=False   (honest human work)
    copy      : role=submission, label_copy=True,  label_ai=False   (plagiarised human work)
    ai        : role=submission, label_copy=False, label_ai=True    (LLM-generated)

The dev/test split is by problem_id (sha256(seed:problem_id) against --test-ratio), so a
problem never spans two splits. Files with identical content (sha256) are deduplicated; the
first path in sorted order is kept.

Usage:
    python data/golden_set/build_manifest.py <root> --seed 42 --test-ratio 0.3 --out manifest.json
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

CLASSES = {
    "reference": {"role": "reference", "label_copy": False, "label_ai": False},
    "original": {"role": "submission", "label_copy": False, "label_ai": False},
    "copy": {"role": "submission", "label_copy": True, "label_ai": False},
    "ai": {"role": "submission", "label_copy": False, "label_ai": True},
}
EXTENSIONS = {".c": "c", ".cpp": "cpp"}
MIN_LLM_FILES_PER_PROBLEM = 6


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assign_split(problem_id: str, seed: int, test_ratio: float) -> str:
    digest = hashlib.sha256(f"{seed}:{problem_id}".encode("utf-8")).hexdigest()
    fraction = int(digest[:8], 16) / 0x100000000
    return "test" if fraction < test_ratio else "dev"


def build_manifest(root: Path, seed: int = 42, test_ratio: float = 0.3) -> Dict[str, Any]:
    """Scan `root` and return the manifest dict (deterministic given the inputs)."""
    root = Path(root)
    samples: List[Dict[str, Any]] = []
    seen_hashes: Dict[str, str] = {}
    duplicates: List[str] = []

    for problem_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        problem_id = problem_dir.name
        split = assign_split(problem_id, seed, test_ratio)
        for class_name, attrs in CLASSES.items():
            class_dir = problem_dir / class_name
            if not class_dir.is_dir():
                continue
            for f in sorted(class_dir.iterdir()):
                lang = EXTENSIONS.get(f.suffix.lower())
                if not f.is_file() or lang is None:
                    continue
                digest = sha256_bytes(f.read_bytes())
                rel = f.relative_to(root).as_posix()
                if digest in seen_hashes:
                    duplicates.append(rel)
                    continue
                seen_hashes[digest] = rel
                samples.append(
                    {
                        "id": rel,
                        "problem_id": problem_id,
                        "path": rel,
                        "lang": lang,
                        "role": attrs["role"],
                        "label_copy": attrs["label_copy"],
                        "label_ai": attrs["label_ai"],
                        "split": split,
                        "sha256": digest,
                    }
                )

    # No problem may appear in two splits.
    problem_splits: Dict[str, set] = {}
    for s in samples:
        problem_splits.setdefault(s["problem_id"], set()).add(s["split"])
    leaking = {p: sorted(v) for p, v in problem_splits.items() if len(v) > 1}
    assert not leaking, f"problems appear in more than one split: {leaking}"

    llm_per_problem = Counter(s["problem_id"] for s in samples if s["label_ai"])
    warnings = [
        f"problem '{p}' has {llm_per_problem.get(p, 0)} LLM files (< {MIN_LLM_FILES_PER_PROBLEM})"
        for p in sorted(problem_splits)
        if llm_per_problem.get(p, 0) < MIN_LLM_FILES_PER_PROBLEM
    ]

    return {
        "version": 1,
        "seed": seed,
        "test_ratio": test_ratio,
        "samples": samples,
        "duplicates_removed": duplicates,
        "counts": {
            "by_label": {
                "copy": sum(1 for s in samples if s["label_copy"]),
                "ai": sum(1 for s in samples if s["label_ai"]),
                "original": sum(
                    1 for s in samples if s["role"] == "submission" and not s["label_copy"] and not s["label_ai"]
                ),
                "reference": sum(1 for s in samples if s["role"] == "reference"),
            },
            "by_split": dict(Counter(s["split"] for s in samples)),
            "by_problem": dict(Counter(s["problem_id"] for s in samples)),
        },
        "warnings": warnings,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path, help="Corpus root: <root>/<problem_id>/<class>/*.c|cpp")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-ratio", type=float, default=0.3)
    parser.add_argument("--out", type=Path, default=Path("data/golden_set/manifest.json"))
    parser.add_argument("--synthetic", action="store_true", help="Mark the manifest as synthetic (not real data).")
    args = parser.parse_args(argv)

    manifest = build_manifest(args.root, seed=args.seed, test_ratio=args.test_ratio)
    manifest["root"] = str(args.root)
    manifest["synthetic"] = bool(args.synthetic)
    manifest["created_at"] = datetime.now(timezone.utc).isoformat()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Manifest: {args.out}  ({len(manifest['samples'])} samples, "
          f"{len(manifest['duplicates_removed'])} duplicates removed)")
    print(f"By label: {manifest['counts']['by_label']}")
    print(f"By split: {manifest['counts']['by_split']}")
    print(f"By problem: {manifest['counts']['by_problem']}")
    for w in manifest["warnings"]:
        print(f"WARNING: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

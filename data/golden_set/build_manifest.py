#!/usr/bin/env python3
"""Build a golden-set manifest from a corpus directory written by build_corpus.py.

Expected layout (one root, passed on the command line; nothing is hardcoded):

    <root>/<problem_id>/<class>/*.c|*.cpp      with class in: reference | original | copy | ai
    <root>/provenance.json                     written by build_corpus.py

Class -> labels:
    reference : role=reference,  label_copy=False, label_ai=False
    original  : role=submission, label_copy=False, label_ai=False   (honest human work)
    copy      : role=submission, label_copy=True,  label_ai=False   (plagiarised human work)
    ai        : role=submission, label_copy=False, label_ai=True    (LLM-generated)

Split and metadata come from `provenance.json` (split id, split, model, profile, dup_group,
cluster, gt_status), so the golden set follows the split manifest instead of hashing its own
split. Every corpus file must be listed there, and a `train` entry raises naming its id. Members
of one dup group are deduplicated (the first path in sorted order is kept). A corpus without
provenance (e.g. a hand-written fixture) needs `--synthetic`; its samples are tagged `test` and
byte-identical files of the same problem AND class are deduplicated by content sha256 (first
path in scan order kept); identical files in different problems or classes (an exact copy of its
original) are all kept.

The output is deterministic (no wall clock, sorted keys, LF), so rebuilding from the same
corpus gives byte-identical manifests that carry `source_manifest_sha256`.

Usage:
    python data/golden_set/build_manifest.py data/golden_set/corpus --out data/golden_set/manifest.json
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.evaluation.provenance import atomic_write_bytes  # noqa: E402

CLASSES = {
    "reference": {"role": "reference", "label_copy": False, "label_ai": False},
    "original": {"role": "submission", "label_copy": False, "label_ai": False},
    "copy": {"role": "submission", "label_copy": True, "label_ai": False},
    "ai": {"role": "submission", "label_copy": False, "label_ai": True},
}
EXTENSIONS = {".c": "c", ".cpp": "cpp"}
MIN_LLM_FILES_PER_PROBLEM = 6
PROVENANCE_FILE = "provenance.json"
META_KEYS = ("source", "model", "profile", "dup_group", "cluster_id", "gt_status", "assignment")


def load_provenance(root: Path) -> Optional[Dict[str, Any]]:
    path = Path(root) / PROVENANCE_FILE
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _content_group(path: Path) -> str:
    """Dedup key of a synthetic corpus file: the sha256 of its bytes."""
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_manifest(root: Path, synthetic: bool = False) -> Dict[str, Any]:
    """Scan `root` and return the manifest dict (deterministic given the inputs)."""
    root = Path(root)
    provenance = load_provenance(root)
    if provenance is None and not synthetic:
        raise ValueError(f"{root} has no {PROVENANCE_FILE}; rebuild it with build_corpus.py or pass --synthetic")
    files: Dict[str, Dict] = (provenance or {}).get("files", {})

    samples: List[Dict[str, Any]] = []
    seen_groups: Dict[str, str] = {}
    duplicates: List[str] = []
    for problem_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        problem_id = problem_dir.name
        for class_name, attrs in CLASSES.items():
            class_dir = problem_dir / class_name
            if not class_dir.is_dir():
                continue
            for f in sorted(class_dir.iterdir()):
                lang = EXTENSIONS.get(f.suffix.lower())
                if not f.is_file() or lang is None:
                    continue
                rel = f.relative_to(root).as_posix()
                if provenance is not None and rel not in files:
                    raise ValueError(f"corpus file {rel} is not listed in {PROVENANCE_FILE}")
                meta = files.get(rel, {})
                split = meta.get("split", "test")
                if split == "train":
                    raise ValueError(f"golden sample {rel} comes from train entry {meta.get('id')}")
                # provenance corpora dedup by the split manifest's dup_group; a synthetic corpus
                # has no provenance, so byte-identical files share a content-hash group instead,
                # scoped to one problem and class: an exact copy byte-identical to its original
                # or reference is a labelled positive, and other problems are independent
                if provenance is not None:
                    group = meta.get("dup_group")
                else:
                    group = f"{problem_id}/{class_name}/{_content_group(f)}"
                if group is not None:
                    if group in seen_groups:
                        duplicates.append(rel)
                        continue
                    seen_groups[group] = rel
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
                        "split_id": meta.get("id"),
                        **{k: meta.get(k) for k in META_KEYS},
                    }
                )

    missing = sorted(set(files) - {s["path"] for s in samples} - set(duplicates))
    if missing:
        raise ValueError(f"{PROVENANCE_FILE} lists files absent from the corpus: {missing[:5]}")

    problems = sorted({s["problem_id"] for s in samples})
    llm_per_problem = Counter(s["problem_id"] for s in samples if s["label_ai"])
    warnings = [
        f"problem '{p}' has {llm_per_problem.get(p, 0)} LLM files (< {MIN_LLM_FILES_PER_PROBLEM})"
        for p in problems
        if llm_per_problem.get(p, 0) < MIN_LLM_FILES_PER_PROBLEM
    ]

    return {
        "version": 2,
        "synthetic": bool(synthetic) or bool((provenance or {}).get("synthetic", False)),
        "source_split": (provenance or {}).get("split", "test"),
        "source_manifest_sha256": (provenance or {}).get("source_manifest_sha256"),
        "source_manifest_path": (provenance or {}).get("source_manifest_path"),
        "selection_seed": (provenance or {}).get("seed"),
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
            "by_split": dict(sorted(Counter(s["split"] for s in samples).items())),
            "by_problem": dict(sorted(Counter(s["problem_id"] for s in samples).items())),
        },
        "warnings": warnings,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path, help="Corpus root: <root>/<problem_id>/<class>/*.c|cpp")
    parser.add_argument("--out", type=Path, default=Path("data/golden_set/manifest.json"))
    parser.add_argument("--synthetic", action="store_true",
                        help="Allow a corpus without provenance.json (synthetic data, tagged split=test)")
    args = parser.parse_args(argv)

    try:
        manifest = build_manifest(args.root, synthetic=args.synthetic)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    manifest["root"] = args.root.as_posix()

    text = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    atomic_write_bytes(args.out, text.encode("utf-8"))

    print(f"Manifest: {args.out}  ({len(manifest['samples'])} samples, "
          f"{len(manifest['duplicates_removed'])} duplicates removed)")
    print(f"By label: {manifest['counts']['by_label']}")
    print(f"By split: {manifest['counts']['by_split']}")
    print(f"Source split manifest sha256: {manifest['source_manifest_sha256']}")
    for w in manifest["warnings"]:
        print(f"WARNING: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Assemble the golden-set corpus from ONE split of the split manifest (`data/splits/split_v1.json`).

Produces the layout consumed by build_manifest.py:

    <out>/<problem_id>/{reference,original,copy,ai}/*.c|*.cpp
    <out>/provenance.json

with problem_id = the manifest `assignment` with "/" -> "_" (e.g. A2016_Z1_Z1).

Only included entries of the requested split are used (excluded and `broken` entries are
dropped by the loader), so the golden set holds zero ids of any other split. `--split test` is
the benchmark set; `--split val` builds `corpus_val/`, used only to fit calibration. Train is
never accepted.

Class sources (labels come from the manifest `gt_status`; the ground truth is not re-parsed):
    copy      : humans with gt_status `positive` (in a static ground-truth cluster)
    original  : humans with gt_status `negative` (in no ground-truth file)
    reference : one honest (`negative`) human per problem, held out from `original`
    ai        : every AI entry of the problem
Humans with gt_status `ambiguous` (dynamic/full ground truth only) or `unlabeled` (courses
without ground truth, e.g. B2017) are skipped: their label is unknown.

Only problems with AI files and at least one labelled human are kept. Human classes are capped
per problem with a seeded, per-problem RNG, so the selection is deterministic for a seed.
`provenance.json` maps every corpus file to its split id, split, class, model, profile,
dup_group, cluster and gt_status, and records the sha256 of the source split manifest.

Usage:
    python data/golden_set/build_corpus.py --split test --force
    python data/golden_set/build_corpus.py --split val --force      # -> data/golden_set/corpus_val
"""

import argparse
import json
import random
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.evaluation.manifest import DEFAULT_MANIFEST, load_manifest  # noqa: E402
from models.evaluation.provenance import atomic_write_bytes  # noqa: E402
from models.evaluation.seed import stable_rng  # noqa: E402

PROVENANCE_SCHEMA = "graphito.golden_provenance/v1"
GOLDEN_SPLITS = ("test", "val")
CLASSES = ("reference", "original", "copy", "ai")


def default_out(split: str) -> Path:
    """`corpus/` for the test set, `corpus_<split>/` otherwise (gitignored)."""
    return HERE / ("corpus" if split == "test" else f"corpus_{split}")


def pick(samples: List, cap: int, rng: random.Random) -> List:
    samples = sorted(samples, key=lambda s: s.id)
    return samples if len(samples) <= cap else sorted(rng.sample(samples, cap), key=lambda s: s.id)


def _display_path(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).name


def _record(sample, cls: str) -> Dict:
    return {
        "id": sample.id,
        "split": sample.split,
        "class": cls,
        "assignment": sample.assignment,
        "source": sample.source,
        "lang": sample.lang,
        "model": sample.model,
        "profile": sample.profile,
        "dup_group": sample.dup_group,
        "cluster_id": sample.cluster_id,
        "gt_status": sample.gt_status,
    }


def build_corpus(
    split_manifest: "str | Path",
    split: str,
    out: "str | Path",
    *,
    repo_root: "str | Path" = ROOT,
    seed: int = 42,
    cap: int = 10,
    expected_sha256: Optional[str] = None,
) -> Dict[str, int]:
    """Write the golden corpus of `split` into `out` and return per-class totals."""
    if split not in GOLDEN_SPLITS:
        raise ValueError(f"the golden set is built from {GOLDEN_SPLITS} only, never {split!r} (train is refused)")
    manifest = load_manifest(split_manifest, expected_sha256)
    samples = manifest.samples(split)
    leaked = next((s for s in samples if s.split != split), None)
    if leaked is not None:  # defensive: the loader already filters by split
        raise ValueError(f"entry {leaked.id} is {leaked.split!r}, not {split!r}")

    by_problem: Dict[str, Dict[str, List]] = {}
    totals = {"problems": 0, "skipped_problems": 0, "skipped_unlabeled": 0, "skipped_ambiguous": 0}
    totals.update({cls: 0 for cls in CLASSES})
    for s in samples:
        bucket = by_problem.setdefault(s.assignment.replace("/", "_"), {"ai": [], "copy": [], "honest": []})
        if s.source == "ai":
            bucket["ai"].append(s)
        elif s.gt_status == "positive":
            bucket["copy"].append(s)
        elif s.gt_status == "negative":
            bucket["honest"].append(s)
        elif s.gt_status == "ambiguous":
            totals["skipped_ambiguous"] += 1
        else:
            totals["skipped_unlabeled"] += 1

    out, repo_root = Path(out), Path(repo_root)
    files: Dict[str, Dict] = {}
    for problem_id in sorted(by_problem):
        bucket = by_problem[problem_id]
        if not bucket["ai"] or not (bucket["copy"] or bucket["honest"]):
            totals["skipped_problems"] += 1
            continue
        rng = stable_rng(seed, problem_id)
        reference = pick(bucket["honest"], 1, rng)
        chosen = {
            "reference": reference,
            "original": pick([s for s in bucket["honest"] if s not in reference], cap, rng),
            "copy": pick(bucket["copy"], cap, rng),
            "ai": sorted(bucket["ai"], key=lambda s: s.id),
        }
        for cls in CLASSES:
            for s in chosen[cls]:
                rel = f"{problem_id}/{cls}/{Path(s.id).name}"
                if rel in files:
                    raise ValueError(f"two entries map to {rel}: {files[rel]['id']} and {s.id}")
                dest = out / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(repo_root / s.id, dest)
                files[rel] = _record(s, cls)
            totals[cls] += len(chosen[cls])
        totals["problems"] += 1

    provenance = {
        "schema": PROVENANCE_SCHEMA,
        "split": split,
        "seed": seed,
        "cap": cap,
        "source_manifest_path": _display_path(manifest.path),
        "source_manifest_sha256": manifest.sha256,
        "totals": totals,
        "files": files,
    }
    text = json.dumps(provenance, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    atomic_write_bytes(out / "provenance.json", text.encode("utf-8"))
    return totals


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--split", choices=GOLDEN_SPLITS, default="test",
                        help="test = benchmark set; val = calibration-fit set only")
    parser.add_argument("--repo-root", type=Path, default=ROOT, help="Base of the manifest's repo-relative ids")
    parser.add_argument("--out", type=Path, default=None, help="Default: data/golden_set/corpus (test) or corpus_val")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cap", type=int, default=10, help="Max originals and max copies per problem")
    parser.add_argument("--expected-sha256", default=None, help="Refuse a split manifest with another hash")
    parser.add_argument("--force", action="store_true", help="Delete --out first if it exists")
    args = parser.parse_args(argv)

    out = args.out or default_out(args.split)
    if out.exists():
        if not args.force:
            print(f"{out} already exists; pass --force to rebuild", file=sys.stderr)
            return 1
        shutil.rmtree(out)

    totals = build_corpus(
        args.split_manifest, args.split, out, repo_root=args.repo_root, seed=args.seed, cap=args.cap,
        expected_sha256=args.expected_sha256,
    )
    print(f"Corpus ({args.split}): {out}")
    print(totals)
    return 0


if __name__ == "__main__":
    sys.exit(main())

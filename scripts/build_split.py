#!/usr/bin/env python3
"""Build the deterministic train/val/test split manifest (data/splits/split_v1.json.gz).

Scans human (`data/raw/src`) and AI (`data/output`) submissions from disk, flags broken files,
groups exact and near duplicates, resolves ground-truth clusters and assigns whole blocks
(one assignment, years merged: course letter + Zx + Zy) to splits. The same inputs and seed
always produce byte-identical output. Per-stage timings are printed to stdout and never written
into the manifest. An `--out` ending in `.gz` is written as deterministic gzip (mtime 0, no file
name), anything else as plain JSON; the printed sha256 is over the decompressed JSON bytes, the
hash consumers record.

Usage:
    python scripts/build_split.py --seed 42
    python scripts/build_split.py --raw-root /tmp/tree/data/raw/src --ai-root ... --out x.json
"""

import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.evaluation.manifest import manifest_sha256  # noqa: E402
from models.evaluation.splits import SplitConfig, build_split, write_manifest  # noqa: E402

DEFAULT_OUT = Path("data") / "splits" / "split_v1.json.gz"
DEFAULT_AMBIGUOUS = (
    Path("data") / "raw" / "ground-truth-dynamic-anon.txt",
    Path("data") / "raw" / "ground-truth-anon.txt",
)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repo-root", type=Path, default=ROOT,
                        help="ids and recorded roots are relative to this directory")
    parser.add_argument("--raw-root", type=Path, help="human sources (default <repo>/data/raw/src)")
    parser.add_argument("--ai-root", type=Path, help="AI sources (default <repo>/data/output)")
    parser.add_argument("--gt-static", type=Path,
                        help="static ground truth (default <repo>/data/raw/ground-truth-static-anon.txt)")
    parser.add_argument("--gt-ambiguous", type=Path, action="append",
                        help="dynamic/full ground truth marking `ambiguous`; repeatable "
                             "(default: the dynamic and full files under <repo>/data/raw)")
    parser.add_argument("--out", type=Path, help=f"output manifest (default <repo>/{DEFAULT_OUT.as_posix()})")
    parser.add_argument("--workers", type=int, default=0,
                        help="file-analysis processes (0 = auto); does not change the output")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    repo = args.repo_root.resolve()
    ambiguous = args.gt_ambiguous if args.gt_ambiguous is not None else [repo / p for p in DEFAULT_AMBIGUOUS]
    config = SplitConfig(
        seed=args.seed,
        repo_root=repo,
        raw_root=args.raw_root,
        ai_root=args.ai_root,
        gt_static=args.gt_static,
        gt_ambiguous=tuple(ambiguous),
        workers=args.workers,
    )
    timings = {}
    start = time.perf_counter()
    try:
        manifest = build_split(config, timings)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    out = write_manifest(manifest, args.out or repo / DEFAULT_OUT)
    timings["total"] = round(time.perf_counter() - start, 3)

    for stage, seconds in timings.items():
        print(f"{stage:>16}: {seconds:8.3f} s")
    stats = manifest["stats"]
    print(f"entries: {stats['n_entries']} (included {stats['n_included']}), attempt {manifest['config']['attempt']}")
    print(f"wrote {out}")
    print(f"sha256 {manifest_sha256(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

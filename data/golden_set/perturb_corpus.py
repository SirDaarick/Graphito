#!/usr/bin/env python3
"""Apply a formatting/comment perturbation to a golden-set corpus (adversarial robustness check).

Reads  <src>/<problem_id>/{reference,original,copy,ai}/*.c|*.cpp
Writes <out>/<problem_id>/<class>/<same name>  with the transform applied to EVERY class, so the
transform itself cannot become the signal separating human from LLM code.

Transforms:
    none           : copy unchanged (control for the same problem filter)
    strip-comments : remove // and /* */ comments (string/char-literal aware, no dependencies)
    clang-format   : run `clang-format -style=Google` (needs the binary, e.g. `pip install clang-format`)

The source is a golden set rebuilt by build_corpus.py from the split manifest; its
`provenance.json` is copied next to the output. `--split-manifest <split_v1.json> --split test`
further restricts the output to problems (assignments) of that split; train is refused.

Usage:
    python data/golden_set/perturb_corpus.py --transform strip-comments \\
        --split-manifest data/splits/split_v1.json --split test \\
        --out data/golden_set/corpus_strip-comments
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional, Set

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.evaluation.manifest import load_manifest  # noqa: E402
from models.evaluation.normalize import strip_comments  # noqa: E402,F401  (re-exported)

CLASSES = ("reference", "original", "copy", "ai")
EXTENSIONS = {".c", ".cpp"}
PERTURB_SPLITS = ("test", "val")
PROVENANCE_FILE = "provenance.json"


def _clang_format_binary() -> str:
    found = shutil.which("clang-format")
    if found:
        return found
    try:
        from clang_format import get_executable  # type: ignore

        return get_executable("clang-format")
    except Exception:
        raise SystemExit("clang-format not found. Install it with: pip install clang-format")


def make_clang_format() -> Callable[[str, str], str]:
    binary = _clang_format_binary()

    def run(code: str, filename: str) -> str:
        proc = subprocess.run(
            [binary, "-style=Google", f"--assume-filename={filename}"],
            input=code.encode("utf-8", errors="replace"),
            capture_output=True,
            check=True,
        )
        return proc.stdout.decode("utf-8", errors="replace")

    return run


def problems_from_split(split_manifest: Path, split: str) -> Set[str]:
    """Problem ids (assignment with "/" -> "_") of the included entries of one split."""
    if split not in PERTURB_SPLITS:
        raise ValueError(f"perturbation runs on {PERTURB_SPLITS} only, never {split!r} (train is refused)")
    return {s.assignment.replace("/", "_") for s in load_manifest(split_manifest).samples(split)}


def build_perturbed(src: Path, out: Path, transform: str, only_problems: Optional[Set[str]] = None) -> int:
    if transform == "none":
        apply: Callable[[str, str], str] = lambda code, _name: code
    elif transform == "strip-comments":
        apply = lambda code, _name: strip_comments(code)
    elif transform == "clang-format":
        apply = make_clang_format()
    else:
        raise ValueError(f"unknown transform: {transform}")

    count = 0
    for problem_dir in sorted(p for p in Path(src).iterdir() if p.is_dir()):
        if only_problems is not None and problem_dir.name not in only_problems:
            continue
        for cls in CLASSES:
            class_dir = problem_dir / cls
            if not class_dir.is_dir():
                continue
            dest = Path(out) / problem_dir.name / cls
            dest.mkdir(parents=True, exist_ok=True)
            for f in sorted(class_dir.iterdir()):
                if not f.is_file() or f.suffix.lower() not in EXTENSIONS:
                    continue
                # newline="" keeps \r\n / \n untouched: Windows text mode would rewrite them
                with open(f, encoding="utf-8", errors="replace", newline="") as fh:
                    code = fh.read()
                with open(dest / f.name, "w", encoding="utf-8", newline="") as fh:
                    fh.write(apply(code, f.name))
                count += 1
    copy_provenance(Path(src), Path(out), only_problems)
    return count


def copy_provenance(src: Path, out: Path, only_problems: Optional[Set[str]] = None) -> None:
    """Copy `provenance.json`, keeping only the files of the selected problems."""
    path = src / PROVENANCE_FILE
    if not path.is_file():
        return
    out.mkdir(parents=True, exist_ok=True)
    if only_problems is None:
        shutil.copyfile(path, out / PROVENANCE_FILE)
        return
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["files"] = {rel: meta for rel, meta in doc["files"].items() if rel.split("/", 1)[0] in only_problems}
    text = json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    (out / PROVENANCE_FILE).write_bytes(text.encode("utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, default=HERE / "corpus")
    parser.add_argument("--transform", choices=["none", "strip-comments", "clang-format"], required=True)
    parser.add_argument("--out", type=Path, default=None, help="Default: data/golden_set/corpus_<transform>")
    parser.add_argument("--split-manifest", type=Path, default=None,
                        help="Split manifest (data/splits/split_v1.json): keep only problems of --split")
    parser.add_argument("--split", choices=PERTURB_SPLITS, default="test")
    parser.add_argument("--force", action="store_true", help="Delete --out first if it exists")
    args = parser.parse_args(argv)

    out = args.out or HERE / f"corpus_{args.transform}"
    if out.exists():
        if not args.force:
            print(f"{out} already exists; pass --force to rebuild", file=sys.stderr)
            return 1
        shutil.rmtree(out)

    only = problems_from_split(args.split_manifest, args.split) if args.split_manifest else None
    n = build_perturbed(args.src, out, args.transform, only)
    print(f"Wrote {n} files to {out}" + (f" ({len(only)} problems, split={args.split})" if only else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

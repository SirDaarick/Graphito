#!/usr/bin/env python3
"""Apply a formatting/comment perturbation to a golden-set corpus (adversarial robustness check).

Reads  <src>/<problem_id>/{reference,original,copy,ai}/*.c|*.cpp
Writes <out>/<problem_id>/<class>/<same name>  with the transform applied to EVERY class, so the
transform itself cannot become the signal separating human from LLM code.

Transforms:
    none           : copy unchanged (control for the same problem filter)
    strip-comments : remove // and /* */ comments (string/char-literal aware, no dependencies)
    clang-format   : run `clang-format -style=Google` (needs the binary, e.g. `pip install clang-format`)

`--only-problems-from <dataset_manifest.json> --split test` restricts the output to the
subproblems a CharCNN never saw in training, removing file-level leakage from the measurement.

Usage:
    python data/golden_set/perturb_corpus.py --transform strip-comments \\
        --only-problems-from models/char_cnn/dataset_manifest.json --split test \\
        --out data/golden_set/corpus_strip-comments
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, Optional, Set

HERE = Path(__file__).resolve().parent
CLASSES = ("reference", "original", "copy", "ai")
EXTENSIONS = {".c", ".cpp"}


def strip_comments(code: str) -> str:
    """Remove C/C++ comments, keeping string/char literals and the original line count."""
    out = []
    i, n = 0, len(code)
    while i < n:
        ch = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if ch in ('"', "'"):
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                c = code[i]
                out.append(c)
                i += 1
                if c == "\\" and i < n:
                    out.append(code[i])
                    i += 1
                elif c == quote or c == "\n":
                    break
        elif ch == "/" and nxt == "/":
            while i < n and code[i] != "\n":
                i += 1
        elif ch == "/" and nxt == "*":
            end = code.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.append(" " + "\n" * code.count("\n", i, end))
            i = end
        else:
            out.append(ch)
            i += 1
    return "".join(out)


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


def problems_from_manifest(manifest: Path, split: str) -> Set[str]:
    data = json.loads(Path(manifest).read_text(encoding="utf-8"))
    return {p.replace("/", "_") for p in data["subproblems"][split]}


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
    return count


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, default=HERE / "corpus")
    parser.add_argument("--transform", choices=["none", "strip-comments", "clang-format"], required=True)
    parser.add_argument("--out", type=Path, default=None, help="Default: data/golden_set/corpus_<transform>")
    parser.add_argument("--only-problems-from", type=Path, default=None, help="CharCNN dataset_manifest.json")
    parser.add_argument("--split", choices=["train", "val", "test"], default="test")
    parser.add_argument("--force", action="store_true", help="Delete --out first if it exists")
    args = parser.parse_args(argv)

    out = args.out or HERE / f"corpus_{args.transform}"
    if out.exists():
        if not args.force:
            print(f"{out} already exists; pass --force to rebuild", file=sys.stderr)
            return 1
        shutil.rmtree(out)

    only = problems_from_manifest(args.only_problems_from, args.split) if args.only_problems_from else None
    n = build_perturbed(args.src, out, args.transform, only)
    print(f"Wrote {n} files to {out}" + (f" ({len(only)} problems, split={args.split})" if only else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

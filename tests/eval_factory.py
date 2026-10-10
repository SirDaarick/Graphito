"""Synthetic corpus factory for the split builder tests (written into `tmp_path`, never real data).

Layout mirrors the real corpus: `data/raw/src/<course>/<Zx>/<Zy>/studentN.(c|cpp)` for human files,
`data/output/<course>/<Zx>/<Zy>/ref_<profile>_or-<model>_<date>_<time>_<NNNN>.(c|cpp)` for AI
files and `data/raw/ground-truth-*-anon.txt` for the ground truth. Course A is C, course B C++.

Planted cases (ids in `Tree.ids`):
- `gt_overlap_*`: two GT lines of A2016/Z1/Z1 sharing student1002 (merged into one cluster).
- `gt_missing`: student1999 listed in A2016/Z2/Z1 but absent on disk (unresolved member).
- `weird_ai`: AI file `weird.c` with an unparseable name.
- `copy_suffix`, `empty`, `too_short`, `comment_only`: broken files.
- `near_a`/`near_b`: same-block pair differing in comments, whitespace and variable names
  (both GT negatives of a headed assignment).
- `near_mid_*` (Jaccard ~0.86) and `near_low_*` (~0.82): same-block pairs that separate the
  0.80/0.85/0.90 sensitivity thresholds.
- `cross_exact`: identical code in every block of course A (one cross-block exact dup group).
- `cross_near_a`/`cross_near_b`: renamed copy in another block (cross-block near-dup).
- `repeat_student`: student1001 also submits in B2016 (repeated student id).
B2017 has no ground truth; A2017/Z6/Z1 has no GT header.
"""

import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

YEARS = ("2016", "2017")
STUDENT_BASE = {"A2016": 1000, "A2017": 2000, "B2016": 3000, "B2017": 4000}
STUDENTS = 4
PROFILES = ("aplicado", "comentado-basic")
MODELS = ("deepseek-chat", "kimi")
OPS = ("+", "-", "*", "/", "%", "<<", ">>", "&", "|", "^")
CMPS = ("<", ">", "<=", ">=", "==", "!=")


@dataclass
class Tree:
    repo_root: Path
    raw_root: Path
    ai_root: Path
    gt_static: Path
    gt_dynamic: Path
    ids: Dict[str, str] = field(default_factory=dict)  # name -> repo-relative id

    def path(self, name: str) -> Path:
        return self.repo_root / self.ids[name]


def _stmt(rng: random.Random, var: str, n_vars: int) -> str:
    def v() -> str:
        return f"{var}{rng.randrange(n_vars)}"

    kind = rng.randrange(5)
    a, b, c = v(), v(), v()
    op1, op2 = rng.choice(OPS), rng.choice(OPS)
    num = rng.randrange(1, 99)
    if kind == 0:
        return f"{a} = {b} {op1} {num} {op2} {c};"
    if kind == 1:
        return f"if ({a} {rng.choice(CMPS)} {b}) {{ {c} = {c} {op1} {num}; }}"
    if kind == 2:
        return f"for (i = 0; i < {num}; i++) {{ {a} {op1}= {b} {op2} i; }}"
    if kind == 3:
        return f"while ({a} {rng.choice(CMPS)} {num}) {{ {a} = {a} {op1} 1; {b}++; }}"
    return f"{a} = ({b} {op1} {c}) {op2} ({a} {rng.choice(OPS)} {num});"


def program(seed: str, lang: str, n_stmts: int = 30, var: str = "v", mutate: int = 0) -> str:
    """A random but deterministic C/C++ program; `mutate` regenerates that many statements."""
    rng = random.Random(seed)
    n_vars = 6
    body = [_stmt(rng, var, n_vars) for _ in range(n_stmts)]
    mutant = random.Random(f"{seed}:mutate")
    for k in range(mutate):
        body[(k * 7) % n_stmts] = _stmt(mutant, var, n_vars)
    decls = ", ".join(f"{var}{k} = {k + 1}" for k in range(n_vars))
    lines = [
        "#include <iostream>" if lang == "cpp" else "#include <stdio.h>",
        "int main(void) {",
        f"    int i, {decls};",
        *[f"    {s}" for s in body],
        f'    std::cout << {var}0 << std::endl;' if lang == "cpp" else f'    printf("%d\\n", {var}0);',
        "    return 0;",
        "}",
        "",
    ]
    return "\n".join(lines)


def disguise(code: str, old: str = "v", new: str = "zz") -> str:
    """Rename variables, add comments and reflow whitespace (same shingles, new norm_hash)."""
    out = ["/* resubmitted version */"]
    rename = re.compile(rf"\b{old}(\d+)\b")
    for line in code.splitlines():
        out.append("  " + rename.sub(rf"{new}\1", line).replace(" = ", "=") + "  // ok")
    return "\n".join(out) + "\n"


def _write(tree: Tree, rel: str, content: "str | bytes") -> str:
    path = tree.repo_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_bytes(content.encode("utf-8"))
    return rel


def make_tree(
    root: Path,
    *,
    n_blocks: int = 6,
    n_zy: int = 1,
    lang_b: str = "cpp",
    cpp_blocks: Optional[int] = None,
    planted: bool = True,
) -> Tree:
    """Write a synthetic corpus under `root` and return its paths and planted ids.

    Every course gets `n_blocks` topics Z1..Zn, each with `n_zy` assignments Z1..Zm (so a
    letter has `n_blocks * n_zy` split blocks, since years merge). `lang_b="c"` makes course
    B C-only; with `cpp_blocks=k` the first k topics of B2016 keep C++ files (used to build an
    unfillable lang stratum).
    """
    tree = Tree(
        repo_root=root,
        raw_root=root / "data" / "raw" / "src",
        ai_root=root / "data" / "output",
        gt_static=root / "data" / "raw" / "ground-truth-static-anon.txt",
        gt_dynamic=root / "data" / "raw" / "ground-truth-dynamic-anon.txt",
    )
    for letter in ("A", "B"):
        for year in YEARS:
            course = f"{letter}{year}"
            for z in range(1, n_blocks + 1):
                lang = "c" if letter == "A" else lang_b
                if letter == "B" and cpp_blocks is not None and course == "B2016" and z <= cpp_blocks:
                    lang = "cpp"
                for y in range(1, n_zy + 1):
                    folder = f"{course}/Z{z}/Z{y}"
                    for s in range(1, STUDENTS + 1):
                        student = f"student{STUDENT_BASE[course] + s}"
                        rel = f"data/raw/src/{folder}/{student}.{lang}"
                        _write(tree, rel, program(rel, lang))
                    profile = PROFILES[z % 2]
                    model = MODELS[(z + int(year)) % 2]
                    ai = f"ref_{profile}_or-{model}_20260714_2234{z:02d}_{z:04d}.{lang}"
                    rel = f"data/output/{folder}/{ai}"
                    _write(tree, rel, program(rel, lang))

    gt_lines: List[str] = []
    for course in ("A2016", "A2017", "B2016"):
        base = STUDENT_BASE[course]
        for z in range(1, n_blocks + 1):
            for y in range(1, n_zy + 1):
                if course == "A2017" and z == 6:
                    continue  # unheaded assignment of a labelled course
                gt_lines.append(f"- {course}/Z{z}/Z{y}")
                gt_lines.append(f"student{base + 1},student{base + 2}")
    if planted:
        _plant(tree, gt_lines, n_blocks)
    tree.gt_static.parent.mkdir(parents=True, exist_ok=True)
    tree.gt_static.write_bytes(("\n".join(gt_lines) + "\n").encode("utf-8"))
    tree.gt_dynamic.write_bytes(b"- A2016/Z3/Z1\nstudent1003\n")
    return tree


def _plant(tree: Tree, gt_lines: List[str], n_blocks: int) -> None:
    ids = tree.ids
    # Overlapping GT lines in A2016/Z1/Z1 (student1002 in both) and a missing member in Z2.
    z1 = gt_lines.index("- A2016/Z1/Z1")
    gt_lines.insert(z1 + 2, "student1002,student1003")
    z2 = gt_lines.index("- A2016/Z2/Z1")
    gt_lines.insert(z2 + 2, "student1004,student1999")
    ids["gt_overlap_a"] = "data/raw/src/A2016/Z1/Z1/student1001.c"
    ids["gt_overlap_b"] = "data/raw/src/A2016/Z1/Z1/student1003.c"
    ids["gt_missing_partner"] = "data/raw/src/A2016/Z2/Z1/student1004.c"

    ids["weird_ai"] = _write(tree, "data/output/A2016/Z3/Z1/weird.c", program("weird", "c"))
    ids["copy_suffix"] = _write(tree, "data/raw/src/A2016/Z4/Z1/x (1).c", program("copy", "c"))
    ids["empty"] = _write(tree, "data/raw/src/A2017/Z1/Z1/student2005.c", b"")
    ids["too_short"] = _write(tree, "data/raw/src/A2017/Z1/Z1/student2006.c", "int main(){return 0;}\n")
    ids["comment_only"] = _write(
        tree,
        "data/raw/src/A2017/Z1/Z1/student2007.c",
        "/* " + "nothing to see here " * 10 + "*/\n// still nothing\n",
    )

    near = program("near", "c")
    ids["near_a"] = _write(tree, "data/raw/src/A2016/Z5/Z1/student1003.c", near)
    ids["near_b"] = _write(tree, "data/raw/src/A2016/Z5/Z1/student1004.c", disguise(near))

    ids["near_mid_a"] = _write(tree, "data/raw/src/A2017/Z3/Z1/student2003.c", program("mid", "c", 40))
    ids["near_mid_b"] = _write(  # Jaccard ~0.86: merged at 0.80 and 0.85, not at 0.90
        tree, "data/raw/src/A2017/Z3/Z1/student2004.c", program("mid", "c", 40, mutate=4)
    )
    ids["near_low_a"] = _write(tree, "data/raw/src/A2017/Z4/Z1/student2003.c", program("low", "c", 40))
    ids["near_low_b"] = _write(  # Jaccard ~0.82: merged only at 0.80
        tree, "data/raw/src/A2017/Z4/Z1/student2004.c", program("low", "c", 40, mutate=5)
    )

    shared = program("cross-exact", "c")
    for z in range(1, n_blocks + 1):
        rel = _write(tree, f"data/raw/src/A2017/Z{z}/Z1/student2009.c", shared)
        ids[f"cross_exact_{z}"] = rel

    cross = program("cross-near", "cpp")
    ids["cross_near_a"] = _write(tree, "data/raw/src/B2016/Z1/Z1/student3004.cpp", cross)
    ids["cross_near_b"] = _write(tree, "data/raw/src/B2016/Z3/Z1/student3004.cpp", disguise(cross))

    ids["repeat_student"] = _write(
        tree, "data/raw/src/B2016/Z2/Z1/student1001.cpp", program("repeat", "cpp")
    )

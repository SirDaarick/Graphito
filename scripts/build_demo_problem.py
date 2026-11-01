"""Build the demo problem used in the teacher survey from the golden set (test split).

The submissions are drawn with a fixed seed from the labelled classes of one task, copied under
anonymous names and shuffled; two more are derived from the reference by renaming identifiers.
The answer key (class of each file) goes to `clave_privada.csv`, which is NOT given to teachers.

Usage: python scripts/build_demo_problem.py [--task A2017_Z4_Z1] [--seed 11] [--out DIR]
"""

import argparse
import csv
import random
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "golden_set" / "corpus"
DEFAULT_OUT = ROOT / "Documentacion" / "encuesta_docentes" / "problema_ejemplo"

N_HUMAN, N_COPY, N_AI = 5, 3, 3

C_RESERVED = set(
    """auto break case char const continue default do double else enum extern float for goto if int
    long register return short signed sizeof static struct switch typedef union unsigned void volatile
    while include define NULL main printf scanf abs strlen strcpy strcmp strcat malloc free calloc
    realloc puts gets fgets getchar putchar sprintf atoi exit EOF stdio stdlib string math h
    sqrt pow fabs FILE fopen fclose""".split()
)
_TOKEN = re.compile(
    r"//[^\n]*|/\*.*?\*/|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'|#[^\n]*|\b[A-Za-z_]\w*\b", re.S
)


def rename_identifiers(src: str) -> str:
    names: dict[str, str] = {}

    def sub(m: re.Match) -> str:
        t = m.group(0)
        if not (t[0].isalpha() or t[0] == "_") or t in C_RESERVED:
            return t
        return names.setdefault(t, f"v{len(names) + 1}")

    return _TOKEN.sub(sub, src)


def strip_comments_and_squeeze(src: str) -> str:
    src = re.sub(r"/\*.*?\*/|//[^\n]*", "", src, flags=re.S)
    return "\n".join(line.rstrip() for line in src.splitlines() if line.strip()) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="A2017_Z4_Z1")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()

    base = CORPUS / a.task
    rng = random.Random(a.seed)

    def pick(cls: str, n: int) -> list[Path]:
        files = sorted((base / cls).glob("*.c*"))
        return rng.sample(files, min(n, len(files)))

    ref = next((base / "reference").glob("*.c*"))
    items: list[tuple[str, str, str]] = []  # (clase, origen, contenido)
    for cls, n in (("original", N_HUMAN), ("copy", N_COPY), ("ai", N_AI)):
        for p in pick(cls, n):
            items.append((cls, p.name, p.read_text(errors="ignore")))
    ref_src = ref.read_text(errors="ignore")
    items.append(("derivada_renombrada", "referencia con identificadores renombrados", rename_identifiers(ref_src)))
    items.append(("derivada_sin_comentarios", "referencia renombrada, sin comentarios ni lineas en blanco",
                  strip_comments_and_squeeze(rename_identifiers(ref_src))))
    rng.shuffle(items)

    out = a.out
    if out.exists():
        shutil.rmtree(out)
    (out / "entregas").mkdir(parents=True)
    (out / "referencia.c").write_text(ref_src, encoding="utf-8")
    with open(out / "clave_privada.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["archivo", "clase", "origen"])
        for i, (cls, origin, src) in enumerate(items, 1):
            name = f"entrega_{i:02d}.c"
            (out / "entregas" / name).write_text(src, encoding="utf-8")
            w.writerow([name, cls, origin])
    print(f"{len(items)} entregas en {out / 'entregas'}; referencia: {ref.name}")


if __name__ == "__main__":
    main()

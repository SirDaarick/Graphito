"""Derived data for the CodeNet thesis figures (needs the raw datasets, the F3 adapter and a GPU).

`generate_codenet_figures.py` reads only small JSON files; the ones that cannot be read from the run
artifacts are computed here once and stored in `runs/contrastivo_codenet/derived/`:

- ``particiones.json``  samples and problems per split and role (after the ESCOM deduplication);
- ``longitud_programas.json``  non-empty lines per program: kept CodeNet samples vs the ESCOM E1 sample;
- ``coseno.json``  histograms of the cosine of val pairs (same problem / different problem), zero-shot and trained;
- ``proyeccion.json``  t-SNE of a few val problems, zero-shot and trained.

    python scripts/derive_codenet_figure_data.py            # all four
    python scripts/derive_codenet_figure_data.py --only particiones longitud_programas
"""

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

CODENET = Path(r"C:\Users\edani\datasets\codenet")
ESCOM_REPO = Path(r"C:\Users\edani\OneDrive\Documents\Proyectos\Graphito")  # holds the gitignored ESCOM data
HEADLINE_ADAPTER = CODENET / "f3" / "B_s1" / "adapter"
OUT = ROOT / "runs" / "contrastivo_codenet" / "derived"
SEED = 0


def write(name: str, doc) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"wrote {name}", flush=True)


def load_manifest() -> list[dict]:
    lines = (CODENET / "f0" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def particiones() -> None:
    rows = load_manifest()
    out = {}
    for split in ("train", "val", "test"):
        sel = [r for r in rows if r["split"] == split]
        out[split] = {
            "problemas": len({r["problem"] for r in sel}),
            "aceptados": sum(r["role"] == "accepted" for r in sel),
            "wrong_answer": sum(r["role"] == "wrong_answer" for r in sel),
        }
    write("particiones.json", out)


def non_empty_lines(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def longitud_programas() -> None:
    from models.logic_eval.data import load_e1_sample

    rows = load_manifest()
    codenet = [non_empty_lines(CODENET / r["path"]) for r in rows]
    sample = load_e1_sample(ESCOM_REPO / "data" / "splits" / "split_v1.json.gz", max_per_block=60, seed=42)
    escom = [non_empty_lines(ESCOM_REPO / it["id"]) for it in sample]
    write("longitud_programas.json", {"codenet": codenet, "escom": escom})


def val_embeddings(adapter):
    import torch

    import contrastive_f1 as f1
    from contrastive_train import load_eval_model

    rows = f1.load_cache(CODENET / "f0" / "cache_val.pkl")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_eval_model(device, adapter)
    emb = f1.embed_rows(model, rows, device)
    return rows, emb


def coseno() -> None:
    out = {"bins": [round(x, 4) for x in np.linspace(-0.2, 1.0, 61)]}
    for name, adapter in (("zero_shot", None), ("entrenado", HEADLINE_ADAPTER)):
        rows, emb = val_embeddings(adapter)
        problems = np.array([r["problem"] for r in rows])
        sim = emb @ emb.T
        iu = np.triu_indices(len(rows), 1)
        same = (problems[:, None] == problems[None, :])[iu]
        vals = sim[iu]
        bins = np.linspace(-0.2, 1.0, 61)
        out[name] = {
            "mismo_problema": np.histogram(vals[same], bins=bins)[0].tolist(),
            "otro_problema": np.histogram(vals[~same], bins=bins)[0].tolist(),
            "media_mismo": float(vals[same].mean()),
            "media_otro": float(vals[~same].mean()),
            "n_mismo": int(same.sum()),
            "n_otro": int((~same).sum()),
        }
    write("coseno.json", out)


def proyeccion() -> None:
    from sklearn.manifold import TSNE

    out: dict = {}
    chosen = None
    for name, adapter in (("zero_shot", None), ("entrenado", HEADLINE_ADAPTER)):
        rows, emb = val_embeddings(adapter)
        if chosen is None:  # the same problems in both panels
            counts: dict[str, dict[str, int]] = {}
            for r in rows:
                counts.setdefault(r["problem"], {"accepted": 0, "wrong_answer": 0})[r["role"]] += 1
            eligible = sorted(p for p, c in counts.items() if c["accepted"] >= 15 and c["wrong_answer"] >= 5)
            chosen = random.Random(SEED).sample(eligible, 6)
        idx = [i for i, r in enumerate(rows) if r["problem"] in chosen]
        xy = TSNE(n_components=2, perplexity=20, init="pca", random_state=SEED).fit_transform(emb[idx])
        out[name] = {
            "x": xy[:, 0].round(3).tolist(),
            "y": xy[:, 1].round(3).tolist(),
            "problema": [rows[i]["problem"] for i in idx],
            "rol": [rows[i]["role"] for i in idx],
        }
    out["problemas"] = chosen
    write("proyeccion.json", out)


STEPS = {"particiones": particiones, "longitud_programas": longitud_programas, "coseno": coseno, "proyeccion": proyeccion}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", nargs="+", choices=sorted(STEPS), default=sorted(STEPS))
    args = ap.parse_args()
    for name in args.only:
        STEPS[name]()


if __name__ == "__main__":
    main()

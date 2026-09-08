#!/usr/bin/env python3
"""
prepare_dataset.py — Construye el dataset etiquetado para CharCNN.

Etiquetas:
  0 = humano   (data/raw/src/)
  1 = sintético (data/output/)

Balancea por subproblema (course/assignment/subproblem) tomando la misma
cantidad de muestras humanas y sintéticas para condiciones justas.
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Optional

from models.char_cnn.config import CharCNNConfig


def collect_human_files(raw_dir: Path) -> list[Path]:
    files: list[Path] = []
    for ext in ("*.c", "*.cpp"):
        files.extend(raw_dir.rglob(ext))
    return sorted(files)


def collect_synthetic_files(synth_dir: Path) -> list[Path]:
    files: list[Path] = []
    for ext in ("*.c", "*.cpp"):
        files.extend(synth_dir.rglob(ext))
    return sorted(files)


def subproblem_key(file_path: Path, base_dir: Path) -> Optional[str]:
    try:
        rel = file_path.relative_to(base_dir)
        parts = rel.parts
        if len(parts) >= 3:
            return "/".join(parts[:3])
    except ValueError:
        pass
    return None


def build_manifest(config: CharCNNConfig) -> dict:
    raw_dir = config.raw_student_dir.resolve()
    synth_dir = config.synthetic_dir.resolve()

    human_files = collect_human_files(raw_dir)
    synth_files = collect_human_files(synth_dir)

    human_by_sp: dict[str, list[Path]] = defaultdict(list)
    for fp in human_files:
        key = subproblem_key(fp, raw_dir)
        if key:
            human_by_sp[key].append(fp)

    synth_by_sp: dict[str, list[Path]] = defaultdict(list)
    for fp in synth_files:
        key = subproblem_key(fp, synth_dir)
        if key:
            synth_by_sp[key].append(fp)

    rng = random.Random(config.seed)
    samples: list[dict] = []

    common_keys = sorted(set(human_by_sp) & set(synth_by_sp))
    print(f"Subproblemas con ambas fuentes: {len(common_keys)}")

    for key in common_keys:
        human_candidates = human_by_sp[key]
        synth_candidates = synth_by_sp[key]
        limit = min(
            len(human_candidates),
            len(synth_candidates),
            config.max_samples_per_subproblem,
        )

        selected_human = rng.sample(human_candidates, limit)
        selected_synth = rng.sample(synth_candidates, limit)

        for fp in selected_human:
            samples.append({"file_path": str(fp.resolve()), "label": 0, "subproblem": key})
        for fp in selected_synth:
            samples.append({"file_path": str(fp.resolve()), "label": 1, "subproblem": key})

    human_only = sorted(set(human_by_sp) - set(synth_by_sp))
    synth_only = sorted(set(synth_by_sp) - set(human_by_sp))
    print(f"Subproblemas solo humanos:  {len(human_only)} ({', '.join(human_only[:5])}{'...' if len(human_only) > 5 else ''})")
    print(f"Subproblemas solo sintéticos: {len(synth_only)} ({', '.join(synth_only[:5])}{'...' if len(synth_only) > 5 else ''})")

    rng.shuffle(samples)

    n = len(samples)
    n_test = int(n * config.test_split)
    n_val = int(n * config.val_split)
    n_train = n - n_val - n_test

    human_count = sum(1 for s in samples if s["label"] == 0)
    synth_count = sum(1 for s in samples if s["label"] == 1)
    print(f"\nTotal samples: {n}")
    print(f"  Humano:    {human_count}")
    print(f"  Sintético: {synth_count}")
    print(f"Split: train={n_train} / val={n_val} / test={n_test}")

    manifest = {
        "config": {
            "raw_student_dir": str(raw_dir),
            "synthetic_dir": str(synth_dir),
            "max_samples_per_subproblem": config.max_samples_per_subproblem,
            "seed": config.seed,
            "alphabet": config.alphabet,
            "seq_length": config.seq_length,
        },
        "splits": {
            "train": samples[:n_train],
            "val": samples[n_train : n_train + n_val],
            "test": samples[n_train + n_val :],
        },
        "stats": {
            "total": n,
            "human": human_count,
            "synthetic": synth_count,
            "subproblems_with_both": len(common_keys),
            "subproblems_human_only": len(human_only),
            "subproblems_synthetic_only": len(synth_only),
        },
    }

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepara dataset balanceado para CharCNN")
    parser.add_argument("--max-samples", type=int, default=200,
                        help="Máximo de muestras por subproblema y clase")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=None,
                        help="Ruta del manifest de salida")
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--synth-dir", type=Path, default=None)
    args = parser.parse_args()

    config = CharCNNConfig()
    config.seed = args.seed
    config.max_samples_per_subproblem = args.max_samples
    if args.raw_dir:
        config.raw_student_dir = args.raw_dir
    if args.synth_dir:
        config.synthetic_dir = args.synth_dir
    if args.output:
        config.manifest_path = args.output

    manifest = build_manifest(config)

    config.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nManifest guardado en: {config.manifest_path.resolve()}")


if __name__ == "__main__":
    main()

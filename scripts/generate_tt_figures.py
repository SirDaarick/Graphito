#!/usr/bin/env python3
"""Generate the thesis (TT) figures from evaluation run artifacts.

Every number drawn comes from a run directory; the script holds no metric values.

Figures (written to ``--out-dir``):
  1. ``curvas_entrenamiento_charcnn.png``: CharCNN training curves from ``history.csv``
     (train loss, val ROC-AUC and val PR-AUC per epoch, with the selected epoch marked).
  2. ``matriz_confusion_charcnn.png``: CharCNN test confusion matrix at the primary
     operating point of ``metrics.json``.
  3. ``comparativa_canal_a.png``: Channel A methods (v2, v2_nodfg, jaccard, winnowing,
     legacy) on the ``__all`` view: ROC-AUC, PR-AUC and MAP@R with 95% CIs.

The old ESCOM benchmark and stylometric invariance bars had no metrics source (their values
were literals) and were removed rather than faked.

Usage (from the repository root):
  python scripts/generate_tt_figures.py \
      --charcnn-run runs/char_cnn/20261011-015734 \
      --gcb-run runs/graphcodebert/20261011-082155

A missing ``metrics.json`` is an error (exit 1). ``history.csv`` is not tracked in git, so a
missing history only skips the training-curves figure, with a message.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

DEFAULT_OUT_DIR = Path("Documentacion/Documento/figuras")
CURVES_FIGURE = "curvas_entrenamiento_charcnn.png"
CONFUSION_FIGURE = "matriz_confusion_charcnn.png"
CHANNEL_A_FIGURE = "comparativa_canal_a.png"
GCB_METHODS = ("v2", "v2_nodfg", "jaccard", "winnowing", "legacy")
GCB_VIEW = "all"

STYLE = {
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.dpi": 300,
}


class RunNotFoundError(FileNotFoundError):
    """A required run artifact is missing; figures are never drawn from defaults."""


@dataclass(frozen=True)
class CharCNNRun:
    path: Path
    metrics: dict
    history: pd.DataFrame | None


@dataclass(frozen=True)
class Confusion:
    key: str
    threshold: float
    tn: int
    fp: int
    fn: int
    tp: int


@dataclass(frozen=True)
class MethodMetrics:
    method: str
    roc_auc: float | None
    roc_auc_ci: tuple[float, float] | None
    pr_auc: float | None
    pr_auc_ci: tuple[float, float] | None
    map_at_r: float | None
    map_at_r_ci: tuple[float, float] | None


def _read_metrics(path: Path) -> dict:
    if not path.is_file():
        raise RunNotFoundError(f"missing run artifact: {path} (pass an existing run directory)")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_charcnn_run(run_dir: Path) -> CharCNNRun:
    run_dir = Path(run_dir)
    metrics = _read_metrics(run_dir / "metrics.json")
    history_path = run_dir / "history.csv"
    history = pd.read_csv(history_path) if history_path.is_file() else None
    return CharCNNRun(path=run_dir, metrics=metrics, history=history)


def _value_ci(block: dict | None) -> tuple[float | None, tuple[float, float] | None]:
    if not block:
        return None, None
    ci = block.get("ci95")
    return block.get("value"), (tuple(ci) if ci else None)


def load_gcb_run(run_dir: Path) -> list[MethodMetrics]:
    run_dir = Path(run_dir)
    rows = []
    for method in GCB_METHODS:
        metrics = _read_metrics(run_dir / f"{method}__{GCB_VIEW}" / "metrics.json")
        tf = metrics.get("threshold_free", {})
        roc, roc_ci = _value_ci(tf.get("roc_auc"))
        pr, pr_ci = _value_ci(tf.get("pr_auc"))
        mapr, mapr_ci = _value_ci(tf.get("map_at_r"))
        rows.append(MethodMetrics(method, roc, roc_ci, pr, pr_ci, mapr, mapr_ci))
    return rows


def confusion_from_metrics(metrics: dict) -> Confusion:
    points = metrics.get("operating_points") or {}
    primary = [(k, p) for k, p in points.items() if p.get("primary")]
    if len(primary) != 1:
        raise ValueError(f"expected exactly one primary operating point, found {len(primary)}")
    key, point = primary[0]
    obs = point["observed"]
    return Confusion(key, point["threshold"], int(obs["tn"]), int(obs["fp"]), int(obs["fn"]), int(obs["tp"]))


def plot_training_curves(run: CharCNNRun, out_dir: Path) -> Path | None:
    if run.history is None:
        print(f"Omitida {CURVES_FIGURE}: no existe {run.path / 'history.csv'} (no se versiona en git).")
        return None
    df = run.history
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    ax1.plot(df["epoch"], df["train_loss"], "o-", color="#1f77b4", label="Pérdida de entrenamiento", markersize=3)
    ax1.set_xlabel("Época")
    ax1.set_ylabel("Pérdida")
    ax1.set_title("Pérdida de entrenamiento")
    ax2.plot(df["epoch"], df["val_roc_auc"], "o-", color="#2ca02c", label="ROC-AUC (val)", markersize=3)
    ax2.plot(df["epoch"], df["val_pr_auc"], "s--", color="#ff7f0e", label="PR-AUC (val)", markersize=3)
    ax2.set_xlabel("Época")
    ax2.set_ylabel("Métrica")
    ax2.set_title("Métricas de validación")
    selected = run.metrics.get("selected_epoch")
    for ax in (ax1, ax2):
        if selected is not None:
            ax.axvline(x=selected, color="gray", linestyle=":", label=f"Época seleccionada ({selected})")
        ax.legend(frameon=True)
        ax.grid(True, alpha=0.3)
    return _save(fig, out_dir / CURVES_FIGURE)


def plot_confusion_matrix(run: CharCNNRun, out_dir: Path) -> Path:
    cm = confusion_from_metrics(run.metrics)
    counts = np.array([[cm.tn, cm.fp], [cm.fn, cm.tp]])
    row_totals = counts.sum(axis=1, keepdims=True)
    pct = np.divide(counts * 100, row_totals, out=np.zeros(counts.shape, dtype=float), where=row_totals > 0)
    labels = ["Humano", "Sintético (IA)"]
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(counts, cmap="Blues")
    fig.colorbar(im, ax=ax)
    for i in range(2):
        for j in range(2):
            color = "white" if counts[i, j] > counts.max() / 2 else "black"
            ax.text(j, i, f"{counts[i, j]}\n({pct[i, j]:.1f}%)", ha="center", va="center", color=color, weight="bold")
    ax.set_xticks([0, 1], labels)
    ax.set_yticks([0, 1], labels)
    ax.set_xlabel("Clase predicha")
    ax.set_ylabel("Clase real")
    split = run.metrics.get("split", "test")
    ax.set_title(f"Matriz de confusión CharCNN ({split})\nPunto de operación {cm.key}, umbral {cm.threshold:.4g}", pad=12)
    return _save(fig, out_dir / CONFUSION_FIGURE)


def plot_channel_a_comparison(rows: list[MethodMetrics], out_dir: Path) -> Path:
    series = (
        ("ROC-AUC", "roc_auc", "#3498db"),
        ("PR-AUC", "pr_auc", "#2ecc71"),
        ("MAP@R", "map_at_r", "#9b59b6"),
    )
    x = np.arange(len(rows))
    width = 0.27
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for offset, (label, attr, color) in zip((-width, 0, width), series):
        values = [getattr(r, attr) for r in rows]
        cis = [getattr(r, f"{attr}_ci") for r in rows]
        heights = [v if v is not None else 0 for v in values]
        # Percentile CIs need not bracket the point estimate; clamp so error bars stay valid.
        lower = [max(v - ci[0], 0) if (v is not None and ci) else 0 for v, ci in zip(values, cis)]
        upper = [max(ci[1] - v, 0) if (v is not None and ci) else 0 for v, ci in zip(values, cis)]
        bars = ax.bar(x + offset, heights, width, label=label, color=color, yerr=[lower, upper], capsize=3)
        for bar, v, up in zip(bars, values, upper):
            text = "n/d" if v is None else f"{v:.3f}"
            y = bar.get_height() + up + 0.01
            ax.text(bar.get_x() + bar.get_width() / 2, y, text, ha="center", va="bottom", fontsize=7, rotation=90)
    ax.set_xticks(x, [r.method for r in rows])
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Valor (IC 95%)")
    ax.set_title("Canal A: comparación de métodos (vista completa, test)")
    ax.legend(frameon=True, loc="upper right")
    ax.grid(True, axis="y", alpha=0.3)
    return _save(fig, out_dir / CHANNEL_A_FIGURE)


def _save(fig, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Guardado: {path}")
    return path


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--charcnn-run", type=Path, required=True, help="runs/char_cnn/<run> directory")
    parser.add_argument("--gcb-run", type=Path, required=True, help="runs/graphcodebert/<run> directory")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="output directory for the PNGs")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        charcnn = load_charcnn_run(args.charcnn_run)
        gcb = load_gcb_run(args.gcb_run)
        confusion_from_metrics(charcnn.metrics)
    except (RunNotFoundError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(STYLE):
        plot_training_curves(charcnn, args.out_dir)
        plot_confusion_matrix(charcnn, args.out_dir)
        plot_channel_a_comparison(gcb, args.out_dir)
    print(f"Figuras generadas en: {args.out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

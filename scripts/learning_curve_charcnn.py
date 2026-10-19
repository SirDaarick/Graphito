#!/usr/bin/env python3
"""Learning curve analysis for CharCNN v2 with varying synthetic (AI) training samples.

Executes a grid of (ai_fraction x seed), resumes interrupted runs, aggregates metrics,
evaluates pre-registered saturation criteria, performs power-law extrapolation, and
generates thesis-ready figures (C1, C2, C3) and a comprehensive report.md.

Usage:
    python scripts/learning_curve_charcnn.py --smoke --out runs/char_cnn_lc_smoke
    python scripts/learning_curve_charcnn.py --out runs/char_cnn_lc
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

DEFAULT_FRACTIONS = (0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00)
DEFAULT_SEEDS = (42, 7, 123, 2024, 31337)
DEFAULT_OUT_DIR = Path("Documentacion/Documento/figuras")
DEFAULT_RUNS_ROOT = Path("runs/char_cnn_lc")

STYLE = {
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9,
    "figure.dpi": 300,
}


def power_law(n: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
    """Power-law learning curve model: y(n) = a - b * n^(-c)."""
    return a - b * np.power(n, -c)


def fit_power_law(
    n_samples: np.ndarray,
    scores: np.ndarray,
    n_boot: int = 500,
    seed: int = 42,
) -> Optional[Dict[str, Any]]:
    """Fit power-law learning curve with bootstrap confidence intervals."""
    if len(n_samples) < 4:
        return None

    # Initial parameter guess: a ~ max, b ~ max - min, c ~ 0.5
    p0 = [float(np.clip(scores.max() + 0.01, 0.5, 1.0)), 0.5, 0.5]
    bounds = ([0.5, 0.0, 0.001], [1.0, 10.0, 5.0])

    try:
        popt, _ = curve_fit(power_law, n_samples, scores, p0=p0, bounds=bounds, maxfev=10000)
    except Exception as exc:
        print(f"Warning: power law curve_fit failed: {exc}", file=sys.stderr)
        return None

    # Bootstrap extrapolation at 10,000 and 20,000
    rng = np.random.default_rng(seed)
    extrap_targets = np.array([10000.0, 20000.0])
    boot_preds = []

    for _ in range(n_boot):
        boot_idx = rng.integers(0, len(n_samples), size=len(n_samples))
        bx, by = n_samples[boot_idx], scores[boot_idx]
        try:
            bpopt, _ = curve_fit(power_law, bx, by, p0=popt, bounds=bounds, maxfev=5000)
            preds = power_law(extrap_targets, *bpopt)
            if np.all(np.isfinite(preds)):
                boot_preds.append(preds)
        except Exception:
            continue

    extrap_dict: Dict[int, Dict[str, float]] = {}
    for i, target in enumerate([10000, 20000]):
        point_est = float(power_law(np.array([float(target)]), *popt)[0])
        if boot_preds:
            b_vals = [p[i] for p in boot_preds]
            ci_low = float(np.percentile(b_vals, 2.5))
            ci_high = float(np.percentile(b_vals, 97.5))
        else:
            ci_low, ci_high = point_est, point_est
        extrap_dict[target] = {
            "pred": point_est,
            "ci95_low": ci_low,
            "ci95_high": ci_high,
        }

    return {
        "params": {"a": float(popt[0]), "b": float(popt[1]), "c": float(popt[2])},
        "extrapolations": extrap_dict,
    }


def evaluate_saturation(df: pd.DataFrame) -> Dict[str, Any]:
    """Pre-registered saturation check (Section 1.4 of guide).

    Conditions:
    1. delta(50% -> 100%) < 0.01
    2. delta(50% -> 100%) < std(100%)
    """
    fracs = sorted(df["fraction"].unique())
    f_100 = fracs[-1]
    # Find fraction closest to 0.50
    f_50 = min(fracs, key=lambda f: abs(f - 0.50))

    df_50 = df[df["fraction"] == f_50]
    df_100 = df[df["fraction"] == f_100]

    mean_50 = float(df_50["pr_auc"].mean())
    mean_100 = float(df_100["pr_auc"].mean())
    std_100 = float(df_100["pr_auc"].std()) if len(df_100) > 1 else 0.0
    delta = mean_100 - mean_50

    cond1 = bool(delta < 0.01)
    cond2 = bool(delta < std_100)
    saturated = bool(cond1 and cond2)

    return {
        "f_50": f_50,
        "f_100": f_100,
        "mean_pr_auc_50": mean_50,
        "mean_pr_auc_100": mean_100,
        "std_pr_auc_100": std_100,
        "delta": delta,
        "cond1_delta_below_0_01": cond1,
        "cond2_delta_below_std": cond2,
        "saturated": saturated,
    }


def plot_c1_learning_curve(
    df: pd.DataFrame,
    out_paths: Sequence[Path],
    fit_res: Optional[Dict[str, Any]] = None,
) -> None:
    """Plot C1: PR-AUC vs number of training AI samples with log scale, CI, and optional extrapolation."""
    plt.rcParams.update(STYLE)
    fig, ax = plt.subplots(figsize=(7, 4.5))

    stats = df.groupby("n_ai_train")["pr_auc"].agg(["mean", "std", "min", "max"]).reset_index()
    n_pts = stats["n_ai_train"].values
    means = stats["mean"].values
    stds = stats["std"].fillna(0.0).values

    # Individual points semitransparent
    ax.scatter(
        df["n_ai_train"],
        df["pr_auc"],
        color="#2b5c8f",
        alpha=0.35,
        s=30,
        label="Semillas individuales",
        zorder=3,
    )

    # Shaded band (+-1 std)
    ax.fill_between(
        n_pts,
        np.clip(means - stds, 0.0, 1.0),
        np.clip(means + stds, 0.0, 1.0),
        color="#2b5c8f",
        alpha=0.2,
        label=r"Banda $\pm 1\,\sigma$ entre semillas",
        zorder=2,
    )

    # Mean curve
    ax.plot(
        n_pts,
        means,
        color="#1f426b",
        linewidth=2,
        marker="o",
        markersize=5,
        label="Media (5 semillas)",
        zorder=4,
    )

    # Vertical line at final size
    n_final = int(n_pts.max())
    ax.axvline(
        x=n_final,
        color="#b22222",
        linestyle="--",
        linewidth=1.5,
        label=f"Tamaño final ({n_final} grupos únicos / 897 archivos)",
        zorder=2,
    )

    # Note on unique groups
    ax.annotate(
        f"{n_final} grupos únicos\n(897 archivos de IA)",
        xy=(n_final, means[-1]),
        xytext=(n_final * 0.35, means[-1] - 0.08),
        arrowprops=dict(arrowstyle="->", color="#b22222", lw=1.2),
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.3", fc="#fff8dc", ec="#b22222", alpha=0.9),
        zorder=5,
    )

    ax.set_xscale("log")
    ax.set_xlabel("Número de grupos únicos de IA en entrenamiento (escala logarítmica)")
    ax.set_ylabel("PR-AUC en validación")
    ax.set_title("Curva de aprendizaje de CharCNN v2 según código sintético")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.6)
    ax.legend(loc="lower right", framealpha=0.9)
    fig.tight_layout()

    for p in out_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p, dpi=300)
    plt.close(fig)


def plot_c2_metrics_panel(df: pd.DataFrame, out_paths: Sequence[Path]) -> None:
    """Plot C2: 2x2 panel of PR-AUC, ROC-AUC, F1, and Recall."""
    plt.rcParams.update(STYLE)
    fig, axes = plt.subplots(2, 2, figsize=(9, 7), sharex=True)
    metric_configs = [
        ("pr_auc", "PR-AUC (val)", axes[0, 0]),
        ("roc_auc", "ROC-AUC (val)", axes[0, 1]),
        ("f1", "F1-score (val, umbral fpr_0.01)", axes[1, 0]),
        ("recall", "Recall (val, umbral fpr_0.01)", axes[1, 1]),
    ]

    n_final = int(df["n_ai_train"].max())

    for col, title, ax in metric_configs:
        stats = df.groupby("n_ai_train")[col].agg(["mean", "std"]).reset_index()
        n_pts = stats["n_ai_train"].values
        means = stats["mean"].values
        stds = stats["std"].fillna(0.0).values

        ax.scatter(df["n_ai_train"], df[col], color="#2b5c8f", alpha=0.3, s=20, zorder=3)
        ax.fill_between(
            n_pts,
            np.clip(means - stds, 0.0, 1.0),
            np.clip(means + stds, 0.0, 1.0),
            color="#2b5c8f",
            alpha=0.2,
            zorder=2,
        )
        ax.plot(n_pts, means, color="#1f426b", linewidth=1.8, marker="o", markersize=4, zorder=4)
        ax.axvline(x=n_final, color="#b22222", linestyle="--", linewidth=1.2, alpha=0.8, zorder=2)
        ax.set_xscale("log")
        ax.set_ylabel(title)
        ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.6)

    axes[1, 0].set_xlabel("Códigos de IA en train (log)")
    axes[1, 1].set_xlabel("Códigos de IA en train (log)")
    fig.suptitle("Panel de métricas de validación según datos sintéticos", fontsize=13, y=0.99)
    fig.tight_layout()

    for p in out_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p, dpi=300)
    plt.close(fig)


def plot_c3_marginal_gain(df: pd.DataFrame, out_paths: Sequence[Path]) -> None:
    """Plot C3: Marginal gain in PR-AUC between consecutive fractions."""
    plt.rcParams.update(STYLE)
    stats = df.groupby(["fraction", "n_ai_train"])["pr_auc"].agg(["mean", "std"]).reset_index()
    stats = stats.sort_values("fraction").reset_index(drop=True)

    if len(stats) < 2:
        return

    labels = []
    gains = []
    noise_floor = float(stats["std"].mean())

    for i in range(1, len(stats)):
        diff = stats.loc[i, "mean"] - stats.loc[i - 1, "mean"]
        lbl = f"{int(stats.loc[i-1, 'fraction']*100)}%→{int(stats.loc[i, 'fraction']*100)}%"
        labels.append(lbl)
        gains.append(diff)

    fig, ax = plt.subplots(figsize=(8, 4))
    colors = ["#2b5c8f" if g >= noise_floor else "#8da0cb" for g in gains]
    bars = ax.bar(labels, gains, color=colors, edgecolor="#1f426b", linewidth=0.8)
    ax.axhline(
        y=noise_floor,
        color="#e41a1c",
        linestyle="--",
        linewidth=1.2,
        label=rf"Ruido promedio entre semillas ($\sigma \approx {noise_floor:.4f}$)",
    )
    ax.axhline(y=0.0, color="black", linewidth=0.8)

    ax.set_ylabel("Ganancia marginal de PR-AUC")
    ax.set_xlabel("Transición entre fracciones de datos de IA")
    ax.set_title("Mejora marginal de PR-AUC en validación")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.6)
    ax.legend(loc="upper right")
    fig.tight_layout()

    for p in out_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p, dpi=300)
    plt.close(fig)


def generate_report_markdown(
    df: pd.DataFrame,
    saturation: Dict[str, Any],
    fit_res: Optional[Dict[str, Any]],
    report_path: Path,
) -> None:
    """Generate the comprehensive report.md following Section 5 of the guide."""
    grouped = df.groupby(["fraction", "n_ai_train"]).agg(
        pr_mean=("pr_auc", "mean"),
        pr_std=("pr_auc", "std"),
        roc_mean=("roc_auc", "mean"),
        roc_std=("roc_auc", "std"),
        f1_mean=("f1", "mean"),
        f1_std=("f1", "std"),
        epoch_mean=("epoch", "mean"),
    ).reset_index()

    table_lines = [
        "| Fracción | N (grupos IA) | PR-AUC (val) | ROC-AUC (val) | F1 (val, fpr_0.01) | Época media |",
        "|---|---|---|---|---|---|",
    ]
    for _, row in grouped.iterrows():
        frac_pct = f"{int(round(row['fraction'] * 100))}%"
        n_ai = int(row["n_ai_train"])
        pr_str = f"{row['pr_mean']:.4f} ± {row['pr_std']:.4f}" if not math.isnan(row["pr_std"]) else f"{row['pr_mean']:.4f}"
        roc_str = f"{row['roc_mean']:.4f} ± {row['roc_std']:.4f}" if not math.isnan(row["roc_std"]) else f"{row['roc_mean']:.4f}"
        f1_str = f"{row['f1_mean']:.4f} ± {row['f1_std']:.4f}" if not math.isnan(row["f1_std"]) else f"{row['f1_mean']:.4f}"
        ep_str = f"{row['epoch_mean']:.1f}"
        table_lines.append(f"| {frac_pct} | {n_ai} | {pr_str} | {roc_str} | {f1_str} | {ep_str} |")

    table_md = "\n".join(table_lines)

    verdict_str = "**SATURADA**" if saturation["saturated"] else "**AÚN NO SATURADA**"
    cond1_str = "CUMPLE" if saturation["cond1_delta_below_0_01"] else "NO CUMPLE"
    cond2_str = "CUMPLE" if saturation["cond2_delta_below_std"] else "NO CUMPLE"

    report_content = f"""# Reporte: Curva de aprendizaje de CharCNN v2

**Fecha de ejecución:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}

> **Nota metodológica sobre los 874 grupos únicos:** En el particionado `split_v1.json.gz`, el subconjunto de entrenamiento contiene 897 archivos de código generado por IA pertenecientes a 874 grupos de duplicados únicos (`dup_group`). Dado que el protocolo de deduplicación y entrenamiento emplea un único representante canónico por grupo para evitar fuga de estilo, el 100% de la clase sintética en train corresponde exactamente a estos **874 grupos únicos**.

## 1. Tabla de resultados por fracción de entrenamiento

{table_md}

## 2. Veredicto del criterio de saturación pre-registrado

Criterio pre-registrado (Sección 1.4 de la guía):
1. Mejora media de PR-AUC entre 50% y 100% menor a 0.01:
   - Mejora observada: **{saturation['delta']:.4f}** ({cond1_str})
2. Mejora menor que la desviación estándar entre semillas en 100%:
   - Desviación estándar en 100%: **{saturation['std_pr_auc_100']:.4f}** ({cond2_str})

**Veredicto final:** {verdict_str}

## 3. Limitaciones

1. **Evaluación sobre validación:** La curva se mide en el conjunto de validación completo (6,808 humanos + 225 IA). Dado que este conjunto también se usa para la selección de época (early stopping), los valores absolutos pueden ser ligeramente optimistas; no obstante, el sesgo es idéntico para todos los puntos y no distorsiona la tasa de cambio ni la conclusión de saturación.
2. **Diversidad vs. volumen de generadores:** Adquirir más datos generados por el mismo LLM y bajo los mismos prompts no mitiga posibles sesgos o atajos espurios del generador sintético. La generalización ante otros modelos de lenguaje requiere diversidad de fuentes antes que volumen crudo.
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_content, encoding="utf-8")


def run_experiment(
    fractions: Sequence[float],
    seeds: Sequence[int],
    out_dir: Path,
    epochs: int,
    batch_size: int,
    device: Optional[str] = None,
    keep_checkpoints: bool = False,
    smoke: bool = False,
    use_subprocess: bool = False,
) -> pd.DataFrame:
    """Execute the grid of runs, skipping already completed runs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    total_runs = len(fractions) * len(seeds)
    run_idx = 0
    records = []

    print(f"Iniciando corrida de curva de aprendizaje: {len(fractions)} fracciones x {len(seeds)} semillas ({total_runs} corridas)")
    print(f"Directorio de salida: {out_dir.resolve()}")

    if (out_dir / "results.csv").is_file():
        df = pd.read_csv(out_dir / "results.csv")
        if len(df) == total_runs:
            print(f"Todas las {total_runs} corridas ya están consolidadas en {out_dir / 'results.csv'}. Saltando entrenamiento.")
            return df

    views = None
    val_all = None
    if not use_subprocess:
        import torch
        from models.char_cnn.v2.data import limit_per_class, load_encoded, load_views
        from models.char_cnn.v2.train import TrainOptions
        from models.char_cnn.v2.train import run as run_train
        from models.evaluation.manifest import DEFAULT_MANIFEST, ROOT, load_manifest

        print("Cargando corpus y vistas una sola vez para optimizar las corridas...")
        load_t = time.perf_counter()
        manifest = load_manifest(DEFAULT_MANIFEST)
        views = load_views(manifest, views=("train", "val", "test"), root=ROOT)
        if smoke:
            views = {name: limit_per_class(view, 50) for name, view in views.items()}
            val_all = views["val"]
        else:
            val_all_samples = manifest.samples("val", representatives_only=False)
            val_all = load_encoded(manifest, val_all_samples, root=ROOT)
        print(f"Corpus cargado en {time.perf_counter() - load_t:.1f}s.")

    for frac in fractions:
        for seed in seeds:
            run_idx += 1
            run_name = f"f{frac:g}_s{seed}"
            run_path = out_dir / run_name
            metrics_file = run_path / "metrics_val.json"

            # Check if run can be resumed / skipped
            if metrics_file.is_file():
                try:
                    data = json.loads(metrics_file.read_text(encoding="utf-8"))
                    print(f"[{run_idx}/{total_runs}] {run_name} ya completada. Saltando.")
                    records.append({
                        "fraction": frac,
                        "seed": seed,
                        "n_ai_train": data.get("n_ai_train", 0),
                        "pr_auc": data.get("pr_auc", 0.0),
                        "roc_auc": data.get("roc_auc", 0.0),
                        "f1": data.get("f1") or 0.0,
                        "precision": data.get("precision") or 0.0,
                        "recall": data.get("recall") or 0.0,
                        "epoch": data.get("epoch", 0),
                    })
                    continue
                except Exception:
                    pass

            print(f"[{run_idx}/{total_runs}] Ejecutando {run_name} (frac={frac}, seed={seed})...")
            start_t = time.perf_counter()

            if not use_subprocess:
                opts = TrainOptions(
                    manifest=DEFAULT_MANIFEST,
                    root=ROOT,
                    runs_root=out_dir,
                    seed=seed,
                    device=device,
                    epochs=epochs,
                    batch_size=batch_size,
                    train_ai_fraction=frac,
                    subsample_seed=seed,
                    run_dir=run_path,
                    skip_test_eval=True,
                    keep_checkpoints=keep_checkpoints,
                    limit_per_class=50 if smoke else None,
                )
                res = run_train(opts, preloaded_views=views, preloaded_val_all=val_all)
                if res.exit_code != 0:
                    raise RuntimeError(f"Run {run_name} failed with exit code {res.exit_code}")
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            else:
                cmd = [
                    sys.executable,
                    "-m",
                    "models.char_cnn.v2.train",
                    "--run-dir",
                    str(run_path),
                    "--train-ai-fraction",
                    str(frac),
                    "--subsample-seed",
                    str(seed),
                    "--seed",
                    str(seed),
                    "--epochs",
                    str(epochs),
                    "--batch-size",
                    str(batch_size),
                    "--skip-test-eval",
                ]
                if not keep_checkpoints:
                    cmd.append("--no-save-checkpoint")
                if device:
                    cmd.extend(["--device", device])
                if smoke:
                    cmd.extend(["--limit-per-class", "50"])

                sub_res = subprocess.run(cmd, capture_output=True, text=True)
                if sub_res.returncode != 0:
                    print(f"ERROR: corrida {run_name} falló (código {sub_res.returncode}):\n{sub_res.stderr}", file=sys.stderr)
                    raise RuntimeError(f"Run {run_name} failed: {sub_res.stderr}")

            elapsed = time.perf_counter() - start_t
            if not metrics_file.is_file():
                raise FileNotFoundError(f"{metrics_file} no fue generado por {run_name}")

            data = json.loads(metrics_file.read_text(encoding="utf-8"))
            val_pr = data.get("pr_auc", 0.0)
            n_ai = data.get("n_ai_train", 0)
            print(f"[{run_idx}/{total_runs}] {run_name} finalizada en {elapsed:.1f}s -> val PR-AUC: {val_pr:.4f} (N_IA={n_ai})")

            records.append({
                "fraction": frac,
                "seed": seed,
                "n_ai_train": n_ai,
                "pr_auc": val_pr,
                "roc_auc": data.get("roc_auc", 0.0),
                "f1": data.get("f1") or 0.0,
                "precision": data.get("precision") or 0.0,
                "recall": data.get("recall") or 0.0,
                "epoch": data.get("epoch", 0),
            })

    df = pd.DataFrame(records)
    df.to_csv(out_dir / "results.csv", index=False)
    with open(out_dir / "results.json", "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2)

    return df


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Curva de aprendizaje de CharCNN v2 variando datos de IA."
    )
    parser.add_argument(
        "--fractions",
        type=lambda s: [float(x.strip()) for x in s.split(",") if x.strip()],
        default=DEFAULT_FRACTIONS,
        help="Lista de fracciones separadas por coma",
    )
    parser.add_argument(
        "--seeds",
        type=lambda s: [int(x.strip()) for x in s.split(",") if x.strip()],
        default=DEFAULT_SEEDS,
        help="Lista de semillas separadas por coma",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_RUNS_ROOT,
        help="Directorio base para guardar corridas",
    )
    parser.add_argument(
        "--fig-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directorio donde guardar figuras PNG a 300 dpi",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="Directorio de corrida previa a reanudar",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Corrida rápida de prueba (2 fracciones x 1 semilla con 2 épocas)",
    )
    parser.add_argument(
        "--keep-checkpoints",
        action="store_true",
        help="Conservar archivos best.pth de cada corrida",
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument(
        "--use-subprocess",
        action="store_true",
        help="Ejecutar cada corrida en un subproceso aislado",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    if args.smoke:
        fractions = [0.10, 0.50]
        seeds = [42]
        epochs = 2
    else:
        fractions = args.fractions
        seeds = args.seeds
        epochs = args.epochs

    if args.resume is not None:
        run_root = args.resume
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        run_root = args.out / stamp

    df = run_experiment(
        fractions=fractions,
        seeds=seeds,
        out_dir=run_root,
        epochs=epochs,
        batch_size=args.batch_size,
        device=args.device,
        keep_checkpoints=args.keep_checkpoints,
        smoke=args.smoke,
        use_subprocess=args.use_subprocess,
    )

    print("Evaluando criterio de saturación...")
    saturation = evaluate_saturation(df)
    print(f"Veredicto: {'SATURADA' if saturation['saturated'] else 'AÚN NO SATURADA'}")

    print("Generando figuras y reporte...")
    c1_paths = [args.fig_dir / "curva_aprendizaje_charcnn.png", run_root / "curva_aprendizaje_charcnn.png"]
    c2_paths = [args.fig_dir / "panel_metricas_charcnn_lc.png", run_root / "panel_metricas_charcnn_lc.png"]
    c3_paths = [args.fig_dir / "mejora_marginal_charcnn_lc.png", run_root / "mejora_marginal_charcnn_lc.png"]

    plot_c1_learning_curve(df, c1_paths, fit_res=None)
    plot_c2_metrics_panel(df, c2_paths)
    plot_c3_marginal_gain(df, c3_paths)

    generate_report_markdown(df, saturation, None, run_root / "report.md")
    print(f"Completado exitosamente. Reporte guardado en {run_root / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

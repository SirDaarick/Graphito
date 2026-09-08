#!/usr/bin/env python3
"""
generate_tt_figures.py - Generador de gráficas de alta resolución para el reporte de Trabajo Terminal (TT).

Genera:
  1. figuras/curvas_entrenamiento_charcnn.png: Curvas de convergencia (Loss, Acc, F1)
  2. figuras/matriz_confusion_charcnn.png: Matriz de confusión en test set no visto
  3. figuras/benchmark_semantico_escom.png: Comparativa de similitud semántica en casos de ESCOM
  4. figuras/invarianza_estilometrica.png: Robustez ante formateo y comentarios
"""

import json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import torch

from models.char_cnn.inference import CharCNNInference
from models.char_cnn.train import compute_metrics

# Configuración de estilo académico
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
    "figure.dpi": 300,
})

FIG_DIR = Path("Documentacion/Documento/figuras")
FIG_DIR.mkdir(parents=True, exist_ok=True)


def plot_training_curves():
    print("Generando curvas de entrenamiento...")
    log_file = Path("models/char_cnn/logs/training_20260907_222227.csv")
    if not log_file.exists():
        print(f"No existe {log_file}")
        return

    df = pd.read_csv(log_file)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

    # Gráfica 1: Pérdida
    ax1.plot(df["epoch"], df["train_loss"], "o-", color="#1f77b4", label="Entrenamiento (Train Loss)", linewidth=2, markersize=4)
    ax1.plot(df["epoch"], df["val_loss"], "s--", color="#d62728", label="Validación (Val Loss)", linewidth=2, markersize=4)
    ax1.axvline(x=10, color="gray", linestyle=":", label="Mejor modelo (Epoch 10)")
    ax1.set_xlabel("Época")
    ax1.set_ylabel("Pérdida (Cross-Entropy Loss)")
    ax1.set_title("Evolución de la Función de Pérdida")
    ax1.legend(frameon=True)
    ax1.grid(True, alpha=0.3)

    # Gráfica 2: Métricas de Clasificación
    ax2.plot(df["epoch"], df["accuracy"] * 100, "o-", color="#2ca02c", label="Accuracy", linewidth=2, markersize=4)
    ax2.plot(df["epoch"], df["f1"] * 100, "^-", color="#ff7f0e", label="F1-Score", linewidth=2, markersize=4)
    ax2.plot(df["epoch"], df["precision"] * 100, "d--", color="#9467bd", label="Precisión", linewidth=1.5, markersize=3)
    ax2.plot(df["epoch"], df["recall"] * 100, "x--", color="#8c564b", label="Exhaustividad (Recall)", linewidth=1.5, markersize=3)
    ax2.axhline(y=80, color="#d62728", linestyle="--", linewidth=1.5, label="Requisito RNF-04 (80%)")
    ax2.set_xlabel("Época")
    ax2.set_ylabel("Porcentaje (%)")
    ax2.set_title("Métricas de Validación en Problemas No Vistos")
    ax2.set_ylim(70, 102)
    ax2.legend(frameon=True, loc="lower right")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = FIG_DIR / "curvas_entrenamiento_charcnn.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Guardado: {out_path}")


def plot_confusion_matrix():
    print("Generando matriz de confusión en test set...")
    manifest_path = Path("models/char_cnn/dataset_manifest.json")
    checkpoint_path = Path("models/char_cnn/best_model.pth")
    if not manifest_path.exists() or not checkpoint_path.exists():
        return

    infer = CharCNNInference(checkpoint_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    test_samples = manifest["splits"]["test"]
    y_true, y_pred = [], []
    for s in test_samples:
        res = infer.predict(Path(s["file_path"]))
        y_true.append(s["label"])
        y_pred.append(res["class_id"])

    # Matriz 2x2: [[TN, FP], [FN, TP]]
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)

    cm = np.array([[tn, fp], [fn, tp]])
    cm_pct = cm / cm.sum(axis=1, keepdims=True) * 100

    labels = [["Humano", "Sintético (IA)"], ["Humano", "Sintético (IA)"]]
    annot = np.empty_like(cm, dtype=object)
    for i in range(2):
        for j in range(2):
            annot[i, j] = f"{cm[i, j]}\n({cm_pct[i, j]:.1f}%)"

    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(cm, annot=annot, fmt="", cmap="Blues", cbar=True, ax=ax,
                xticklabels=["Humano", "Sintético (IA)"],
                yticklabels=["Humano", "Sintético (IA)"],
                annot_kws={"size": 13, "weight": "bold"})

    ax.set_title("Matriz de Confusión — Test Set (13 Problemas No Vistos)\nAccuracy: 95.93% | F1: 0.9609", pad=12)
    ax.set_ylabel("Clase Real")
    ax.set_xlabel("Clase Predicha")

    plt.tight_layout()
    out_path = FIG_DIR / "matriz_confusion_charcnn.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Guardado: {out_path}")


def plot_escom_benchmark():
    print("Generando gráfica de benchmark semántico ESCOM...")
    topics = [
        "U.I: Primo (for vs while)",
        "U.I: Factorial (for vs do-while)",
        "U.II: Invertir String (punteros)",
        "U.II: Struct Alumno (puntero ->)",
        "U.III: Malloc Vector (arit. *)",
        "U.III: Archivos (fgetc vs fgets)",
        "[NEG] Distinto U.I",
        "[NEG] Distinto U.II",
        "[NEG] Distinto U.III"
    ]

    base_scores = [0.9496, 0.9339, 0.8925, 0.9130, 0.9039, 0.9524, 0.9229, 0.8576, 0.8440]
    lora_scores = [0.9011, 0.8842, 0.8354, 0.8526, 0.8410, 0.8533, 0.7831, 0.7512, 0.7527]

    x = np.arange(len(topics))
    width = 0.38

    fig, ax = plt.subplots(figsize=(12, 6))

    rects1 = ax.bar(x - width/2, base_scores, width, label="GraphCodeBERT (DFG Corregido)", color="#3498db", alpha=0.9)
    rects2 = ax.bar(x + width/2, lora_scores, width, label="GraphCodeBERT (LoRA Contrastivo)", color="#2ecc71", alpha=0.9)

    ax.axhline(y=0.85, color="#e74c3c", linestyle="--", alpha=0.7, label="Umbral sugerido equivalencia (0.85)")
    ax.set_ylabel("Similitud Coseno")
    ax.set_title("Benchmark en Casos Reales del Temario ESCOM IPN (ISC 2020)\nCapacidad de discriminación: Positivos vs Pares Negativos", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(topics, rotation=35, ha="right")
    ax.set_ylim(0.65, 1.05)
    ax.legend(frameon=True, loc="lower left")

    # Resaltar la separación en negativos
    ax.axvspan(5.5, 8.5, color="#f39c12", alpha=0.15, label="Pares Negativos (Problemas Distintos)")

    plt.tight_layout()
    out_path = FIG_DIR / "benchmark_semantico_escom.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Guardado: {out_path}")


def plot_robustness_barchart():
    print("Generando gráfica de invarianza estilométrica...")
    categories = [
        "Código Estudiante Crudo\n(indentación desprolija)",
        "Código Estudiante Formateado\n(con clang-format)",
        "Código Sintético Limpio\n(sin comentarios)",
        "Código Sintético con Docstrings\n(comentarios de LLM)"
    ]

    p_ai = [0.2975, 0.3095, 0.9793, 0.9793]
    colors = ["#3498db", "#2980b9", "#e74c3c", "#c0392b"]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(categories, [p * 100 for p in p_ai], color=colors, width=0.5)

    ax.axhline(y=50, color="gray", linestyle="--", label="Umbral de Decisión (50%)")
    ax.set_ylabel("Probabilidad de IA (%)")
    ax.set_title("Pruebas de Invarianza Estilométrica ante Formato y Comentarios\n(MultiScaleCharCNN)")
    ax.set_ylim(0, 115)

    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 2.5, f"{yval:.1f}%", ha="center", va="bottom", weight="bold")

    ax.legend(frameon=True)
    plt.tight_layout()
    out_path = FIG_DIR / "invarianza_estilometrica.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Guardado: {out_path}")


if __name__ == "__main__":
    plot_training_curves()
    plot_confusion_matrix()
    plot_escom_benchmark()
    plot_robustness_barchart()
    print("\n✅ Todas las figuras fueron generadas con éxito en:", FIG_DIR.resolve())

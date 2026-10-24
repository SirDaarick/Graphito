#!/usr/bin/env python3
"""Thesis figures and tables of the contrastive CodeNet experiment (texts in Spanish, one file per figure).

Every number drawn comes from the run artifacts in ``runs/contrastivo_codenet/`` (copied from
``C:\\Users\\edani\\datasets\\codenet``) or from ``runs/contrastivo_codenet/derived/`` (computed once by
``scripts/derive_codenet_figure_data.py``); the script holds no metric values. The only drawing without data is
``codenet_esquema_triplete.png``, a labelled schematic.

Figures (``--out-dir``, default ``Documentacion/Documento/figuras``):
  Datos: codenet_exclusiones, codenet_particiones, codenet_longitud_comparada, codenet_esquema_triplete,
         coseno_zero_shot, coseno_entrenado, proyeccion_zero_shot, proyeccion_entrenado
  Entrenamiento: entrenamiento_perdida, entrenamiento_val_auc, entrenamiento_val_map
  Resultados (ESCOM): resultado_e1, resultado_e2, resultado_e2_por_tarea, resultado_robustez_auc,
         resultado_robustez_did
  Ablacion: ablacion_val_auc, ablacion_e2
Tables (``--tables-dir``, default ``Documentacion/Documento/tablas``): LaTeX ``table`` environments to \\input.

    python scripts/generate_codenet_figures.py
    python scripts/generate_codenet_figures.py --only resultado_e2 tabla_veredictos
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "runs" / "contrastivo_codenet"
DERIVED = DATA / "derived"
OUT_DIR = ROOT / "Documentacion" / "Documento" / "figuras"
TABLES_DIR = ROOT / "Documentacion" / "Documento" / "tablas"

STYLE = {
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.dpi": 300,
    "axes.spines.top": False,
    "axes.spines.right": False,
}

GRIS, ROJO, AZUL, NARANJA, VERDE = "#555555", "#D55E00", "#0072B2", "#E69F00", "#009E73"
NOMBRES = {
    "jaccard": "Jaccard",
    "v2_norm": "GraphCodeBERT\nsin entrenar",
    "ft_B_s1": "Ajustado B\n(semilla 1, titular)",
    "ft_B_s0": "Ajustado B\n(semilla 0)",
    "ft_A_s0": "Ajustado A\n(semilla 0)",
    "ft_A_s1": "Ajustado A\n(semilla 1)",
}
COLORES = {"jaccard": GRIS, "v2_norm": ROJO, "ft_B_s1": AZUL, "ft_B_s0": "#56B4E9", "ft_A_s0": NARANJA, "ft_A_s1": "#F0C75E"}
CONDICIONES = {
    "T0": "Original", "T1": "T1 Renombrar\nidentificadores", "T2": "T2 for ↔ while", "T3": "T3 Reordenar\nsentencias",
    "T4": "T4 Operadores\nequivalentes", "T5": "T5 Código\nmuerto", "T6": "T6 Invertir\nif/else",
    "T7@0.25": "T7 combinado\n25 %", "T7@0.5": "T7 combinado\n50 %", "T7@1.0": "T7 combinado\n100 %",
}
CORRIDAS = ("B_s0", "B_s1", "A_s0", "A_s1")
TITULAR = "ft_B_s1"


class MissingArtifact(FileNotFoundError):
    """A required artifact is absent: figures are never drawn from defaults."""


def load(*parts: str):
    path = DATA.joinpath(*parts)
    if not path.is_file():
        raise MissingArtifact(f"falta {path}")
    text = path.read_text(encoding="utf-8-sig")
    return [json.loads(line) for line in text.splitlines() if line.strip()] if path.suffix == ".jsonl" else json.loads(text)


def derived(name: str):
    path = DERIVED / name
    if not path.is_file():
        raise MissingArtifact(f"falta {path}: ejecuta scripts/derive_codenet_figure_data.py")
    return json.loads(path.read_text(encoding="utf-8"))


def miles(n: int | float) -> str:
    return f"{int(n):,}".replace(",", " ")


def save(fig, out: Path, name: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    fig.savefig(path, bbox_inches="tight", dpi=300)
    plt.close(fig)
    return path


def smooth(values, window: int):
    values = np.asarray(values, dtype=float)
    if values.size < window:
        return values
    kernel = np.ones(window) / window
    return np.convolve(values, kernel, mode="valid")


def run_label(run: str) -> str:
    return f"{run[0]} (semilla {run[-1]})"


# --- datos ----------------------------------------------------------------------------------------


def codenet_exclusiones(out):
    stats, dedup = load("f0", "stats.json"), load("f0", "dedup_escom_corpus.json")
    dropped = stats["dropped"]
    rows = [
        ("Demasiado largo o vacío\n(no cabe en una ventana de 512 tokens)", dropped["not_single_window_or_empty"], AZUL),
        ("Wrong Answer casi idéntico a un Accepted\n(Jaccard > 0.9)", dropped["wa_near_duplicate_of_accepted"], NARANJA),
        ("Casi duplicado de un programa de ESCOM\n(Jaccard ≥ 0.8)", dropped["escom_near_duplicate"] + dedup["flagged_samples"], ROJO),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    y = np.arange(len(rows))[::-1]
    ax.barh(y, [r[1] for r in rows], color=[r[2] for r in rows], height=0.55)
    ax.set_xscale("symlog", linthresh=1)
    for yi, (_, n, _) in zip(y, rows):
        ax.text(max(n, 1) * 1.15 + 0.2, yi, miles(n), va="center")
    ax.set_yticks(y, [r[0] for r in rows])
    ax.set_xlabel("Programas descartados (escala logarítmica)")
    ax.set_xlim(0, 1e6)
    kept = sum(v for v in (load("f0", "stats.json")["by_split"][s]["accepted"] + load("f0", "stats.json")["by_split"][s]["wrong_answer"] for s in ("train", "val", "test"))) - dedup["flagged_samples"]
    ax.set_title(f"Programas de CodeNet descartados por motivo ({miles(kept)} conservados)")
    return save(fig, out, "codenet_exclusiones")


def codenet_particiones(out):
    p = derived("particiones.json")
    nombres = {"train": "Entrenamiento", "val": "Validación", "test": "Prueba"}
    x = np.arange(3)
    acc = [p[s]["aceptados"] for s in nombres]
    wa = [p[s]["wrong_answer"] for s in nombres]
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    ax.bar(x, acc, color=AZUL, label="Accepted", width=0.6)
    ax.bar(x, wa, bottom=acc, color=ROJO, label="Wrong Answer", width=0.6)
    for xi, a, w in zip(x, acc, wa):
        ax.text(xi, a / 2, miles(a), ha="center", va="center", color="white")
        if w > 3000:
            ax.text(xi, a + w / 2, miles(w), ha="center", va="center", color="white")
        else:  # a thin segment: write its count above the bar
            ax.text(xi, a + w + 300, miles(w), ha="center", va="bottom", color=ROJO)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: miles(v)))
    ax.set_xticks(x, [f"{nombres[s]}\n{p[s]['problemas']} problemas" for s in nombres])
    ax.set_ylabel("Programas")
    ax.set_title("Partición de CodeNet por problema")
    ax.legend(frameon=False)
    return save(fig, out, "codenet_particiones")


def codenet_longitud_comparada(out):
    d = derived("longitud_programas.json")
    cn, es = np.asarray(d["codenet"]), np.asarray(d["escom"])
    bins = np.unique(np.round(np.logspace(0, np.log10(max(cn.max(), es.max()) + 1), 36)))
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    ax.hist(cn, bins=bins, density=True, alpha=0.6, color=AZUL, label=f"CodeNet conservado (n = {miles(cn.size)})")
    ax.hist(es, bins=bins, density=True, alpha=0.6, color=NARANJA, label=f"ESCOM, muestra de E1 (n = {miles(es.size)})")
    top = ax.get_ylim()[1]
    ax.set_ylim(0, top * 1.18)  # headroom for the median labels
    for arr, color, ha in ((cn, AZUL, "right"), (es, NARANJA, "left")):
        med = np.median(arr)
        ax.axvline(med, color=color, linestyle="--", linewidth=1.5)
        ax.text(med * (0.93 if ha == "right" else 1.07), top * 1.1, f"mediana {med:.0f} líneas", color=color, va="center", ha=ha)
    ax.set_xscale("log")
    ax.set_xlabel("Líneas no vacías por programa (escala logarítmica)")
    ax.set_ylabel("Densidad")
    ax.set_title("Los programas de CodeNet conservados son más cortos que los de ESCOM")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    return save(fig, out, "codenet_longitud_comparada")


def codenet_esquema_triplete(out):
    """Schematic (no data): what the contrastive loss pulls together and pushes apart."""
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    ancla, positivo, negativo = (0.0, 0.0), (2.2, 0.9), (1.6, -1.3)
    for punto, color in ((ancla, AZUL), (positivo, VERDE), (negativo, ROJO)):
        ax.scatter(*punto, s=300, color=color, zorder=3)
    rng = np.random.default_rng(3)
    otros = rng.normal(loc=[-3.0, 1.3], scale=[0.4, 0.3], size=(9, 2))
    ax.scatter(otros[:, 0], otros[:, 1], s=70, color=GRIS, alpha=0.75, zorder=2)
    # the loss moves the positive towards the anchor and the hard negative away from it
    ax.annotate("", xy=(0.35, 0.16), xytext=(1.95, 0.8), arrowprops=dict(arrowstyle="->", color=VERDE, lw=2.4))
    ax.annotate("", xy=(2.75, -1.75), xytext=(1.8, -1.42), arrowprops=dict(arrowstyle="->", color=ROJO, lw=2.4))
    ax.text(1.2, 0.72, "acercar", color=VERDE, ha="center", va="bottom", rotation=20)
    ax.text(2.45, -1.28, "alejar", color=ROJO, ha="left", va="bottom", rotation=-20)
    ax.text(0.0, -0.3, "Ancla\n(solución correcta)", ha="center", va="top", color=AZUL)
    ax.text(2.2, 1.25, "Positivo\n(otra solución correcta del mismo problema)", ha="center", va="bottom", color=VERDE)
    ax.text(1.6, -1.95, "Negativo difícil\n(Wrong Answer del mismo problema)", ha="center", va="top", color=ROJO)
    ax.text(-3.0, 2.45, "Negativos del lote\n(programas de otros problemas)", ha="center", va="bottom", color=GRIS)
    ax.set_xlim(-4.4, 4.4)
    ax.set_ylim(-3.0, 3.0)
    ax.axis("off")
    ax.set_title("Tripleta de entrenamiento contrastivo (esquema)")
    return save(fig, out, "codenet_esquema_triplete")


def _coseno(out, clave, titulo, nombre, color_otro, leyenda="upper left"):
    c = derived("coseno.json")
    bins = np.asarray(c["bins"])
    centros = (bins[:-1] + bins[1:]) / 2
    ancho = np.diff(bins)
    ymax = 0.0
    for k in ("zero_shot", "entrenado"):
        for serie in ("mismo_problema", "otro_problema"):
            h = np.asarray(c[k][serie], dtype=float)
            ymax = max(ymax, (h / h.sum() / ancho).max())
    d = c[clave]
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    for serie, color, etiqueta, media in (
        ("otro_problema", color_otro, "Problemas distintos", d["media_otro"]),
        ("mismo_problema", VERDE, "Mismo problema", d["media_mismo"]),
    ):
        h = np.asarray(d[serie], dtype=float)
        ax.bar(centros, h / h.sum() / ancho, width=ancho, color=color, alpha=0.65, label=f"{etiqueta} (media {media:.2f})")
        ax.axvline(media, color=color, linestyle="--", linewidth=1.5)
    ax.set_xlim(-0.2, 1.0)
    ax.set_ylim(0, ymax * 1.08)
    ax.set_xlabel("Similitud coseno entre dos programas")
    ax.set_ylabel("Densidad")
    ax.set_title(titulo)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)  # below: never on the data
    return save(fig, out, nombre)


def coseno_zero_shot(out):
    return _coseno(out, "zero_shot", "Sin entrenar: todos los programas parecen similares", "coseno_zero_shot", ROJO)


def coseno_entrenado(out):
    return _coseno(out, "entrenado", "Tras el ajuste: los problemas distintos se separan", "coseno_entrenado", AZUL, leyenda="upper right")


def _proyeccion(out, clave, titulo, nombre):
    p = derived("proyeccion.json")
    d = p[clave]
    paleta = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]
    problemas = p["problemas"]
    x, y = np.asarray(d["x"]), np.asarray(d["y"])
    prob, rol = np.asarray(d["problema"]), np.asarray(d["rol"])
    fig, ax = plt.subplots(figsize=(5.8, 4.8))
    for i, pid in enumerate(problemas):
        for r, marker, size in (("accepted", "o", 34), ("wrong_answer", "x", 40)):
            m = (prob == pid) & (rol == r)
            ax.scatter(x[m], y[m], s=size, marker=marker, color=paleta[i], alpha=0.85, linewidths=1.4 if r != "accepted" else 0)
    handles = [plt.Line2D([], [], marker="o", linestyle="", color=paleta[i], label=f"Problema {pid}") for i, pid in enumerate(problemas)]
    handles += [
        plt.Line2D([], [], marker="o", linestyle="", color="black", label="Accepted"),
        plt.Line2D([], [], marker="x", linestyle="", color="black", label="Wrong Answer"),
    ]
    ax.legend(handles=handles, frameon=False, fontsize=8.5, loc="center left", bbox_to_anchor=(1.0, 0.5))
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(titulo)
    for s in ("left", "bottom"):
        ax.spines[s].set_visible(True)
    return save(fig, out, nombre)


def proyeccion_zero_shot(out):
    return _proyeccion(out, "zero_shot", "Sin entrenar (t-SNE, validación)", "proyeccion_zero_shot")


def proyeccion_entrenado(out):
    return _proyeccion(out, "entrenado", "Ajustado (t-SNE, validación)", "proyeccion_entrenado")


# --- entrenamiento --------------------------------------------------------------------------------


def _estilo_corrida(run):
    return COLORES["ft_" + run], "-" if run.endswith("0") else "--"


def entrenamiento_perdida(out):
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    for run in CORRIDAS:
        log = load("f3", run, "train_log.jsonl")
        steps = np.array([r["step"] for r in log])
        loss = np.array([r["loss"] for r in log])
        w = 50
        color, ls = _estilo_corrida(run)
        ax.plot(steps[w - 1:], smooth(loss, w), color=color, linestyle=ls, linewidth=1.8, label=run_label(run))
    ax.set_xlabel("Paso de entrenamiento")
    ax.set_ylabel("Pérdida InfoNCE (media móvil de 500 pasos)")
    ax.set_title("Pérdida de entrenamiento")
    ax.legend(frameon=False, title="Configuración")
    return save(fig, out, "entrenamiento_perdida")


def _validacion(out, clave, ylabel, titulo, nombre, referencia, etiqueta_ref):
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    for run in CORRIDAS:
        log = load("f3", run, "val_log.jsonl")
        color, ls = _estilo_corrida(run)
        ax.plot([r["step"] for r in log], [r[clave] for r in log], color=color, linestyle=ls, marker="o", markersize=3.5, linewidth=1.8, label=run_label(run))
    ax.axhline(referencia, color=ROJO, linestyle=":", linewidth=1.8)
    ax.text(ax.get_xlim()[1], referencia, f"{etiqueta_ref} ({referencia:.3f})", color=ROJO, ha="right", va="bottom")
    ax.set_xlabel("Paso de entrenamiento")
    ax.set_ylabel(ylabel)
    ax.set_title(titulo)
    ax.legend(frameon=False, title="Configuración", loc="lower right", bbox_to_anchor=(1.0, 0.1))
    return save(fig, out, nombre)


def entrenamiento_val_auc(out):
    base = load("f0", "f1_baseline_val.json")["accepted_vs_wa_auc"]["pooled_auc"]
    return _validacion(out, "val_auc", "AUC correcta vs. incorrecta", "Validación en CodeNet: AUC dentro del problema", "entrenamiento_val_auc", base, "sin entrenar")


def entrenamiento_val_map(out):
    base = load("f0", "f1_baseline_val.json")["map_at_r_accepted"]
    return _validacion(out, "val_map_at_r", "MAP@R entre soluciones correctas", "Validación en CodeNet: MAP@R entre problemas", "entrenamiento_val_map", base, "sin entrenar")


# --- resultados en ESCOM ----------------------------------------------------------------------------

ORDEN = ("jaccard", "v2_norm", "ft_B_s1", "ft_B_s0", "ft_A_s0", "ft_A_s1")
CORTOS = {
    "jaccard": "Jaccard", "v2_norm": "GraphCodeBERT\nsin entrenar", "ft_B_s1": "Ajustado B\ns. 1 (titular)",
    "ft_B_s0": "Ajustado B\ns. 0", "ft_A_s0": "Ajustado A\ns. 0", "ft_A_s1": "Ajustado A\ns. 1",
}


def _barras_ci(out, valores, cis, ylabel, titulo, nombre, ref=None, ylim=None):
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    x = np.arange(len(ORDEN))
    vals = [valores[m] for m in ORDEN]
    err = np.array([[v - cis[m][0], cis[m][1] - v] for m, v in zip(ORDEN, vals)]).T
    bars = ax.bar(x, vals, color=[COLORES[m] for m in ORDEN], width=0.62, yerr=err, capsize=4, error_kw=dict(lw=1.3))
    bars[ORDEN.index(TITULAR)].set_edgecolor("black")
    bars[ORDEN.index(TITULAR)].set_linewidth(2.2)
    for xi, v, hi in zip(x, vals, [cis[m][1] for m in ORDEN]):
        ax.text(xi, hi + 0.012, f"{v:.3f}", ha="center", va="bottom")
    if ref is not None:
        ax.axhline(ref[0], color="black", linestyle=":", linewidth=1.2)
        ax.text(len(ORDEN) - 0.45, ref[0], ref[1], ha="right", va="bottom", fontsize=9)
    ax.set_xticks(x, [CORTOS[m] for m in ORDEN], fontsize=8.5)
    ax.set_ylabel(ylabel)
    ax.set_title(titulo)
    if ylim:
        ax.set_ylim(*ylim)
    return save(fig, out, nombre)


def resultado_e1(out):
    e1 = load("f4", "e1.json")["methods"]
    return _barras_ci(out, {m: e1[m]["map_at_r"] for m in ORDEN}, {m: e1[m]["ci95"] for m in ORDEN}, "MAP@R (IC95 %)", "E1: agrupamiento por tarea en ESCOM", "resultado_e1", ylim=(0, 0.6))


def resultado_e2(out):
    e2 = load("f4", "e2.json")["methods"]
    return _barras_ci(out, {m: e2[m]["macro_auc"] for m in ORDEN}, {m: e2[m]["auc_ci95"] for m in ORDEN}, "AUC macro (IC95 %)", "E2: la similitud con la referencia predice si el código aprueba", "resultado_e2", ref=(0.5, "azar"), ylim=(0.4, 0.75))


def resultado_e2_por_tarea(out):
    e2 = load("f4", "e2.json")["methods"]
    metodos = ("jaccard", "v2_norm", TITULAR)
    por = {m: {r["assignment"]: r["auc"] for r in e2[m]["per_assignment"] if r["auc"] is not None} for m in metodos}
    tareas = sorted(set.intersection(*(set(v) for v in por.values())), key=lambda t: por["v2_norm"][t])
    fig, ax = plt.subplots(figsize=(6.6, 5.2))
    y = np.arange(len(tareas))
    for m, marker in zip(metodos, ("s", "o", "D")):
        ax.scatter([por[m][t] for t in tareas], y, color=COLORES[m], marker=marker, s=42, label=NOMBRES[m].replace("\n", " "), zorder=3)
    for yi, t in zip(y, tareas):
        vals = [por[m][t] for m in metodos]
        ax.plot([min(vals), max(vals)], [yi, yi], color="#CCCCCC", linewidth=1, zorder=1)
    ax.axvline(0.5, color="black", linestyle=":", linewidth=1.2)
    ax.set_yticks(y, tareas, fontsize=8.5)
    ax.set_xlabel("AUC de la tarea (referencias de aprobados, una a una)")
    ax.set_title("E2 por tarea")
    ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.45, -0.1), ncol=3, columnspacing=1.2, handletextpad=0.3)
    return save(fig, out, "resultado_e2_por_tarea")


def resultado_robustez_auc(out):
    r = load("f4", "robustness_summary.json")
    conds = list(r["auc"])
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    x = np.arange(len(conds))
    for m, marker in (("jaccard", "s"), ("v2_norm", "o"), (TITULAR, "D")):
        ax.plot(x, [r["auc"][c][m] for c in conds], marker=marker, color=COLORES[m], linewidth=1.9, label=NOMBRES[m].replace("\n", " "))
    ax.set_xticks(x, [CONDICIONES[c] for c in conds], rotation=40, ha="right", fontsize=8.5)
    ax.set_ylabel("AUC (pares de plagio)")
    ax.set_title("Robustez frente a transformaciones que conservan el comportamiento")
    ax.legend(frameon=False, loc="lower left")
    return save(fig, out, "resultado_robustez_auc")


def resultado_robustez_did(out):
    r = load("f4", "robustness_summary.json")["did_vs_v2_norm"][TITULAR]
    conds = list(r)
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    y = np.arange(len(conds))[::-1]
    for yi, c in zip(y, conds):
        d = r[c]
        color = AZUL if d["ci95"][0] > 0 else ("#B22222" if d["ci95"][1] < 0 else GRIS)
        ax.errorbar(d["value"], yi, xerr=[[d["value"] - d["ci95"][0]], [d["ci95"][1] - d["value"]]], fmt="o", color=color, capsize=4, linewidth=1.8)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_yticks(y, [CONDICIONES[c].replace("\n", " ") for c in conds], fontsize=9)
    ax.set_xlabel("Diferencia en la caída de AUC (ajustado − sin entrenar)")
    ax.set_title("Degradación del ajustado frente a GraphCodeBERT sin entrenar")
    ax.text(0.98, 0.97, "positivo: el ajustado se degrada menos\nazul: IC95 % enteramente sobre 0", transform=ax.transAxes, color=AZUL, fontsize=9, ha="right", va="top")
    return save(fig, out, "resultado_robustez_did")


# --- ablacion A vs B ---------------------------------------------------------------------------------


def _ablacion(out, valores, ref, etiqueta_ref, ylabel, titulo, nombre, cis=None, ylim=None):
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    ms = ["ft_A_s0", "ft_A_s1", "ft_B_s0", "ft_B_s1"]
    x = np.arange(len(ms))
    vals = [valores[m] for m in ms]
    kw = {}
    if cis:
        kw = dict(yerr=np.array([[v - cis[m][0], cis[m][1] - v] for m, v in zip(ms, vals)]).T, capsize=4, error_kw=dict(lw=1.3))
    ax.bar(x, vals, color=[COLORES[m] for m in ms], width=0.6, **kw)
    for xi, m, v in zip(x, ms, vals):
        top = cis[m][1] + 0.006 if cis else v + 0.003
        ax.text(xi, top, f"{v:.3f}", ha="center", va="bottom")
    ax.axhline(ref, color=ROJO, linestyle=":", linewidth=1.8)
    ax.text(-0.45, ref, f"{etiqueta_ref} ({ref:.3f})", color=ROJO, ha="left", va="bottom", fontsize=9)
    ax.set_xticks(x, ["A\nsemilla 0", "A\nsemilla 1", "B\nsemilla 0", "B\nsemilla 1"])
    ax.set_ylabel(ylabel)
    ax.set_title(titulo)
    if ylim:
        ax.set_ylim(*ylim)
    return save(fig, out, nombre)


def ablacion_val_auc(out):
    vals = {f"ft_{r}": load("f3", r, "val_log.jsonl")[-1]["val_auc"] for r in CORRIDAS}
    base = load("f0", "f1_baseline_val.json")["accepted_vs_wa_auc"]["pooled_auc"]
    return _ablacion(out, vals, base, "sin entrenar", "AUC correcta vs. incorrecta", "Ablación en CodeNet: Wrong Answer como negativos", "ablacion_val_auc", ylim=(0.5, 0.67))


def ablacion_e2(out):
    e2 = load("f4", "e2.json")["methods"]
    vals = {m: e2[m]["macro_auc"] for m in ("ft_A_s0", "ft_A_s1", "ft_B_s0", "ft_B_s1")}
    cis = {m: e2[m]["auc_ci95"] for m in vals}
    return _ablacion(out, vals, e2["v2_norm"]["macro_auc"], "sin entrenar", "AUC macro de E2 (IC95 %)", "Ablación en ESCOM (E2): los intervalos se traslapan", "ablacion_e2", cis=cis, ylim=(0.45, 0.75))


# --- tablas LaTeX -------------------------------------------------------------------------------------


def tex_num(x: float, nd: int = 3) -> str:
    return f"{x:.{nd}f}"


def tex_ci(ci) -> str:
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci else "--"


def write_table(tables_dir: Path, name: str, caption: str, label: str, spec: str, header: list[str], rows: list[list[str]]) -> Path:
    tables_dir.mkdir(parents=True, exist_ok=True)
    lines = ["% Generado por scripts/generate_codenet_figures.py: no editar a mano.", "\\begin{table}[H]", "\\centering", "\\small",
             f"\\begin{{tabular}}{{{spec}}}", "\\hline", " & ".join(f"\\textbf{{{h}}}" for h in header) + " \\\\ \\hline"]
    lines += [" & ".join(r) + " \\\\ \\hline" for r in rows]
    lines += ["\\end{tabular}", f"\\caption{{{caption}}}", f"\\label{{{label}}}", "\\end{table}"]
    path = tables_dir / f"{name}.tex"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def tabla_codenet_particiones(_out, tables_dir):
    p = derived("particiones.json")
    nombres = {"train": "Entrenamiento", "val": "Validación", "test": "Prueba"}
    rows = [[nombres[s], str(p[s]["problemas"]), f"{p[s]['aceptados']:,}".replace(",", "\\,"), f"{p[s]['wrong_answer']:,}".replace(",", "\\,"),
             f"{p[s]['aceptados'] + p[s]['wrong_answer']:,}".replace(",", "\\,")] for s in nombres]
    tot = [sum(p[s][k] for s in nombres) for k in ("problemas", "aceptados", "wrong_answer")]
    rows.append(["\\textbf{Total}", str(tot[0])] + [f"{v:,}".replace(",", "\\,") for v in (tot[1], tot[2], tot[1] + tot[2])])
    return write_table(tables_dir, "tabla_codenet_particiones", "Programas de CodeNet (C++) conservados, por partición. La partición es por problema.",
                       "tab:codenet_particiones", "|l|r|r|r|r|", ["Partición", "Problemas", "Accepted", "Wrong Answer", "Total"], rows)


def tabla_resultados_e1_e2(_out, tables_dir):
    e1, e2 = load("f4", "e1.json")["methods"], load("f4", "e2.json")["methods"]
    nombre = {"jaccard": "Jaccard", "v2_norm": "GraphCodeBERT sin entrenar", "ft_B_s1": "Ajustado B, semilla 1 (titular)", "ft_B_s0": "Ajustado B, semilla 0",
              "ft_A_s0": "Ajustado A, semilla 0", "ft_A_s1": "Ajustado A, semilla 1"}
    rows = [[nombre[m], tex_num(e1[m]["map_at_r"]), tex_ci(e1[m]["ci95"]), tex_num(e1[m]["recall_at_1"]), tex_num(e2[m]["macro_auc"]), tex_ci(e2[m]["auc_ci95"])] for m in ORDEN]
    return write_table(tables_dir, "tabla_resultados_e1_e2", "Resultados en ESCOM: agrupamiento por tarea (E1) y relación entre similitud con la referencia y aprobación (E2).",
                       "tab:resultados_e1_e2", "|l|r|c|r|r|c|", ["Método", "MAP@R", "IC95 \\%", "Recall@1", "AUC macro", "IC95 \\%"], rows)


def tabla_robustez_auc(_out, tables_dir):
    r = load("f4", "robustness_summary.json")
    conds = list(r["auc"])
    rows = []
    for c in conds:
        did = r["did_vs_v2_norm"][TITULAR].get(c)
        rows.append([CONDICIONES[c].replace("\n", " ").replace("%", "\\%").replace("↔", "$\\leftrightarrow$"), tex_num(r["auc"][c]["jaccard"]), tex_num(r["auc"][c]["v2_norm"]),
                     tex_num(r["auc"][c][TITULAR]), "--" if not did else f"{did['value']:+.3f} {tex_ci(did['ci95'])}"])
    return write_table(tables_dir, "tabla_robustez_auc", "AUC bajo transformaciones que conservan el comportamiento (pares de plagio de la partición de prueba) y diferencia de degradación del modelo ajustado frente al no entrenado.",
                       "tab:robustez_auc", "|l|r|r|r|c|", ["Condición", "Jaccard", "Sin entrenar", "Ajustado (titular)", "Diferencia de degradación [IC95 \\%]"], rows)


def tabla_veredictos(_out, tables_dir):
    s = load("f4", "f4_summary.json")
    ver = {"confirmed": "Confirmada", "refuted": "Refutada", "inconclusive": "No concluyente"}
    rows = [
        ["H1", "El ajuste mejora el AUC macro de E2", f"{s['H1']['mean_diff']:+.3f} {tex_ci(s['H1']['ci95'])}", ver[s["H1"]["verdict"]]],
        ["H2", "El ajuste mejora el MAP@R de E1", f"{s['H2']['mean_diff']:+.3f} {tex_ci(s['H2']['ci95'])}", ver[s["H2"]["verdict"]]],
        ["H3", "El ajuste no degrada más que el modelo no entrenado bajo T1--T7", "ninguna condición con IC bajo 0", ver[s["H3"]["verdict"]]],
    ]
    return write_table(tables_dir, "tabla_veredictos", "Hipótesis preregistradas y su resultado (modelo titular frente a GraphCodeBERT sin entrenar).",
                       "tab:veredictos", "|l|p{5.2cm}|c|c|", ["Hipótesis", "Enunciado", "Estimación [IC95 \\%]", "Veredicto"], rows)


def tabla_ablacion(_out, tables_dir):
    e1, e2 = load("f4", "e1.json")["methods"], load("f4", "e2.json")["methods"]
    rows = []
    for run in ("A_s0", "A_s1", "B_s0", "B_s1"):
        v = load("f3", run, "val_log.jsonl")[-1]
        m = "ft_" + run
        rows.append([run[0] + (" (sin negativos difíciles)" if run[0] == "A" else " (con Wrong Answer)"), run[-1], tex_num(v["val_auc"]), tex_num(v["val_map_at_r"]), tex_num(e1[m]["map_at_r"]), tex_num(e2[m]["macro_auc"])])
    return write_table(tables_dir, "tabla_ablacion", "Ablación de la configuración de negativos: validación en CodeNet y evaluación en ESCOM, por semilla.",
                       "tab:ablacion", "|l|c|r|r|r|r|", ["Configuración", "Semilla", "AUC val.", "MAP@R val.", "E1 MAP@R", "E2 AUC macro"], rows)


def tabla_hiperparametros(_out, tables_dir):
    sys.path.insert(0, str(ROOT / "scripts"))
    from contrastive_train import TEMPERATURE

    t = load("f3", "B_s1", "result.json")["train"]
    rows = [
        ["Modelo base", "microsoft/graphcodebert-base (125 M parámetros)"],
        ["Adaptación", f"LoRA, rango {t['rank']}, en las proyecciones \\texttt{{query}} y \\texttt{{value}}"],
        ["Pérdida", f"InfoNCE, temperatura {TEMPERATURE}"],
        ["Problemas por lote", f"{t['pairs']} (cada uno aporta ancla, positivo y negativo difícil)"],
        ["Tripletas totales", f"{t['triplets']:,}".replace(",", "\\,") + f" ({int(t['triplets'] / (t['pairs'])):,}".replace(",", "\\,") + " pasos, 3 épocas)"],
        ["Tasa de aprendizaje", f"{t['lr']:g}, calentamiento del 5 \\% y decaimiento lineal"],
        ["Precisión", "fp32, atención con máscara guiada por el grafo de flujo de datos"],
        ["Entrada", "código con identificadores canónicos, una ventana de 384 + 128 tokens"],
        ["Selección del punto de control", "AUC dentro del problema en validación de CodeNet; ESCOM no se usa"],
    ]
    return write_table(tables_dir, "tabla_hiperparametros", "Configuración del ajuste contrastivo de GraphCodeBERT.", "tab:hiperparametros", "|l|p{9cm}|", ["Parámetro", "Valor"], rows)


FIGURES = {f.__name__: f for f in (
    codenet_exclusiones, codenet_particiones, codenet_longitud_comparada, codenet_esquema_triplete, coseno_zero_shot, coseno_entrenado,
    proyeccion_zero_shot, proyeccion_entrenado, entrenamiento_perdida, entrenamiento_val_auc, entrenamiento_val_map, resultado_e1, resultado_e2,
    resultado_e2_por_tarea, resultado_robustez_auc, resultado_robustez_did, ablacion_val_auc, ablacion_e2)}
TABLES = {f.__name__: f for f in (tabla_codenet_particiones, tabla_resultados_e1_e2, tabla_robustez_auc, tabla_veredictos, tabla_ablacion, tabla_hiperparametros)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--tables-dir", type=Path, default=TABLES_DIR)
    ap.add_argument("--only", nargs="+", choices=sorted([*FIGURES, *TABLES]))
    args = ap.parse_args()
    plt.rcParams.update(STYLE)
    status = 0
    for name, fn in [*FIGURES.items(), *TABLES.items()]:
        if args.only and name not in args.only:
            continue
        try:
            path = fn(args.out_dir) if name in FIGURES else fn(args.out_dir, args.tables_dir)
            print(f"ok   {path}")
        except MissingArtifact as exc:
            print(f"OMITIDA {name}: {exc}", file=sys.stderr)
            status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())

"""Leave-one-LLM-out experiment for CharCNN v2 (train on one generator, test on another).

    python scripts/charcnn_lolo.py preregister --stamp S
    python scripts/charcnn_lolo.py run --condition D --seed 42 --root <corpus root> --stamp S
    python scripts/charcnn_lolo.py aggregate --stamp S --reference-run <run dir> --root <corpus root>

Runs go to `runs/char_cnn_lolo/<stamp>/<condition>_s<seed>/`; finished runs are skipped (resume).
Smoke mode (`--smoke`) uses 1 epoch, a small per-class limit and `runs/char_cnn_lolo/smoke`.
"""

import argparse
import csv
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from models.evaluation import metrics as M  # noqa: E402
from models.evaluation.manifest import DEFAULT_MANIFEST, load_manifest  # noqa: E402

RUNS = REPO / "runs" / "char_cnn_lolo"
SEEDS = (42, 7, 123)
GENERATORS = ("deepseek-chat", "qwen3")
FPR_KEY = "fpr_0.01"
CONDITIONS: Dict[str, Dict[str, Any]] = {
    "D": {"label": "D: entrenado con deepseek", "flags": ["--train-ai-models", "deepseek-chat"],
          "seen": "deepseek-chat", "unseen": "qwen3"},
    "DM": {"label": "D-matched: deepseek (mismo tamaño que qwen3)",
           "flags": ["--train-ai-models", "deepseek-chat", "--match-ai-groups-to", "qwen3"],
           "seen": "deepseek-chat", "unseen": "qwen3"},
    "Q": {"label": "Q: entrenado con qwen3", "flags": ["--train-ai-models", "qwen3"],
          "seen": "qwen3", "unseen": "deepseek-chat"},
}
ROC_BOUND, RECALL_BOUND = 0.02, 0.10
CAT_NAMES = {
    "D": "D\nentrena: {seen}\nno visto: {unseen}",
    "DM": "D-matched\nentrena: {seen}\n(mismo n que {unseen})",
    "Q": "Q\nentrena: {seen}\nno visto: {unseen}",
}

PREREGISTRO = """## Diseño preregistrado

**Pregunta.** ¿CharCNN generaliza a un generador de IA que nunca vio, o aprende un estilo propio de cada generador?

**Condiciones.** Los humanos son siempre el split completo. El código de IA de los demás generadores
(con a lo sumo 2 archivos cada uno) se excluye del entrenamiento, de la selección en val y de las
métricas principales.

- **R. Referencia** (sin entrenar): puntajes de test del modelo desplegado (`20261011-015734`), desglosados por
  generador: humanos de test contra IA de deepseek y contra IA de qwen3.
- **D.** Entrenamiento y val con IA solo de deepseek. El generador retenido no influye en la parada temprana ni en la
  calibración. Se evalúa en test contra deepseek (visto) y qwen3 (no visto).
- **Q.** Simétrica a D: entrenamiento y val solo con qwen3.
- **D-matched.** Como D, pero la IA de deepseek en train se submuestrea por `dup_group`, estratificada por
  `assignment`, hasta el MISMO número de grupos únicos que qwen3 tiene en train. Separa "generador no visto"
  de "menos datos".
- **Semillas.** 3 por condición entrenada (42, 7, 123): 9 entrenamientos.

**Métricas** (test, solo representantes de `dup_group`). Para cada subconjunto de IA (visto / no visto) contra
TODOS los humanos de test: ROC-AUC, PR-AUC y recall en el umbral `fpr_0.01` ajustado en val por la propia corrida;
además el FPR humano en ese umbral. Se reporta media ± desviación estándar (ddof=1) entre semillas. El PR-AUC
depende de la prevalencia de cada subconjunto, por lo que no es comparable entre generadores de distinto tamaño.

**Contraste primario.** Por condición, (visto - no visto) en recall y en ROC-AUC, sobre las medias entre semillas.

**Interpretación preregistrada.**

- *Generaliza*: en D-matched Y en Q, la caída de ROC-AUC es < 0.02 Y la caída de recall es < 0.10.
- *Dependiente del generador*: la condición D-matched y la Q superan cada una al menos una de esas cotas.
- *Mixto*: cualquier otro caso (una sola de las dos condiciones supera alguna cota).

(Operacionalización de la regla "alguna caída supera la cota": se exige que ocurra en ambas condiciones para
"dependiente"; si ocurre solo en una, es "mixto".)

**Limitaciones declaradas.** Solo hay dos generadores sustanciales; deepseek y qwen3 se solicitaron con prompts
idénticos, de modo que el estilo del prompt queda constante; el experimento mide transferencia solo entre estos dos
generadores; los humanos de test provienen del mismo curso que los de entrenamiento; no se calculó IC bootstrap.
"""


def stamp_dir(stamp: Optional[str], smoke: bool) -> Path:
    if smoke:
        return RUNS / "smoke"
    if stamp:
        return RUNS / stamp
    existing = sorted(p for p in RUNS.glob("*") if p.is_dir() and p.name != "smoke") if RUNS.exists() else []
    return existing[-1] if existing else RUNS / datetime.now().strftime("%Y%m%d-%H%M%S")


def run_dir_of(out: Path, condition: str, seed: int) -> Path:
    return out / f"{condition}_s{seed}"


def is_finished(run_dir: Path) -> bool:
    cfg = run_dir / "config.json"
    if not cfg.is_file() or not (run_dir / "scores_test.csv").is_file():
        return False
    return json.loads(cfg.read_text(encoding="utf-8")).get("status") == "complete"


def train_one(args: argparse.Namespace, condition: str, seed: int) -> int:
    out = stamp_dir(args.stamp, args.smoke)
    out.mkdir(parents=True, exist_ok=True)
    run_dir = run_dir_of(out, condition, seed)
    if is_finished(run_dir):
        print(f"skip {run_dir.name}: already complete")
        return 0
    if run_dir.exists():  # an interrupted attempt: restart it from scratch
        for p in sorted(run_dir.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
        run_dir.rmdir()
    cmd = [
        sys.executable, "-m", "models.char_cnn.v2.train",
        "--root", str(args.root), "--manifest", str(args.manifest), "--expected-sha256", args.expected_sha256,
        "--seed", str(seed), "--run-dir", str(run_dir), "--no-save-checkpoint",
        *CONDITIONS[condition]["flags"],
    ]
    if args.smoke:
        cmd += ["--epochs", "1", "--limit-per-class", "40", "--n-boot", "20"]
    log = out / f"{condition}_s{seed}.log"
    with log.open("w", encoding="utf-8") as fh:
        code = subprocess.call(cmd, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
    print(f"{condition} seed {seed}: exit {code} (log: {log})")
    return code


# --- metrics --------------------------------------------------------------------------------------


def read_scores(path: Path) -> List[Dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [
            {"id": r["id"], "y": int(r["y"]), "cal": float(r["calibrated"]), "rep": r["representative"] == "1"}
            for r in csv.DictReader(fh)
        ]


def threshold_of(calibration: Path) -> float:
    return float(json.loads(calibration.read_text(encoding="utf-8"))["thresholds"][FPR_KEY]["threshold"])


def subset_metrics(rows: Sequence[Dict[str, Any]], models_by_id: Dict[str, Optional[str]], threshold: float,
                   generator: str) -> Dict[str, Any]:
    """AI of `generator` versus ALL test humans (representatives only)."""
    sel = [r for r in rows if r["rep"] and (r["y"] == 0 or models_by_id.get(r["id"]) == generator)]
    y = np.array([r["y"] for r in sel])
    s = np.array([r["cal"] for r in sel])
    tm = M.threshold_metrics(y, s, threshold)
    return {
        "n_ai": int(y.sum()), "n_human": int((1 - y).sum()),
        "roc_auc": M.roc_auc(y, s), "pr_auc": M.average_precision(y, s),
        "recall": tm["recall"], "fpr": tm["fpr"], "threshold": threshold,
    }


def run_metrics(run_dir: Path, models_by_id: Dict[str, Optional[str]]) -> Dict[str, Dict[str, Any]]:
    rows = read_scores(run_dir / "scores_test.csv")
    thr = threshold_of(run_dir / "calibration.json")
    return {g: subset_metrics(rows, models_by_id, thr, g) for g in GENERATORS}


def mean_std(values: Sequence[Optional[float]]) -> Dict[str, Optional[float]]:
    v = [x for x in values if x is not None]
    if not v:
        return {"mean": None, "std": None, "n": 0}
    return {"mean": float(np.mean(v)), "std": float(np.std(v, ddof=1)) if len(v) > 1 else 0.0, "n": len(v)}


METRIC_KEYS = ("roc_auc", "pr_auc", "recall", "fpr")


def aggregate_data(out: Path, reference: Optional[Path], models_by_id: Dict[str, Optional[str]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {"conditions": {}, "reference": None}
    if reference is not None:
        ref_dir = out / "R"
        ref_dir.mkdir(exist_ok=True)
        for name in ("scores_test.csv", "calibration.json"):
            (ref_dir / name).write_bytes((reference / name).read_bytes())
        result["reference"] = {"source_run": reference.name, "per_generator": run_metrics(ref_dir, models_by_id)}
    for cond, spec in CONDITIONS.items():
        per_seed: Dict[int, Dict[str, Any]] = {}
        for seed in SEEDS:
            rd = run_dir_of(out, cond, seed)
            if is_finished(rd):
                per_seed[seed] = run_metrics(rd, models_by_id)
        if not per_seed:
            continue
        entry: Dict[str, Any] = {"label": spec["label"], "seen": spec["seen"], "unseen": spec["unseen"],
                                 "seeds": sorted(per_seed), "per_seed": {str(k): v for k, v in per_seed.items()},
                                 "summary": {}}
        for role in ("seen", "unseen"):
            gen = spec[role]
            entry["summary"][role] = {
                k: mean_std([per_seed[s][gen][k] for s in per_seed]) for k in METRIC_KEYS
            }
        entry["drop"] = {
            k: {"mean": _diff(entry["summary"]["seen"][k]["mean"], entry["summary"]["unseen"][k]["mean"]),
                "per_seed": {str(s): _diff(per_seed[s][spec["seen"]][k], per_seed[s][spec["unseen"]][k])
                             for s in per_seed}}
            for k in ("roc_auc", "recall")
        }
        cfg = json.loads((run_dir_of(out, cond, sorted(per_seed)[0]) / "config.json").read_text(encoding="utf-8"))
        entry["training_counts"] = cfg.get("lolo")
        result["conditions"][cond] = entry
    result["verdict"] = verdict(result["conditions"])
    return result


def _diff(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return None if a is None or b is None else a - b


def verdict(conditions: Dict[str, Any]) -> Dict[str, Any]:
    if "DM" not in conditions or "Q" not in conditions:
        return {"label": "incompleto", "detail": "faltan las condiciones D-matched o Q"}
    detail = {}
    exceeds = {}
    for cond in ("DM", "Q"):
        d_roc = conditions[cond]["drop"]["roc_auc"]["mean"]
        d_rec = conditions[cond]["drop"]["recall"]["mean"]
        over = (d_roc is None or d_roc >= ROC_BOUND) or (d_rec is None or d_rec >= RECALL_BOUND)
        exceeds[cond] = over
        detail[cond] = {"drop_roc_auc": d_roc, "drop_recall": d_rec, "exceeds_bounds": over}
    if not any(exceeds.values()):
        label = "generaliza"
    elif all(exceeds.values()):
        label = "dependiente del generador"
    else:
        label = "mixto"
    return {"label": label, "detail": detail, "bounds": {"roc_auc": ROC_BOUND, "recall": RECALL_BOUND}}


# --- outputs --------------------------------------------------------------------------------------


def fmt(x: Optional[float], digits: int = 3) -> str:
    return "n/d" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{digits}f}"


def fmt_ms(ms: Dict[str, Optional[float]]) -> str:
    return "n/d" if ms["mean"] is None else f"{ms['mean']:.3f} ± {ms['std']:.3f}"


def write_csv_file(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["condition", "seed", "role", "generator", "n_ai", "n_human", "roc_auc", "pr_auc", "recall",
                    "fpr", "threshold"])
        if data["reference"]:
            for g, m in data["reference"]["per_generator"].items():
                w.writerow(["R", "deployed", "reference", g, m["n_ai"], m["n_human"], m["roc_auc"], m["pr_auc"],
                            m["recall"], m["fpr"], m["threshold"]])
        for cond, c in data["conditions"].items():
            for seed, per in c["per_seed"].items():
                for role in ("seen", "unseen"):
                    g = c[role]
                    m = per[g]
                    w.writerow([cond, seed, role, g, m["n_ai"], m["n_human"], m["roc_auc"], m["pr_auc"],
                                m["recall"], m["fpr"], m["threshold"]])


def write_report(path: Path, data: Dict[str, Any], smoke: bool) -> None:
    L: List[str] = ["# Experimento leave-one-LLM-out para CharCNN v2", ""]
    if smoke:
        L += ["> Corrida de humo (1 época, subconjunto pequeño): los números no son resultados.", ""]
    L += [PREREGISTRO, "## Resultados", ""]
    if data["reference"]:
        L += ["### R. Referencia (modelo desplegado, entrenado con todos los generadores)", "",
              "| Generador | n IA | ROC-AUC | PR-AUC | Recall@fpr_0.01 | FPR humano |", "|---|---|---|---|---|---|"]
        for g, m in data["reference"]["per_generator"].items():
            L.append(f"| {g} | {m['n_ai']} | {fmt(m['roc_auc'])} | {fmt(m['pr_auc'])} | {fmt(m['recall'])} "
                     f"| {fmt(m['fpr'], 4)} |")
        thr = next(iter(data["reference"]["per_generator"].values()))["threshold"]
        L += ["", f"Umbral `fpr_0.01` del modelo desplegado: {thr:.4f}. Un solo modelo, sin semillas.", ""]
    L += ["### Condiciones entrenadas (media ± desviación estándar entre semillas)", "",
          "| Condición | Subconjunto | Generador | ROC-AUC | PR-AUC | Recall@fpr_0.01 | FPR humano |",
          "|---|---|---|---|---|---|---|"]
    for cond, c in data["conditions"].items():
        for role, name in (("seen", "visto"), ("unseen", "no visto")):
            s = c["summary"][role]
            L.append(f"| {c['label']} | {name} | {c[role]} | {fmt_ms(s['roc_auc'])} | {fmt_ms(s['pr_auc'])} "
                     f"| {fmt_ms(s['recall'])} | {fmt_ms(s['fpr'])} |")
    L += ["", "### Contraste primario (visto − no visto, medias entre semillas)", "",
          "| Condición | Caída ROC-AUC | Caída recall | Semillas |", "|---|---|---|---|"]
    for cond, c in data["conditions"].items():
        L.append(f"| {c['label']} | {fmt(c['drop']['roc_auc']['mean'])} | {fmt(c['drop']['recall']['mean'])} "
                 f"| {len(c['seeds'])} |")
    L += ["", "### Datos de entrenamiento por condición (primera semilla)", ""]
    for cond, c in data["conditions"].items():
        info = c.get("training_counts") or {}
        L.append(f"- {c['label']}: train después = `{json.dumps(info.get('after', {}).get('train', {}))}`; "
                 f"val después = `{json.dumps(info.get('after', {}).get('val', {}))}`")
    v = data["verdict"]
    L += ["", "## Veredicto preregistrado", "", f"**{v['label']}**", ""]
    for cond, d in (v["detail"].items() if "bounds" in v else []):
        L.append(f"- {CONDITIONS[cond]['label']}: caída ROC-AUC {fmt(d['drop_roc_auc'])} (cota {ROC_BOUND}), "
                 f"caída recall {fmt(d['drop_recall'])} (cota {RECALL_BOUND}); supera cotas: "
                 f"{'sí' if d['exceeds_bounds'] else 'no'}")
    L += ["", "## Limitaciones", "",
          "- Solo dos generadores sustanciales (deepseek y qwen3); los demás tienen a lo sumo 2 archivos por split.",
          "- deepseek y qwen3 recibieron prompts idénticos: el estilo del prompt queda constante, "
          "por lo que no se evalúa sensibilidad al prompt.",
          "- Solo mide transferencia entre estos dos generadores; no permite concluir sobre otros LLM.",
          "- Los humanos de test son del mismo curso que los de entrenamiento.",
          "- Con 100 archivos de qwen3 en test, cada archivo equivale a 0.01 de recall, y la "
          "desviación estándar entre 3 semillas es una estimación pobre de la varianza.",
          "- No se calculó IC bootstrap.", ""]
    path.write_text("\n".join(L), encoding="utf-8")


def write_figure(path: Path, data: Dict[str, Any]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    seen_c, unseen_c, ref_c = "#2a6fb0", "#e08a1e", "#8c8c8c"
    cats: List[Dict[str, Any]] = []
    if data["reference"]:
        pg = data["reference"]["per_generator"]
        cats.append({"name": "R. Referencia\n(modelo desplegado,\ntodos los generadores)", "bars": [
            ("deepseek", pg["deepseek-chat"], None, ref_c, ""), ("qwen3", pg["qwen3"], None, ref_c, "//")]})
    for cond in ("D", "DM", "Q"):
        c = data["conditions"].get(cond)
        if c:
            cats.append({"name": CAT_NAMES[cond].format(**c), "bars": [
                ("visto", c["summary"]["seen"], True, seen_c, ""),
                ("no visto", c["summary"]["unseen"], True, unseen_c, "")]})
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for ax, key, ylab, lo in ((axes[0], "roc_auc", "ROC-AUC (eje desde 0.5)", 0.5),
                              (axes[1], "recall", "Recall con FPR humano ≈ 1% (umbral fpr_0.01)", 0.0)):
        x = 0
        ticks, labels = [], []
        for cat in cats:
            xs = []
            for label, val, is_summary, color, hatch in cat["bars"]:
                mean = val[key]["mean"] if is_summary else val[key]
                std = (val[key]["std"] if is_summary else 0.0) or 0.0
                ax.bar(x, (mean or lo) - lo, bottom=lo, width=0.8, color=color, hatch=hatch,
                       edgecolor="white", yerr=std if is_summary else None, capsize=4, ecolor="#222222")
                ax.text(x, (mean or lo) + std + 0.012, "n/d" if mean is None else f"{mean:.3f}",
                        ha="center", va="bottom", fontsize=8)
                ticks.append(x)
                labels.append(label)
                xs.append(x)
                x += 1
            ax.text(sum(xs) / len(xs), lo - (1 - lo) * 0.09, cat["name"], ha="center", va="top", fontsize=8.5,
                    fontweight="bold")
            x += 0.8
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, fontsize=7.5)
        ax.set_ylim(lo, 1.04)
        ax.set_ylabel(ylab)
        ax.grid(axis="y", alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=seen_c, label="generador visto en entrenamiento"),
                            Patch(color=unseen_c, label="generador no visto"),
                            Patch(color=ref_c, label="referencia (todos los generadores)")],
                   loc="lower center", bbox_to_anchor=(0.5, 0.035), ncol=3, fontsize=9, frameon=False)
    fig.suptitle("CharCNN v2: detección de generadores vistos y no vistos en entrenamiento "
                 "(test, IA contra todos los humanos)", fontsize=12)
    fig.text(0.5, 0.005, "Barras de error: desviación estándar entre 3 semillas. La referencia es un único modelo "
             "entrenado con todos los generadores.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.09, 1, 0.95))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def aggregate(args: argparse.Namespace) -> int:
    out = stamp_dir(args.stamp, args.smoke)
    manifest = load_manifest(args.manifest, args.expected_sha256)
    models_by_id = {s.id: s.model for s in manifest.samples("test", representatives_only=False)}
    reference = Path(args.reference_run) if args.reference_run else None
    data = aggregate_data(out, reference, models_by_id)
    (out / "results.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv_file(out / "results.csv", data)
    write_report(out / "report.md", data, args.smoke)
    write_figure(out / "lolo_charcnn.png", data)
    print(f"verdict: {data['verdict']['label']}; wrote results.json, results.csv, report.md, lolo_charcnn.png in {out}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=("preregister", "run", "aggregate"))
    p.add_argument("--condition", choices=sorted(CONDITIONS), help="run: condition (default: all)")
    p.add_argument("--seed", type=int, help="run: seed (default: 42, 7, 123)")
    p.add_argument("--root", type=Path, default=REPO, help="corpus root (the main checkout)")
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--expected-sha256", default="e835362d2e7a4153ef97204d4b30e769759a0f8f54f7db67b9e1fb2639e5238f")
    p.add_argument("--stamp", default=None, help="run directory name under runs/char_cnn_lolo (default: latest/new)")
    p.add_argument("--reference-run", default=None, help="deployed run directory (reads scores_test.csv + calibration.json)")
    p.add_argument("--smoke", action="store_true", help="1 epoch, tiny subset, runs/char_cnn_lolo/smoke")
    args = p.parse_args(argv)
    out = stamp_dir(args.stamp, args.smoke)
    out.mkdir(parents=True, exist_ok=True)
    if args.action == "preregister":
        (out / "preregistro.md").write_text("# Preregistro\n\n" + PREREGISTRO, encoding="utf-8")
        print(f"wrote {out / 'preregistro.md'}")
        return 0
    if args.action == "run":
        conds = [args.condition] if args.condition else list(CONDITIONS)
        seeds = [args.seed] if args.seed is not None else list(SEEDS)
        for cond in conds:
            for seed in seeds:
                code = train_one(args, cond, seed)
                if code != 0:
                    return code
        return 0
    return aggregate(args)


if __name__ == "__main__":
    sys.exit(main())

"""Run directories: provenance, `graphito.metrics/v1`, curve CSVs, headless plots, report.md.

A run lives in `<root>/<channel>/<YYYYmmdd-HHMMSS>[-N]/` (UTC; `-N` on collision, so two runs
never share a directory). matplotlib is imported lazily and drawn on the Agg canvas; when it
is missing, a plot is undefined (e.g. ROC on a single class) or drawing it raises, the run
still completes and the omission is recorded in `metrics.json` (`artifacts_missing`) and
explained in report.md.
"""

import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Union

import numpy as np

from . import metrics as M
from . import provenance

METRICS_SCHEMA = "graphito.metrics/v1"
CONFIG_SCHEMA = "graphito.run_config/v1"
PLOTS = ("roc.png", "pr.png", "confusion.png", "reliability.png")
POINT_METRICS = ("precision", "recall", "fpr", "f1")
STUDENT_OVERLAP_CAVEAT = (
    "Student overlap: the split unit is the block (course letter + Zx), not the student, so the "
    "same student can appear in train, val and test. Per-student style can leak across splits; "
    "treat results as optimistic for unseen students."
)


def _jsonable(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _write_json(path: Path, doc: Mapping) -> None:
    text = json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False, default=_jsonable)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def _key(value) -> str:
    return "<none>" if value is None else str(value)


# --- metrics ----------------------------------------------------------------------------------


def operating_points_from_calibration(calibration, *, source: Optional[str] = None) -> Dict[str, Dict]:
    """Operating points from a `LoadedCalibration` (or a calibration artifact).

    The source defaults to `calibration:<sha256 of the file>` when the file hash is known."""
    artifact = getattr(calibration, "artifact", calibration)
    sha = getattr(calibration, "sha256", None)
    source = source or (f"calibration:{sha}" if sha else "calibration")
    primary = artifact["primary"]
    points = {}
    for key in sorted(artifact["thresholds"], key=lambda k: k != primary):  # primary first
        entry = artifact["thresholds"][key]
        points[key] = {
            "threshold": entry["threshold"],
            "primary": key == primary,
            "source": source,
            "target_fpr": entry["target_fpr"],
            "low_support": entry["low_support"],
            "unachievable": entry["unachievable"],
            "reason": entry["reason"],
            "val": {k: entry[k] for k in ("achieved_fpr", "tpr", "n_neg", "n_pos", "min_negatives")},
        }
    return points


class _SharedViews:
    """`threshold_views` at one threshold, computed once per `(y, s)` pair.

    `bootstrap_many` calls every metric function with the same resampled arrays before moving
    to the next resample, so caching on array identity (references are held, so ids cannot be
    reused) lets all view/metric entries of an operating point share one evaluation."""

    def __init__(self, t: float, natural_prevalence: Optional[float]):
        self.t, self.natural_prevalence = t, natural_prevalence
        self._key = None
        self._views = None

    def __call__(self, y, s) -> Dict[str, Dict]:
        if self._key is None or self._key[0] is not y or self._key[1] is not s:
            self._views = M.threshold_views(y, s, self.t, self.natural_prevalence)
            self._key = (y, s)
        return self._views


def _view_metric(y, s, *, views: _SharedViews, view: str, metric: str):
    return views(y, s)[view][metric]


def _is_probability(s: np.ndarray) -> bool:
    return s.size == 0 or bool(np.isfinite(s).all() and s.min() >= 0.0 and s.max() <= 1.0)


def compute_metrics(
    y,
    s,
    *,
    channel: str,
    split: str,
    mode: str,
    seed: int,
    operating_points: Optional[Mapping[str, Mapping]] = None,
    natural_prevalence: Optional[float] = None,
    groups: Optional[Mapping[str, Sequence]] = None,
    bootstrap_groups=None,
    bootstrap_unit: Optional[str] = None,
    n_boot: int = 1000,
    alpha: float = 0.05,
    n_bins: int = 15,
    map_at_r: Optional[Mapping] = None,
) -> Dict:
    """The `graphito.metrics/v1` document for one channel on one split.

    Threshold-free metrics are computed on the observed set; every operating point is reported
    under the `observed` and `balanced` views, plus `natural` only when `natural_prevalence`
    is configured. Each value carries a bootstrap CI95 (`bootstrap_groups` resamples whole
    units, e.g. atomic units). `s` should be calibrated scores when the operating points come
    from a calibration file (thresholds live in calibrated space).
    """
    y = M.validate_labels(y)
    s = np.asarray(s, dtype=np.float64)
    views = ["observed", "balanced"] + (["natural"] if natural_prevalence is not None else [])
    probabilistic = _is_probability(s)
    points = dict(operating_points or {})

    fns = {"roc_auc": M.roc_auc, "pr_auc": M.average_precision}
    if probabilistic:
        fns["ece"] = partial(M.ece, n_bins=n_bins)
    shared: Dict[str, _SharedViews] = {}
    for key, point in points.items():
        if point.get("threshold") is None:
            continue
        shared[key] = _SharedViews(point["threshold"], natural_prevalence)
        for view in views:
            for metric in POINT_METRICS:
                fns[f"{key}|{view}|{metric}"] = partial(_view_metric, views=shared[key], view=view, metric=metric)
    boot = M.bootstrap_many(fns, y, s, n_boot=n_boot, seed=seed, groups=bootstrap_groups, alpha=alpha)
    counts = {"n": int(y.size), "n_pos": int(y.sum()), "n_neg": int(y.size - y.sum())}

    def summary(name: str) -> Dict:
        b = boot[name]
        return {
            "value": b["value"],
            "reason": b["reason"] if b["value"] is None else None,
            "ci95": b["ci95"],
            "ci_reason": b["reason"] if b["value"] is not None else None,
            "n_boot_valid": b["n_valid"],
            "skipped_resamples": b["skipped_resamples"],
        }

    threshold_free = {
        name: {**counts, "view": "observed", **summary(name)} for name in ("roc_auc", "pr_auc")
    }
    if probabilistic:
        threshold_free["ece"] = {**counts, "view": "observed", "n_bins": n_bins, **summary("ece")}
    else:
        threshold_free["ece"] = {
            **counts, "view": "observed", "n_bins": n_bins, "value": None,
            "reason": "scores_not_probabilities", "ci95": None, "ci_reason": None,
            "n_boot_valid": 0, "skipped_resamples": 0,
        }
    if map_at_r is not None:
        threshold_free["map_at_r"] = {"view": "observed", "ci95": None, **dict(map_at_r)}

    warnings: List[str] = []
    reason = M.undefined_reason(y)
    if reason:
        warnings.append(f"{reason}: ROC-AUC and PR-AUC are undefined on this set")
    if not probabilistic:
        warnings.append("scores_not_probabilities: ECE and reliability are not computed")

    op_out = {}
    for key, point in points.items():
        entry = {k: v for k, v in point.items()}
        t = point.get("threshold")
        if point.get("low_support"):
            warnings.append(f"low_support: operating point {key} was selected on few val negatives")
        if t is None:
            entry["reason"] = entry.get("reason") or "unachievable"
            warnings.append(f"unachievable: operating point {key} has no threshold ({entry['reason']})")
            op_out[key] = entry
            continue
        at = shared[key](y, s)  # usually cached from the bootstrap's full-set evaluation
        for view in views:
            base = {k: at[view][k] for k in ("tp", "fp", "tn", "fn", "n", "n_pos", "n_neg", "prevalence")}
            for metric in POINT_METRICS:
                b = summary(f"{key}|{view}|{metric}")
                base[metric] = {"view": view, **b, "value": at[view][metric]}
            entry[view] = {"view": view, **base}
        op_out[key] = entry

    per_group = {}
    for name, labels in (groups or {}).items():
        labels = np.asarray(labels, dtype=object)
        per_group[name] = {
            metric: {_key(g): v for g, v in M.per_group(fn, y, s, labels).items()}
            for metric, fn in (("roc_auc", M.roc_auc), ("pr_auc", M.average_precision))
        }

    any_boot = next(iter(boot.values()))
    return {
        "schema": METRICS_SCHEMA,
        "channel": channel,
        "split": split,
        "mode": mode,
        **counts,
        "prevalence_observed": float(y.mean()) if y.size else None,
        "views": views,
        "natural_prevalence": natural_prevalence,
        "threshold_free": threshold_free,
        "operating_points": op_out,
        "per_group": per_group,
        "bootstrap": {
            "n_boot": n_boot,
            "seed": seed,
            "alpha": alpha,
            "unit": bootstrap_unit or any_boot["unit"],
            "n_units": any_boot["n_units"],
        },
        "warnings": warnings,
    }


# --- plots ------------------------------------------------------------------------------------


def _matplotlib():
    """`(Figure, FigureCanvasAgg)` or None when matplotlib is unavailable. No pyplot, so no
    global backend state is touched and plotting works headless."""
    try:
        import matplotlib  # noqa: F401
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except ImportError:
        return None
    return Figure, FigureCanvasAgg


def _figure(mpl, title: str, xlabel: str, ylabel: str):
    Figure, FigureCanvasAgg = mpl
    fig = Figure(figsize=(4.5, 4.5), dpi=100)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(1, 1, 1)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    return fig, ax


def _plot_curve(mpl, path: Path, x, y_, title: str, xlabel: str, ylabel: str, diagonal: bool) -> None:
    fig, ax = _figure(mpl, title, xlabel, ylabel)
    if diagonal:
        ax.plot([0, 1], [0, 1], linestyle="--", color="0.6", linewidth=1)
    ax.plot(x, y_, color="#1f5aa6", linewidth=2)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    fig.tight_layout()
    fig.savefig(path)


def _plot_confusion(mpl, path: Path, point: Mapping, key: str) -> None:
    obs = point["observed"]
    cells = np.array([[obs["tn"], obs["fp"]], [obs["fn"], obs["tp"]]], dtype=np.float64)
    fig, ax = _figure(mpl, f"Confusion at {key} (t={point['threshold']:.4f})", "Predicted", "Actual")
    ax.imshow(cells, cmap="Blues")
    ax.set_xticks([0, 1], labels=["negative", "positive"])
    ax.set_yticks([0, 1], labels=["negative", "positive"])
    high = cells.max() / 2 if cells.max() else 0
    for (i, j), v in np.ndenumerate(cells):
        ax.text(j, i, f"{int(v)}", ha="center", va="center", color="white" if v > high else "black")
    fig.tight_layout()
    fig.savefig(path)


def _plot_reliability(mpl, path: Path, rel: Mapping) -> None:
    fig, ax = _figure(mpl, f"Reliability ({rel['n_bins']} bins)", "Mean predicted", "Fraction positive")
    ax.plot([0, 1], [0, 1], linestyle="--", color="0.6", linewidth=1)
    used = [b for b in rel["bins"] if b["n"]]
    ax.plot([b["mean_pred"] for b in used], [b["frac_pos"] for b in used], marker="o", color="#1f5aa6")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    fig.tight_layout()
    fig.savefig(path)


# --- run directory ----------------------------------------------------------------------------


def _write_csv(path: Path, header: Sequence[str], rows) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _fmt(value, digits: int = 4) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _fmt_ci(ci) -> str:
    return "null" if ci is None else f"[{ci[0]:.4f}, {ci[1]:.4f}]"


@dataclass(frozen=True)
class RunContext:
    path: Path
    channel: str
    config: Dict

    @classmethod
    def create(
        cls,
        channel: str,
        *,
        seed: int,
        split: str,
        mode: Optional[str] = None,
        manifest_path: Optional[Union[str, Path]] = None,
        manifest_sha256: Optional[str] = None,
        calibration_path: Optional[Union[str, Path]] = None,
        thresholds: Optional[Mapping[str, Optional[float]]] = None,
        config: Optional[Mapping] = None,
        argv: Optional[Sequence[str]] = None,
        root: Union[str, Path] = "runs",
        now: Optional[datetime] = None,
    ) -> "RunContext":
        """Create a fresh run directory and write `config.json` (provenance inside)."""
        if manifest_sha256 is None and manifest_path is not None:
            manifest_sha256 = provenance.file_sha256(manifest_path)
        if not manifest_sha256:
            raise ValueError("a run must record the split manifest sha256 (manifest_path or manifest_sha256)")
        calibration_sha256 = provenance.file_sha256(calibration_path) if calibration_path else None
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        base = Path(root) / channel
        base.mkdir(parents=True, exist_ok=True)
        stamp = now.strftime("%Y%m%d-%H%M%S")
        suffix = 0
        while True:
            path = base / (stamp if suffix == 0 else f"{stamp}-{suffix}")
            try:
                path.mkdir()
                break
            except FileExistsError:
                suffix += 1
        if calibration_sha256:
            threshold_source = f"calibration:{calibration_sha256}"
        else:
            threshold_source = "manual" if thresholds else None
        git = provenance.git_info()
        doc = {
            "schema": CONFIG_SCHEMA,
            "run_id": f"{channel}/{path.name}",
            "channel": channel,
            "split": split,
            "mode": mode,
            "seed": seed,
            "manifest_path": Path(manifest_path).as_posix() if manifest_path is not None else None,
            "manifest_sha256": manifest_sha256,
            "calibration_path": Path(calibration_path).as_posix() if calibration_path else None,
            "calibration_sha256": calibration_sha256,
            "thresholds": dict(thresholds or {}),
            "threshold_source": threshold_source,
            "git_sha": git["git_sha"],
            "dirty": git["dirty"],
            "argv": list(sys.argv if argv is None else argv),
            "created_at": now.isoformat(),
            **provenance.runtime_info(),
            "config": dict(config or {}),
        }
        _write_json(path / "config.json", doc)
        return cls(path=path, channel=channel, config=doc)

    def write(self, y, s, metrics: Mapping, *, manifest_stats: Optional[Mapping] = None) -> Dict:
        """Write curve CSVs, plots, `metrics.json` and `report.md`; return the metrics written."""
        y = M.validate_labels(y)
        s = np.asarray(s, dtype=np.float64)
        metrics = dict(metrics)
        missing: List[Dict[str, str]] = []

        roc = M.roc_curve(y, s)
        pr = M.pr_curve(y, s)
        rel = M.reliability_bins(y, s) if _is_probability(s) else None
        # roc_curve returns (fpr, tpr, thresholds); rows follow the header order
        _write_csv(self.path / "roc.csv", ("threshold", "fpr", "tpr"), zip(roc[2], roc[0], roc[1]) if roc else [])
        _write_csv(self.path / "pr.csv", ("threshold", "precision", "recall"),
                   zip(pr[2], pr[0], pr[1]) if pr else [])
        _write_csv(
            self.path / "reliability.csv", ("bin", "lo", "hi", "n", "mean_pred", "frac_pos"),
            ([i, b["lo"], b["hi"], b["n"], b["mean_pred"], b["frac_pos"]] for i, b in enumerate(rel["bins"]))
            if rel else [],
        )

        usable = [(k, p) for k, p in metrics.get("operating_points", {}).items() if "observed" in p]
        primary = next((kp for kp in usable if kp[1].get("primary")), usable[0] if usable else None)
        undefined = M.undefined_reason(y)
        plan = {
            "roc.png": undefined,
            "pr.png": undefined,
            "confusion.png": None if primary else "no_operating_point",
            "reliability.png": None if rel else "scores_not_probabilities",
        }
        mpl = _matplotlib()
        for name, reason in plan.items():
            if mpl is None:
                reason = "matplotlib_unavailable"
            if reason:
                missing.append({"file": name, "reason": reason})
                continue
            target = self.path / name
            try:
                if name == "roc.png":
                    auc = metrics["threshold_free"]["roc_auc"]["value"]
                    _plot_curve(mpl, target, roc[0], roc[1], f"ROC (AUC={_fmt(auc)})", "FPR", "TPR", True)
                elif name == "pr.png":
                    ap = metrics["threshold_free"]["pr_auc"]["value"]
                    _plot_curve(mpl, target, pr[1], pr[0], f"PR (AP={_fmt(ap)})", "Recall", "Precision", False)
                elif name == "confusion.png":
                    _plot_confusion(mpl, target, primary[1], primary[0])
                else:
                    _plot_reliability(mpl, target, rel)
            except Exception as exc:  # a plot is optional: record it, keep metrics.json and report.md
                target.unlink(missing_ok=True)  # never leave a half-written image behind
                missing.append({"file": name, "reason": f"{type(exc).__name__}: {exc}"})

        metrics["artifacts_missing"] = missing
        _write_json(self.path / "metrics.json", metrics)
        (self.path / "report.md").write_text(
            render_report(self.config, metrics, manifest_stats), encoding="utf-8", newline="\n"
        )
        return metrics


def render_report(config: Mapping, metrics: Mapping, manifest_stats: Optional[Mapping] = None) -> str:
    """Markdown summary: provenance, threshold-free metrics with CI95, operating points with
    their threshold source and support flags, per-group table, plots, warnings, limitations."""
    lines = [f"# Run report: {config['channel']} on {config['split']}", "", "## Provenance", ""]
    lines += ["| Field | Value |", "|---|---|"]
    for label, value in (
        ("Run", config["run_id"]),
        ("Split", config["split"]),
        ("Mode", config.get("mode")),
        ("Seed", config["seed"]),
        ("Manifest", config.get("manifest_path")),
        ("Manifest sha256", config["manifest_sha256"]),
        ("Calibration sha256", config.get("calibration_sha256")),
        ("Threshold source", config.get("threshold_source")),
        ("Git", f"{config['git_sha']} (dirty: {config['dirty']})"),
        ("Created (UTC)", config["created_at"]),
    ):
        lines.append(f"| {label} | {_fmt(value)} |")

    lines += ["", "## Threshold-free metrics (observed view)", ""]
    lines += ["| Metric | Value | CI95 | n | n_pos | n_neg | Note |", "|---|---|---|---|---|---|---|"]
    for name, m in metrics["threshold_free"].items():
        note = m.get("reason") or m.get("ci_reason") or ""
        lines.append(
            f"| {name} | {_fmt(m.get('value'))} | {_fmt_ci(m.get('ci95'))} | {m.get('n', '')} "
            f"| {m.get('n_pos', '')} | {m.get('n_neg', '')} | {note} |"
        )

    lines += ["", "## Operating points", ""]
    points = metrics.get("operating_points", {})
    if not points:
        lines.append("No operating points (threshold-free evaluation only).")
    else:
        lines += [
            "| Point | Threshold | Source | Target FPR | View | Precision | Recall | FPR | F1 | Support |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for key, p in points.items():
            val = p.get("val") or {}
            support = (
                f"low_support (val n_neg={val.get('n_neg')} < {val.get('min_negatives')})"
                if p.get("low_support") else "ok"
            )
            views = [v for v in metrics["views"] if v in p]
            if not views:
                lines.append(
                    f"| {key} | null | {p.get('source')} | {_fmt(p.get('target_fpr'))} | - | - | - | - | - "
                    f"| {support}; {p.get('reason')} |"
                )
            for view in views:
                cells = [
                    f"{_fmt(p[view][m]['value'])} {_fmt_ci(p[view][m]['ci95'])}" for m in POINT_METRICS
                ]
                lines.append(
                    f"| {key} | {_fmt(p['threshold'])} | {p.get('source')} | {_fmt(p.get('target_fpr'))} "
                    f"| {view} | {' | '.join(cells)} | {support} |"
                )

    if metrics.get("per_group"):
        lines += ["", "## Per group (ROC-AUC)", "", "| Breakdown | Group | n | n_pos | AUC | Note |", "|---|---|---|---|---|---|"]
        for name, table in metrics["per_group"].items():
            for g, m in table["roc_auc"].items():
                lines.append(f"| {name} | {g} | {m['n']} | {m['n_pos']} | {_fmt(m['value'])} | {m['reason'] or ''} |")

    lines += ["", "## Plots", ""]
    missing = {m["file"]: m["reason"] for m in metrics.get("artifacts_missing", [])}
    for name in PLOTS:
        if name in missing:
            lines.append(f"- {name} not produced: {missing[name]}")
        else:
            lines.append(f"- ![{name}]({name})")

    if metrics.get("warnings"):
        lines += ["", "## Warnings", ""] + [f"- {w}" for w in metrics["warnings"]]

    lines += ["", "## Limitations", "", f"- {STUDENT_OVERLAP_CAVEAT}"]
    stats = manifest_stats or {}
    if "student_overlap" in stats:
        lines.append(f"- Student overlap counts from the manifest: `{json.dumps(stats['student_overlap'], sort_keys=True)}`")
    for key in sorted(k for k in stats if k != "student_overlap"):
        lines.append(f"- Manifest {key}: `{json.dumps(stats[key], sort_keys=True, default=_jsonable)}`")
    return "\n".join(lines) + "\n"

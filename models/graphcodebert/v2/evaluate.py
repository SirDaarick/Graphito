"""Zero-shot evaluation of GraphCodeBERT v2 on split_v1 (spec GV1-GV6; design "Evaluation").

    python -m models.graphcodebert.v2.evaluate --manifest data/splits/split_v1.json.gz \
        --expected-sha256 <sha> --device cuda --local-files-only --n-boot 1000

Data: labelled human pairs of `val` and `test` (`plagiarism_pairs`, ambiguous and unlabeled
entries excluded and counted), scored within assignment only. File bytes are read from
`<root>/<id>` and must match the manifest sha256.

Stages (each split is touched in this order, and test only once):

1. `val`: embed val files (cached) and score val pairs for every method and pooling.
2. `selection`: pooling per embedding method on val PR-AUC (`all` view; ties by MAP@R, then
   `cls`, design D9) -> `selection.json`; thresholds with `select_threshold` on the raw val score
   at `DEFAULT_TARGETS` (design D10) -> `thresholds_val.json`; an isotonic `calibration.json` of
   the selected v2 cosine (for SDD-4 only; metrics never use it).
3. `test`: embed and score test pairs once, then per method and view `compute_metrics` (bootstrap
   by assignment, design D11; MAP@R with its own assignment bootstrap CI) -> `<method>__<view>/`.
4. `report`: `summary.json`, `data_summary.json` and the root `report.md`.

Methods: `v2` (DFG), `v2_nodfg` (same windows, no nodes), `jaccard` (5-token shingles),
`winnowing` (k=5, w=4) and `legacy` (frozen pipeline with its adapter; `skipped` with a reason
when it cannot be built). Views: `all` and `no_identical` (label-0 pairs with equal `norm_hash`
dropped).

Curves: `roc.csv.gz` and `pr.csv.gz` are thinned to at most `CURVE_MAX_POINTS` points (uniform
arc length, endpoints kept) and gzip-compressed, since full curves over ~1.9M pairs would cost
about 1 GB per run; the thinning is recorded in `metrics.json` (`curves`). PR-AUC/ROC-AUC are
computed on the full scores.

Exit codes (`runs.py`): 0 complete; 1 refused (nothing written); 2 usage error; 3 run failed
(`config.json` status `failed` with stage and reason).
"""

import argparse
import gzip
import hashlib
import io
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from models.evaluation import metrics as M
from models.evaluation.calibration import (
    DEFAULT_TARGETS,
    ScoredSet,
    build_calibration,
    save_calibration,
    select_threshold,
    threshold_key,
)
from models.evaluation.manifest import DEFAULT_MANIFEST, ManifestError, load_manifest
from models.evaluation.provenance import atomic_write_bytes, package_versions
from models.evaluation.report import RunContext, compute_metrics, render_report
from models.graphcodebert.v2.baselines import SetSimilarity, V2FileEmbedder, jaccard_set, load_legacy, winnowing_set
from models.graphcodebert.v2.cache import CachedEmbedder, EmbeddingCache, FileEmbedding
from models.graphcodebert.v2.config import GCBV2Config
from models.graphcodebert.v2.pairs import (
    VIEWS,
    EvalPairs,
    ScoredPairs,
    embedding_similarity,
    map_at_r_ci,
    score_pairs,
    stack_embeddings,
)
from models.graphcodebert.v2.runs import (
    DEFAULT_N_BOOT,
    REFUSED_EXIT,
    RUN_FAILED_EXIT,
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_RUNNING,
    describe_error,
    resolve_device,
    set_run_status,
    write_json,
)

__all__ = [
    "CHANNEL",
    "METHODS",
    "CURVE_MAX_POINTS",
    "Refused",
    "FileRecord",
    "Evaluation",
    "choose_pooling",
    "operating_points",
    "view_metrics",
    "thin_indices",
    "load_files",
    "load_embedders",
    "build_parser",
    "main",
]

CHANNEL = "graphcodebert"
METHODS = ("v2", "v2_nodfg", "jaccard", "winnowing", "legacy")
EMBEDDING_METHODS = ("v2", "v2_nodfg", "legacy")
LEXICAL: Dict[str, Callable[[str], np.ndarray]] = {"jaccard": jaccard_set, "winnowing": winnowing_set}
DEFAULT_MODEL = "microsoft/graphcodebert-base"
CURVE_MAX_POINTS = 2000
VERSION_PACKAGES = (
    "torch", "transformers", "tree-sitter", "tree-sitter-c", "tree-sitter-cpp", "numpy", "scipy", "scikit-learn",
)
POINT_SOURCE = "val_raw_score"


class Refused(Exception):
    """A pre-run check failed; nothing has been written."""


def _log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def _plain(value):
    """JSON-safe copy (numpy scalars/arrays and paths converted)."""
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_plain(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return value.as_posix()
    return value


# --- inputs -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FileRecord:
    id: str
    sha256: str
    text: str
    lang: str


def load_files(root: Path, samples: Sequence) -> Dict[str, FileRecord]:
    """Read and sha256-check every file; refuse on any missing or changed file."""
    out: Dict[str, FileRecord] = {}
    missing, changed = [], []
    for s in samples:
        if s.id in out:
            continue
        path = Path(root) / s.id
        if not path.is_file():
            missing.append(s.id)
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != s.sha256:
            changed.append(s.id)
            continue
        out[s.id] = FileRecord(s.id, s.sha256, data.decode("utf-8", errors="replace"), s.lang)
    if missing or changed:
        parts = []
        if missing:
            parts.append(f"{len(missing)} missing (e.g. {missing[:3]})")
        if changed:
            parts.append(f"{len(changed)} with a sha256 different from the manifest (e.g. {changed[:3]})")
        raise Refused("input files do not match the manifest: " + "; ".join(parts))
    return out


def _model_available(name: str) -> bool:
    """True when the model config is in the local HF cache (no network)."""
    try:
        from transformers import AutoConfig

        AutoConfig.from_pretrained(name, local_files_only=True)
        return True
    except Exception:
        return False


def load_embedders(
    methods: Sequence[str],
    *,
    model_name: str = DEFAULT_MODEL,
    local_files_only: bool = False,
    device=None,
    batch_size: int = 16,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """File embedders and status per embedding method. Raises `Refused` when a v2 method is
    requested and the model cannot be loaded; legacy is `skipped` instead (GV5.1)."""
    embedders: Dict[str, Any] = {}
    statuses: Dict[str, Dict[str, Any]] = {}
    v2_methods = [m for m in methods if m in ("v2", "v2_nodfg")]
    if v2_methods:
        if local_files_only and not _model_available(model_name):
            raise Refused(f"{model_name} is not in the local cache (--local-files-only)")
        from models.graphcodebert.v2.embed import GraphCodeBERTV2Embedder

        try:
            v2 = GraphCodeBERTV2Embedder.from_pretrained(
                model_name, GCBV2Config(), local_files_only=local_files_only, device=device, batch_size=batch_size
            )
        except Exception as exc:
            raise Refused(f"cannot load {model_name}: {describe_error(exc)}") from None
        for m in v2_methods:
            embedders[m] = V2FileEmbedder(v2, use_dfg=(m == "v2"))
            statuses[m] = {"status": "ok", "variant": embedders[m].variant, "reason": None}
    if "legacy" in methods:
        if local_files_only and not _model_available(model_name):
            statuses["legacy"] = {"status": "skipped", "variant": None, "reason": "model not cached locally (--local-files-only)"}
        else:
            from models.graphcodebert.config import GraphCodeBERTConfig

            legacy, status = load_legacy(GraphCodeBERTConfig(model_name=model_name), device=device)
            statuses["legacy"] = status
            if legacy is not None:
                embedders["legacy"] = legacy
    return embedders, statuses


# --- selection, thresholds, metrics -------------------------------------------------------------


def _rank(value: Optional[float]) -> float:
    return -np.inf if value is None else float(value)


def choose_pooling(candidates: Mapping[str, Mapping[str, Optional[float]]]) -> str:
    """Highest val PR-AUC, ties broken by MAP@R, then `cls` (design D9). None ranks lowest."""
    order = sorted(candidates, key=lambda p: (p != "cls", p))  # cls first, so it wins full ties
    return max(order, key=lambda p: (_rank(candidates[p].get("pr_auc")), _rank(candidates[p].get("map_at_r"))))


def operating_points(entry: Mapping[str, Any]) -> Dict[str, Dict]:
    """`compute_metrics` operating points from a `thresholds_val.json` method entry (primary first)."""
    primary = entry["primary"]
    points = {}
    for key in sorted(entry["thresholds"], key=lambda k: k != primary):
        t = entry["thresholds"][key]
        points[key] = {
            "threshold": t["threshold"],
            "primary": key == primary,
            "source": POINT_SOURCE,
            "target_fpr": t["target_fpr"],
            "low_support": t["low_support"],
            "unachievable": t["unachievable"],
            "reason": t["reason"],
            "val": {k: t[k] for k in ("achieved_fpr", "tpr", "n_neg", "n_pos", "min_negatives")},
        }
    return points


def view_metrics(
    ep: EvalPairs, scored: ScoredPairs, view: str, *, points: Mapping, n_boot: int, seed: int, mode: str
) -> Dict:
    """`graphito.metrics/v1` for one method and view, bootstrap by assignment."""
    mask = ep.view_mask(view)
    y = ep.pairs.label[mask].astype(np.int64)
    s = scored.scores[mask]
    groups = ep.pairs.assignment[mask]
    map_ci = map_at_r_ci(scored.map_at_r[view]["per_assignment"], n_boot=n_boot, seed=seed)
    return compute_metrics(
        y, s, channel=CHANNEL, split=ep.split, mode=mode, seed=seed, operating_points=points,
        bootstrap_groups=groups, bootstrap_unit="assignment", n_boot=n_boot, map_at_r=map_ci,
    )


def _point_values(ep: EvalPairs, scored: ScoredPairs, view: str) -> Dict[str, Optional[float]]:
    mask = ep.view_mask(view)
    y = ep.pairs.label[mask].astype(np.int64)
    s = scored.scores[mask]
    return {
        "pr_auc": M.average_precision(y, s),
        "roc_auc": M.roc_auc(y, s),
        "map_at_r": scored.map_at_r[view]["value"],
    }


# --- curves -------------------------------------------------------------------------------------


def thin_indices(x, y, max_points: int) -> np.ndarray:
    """At most ~`max_points` indices of a curve, uniform in arc length, first and last kept."""
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    n = x.size
    if n <= max_points:
        return np.arange(n)
    step = np.abs(np.diff(x)) + np.abs(np.diff(y))
    arc = np.r_[0.0, np.cumsum(np.nan_to_num(step))]
    if arc[-1] <= 0:
        idx = np.linspace(0, n - 1, max_points).round().astype(np.int64)
    else:
        idx = np.searchsorted(arc, np.linspace(0.0, arc[-1], max_points), side="left")
    return np.unique(np.r_[0, np.clip(idx, 0, n - 1), n - 1])


def _gzip_csv(path: Path, header: Sequence[str], columns: Sequence[np.ndarray]) -> None:
    text = io.StringIO()
    text.write(",".join(header) + "\n")
    for row in zip(*columns):
        text.write(",".join(repr(float(v)) for v in row) + "\n")
    atomic_write_bytes(path, gzip.compress(text.getvalue().encode("utf-8"), mtime=0))


def _plot(path: Path, x, y, title: str, xlabel: str, ylabel: str, diagonal: bool) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(4.5, 4.5), dpi=100)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(1, 1, 1)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if diagonal:
        ax.plot([0, 1], [0, 1], linestyle="--", color="0.6", linewidth=1)
    ax.plot(x, y, color="#1f5aa6", linewidth=2)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    atomic_write_bytes(path, buf.getvalue())


def write_curves(path: Path, y, s, metrics: Mapping, max_points: int) -> Tuple[Dict, List[Dict[str, str]]]:
    """Thinned gzip curve CSVs and ROC/PR plots; returns (`curves` record, missing artifacts)."""
    roc, pr = M.roc_curve(y, s), M.pr_curve(y, s)
    info: Dict[str, Any] = {
        "files": [],
        "max_points": max_points,
        "thinning": "uniform arc length, first and last point kept",
        "compressed": "gzip",
        "n_points_full": {"roc": None if roc is None else int(roc[0].size), "pr": None if pr is None else int(pr[0].size)},
        "n_points_written": {"roc": 0, "pr": 0},
    }
    missing = [{"file": "confusion.png", "reason": "omitted (counts are in metrics.json operating_points)"},
               {"file": "reliability.png", "reason": "scores_not_probabilities"}]
    undefined = M.undefined_reason(y)
    if roc is None or pr is None:
        missing += [{"file": "roc.png", "reason": undefined}, {"file": "pr.png", "reason": undefined}]
        return info, missing
    fpr, tpr, thr = roc
    i = thin_indices(fpr, tpr, max_points)
    _gzip_csv(path / "roc.csv.gz", ("threshold", "fpr", "tpr"), (thr[i], fpr[i], tpr[i]))
    precision, recall, pthr = pr
    j = thin_indices(recall, precision, max_points)
    _gzip_csv(path / "pr.csv.gz", ("threshold", "precision", "recall"), (pthr[j], precision[j], recall[j]))
    info["files"] = ["roc.csv.gz", "pr.csv.gz"]
    info["n_points_written"] = {"roc": int(i.size), "pr": int(j.size)}
    tf = metrics["threshold_free"]
    for name, args in (
        ("roc.png", (fpr[i], tpr[i], f"ROC (AUC={tf['roc_auc']['value']:.4f})", "FPR", "TPR", True)),
        ("pr.png", (recall[j], precision[j], f"PR (AP={tf['pr_auc']['value']:.4f})", "Recall", "Precision", False)),
    ):
        try:
            _plot(path / name, *args)
        except Exception as exc:  # plots are optional
            missing.append({"file": name, "reason": describe_error(exc)})
    return info, missing


# --- evaluation ---------------------------------------------------------------------------------


class Evaluation:
    """The staged evaluation of one run directory (val -> selection -> test once -> report)."""

    def __init__(
        self,
        run_dir: Path,
        *,
        val: EvalPairs,
        test: EvalPairs,
        files: Mapping[str, FileRecord],
        embedders: Mapping[str, Any],
        statuses: Mapping[str, Mapping[str, Any]],
        methods: Sequence[str],
        cache_root: Optional[Path],
        n_boot: int,
        seed: int,
        manifest_sha256: str,
        manifest_path: Optional[Path],
        run_config: Optional[Mapping] = None,
        curve_max_points: int = CURVE_MAX_POINTS,
    ):
        self.run_dir = Path(run_dir)
        self.splits = {"val": val, "test": test}
        self.files = files
        self.methods = tuple(methods)
        self.n_boot, self.seed = n_boot, seed
        self.manifest_sha256, self.manifest_path = manifest_sha256, manifest_path
        self.curve_max_points = curve_max_points
        self.config = dict(run_config) if run_config else {
            "channel": CHANNEL, "split": "test", "mode": "zero_shot", "run_id": f"{CHANNEL}/{self.run_dir.name}",
            "seed": seed, "manifest_sha256": manifest_sha256, "git_sha": None, "dirty": None, "created_at": None,
        }
        self.status: Dict[str, Dict[str, Any]] = {}
        self.cached: Dict[str, CachedEmbedder] = {}
        for m in self.methods:
            if m in LEXICAL:
                self.status[m] = {"status": "ok", "variant": m, "reason": None}
            elif m in embedders:
                self.cached[m] = CachedEmbedder(embedders[m], EmbeddingCache(cache_root, embedders[m].key_fields()))
                self.status[m] = dict(statuses.get(m) or {"status": "ok", "variant": embedders[m].variant, "reason": None})
            else:
                self.status[m] = dict(statuses.get(m) or {"status": "skipped", "variant": None, "reason": "not_loaded"})
        self.entries: Dict[str, Dict[str, List[FileEmbedding]]] = {m: {} for m in self.cached}
        self._val: Dict[str, Dict[Optional[str], ScoredPairs]] = {}
        self._selection: Optional[Dict] = None
        self._thresholds: Optional[Dict] = None
        self._test: Dict[str, Dict] = {}
        self._test_started = False

    @property
    def active(self) -> List[str]:
        return [m for m in self.methods if self.status[m]["status"] == "ok"]

    def _score(self, method: str, split: str) -> Dict[Optional[str], ScoredPairs]:
        ep = self.splits[split]
        records = [self.files[i] for i in ep.pairs.ids]
        t0 = time.perf_counter()
        if method in LEXICAL:
            fn = LEXICAL[method]
            sims = {None: SetSimilarity([fn(r.text) for r in records])}
        else:
            cached = self.cached[method]
            entries = [cached.embed(r.sha256, r.text, r.lang) for r in records]
            self.entries[method][split] = entries
            sims = {p: embedding_similarity(stack_embeddings(entries, p)[0]) for p in cached.poolings}
        out = {p: score_pairs(sim, ep) for p, sim in sims.items()}
        _log(f"{split}/{method}: {len(records)} files, {ep.pairs.a.size} pairs in {time.perf_counter() - t0:.1f}s")
        return out

    def run_val(self) -> None:
        for m in self.active:
            self._val[m] = self._score(m, "val")

    def select(self) -> None:
        if not self._val and self.active:
            raise RuntimeError("selection needs the val stage first")
        val = self.splits["val"]
        y = val.pairs.label.astype(np.int64)
        selection = {
            "split": "val",
            "view": "all",
            "rule": "max val PR-AUC, ties by MAP@R, then cls",
            "n_files": len(val.pairs.ids),
            "files_sha256": hashlib.sha256("\n".join(sorted(val.pairs.ids)).encode("utf-8")).hexdigest(),
            "n_pairs": int(val.pairs.a.size),
            "methods": {},
        }
        thresholds = {"split": "val", "view": "all", "space": "raw", "targets": list(DEFAULT_TARGETS), "methods": {}}
        for m in self.active:
            scored = self._val[m]
            candidates = {p: _point_values(val, s, "all") for p, s in scored.items()}
            pooling = None if list(scored) == [None] else choose_pooling(candidates)
            selection["methods"][m] = {"pooling": pooling, "candidates": {(p or "set"): v for p, v in candidates.items()}}
            s = scored[pooling].scores
            thresholds["methods"][m] = {
                "split": "val",
                "view": "all",
                "space": "raw",
                "pooling": pooling,
                "primary": threshold_key(DEFAULT_TARGETS[0]),
                "thresholds": {threshold_key(t): select_threshold(y, s, t) for t in DEFAULT_TARGETS},
            }
        write_json(self.run_dir / "selection.json", _plain(selection))
        write_json(self.run_dir / "thresholds_val.json", _plain(thresholds))
        self._selection, self._thresholds = selection, thresholds
        if "v2" in self.active:
            pooling = selection["methods"]["v2"]["pooling"]
            ids = val.pairs.ids
            data = ScoredSet(
                [f"{ids[a]}|{ids[b]}" for a, b in zip(val.pairs.a, val.pairs.b)],
                self._val["v2"][pooling].scores, y, "val", manifest_sha256=self.manifest_sha256,
            )
            artifact, _ = build_calibration(
                data, channel=CHANNEL, score_name=f"cosine_v2_{pooling}", seed=self.seed, method="isotonic",
                manifest_path=self.manifest_path,
            )
            save_calibration(artifact, self.run_dir / "calibration.json")

    def evaluate_test(self) -> None:
        if self._selection is None:
            raise RuntimeError("test evaluation needs the val selection first")
        if self._test_started:
            raise RuntimeError("the test split is evaluated once per run")
        self._test_started = True
        test = self.splits["test"]
        for m in self.active:
            scored = self._score(m, "test")
            pooling = self._selection["methods"][m]["pooling"]
            points = operating_points(self._thresholds["methods"][m])
            other = [p for p in scored if p != pooling]
            result = {"pooling": pooling, "views": {}}
            for view in VIEWS:
                metrics = view_metrics(
                    test, scored[pooling], view, points=points, n_boot=self.n_boot, seed=self.seed,
                    mode=f"zero_shot/{m}/{view}",
                )
                metrics.update(
                    method=m,
                    view=view,
                    variant=self.status[m].get("variant"),
                    pooling=pooling,
                    pooling_selected_on="val",
                    dropped_pairs=test.dropped(view),
                    secondary_pooling=(
                        {"pooling": other[0], "note": "test point values only, no CI", **_point_values(test, scored[other[0]], view)}
                        if other else None
                    ),
                )
                self._write_method_dir(m, view, test, scored[pooling], metrics)
                result["views"][view] = metrics
            self._test[m] = result

    def _write_method_dir(self, method: str, view: str, ep: EvalPairs, scored: ScoredPairs, metrics: Dict) -> None:
        path = self.run_dir / f"{method}__{view}"
        path.mkdir(parents=True, exist_ok=False)
        mask = ep.view_mask(view)
        y, s = ep.pairs.label[mask].astype(np.int64), scored.scores[mask]
        curves, missing = write_curves(path, y, s, metrics, self.curve_max_points)
        metrics["curves"] = curves
        metrics["artifacts_missing"] = missing
        doc = _plain(metrics)
        write_json(path / "metrics.json", doc)
        atomic_write_bytes(path / "report.md", render_report(self.config, doc).encode("utf-8"))

    # --- report -----------------------------------------------------------------------------

    def _data_summary(self) -> Dict:
        splits = {}
        for name, ep in self.splits.items():
            views = {}
            for view in VIEWS:
                mask = ep.view_mask(view)
                n_pos = int(ep.pairs.label[mask].sum())
                views[view] = {"n_pairs": int(mask.sum()), "n_pos": n_pos, "n_neg": int(mask.sum()) - n_pos,
                               "dropped": ep.dropped(view)}
            splits[name] = {
                "n_files": len(ep.pairs.ids),
                "n_assignments": len(ep.blocks),
                "exclusions": ep.exclusions,
                "same_student_pairs": ep.same_student_pairs,
                "views": views,
            }
        embeddings = {}
        for m, per_split in self.entries.items():
            flat = [e for entries in per_split.values() for e in entries]

            def rate(key, items=flat):
                values = [bool(e.flags[key]) for e in items if e.flags.get(key) is not None]
                return float(np.mean(values)) if values else None

            windows = [e.flags["n_windows"] for e in flat if e.flags.get("n_windows") is not None]
            embeddings[m] = {
                "variant": self.status[m].get("variant"),
                "files": len(flat),
                "failed": sum(not e.success for e in flat),
                "parse_error_rate": rate("parse_errors"),
                "truncation_rate": rate("truncated"),
                "mean_windows": float(np.mean(windows)) if windows else None,
                "cache": dict(self.cached[m].stats),
                "cache_key": self.cached[m].cache.key,
            }
        return {"splits": splits, "embeddings": embeddings}

    def _summary(self) -> Dict:
        methods = {}
        for m in self.methods:
            entry = {**self.status[m]}
            if m in self._test:
                res = self._test[m]
                entry["pooling"] = res["pooling"]
                entry["views"] = {}
                for view, metrics in res["views"].items():
                    tf = metrics["threshold_free"]
                    entry["views"][view] = {
                        "n": metrics["n"],
                        "n_pos": metrics["n_pos"],
                        **{k: {"value": tf[k]["value"], "ci95": tf[k]["ci95"], "reason": tf[k].get("reason")}
                           for k in ("pr_auc", "map_at_r", "roc_auc")},
                        "secondary_pooling": metrics["secondary_pooling"],
                    }
            methods[m] = entry
        return {"run_id": self.config.get("run_id"), "split": "test", "n_boot": self.n_boot, "seed": self.seed,
                "selection": {m: v["pooling"] for m, v in (self._selection or {}).get("methods", {}).items()},
                "methods": methods}

    def finish(self) -> None:
        summary = _plain(self._summary())
        data = _plain(self._data_summary())
        write_json(self.run_dir / "summary.json", summary)
        write_json(self.run_dir / "data_summary.json", data)
        atomic_write_bytes(self.run_dir / "report.md", render_root_report(self.config, summary, data).encode("utf-8"))


def _fmt(entry: Mapping) -> str:
    value, ci = entry.get("value"), entry.get("ci95")
    if value is None:
        return f"null ({entry.get('reason') or 'undefined'})"
    return f"{value:.4f}" + (f" [{ci[0]:.4f}, {ci[1]:.4f}]" if ci else "")


def render_root_report(config: Mapping, summary: Mapping, data: Mapping) -> str:
    lines = [
        "# GraphCodeBERT zero-shot evaluation",
        "",
        f"- Run: {config.get('run_id')}; manifest sha256 {config.get('manifest_sha256')}",
        f"- Model revision: {(config.get('config') or {}).get('model_revision')}; seed {summary['seed']}; "
        f"n_boot {summary['n_boot']}; limit_assignments {(config.get('config') or {}).get('limit_assignments')}",
        "- Split: test, evaluated once. Pooling and thresholds were chosen on val only (raw scores).",
        "",
    ]
    for view in VIEWS:
        lines += [f"## Test, view `{view}`", "",
                  "| Method | Pooling | PR-AUC [CI95] | MAP@R [CI95] | ROC-AUC [CI95] | n | n_pos |",
                  "|---|---|---|---|---|---|---|"]
        for m, entry in summary["methods"].items():
            if entry.get("status") != "ok":
                lines.append(f"| {m} | - | skipped: {entry.get('reason')} | | | | |")
                continue
            v = entry["views"][view]
            lines.append(
                f"| {m} | {entry.get('pooling') or '-'} | {_fmt(v['pr_auc'])} | {_fmt(v['map_at_r'])} "
                f"| {_fmt(v['roc_auc'])} | {v['n']} | {v['n_pos']} |"
            )
        lines.append("")
    lines += ["## Data", ""]
    for split, d in data["splits"].items():
        lines.append(
            f"- {split}: {d['n_files']} files, {d['n_assignments']} assignments, "
            f"{d['views']['all']['n_pairs']} pairs ({d['views']['all']['n_pos']} positive); "
            f"`no_identical` drops {d['views']['no_identical']['dropped']}; exclusions {d['exclusions']}; "
            f"same-student candidate pairs {d['same_student_pairs']}"
        )
    for m, e in data["embeddings"].items():
        lines.append(
            f"- {m} ({e['variant']}): {e['files']} file embeddings, {e['failed']} failed (scored 0), "
            f"parse-error rate {e['parse_error_rate']}, truncation rate {e['truncation_rate']}, "
            f"mean windows {e['mean_windows']}, cache {e['cache']}"
        )
    lines += [
        "",
        "## Caveats",
        "",
        "- `legacy` is the frozen pre-v2 pipeline with its adapter (or base encoder, see reason); its "
        "numbers are not comparable with earlier reports.",
        "- Ground-truth labels are noisy (plagiarism clusters annotated per assignment); unlabeled and "
        "ambiguous files are excluded.",
        "- Curves are thinned to at most "
        f"{CURVE_MAX_POINTS} points and gzip-compressed; AUC values use every pair.",
        "- `calibration.json` (isotonic on val cosine) is for SDD-4; no metric here uses it.",
        "",
    ]
    return "\n".join(lines)


# --- CLI ----------------------------------------------------------------------------------------


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m models.graphcodebert.v2.evaluate", description=__doc__.split("\n\n")[0])
    p.add_argument("--manifest", default=str(DEFAULT_MANIFEST.relative_to(DEFAULT_MANIFEST.parents[2])))
    p.add_argument("--expected-sha256", default=None)
    p.add_argument("--root", default=".")
    p.add_argument("--runs-root", default="runs")
    p.add_argument("--device", default=None)
    p.add_argument("--batch-size", type=_positive_int, default=16)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n-boot", type=_positive_int, default=DEFAULT_N_BOOT)
    p.add_argument("--methods", default=",".join(METHODS))
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--cache-dir", default=None, help="default: <runs-root>/graphcodebert/_cache")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--local-files-only", action="store_true")
    p.add_argument("--limit-assignments", type=_positive_int, default=None, help="debug: first N assignments per split")
    return p


def _refuse(message: str) -> int:
    print(f"REFUSED: {message}", file=sys.stderr)
    return REFUSED_EXIT


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    argv_list = list(sys.argv if argv is None else ["models.graphcodebert.v2.evaluate", *argv])
    try:
        methods = [m.strip() for m in args.methods.split(",") if m.strip()]
        unknown = [m for m in methods if m not in METHODS]
        if unknown or not methods:
            raise Refused(f"unknown methods {unknown} (choose from {list(METHODS)})")
        try:
            manifest = load_manifest(args.manifest, expected_sha256=args.expected_sha256)
        except (ManifestError, OSError) as exc:
            raise Refused(describe_error(exc)) from None
        val = EvalPairs.from_manifest(manifest, "val", limit_assignments=args.limit_assignments)
        test = EvalPairs.from_manifest(manifest, "test", limit_assignments=args.limit_assignments)
        files = load_files(Path(args.root), list(val.samples) + list(test.samples))
        device = resolve_device(args.device)
        embedders, statuses = load_embedders(
            [m for m in methods if m in EMBEDDING_METHODS], model_name=args.model,
            local_files_only=args.local_files_only, device=device, batch_size=args.batch_size,
        )
    except Refused as exc:
        return _refuse(str(exc))

    n_pairs = val.pairs.a.size + test.pairs.a.size
    _log(
        f"{len(files)} files, val {val.pairs.a.size} pairs, test {test.pairs.a.size} pairs, "
        f"methods {methods}, n_boot {args.n_boot}; bootstrap estimate ~{n_pairs / 1.9e6 * args.n_boot * 2 * len(methods) / 60:.0f} min "
        "(~1 s per resample per 1.9M pairs)"
    )
    cache_root = None if args.no_cache else Path(args.cache_dir or Path(args.runs_root) / CHANNEL / "_cache")
    revision = next(
        (e.key_fields().get("model_revision") for m, e in embedders.items() if m in ("v2", "v2_nodfg")), None
    )
    run_config = {
        "model_name": args.model,
        "model_revision": revision,
        "gcb_v2": GCBV2Config().to_dict(),
        "versions": package_versions(VERSION_PACKAGES),
        "device": str(device),
        "methods": methods,
        "method_status": statuses,
        "n_boot": args.n_boot,
        "batch_size": args.batch_size,
        "limit_assignments": args.limit_assignments,
        "cache_dir": None if cache_root is None else cache_root.as_posix(),
        "local_files_only": args.local_files_only,
        "curve_max_points": CURVE_MAX_POINTS,
        "targets": list(DEFAULT_TARGETS),
    }
    ctx = RunContext.create(
        CHANNEL, seed=args.seed, split="test", mode="zero_shot", manifest_path=args.manifest,
        manifest_sha256=manifest.sha256, config=_plain(run_config), argv=argv_list, root=args.runs_root,
    )
    config = set_run_status(ctx.path, STATUS_RUNNING)
    _log(f"run directory {ctx.path}")
    evaluation = Evaluation(
        ctx.path, val=val, test=test, files=files, embedders=embedders, statuses=statuses, methods=methods,
        cache_root=cache_root, n_boot=args.n_boot, seed=args.seed, manifest_sha256=manifest.sha256,
        manifest_path=Path(args.manifest), run_config=config,
    )
    stage = "val"
    try:
        evaluation.run_val()
        stage = "selection"
        evaluation.select()
        stage = "test"
        evaluation.evaluate_test()
        stage = "report"
        evaluation.finish()
    except Exception as exc:
        reason = describe_error(exc)
        set_run_status(ctx.path, STATUS_FAILED, stage=stage, reason=reason)
        print(f"ERROR: stage {stage} failed: {reason}", file=sys.stderr)
        return RUN_FAILED_EXIT
    set_run_status(ctx.path, STATUS_COMPLETE)
    _log(f"complete: {ctx.path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

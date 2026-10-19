"""Seeded CharCNN v2 trainer: `python -m models.char_cnn.v2.train`.

Order (design "Training"): (1) `seed_everything(seed, deterministic_torch=True)`, (2) load the
split manifest, (3) create the run directory `<runs-root>/char_cnn/<ts>/` (`RunContext`), (4) read,
normalize and encode train/val/test once, running the leak guard on the normalized human
representatives of every split and the shortcut audit in the same pass, (5) build the model
(seeded, no dummy forward pass), (6) train with the 1:1 epoch sampler and select the checkpoint by
val ROC-AUC (ties: val PR-AUC, then the earlier epoch), saving `best.pth` on every improvement,
(7) `evaluate_run`: val-only calibration, then the test split scored once (`v2/evaluate.py`).

The trainer writes only inside its run directory. It never writes `models/char_cnn/best_model.pth`
(or anything under `models/`) and never promotes a checkpoint; promotion is a separate CLI.

Exit codes (`v2/runs.py`): 0 complete; 2 on a leak-guard failure (`leak_guard.json` written, no
checkpoint, run marked failed in stage `leak_guard`); 3 when the run is marked failed in any other
stage after its directory exists (data, training or evaluation error, e.g. no epoch with a defined
val ROC-AUC). `config.json` records `status` (`running` -> `complete` | `failed`), when failed
`failure: {stage, reason}`, and `best_sha256` (the selected `best.pth`, which promote requires).
An interrupt (`KeyboardInterrupt`) also marks the run failed with its stage, then propagates.
Invalid options are rejected (argparse, exit 2) before anything is written.
"""

import argparse
import csv
import io
import json
import math
import sys
import time
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.optim.lr_scheduler import ReduceLROnPlateau

from models.char_cnn.v2.checkpoint import load_checkpoint, make_checkpoint
from models.char_cnn.v2.config import CharCNNV2Config
from models.char_cnn.v2.data import (
    VIEWS,
    EncodedSet,
    check_trainable,
    collate,
    data_summary,
    epoch_batches,
    label_of,
    limit_per_class,
    load_encoded,
    load_views,
    view_samples,
)
from models.char_cnn.v2 import lolo
from models.char_cnn.v2.subsample import subsample_ai_train
from models.evaluation.calibration import select_threshold
from models.char_cnn.v2.evaluate import SHORTCUT_VIEWS, evaluate_run, update_run_config
from models.char_cnn.v2.model import CharCNNV2
from models.char_cnn.v2.preprocess import LeakGuardError, leak_guard
from models.char_cnn.v2.runs import (
    CHECKPOINT_NAME,
    DEFAULT_EVAL_BATCH_SIZE,
    DEFAULT_N_BOOT,
    LEAK_GUARD_EXIT,
    RUN_FAILED_EXIT,
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_RUNNING,
    describe_error,
    resolve_device,
    set_run_status,
    write_json,
)
from models.char_cnn.v2.scoring import score_arrays
from models.char_cnn.v2.shortcuts import ShortcutAudit
from models.evaluation import metrics as M
from models.evaluation.manifest import DEFAULT_MANIFEST, ROOT, Sample, load_manifest
from models.evaluation.provenance import atomic_write_bytes, file_sha256
from models.evaluation.report import RunContext
from models.evaluation.seed import seed_everything

__all__ = [
    "CHANNEL",
    "LEAK_GUARD_EXIT",
    "RUN_FAILED_EXIT",
    "TrainOptions",
    "Selection",
    "FitResult",
    "build_model",
    "val_metrics",
    "fit",
    "run",
    "main",
]

CHANNEL = "char_cnn"
LEAK_GUARD_SCHEMA = "graphito.charcnn_leak_guard/v1"
LEAK_GUARD_THRESHOLD = 0.001
GUARD_VIEWS = ("train", "val", "test")  # representatives of every split
HISTORY_COLUMNS = ("epoch", "train_loss", "val_roc_auc", "val_pr_auc", "lr", "n_epoch_samples", "seconds")

OnText = Callable[[Sample, str, str], None]

# (field, CLI flag, minimum, minimum inclusive) for the numeric options; `limit_per_class` may be None.
_OPTION_BOUNDS = (
    ("epochs", "--epochs", 1, True),
    ("batch_size", "--batch-size", 1, True),
    ("eval_batch_size", "--eval-batch-size", 1, True),
    ("early_stop", "--early-stop", 1, True),
    ("lr_patience", "--lr-patience", 0, True),
    ("n_boot", "--n-boot", 1, True),
    ("limit_per_class", "--limit-per-class", 1, True),
    ("lr", "--lr", 0.0, False),
    ("weight_decay", "--weight-decay", 0.0, True),
)


@dataclass(frozen=True)
class TrainOptions:
    """Run inputs and hyperparameters (defaults: the legacy CLI and `CharCNNConfig` values).

    Construction validates every number (`ValueError` naming the field and its CLI flag), so an
    invalid run is refused before its directory is created.
    """

    manifest: Path = DEFAULT_MANIFEST
    expected_sha256: Optional[str] = None
    root: Path = ROOT
    runs_root: Path = ROOT / "runs"
    seed: int = 42
    device: Optional[str] = None
    epochs: int = 50
    batch_size: int = 128
    lr: float = 1e-3
    weight_decay: float = 1e-4
    early_stop: int = 7
    lr_patience: int = 3
    lr_factor: float = 0.5
    eval_batch_size: int = DEFAULT_EVAL_BATCH_SIZE
    n_boot: int = DEFAULT_N_BOOT
    limit_per_class: Optional[int] = None
    train_ai_fraction: float = 1.0
    subsample_seed: Optional[int] = None
    run_dir: Optional[Path] = None
    skip_test_eval: bool = False
    keep_checkpoints: bool = True
    train_ai_models: Tuple[str, ...] = ()  # leave-one-LLM-out: AI generators allowed in train/val (empty = all)
    match_ai_groups_to: Optional[str] = None  # subsample train AI to this generator's train dup_group count

    def __post_init__(self) -> None:
        if self.match_ai_groups_to is not None and not self.train_ai_models:
            raise ValueError("match_ai_groups_to (--match-ai-groups-to) requires --train-ai-models")
        for name, flag, minimum, inclusive in _OPTION_BOUNDS:
            value = getattr(self, name)
            if value is None and name == "limit_per_class":
                continue
            ok = math.isfinite(value) and (value >= minimum if inclusive else value > minimum)
            if not ok:
                bound = f">= {minimum}" if inclusive else f"> {minimum}"
                raise ValueError(f"{name} ({flag}) must be a finite number {bound} (got {value!r})")
        if not (math.isfinite(self.lr_factor) and 0.0 < self.lr_factor < 1.0):
            raise ValueError(f"lr_factor (--lr-factor) must be in (0, 1) (got {self.lr_factor!r})")
        if not (math.isfinite(self.train_ai_fraction) and 0.0 < self.train_ai_fraction <= 1.0):
            raise ValueError(
                f"train_ai_fraction (--train-ai-fraction) must be in (0, 1] (got {self.train_ai_fraction!r})"
            )

    def hyperparams(self) -> Dict[str, Any]:
        keys = (
            "seed", "epochs", "batch_size", "lr", "weight_decay", "early_stop", "lr_patience",
            "lr_factor", "eval_batch_size", "n_boot", "limit_per_class",
            "train_ai_fraction", "subsample_seed",
        )
        out = {key: getattr(self, key) for key in keys}
        if self.train_ai_models:  # recorded only when active, so default configs are unchanged
            out["train_ai_models"] = list(self.train_ai_models)
            out["match_ai_groups_to"] = self.match_ai_groups_to
        return out


# --- selection -----------------------------------------------------------------------------------


def _finite(value: Optional[float]) -> bool:
    return value is not None and math.isfinite(value)


@dataclass
class Selection:
    """Best epoch by the tuple (val ROC-AUC, val PR-AUC); exact ties keep the earlier epoch.

    Epochs with an undefined ROC-AUC (single-class val) are never selected. `stale` counts the
    epochs since the last improvement and drives early stopping.
    """

    best_epoch: Optional[int] = None
    best_roc_auc: Optional[float] = None
    best_pr_auc: Optional[float] = None
    stale: int = 0

    @staticmethod
    def _key(roc_auc: float, pr_auc: Optional[float]) -> Tuple[float, float]:
        return roc_auc, (pr_auc if _finite(pr_auc) else -math.inf)

    def update(self, epoch: int, roc_auc: Optional[float], pr_auc: Optional[float]) -> bool:
        """Record one epoch; True when it becomes the selected one."""
        improved = _finite(roc_auc) and (
            self.best_epoch is None
            or self._key(roc_auc, pr_auc) > self._key(self.best_roc_auc, self.best_pr_auc)
        )
        if improved:
            self.best_epoch, self.best_roc_auc, self.best_pr_auc, self.stale = epoch, roc_auc, pr_auc, 0
        else:
            self.stale += 1
        return improved


@dataclass(frozen=True)
class FitResult:
    best_epoch: int
    best_val_roc_auc: float
    best_val_pr_auc: Optional[float]
    epochs_run: int
    stopped_early: bool
    history: Tuple[Dict[str, Any], ...]
    sampling: Dict[str, Any]


# --- model, scoring, checkpoints -----------------------------------------------------------------


def build_model(config: CharCNNV2Config, device: torch.device, seed: int) -> CharCNNV2:
    """Seeded model construction; no forward pass of any kind happens here."""
    torch.manual_seed(seed)
    return CharCNNV2(config).to(device)


def val_metrics(
    model: nn.Module, val: EncodedSet, device: torch.device, batch_size: int
) -> Tuple[Optional[float], Optional[float]]:
    """(ROC-AUC, PR-AUC) of the raw windowed scores on the val representatives."""
    p_synth, _, _ = score_arrays(model, val.arrays, device, batch_size)
    return M.roc_auc(val.y, p_synth), M.average_precision(val.y, p_synth)


def _write_history(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=HISTORY_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows({k: ("" if row[k] is None else row[k]) for k in HISTORY_COLUMNS} for row in rows)
    atomic_write_bytes(path, out.getvalue().encode("utf-8"))


def save_checkpoint(model: CharCNNV2, path: Path, **metadata: Any) -> None:
    """Atomically write a v2 checkpoint (primitives only, `weights_only`-loadable)."""
    buffer = io.BytesIO()
    torch.save(make_checkpoint(model, **metadata), buffer)
    atomic_write_bytes(path, buffer.getvalue())


# --- training loop -------------------------------------------------------------------------------


def fit(
    model: CharCNNV2,
    train: EncodedSet,
    val: EncodedSet,
    options: TrainOptions,
    device: torch.device,
    run_dir: Path,
    checkpoint_metadata: Optional[Mapping[str, Any]] = None,
) -> FitResult:
    """Train on `train`, select on `val` only; writes `history.csv` and `best.pth` in `run_dir`.

    Raises `RuntimeError` when no epoch had a defined val ROC-AUC (nothing can be selected).
    """
    run_dir = Path(run_dir)
    optimizer = torch.optim.Adam(model.parameters(), lr=options.lr, weight_decay=options.weight_decay)
    scheduler = ReduceLROnPlateau(optimizer, mode="max", factor=options.lr_factor, patience=options.lr_patience)
    criterion = nn.CrossEntropyLoss()
    selection = Selection()
    history: List[Dict[str, Any]] = []
    sampling: Dict[str, Any] = {}
    stopped_early = False

    for epoch in range(options.epochs):
        started = time.perf_counter()
        plan = epoch_batches(train, epoch, options.seed, options.batch_size, window=model.config.window)
        sampling = plan.summary()
        lr = optimizer.param_groups[0]["lr"]
        model.train()
        loss_sum, n_seen = 0.0, 0
        for batch in plan.batches:
            x, y = collate(batch.arrays, batch.labels)
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            optimizer.step()
            loss_sum += loss.item() * len(batch.indices)
            n_seen += len(batch.indices)

        roc_auc, pr_auc = val_metrics(model, val, device, options.eval_batch_size)
        if _finite(roc_auc):
            scheduler.step(roc_auc)
        if selection.update(epoch, roc_auc, pr_auc):
            save_checkpoint(
                model,
                run_dir / CHECKPOINT_NAME,
                **dict(checkpoint_metadata or {}),
                epoch=epoch,
                val_roc_auc=roc_auc,
                val_pr_auc=pr_auc,
            )
        history.append(
            {
                "epoch": epoch,
                "train_loss": loss_sum / n_seen if n_seen else None,
                "val_roc_auc": roc_auc,
                "val_pr_auc": pr_auc,
                "lr": lr,
                "n_epoch_samples": n_seen,
                "seconds": round(time.perf_counter() - started, 3),
            }
        )
        _write_history(run_dir / "history.csv", history)
        if selection.stale >= options.early_stop:
            stopped_early = epoch + 1 < options.epochs
            break

    if selection.best_epoch is None:
        raise RuntimeError("no epoch had a defined val ROC-AUC (single-class val?); nothing was selected")
    return FitResult(
        best_epoch=selection.best_epoch,
        best_val_roc_auc=selection.best_roc_auc,
        best_val_pr_auc=selection.best_pr_auc,
        epochs_run=len(history),
        stopped_early=stopped_early,
        history=tuple(history),
        sampling=sampling,
    )


# --- data pass and leak guard --------------------------------------------------------------------


class GuardCollector:
    """`on_text` sink keeping the normalized text of the guarded representatives, per class."""

    def __init__(self, ids: Set[str]):
        self.ids = ids
        self.texts: Dict[str, List[str]] = {"human": [], "ai": []}
        self.text_ids: Dict[str, List[str]] = {"human": [], "ai": []}

    def __call__(self, sample: Sample, raw: str, normalized: str) -> None:
        if sample.id in self.ids:
            cls = "ai" if label_of(sample) else "human"
            self.texts[cls].append(normalized)
            self.text_ids[cls].append(sample.id)

    def check(self, threshold: float = LEAK_GUARD_THRESHOLD) -> Dict[str, Any]:
        """The `leak_guard.json` document; the guard gates on humans, AI shares are informational."""
        doc: Dict[str, Any] = {
            "schema": LEAK_GUARD_SCHEMA,
            "scope": "normalized representatives of " + "/".join(GUARD_VIEWS) + "; gated on humans",
            "threshold": threshold,
            "n_texts": {cls: len(texts) for cls, texts in self.texts.items()},
            "passed": True,
            "offending_ids": {},
        }
        try:
            doc["shares"] = leak_guard(self.texts["human"], threshold=threshold)
        except LeakGuardError as exc:
            ids = self.text_ids["human"]
            doc.update(
                passed=False,
                shares=exc.shares,
                offending_ids={name: [ids[i] for i in idx] for name, idx in exc.offending.items() if idx},
            )
        # threshold 1.0 never raises (strict `>`), so this only measures the AI side.
        doc["shares_by_class"] = {"human": doc["shares"], "ai": leak_guard(self.texts["ai"], threshold=1.0)}
        self.texts = {"human": [], "ai": []}  # free the normalized texts once checked
        return doc


def _fan_out(*callbacks: OnText) -> OnText:
    def on_text(sample: Sample, raw: str, normalized: str) -> None:
        for callback in callbacks:
            callback(sample, raw, normalized)

    return on_text


# --- run -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RunResult:
    exit_code: int
    run_dir: Path
    fit: Optional[FitResult] = None


class _Stage:
    """The step a run is in, recorded as `failure.stage` when the run fails."""

    def __init__(self) -> None:
        self.name = "load_data"


def run(
    options: TrainOptions,
    model_config: Optional[CharCNNV2Config] = None,
    argv: Optional[Sequence[str]] = None,
    preloaded_views: Optional[Dict[str, EncodedSet]] = None,
    preloaded_val_all: Optional[EncodedSet] = None,
) -> RunResult:
    """Execute one run (steps 1-7).

    Returns exit code 0, `LEAK_GUARD_EXIT` on a leak-guard failure or `RUN_FAILED_EXIT` when any
    step after the run directory exists raises; in both failure cases `config.json` is marked
    `failed` with the stage and reason, and an `ERROR:` line goes to stderr. A `BaseException`
    that is not an `Exception` (e.g. `KeyboardInterrupt`) is recorded the same way, then re-raised.
    """
    model_config = model_config or CharCNNV2Config()
    seed_everything(options.seed, deterministic_torch=True)
    device = resolve_device(options.device)
    manifest = load_manifest(options.manifest, options.expected_sha256)
    ctx = RunContext.create(
        CHANNEL,
        seed=options.seed,
        split="test",
        mode="representatives",
        manifest_path=manifest.path,
        manifest_sha256=manifest.sha256,
        config={
            **model_config.to_dict(),
            "hyperparams": options.hyperparams(),
            "device": str(device),
            "torch_version": str(torch.__version__),  # TorchVersion is not weights_only-safe
            "data_root": Path(options.root).as_posix(),
        },
        argv=argv,
        root=options.runs_root,
        run_dir=options.run_dir,
    )
    ctx = update_run_config(ctx, status=STATUS_RUNNING, failure=None)
    stage = _Stage()
    try:
        return _execute(
            ctx, manifest, options, model_config, device, stage,
            preloaded_views=preloaded_views, preloaded_val_all=preloaded_val_all,
        )
    except BaseException as exc:  # recorded in config.json instead of leaving a silent half-written run
        reason = describe_error(exc)
        set_run_status(ctx.path, STATUS_FAILED, stage=stage.name, reason=reason)
        print(f"ERROR: run failed during {stage.name}: {reason}; see {ctx.path / 'config.json'}", file=sys.stderr)
        if not isinstance(exc, Exception):  # KeyboardInterrupt / SystemExit: recorded, then propagated
            raise
        return RunResult(RUN_FAILED_EXIT, ctx.path)


def _restrict_view(view: EncodedSet, transform: Callable[[Sequence[Sample]], Sequence[Sample]]) -> EncodedSet:
    """Apply a pure sample-list filter to an encoded view, keeping arrays aligned."""
    kept = {s.id for s in transform(view.samples)}
    idx = [i for i, s in enumerate(view.samples) if s.id in kept]
    return EncodedSet.build([view.samples[i] for i in idx], [view.arrays[i] for i in idx])


def _ai_counts(view: EncodedSet) -> Dict[str, Any]:
    """Counts of AI files and unique dup_groups per generator in a view (for config.json)."""
    files: Dict[str, int] = {}
    groups: Dict[str, Set[str]] = {}
    for s in view.samples:
        if s.source == "ai":
            files[str(s.model)] = files.get(str(s.model), 0) + 1
            groups.setdefault(str(s.model), set()).add(str(s.dup_group or s.id))
    return {
        "n_human": int(len(view) - view.y.sum()),
        "files_by_model": files,
        "groups_by_model": {m: len(g) for m, g in groups.items()},
    }


def _execute(
    ctx: RunContext,
    manifest,
    options: TrainOptions,
    model_config: CharCNNV2Config,
    device: torch.device,
    stage: _Stage,
    preloaded_views: Optional[Dict[str, EncodedSet]] = None,
    preloaded_val_all: Optional[EncodedSet] = None,
) -> RunResult:
    """Steps 4-7 inside an existing run directory (`run` handles failures)."""
    if preloaded_views is not None:
        views = dict(preloaded_views)
    else:
        guard_ids = {s.id for view in GUARD_VIEWS for s in view_samples(manifest, view)}
        guard = GuardCollector(guard_ids)
        audit = ShortcutAudit({view: [s.id for s in view_samples(manifest, view)] for view in SHORTCUT_VIEWS})
        views_to_load = tuple(VIEWS) if not options.skip_test_eval else ("train", "val", "test")
        views = load_views(manifest, views=views_to_load, root=options.root, on_text=_fan_out(guard, audit))
        guard_doc = guard.check()
        write_json(ctx.path / "leak_guard.json", guard_doc)
        ctx = update_run_config(
            ctx,
            leak_guard={"path": "leak_guard.json", "passed": guard_doc["passed"], "shares": guard_doc["shares"]},
        )
        if not guard_doc["passed"]:
            over = {k: v for k, v in guard_doc["shares"].items() if v > guard_doc["threshold"]}
            reason = f"leak patterns above {guard_doc['threshold']} of human representatives: {over}"
            set_run_status(ctx.path, STATUS_FAILED, stage="leak_guard", reason=reason)
            print(f"ERROR: leak guard failed: {over}; see {ctx.path / 'leak_guard.json'}", file=sys.stderr)
            return RunResult(LEAK_GUARD_EXIT, ctx.path)

    lolo_info = None
    if options.train_ai_models:
        lolo_info = {"train_ai_models": list(options.train_ai_models), "match_ai_groups_to": options.match_ai_groups_to}
        lolo_info["before"] = {v: _ai_counts(views[v]) for v in ("train", "val")}
        views["train"] = _restrict_view(views["train"], lambda ss: lolo.restrict_ai_models(ss, options.train_ai_models))
        views["val"] = _restrict_view(views["val"], lambda ss: lolo.restrict_ai_models(ss, options.train_ai_models))
        if options.match_ai_groups_to:
            target = lolo_info["before"]["train"]["groups_by_model"].get(options.match_ai_groups_to, 0)
            lolo_info["match_target_groups"] = target
            sub_seed = options.subsample_seed if options.subsample_seed is not None else options.seed
            views["train"] = _restrict_view(
                views["train"], lambda ss: lolo.match_ai_groups(ss, target, sub_seed, split="train")
            )
        lolo_info["after"] = {v: _ai_counts(views[v]) for v in ("train", "val")}

    n_ai_orig = int(views["train"].y.sum())
    subsample_info = {
        "fraction": options.train_ai_fraction,
        "seed": options.subsample_seed,
        "n_ai_original": n_ai_orig,
        "n_ai_subsampled": n_ai_orig,
    }
    if options.train_ai_fraction < 1.0:
        sub_seed = options.subsample_seed if options.subsample_seed is not None else options.seed
        views["train"] = subsample_ai_train(views["train"], fraction=options.train_ai_fraction, seed=sub_seed)
        subsample_info["n_ai_subsampled"] = int(views["train"].y.sum())

    if options.limit_per_class is not None:
        views = {name: limit_per_class(view, options.limit_per_class) for name, view in views.items()}
    summary = data_summary(views)
    ctx = update_run_config(ctx, data_summary=summary, subsample=subsample_info)
    if lolo_info is not None:
        ctx = update_run_config(ctx, lolo=lolo_info)
    check_trainable(views)

    stage.name = "fit"
    model = build_model(model_config, device, options.seed)
    metadata = {
        "seed": options.seed,
        "manifest_path": Path(manifest.path).as_posix(),
        "manifest_sha256": manifest.sha256,
        "git_sha": ctx.config["git_sha"],
        "dirty": ctx.config["dirty"],
        "run_id": ctx.config["run_id"],
        "hyperparams": options.hyperparams(),
        "device": str(device),
        "torch_version": str(torch.__version__),  # TorchVersion is not weights_only-safe
    }
    result = fit(model, views["train"], views["val"], options, device, ctx.path, metadata)
    ctx = update_run_config(
        ctx,
        best_sha256=file_sha256(ctx.path / CHECKPOINT_NAME),  # binds the run to its checkpoint (promote)
        sampling={"ratio": "1:1", **{k: v for k, v in result.sampling.items() if k != "epoch"}},
        selection={
            "rule": "max (val_roc_auc, val_pr_auc); ties -> earlier epoch; null AUC never selected",
            "epoch": result.best_epoch,
            "val_roc_auc": result.best_val_roc_auc,
            "val_pr_auc": result.best_val_pr_auc,
            "epochs_run": result.epochs_run,
            "stopped_early": result.stopped_early,
            "checkpoint": CHECKPOINT_NAME,
        },
    )

    stage.name = "evaluate_val"
    best_ckpt = load_checkpoint(ctx.path / CHECKPOINT_NAME, map_location=device)
    model.load_state_dict(best_ckpt["model_state_dict"])
    model.eval()

    p_val_rep, _, _ = score_arrays(model, views["val"].arrays, device, options.eval_batch_size)
    y_val_rep = views["val"].y
    val_rep_roc = M.roc_auc(y_val_rep, p_val_rep)
    val_rep_pr = M.average_precision(y_val_rep, p_val_rep)
    th_rep = select_threshold(y_val_rep, p_val_rep, 0.01)
    t_rep = th_rep["threshold"]
    tm_rep = M.threshold_metrics(y_val_rep, p_val_rep, t_rep) if t_rep is not None else {}

    if preloaded_val_all is not None:
        p_val, _, _ = score_arrays(model, preloaded_val_all.arrays, device, options.eval_batch_size)
        y_val = preloaded_val_all.y
    else:
        val_all_samples = manifest.samples("val", representatives_only=False)
        if options.train_ai_models:  # the held-out generator never reaches val-side threshold selection
            val_all_samples = lolo.restrict_ai_models(val_all_samples, options.train_ai_models)
        if len(val_all_samples) != len(views["val"]):
            val_all_encoded = load_encoded(manifest, val_all_samples, root=options.root)
            p_val, _, _ = score_arrays(model, val_all_encoded.arrays, device, options.eval_batch_size)
            y_val = val_all_encoded.y
        else:
            p_val, y_val = p_val_rep, y_val_rep

    val_roc = M.roc_auc(y_val, p_val)
    val_pr = M.average_precision(y_val, p_val)
    th_info = select_threshold(y_val, p_val, 0.01)
    t_val = th_info["threshold"]
    tm = M.threshold_metrics(y_val, p_val, t_val) if t_val is not None else {}

    metrics_val = {
        "pr_auc": val_pr,
        "roc_auc": val_roc,
        "f1": tm.get("f1"),
        "precision": tm.get("precision"),
        "recall": tm.get("recall"),
        "threshold": t_val,
        "epoch": result.best_epoch,
        "n_ai": int(np.sum(y_val == 1)),
        "n_human": int(np.sum(y_val == 0)),
        "train_ai_fraction": options.train_ai_fraction,
        "subsample_seed": options.subsample_seed,
        "n_ai_train": int(views["train"].y.sum()),
        "val_representatives": {
            "pr_auc": val_rep_pr,
            "roc_auc": val_rep_roc,
            "f1": tm_rep.get("f1"),
            "precision": tm_rep.get("precision"),
            "recall": tm_rep.get("recall"),
            "threshold": t_rep,
        },
    }
    write_json(ctx.path / "metrics_val.json", metrics_val)

    if options.skip_test_eval:
        if not options.keep_checkpoints:
            best_pth = ctx.path / CHECKPOINT_NAME
            if best_pth.is_file():
                best_pth.unlink()
        set_run_status(ctx.path, STATUS_COMPLETE)
        return RunResult(0, ctx.path, result)

    stage.name = "evaluate"
    evaluate_run(
        ctx,
        manifest,
        views,
        device,
        seed=options.seed,
        n_boot=options.n_boot,
        batch_size=options.eval_batch_size,
        shortcuts=audit.to_dict(),
        data_summary=summary,
    )
    if not options.keep_checkpoints:
        best_pth = ctx.path / CHECKPOINT_NAME
        if best_pth.is_file():
            best_pth.unlink()
    set_run_status(ctx.path, STATUS_COMPLETE)
    return RunResult(0, ctx.path, result)


# --- CLI -----------------------------------------------------------------------------------------


def load_model_config(path: Optional[Path]) -> CharCNNV2Config:
    """`CharCNNV2Config` overrides from a JSON object of its fields (defaults when `path` is None)."""
    if path is None:
        return CharCNNV2Config()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    names = {f.name for f in fields(CharCNNV2Config)}
    unknown = sorted(set(data) - names)
    if unknown:
        raise ValueError(f"{path}: unknown CharCNNV2Config fields {unknown}")
    return CharCNNV2Config(**data)


def build_parser() -> argparse.ArgumentParser:
    d = TrainOptions()
    p = argparse.ArgumentParser(
        prog="python -m models.char_cnn.v2.train",
        description="Train CharCNN v2 on the split_v1 manifest (writes only under <runs-root>/char_cnn/<ts>/).",
    )
    p.add_argument("--manifest", type=Path, default=d.manifest, help="split manifest (.json or .json.gz)")
    p.add_argument("--expected-sha256", default=None, help="refuse the manifest unless its sha256 matches")
    p.add_argument("--root", type=Path, default=d.root, help="corpus root; files are read at <root>/<id>")
    p.add_argument("--runs-root", type=Path, default=d.runs_root, help="run directories go to <runs-root>/char_cnn/")
    p.add_argument("--seed", type=int, default=d.seed)
    p.add_argument("--device", default=None, help="torch device (default: cuda if available, else cpu)")
    p.add_argument("--epochs", type=int, default=d.epochs)
    p.add_argument("--batch-size", type=int, default=d.batch_size)
    p.add_argument("--lr", type=float, default=d.lr)
    p.add_argument("--weight-decay", type=float, default=d.weight_decay)
    p.add_argument("--early-stop", type=int, default=d.early_stop, help="epochs without improvement before stopping")
    p.add_argument("--lr-patience", type=int, default=d.lr_patience)
    p.add_argument("--lr-factor", type=float, default=d.lr_factor)
    p.add_argument("--eval-batch-size", type=int, default=d.eval_batch_size, help="windows per scoring batch")
    p.add_argument("--n-boot", type=int, default=d.n_boot, help="bootstrap resamples for the CI95")
    p.add_argument("--limit-per-class", type=int, default=None, help="debug only: first N per class per view")
    p.add_argument("--model-config", type=Path, default=None, help="JSON object of CharCNNV2Config overrides")
    p.add_argument("--train-ai-fraction", type=float, default=d.train_ai_fraction, help="fraction of train AI data (0.0, 1.0]")
    p.add_argument("--subsample-seed", type=int, default=d.subsample_seed, help="seed for AI train subsampling")
    p.add_argument("--train-ai-models", nargs="+", default=[], metavar="MODEL",
                   help="leave-one-LLM-out: keep only AI files of these generators in train and val")
    p.add_argument("--match-ai-groups-to", default=None, metavar="MODEL",
                   help="subsample train AI to the number of dup_groups MODEL has in train (needs --train-ai-models)")
    p.add_argument("--run-dir",type=Path, default=d.run_dir, help="exact run directory to write into")
    p.add_argument("--skip-test-eval", action="store_true", default=d.skip_test_eval, help="skip test evaluation (val only)")
    p.add_argument("--no-save-checkpoint", dest="keep_checkpoints", action="store_false", help="do not retain best.pth")
    p.set_defaults(keep_checkpoints=True)
    return p


def options_from_args(args: argparse.Namespace) -> TrainOptions:
    return TrainOptions(
        manifest=args.manifest,
        expected_sha256=args.expected_sha256,
        root=args.root,
        runs_root=args.runs_root,
        seed=args.seed,
        device=args.device,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        weight_decay=args.weight_decay,
        early_stop=args.early_stop,
        lr_patience=args.lr_patience,
        lr_factor=args.lr_factor,
        eval_batch_size=args.eval_batch_size,
        n_boot=args.n_boot,
        limit_per_class=args.limit_per_class,
        train_ai_fraction=args.train_ai_fraction,
        subsample_seed=args.subsample_seed,
        run_dir=args.run_dir,
        skip_test_eval=args.skip_test_eval,
        keep_checkpoints=args.keep_checkpoints,
        train_ai_models=tuple(args.train_ai_models),
        match_ai_groups_to=args.match_ai_groups_to,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:  # validated before anything is written (argparse error, exit 2)
        options = options_from_args(args)
        model_config = load_model_config(args.model_config)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    result = run(options, model_config, argv=["-m", "models.char_cnn.v2.train", *argv])
    if result.exit_code == 0:
        print(f"run directory: {result.run_dir}")
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())

"""Seeded CharCNN v2 trainer: `python -m models.char_cnn.v2.train`.

Order (design "Training"): (1) `seed_everything(seed, deterministic_torch=True)`, (2) load the
split manifest, (3) create the run directory `<runs-root>/char_cnn/<ts>/` (`RunContext`), (4) read,
normalize and encode train/val/test once, running the leak guard on the normalized human
representatives of every split, (5) build the model (seeded, no dummy forward pass), (6) train
with the 1:1 epoch sampler and select the checkpoint by val ROC-AUC (ties: val PR-AUC, then the
earlier epoch), saving `best.pth` on every improvement.

The trainer writes only inside its run directory. It never writes `models/char_cnn/best_model.pth`
(or anything under `models/`) and never promotes a checkpoint; promotion is a separate CLI.
A leak-guard failure writes `leak_guard.json` and exits with code 2 before any checkpoint exists.
"""

import argparse
import csv
import io
import json
import math
import sys
import time
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import torch
import torch.nn as nn
from torch.optim.lr_scheduler import ReduceLROnPlateau

from models.char_cnn.v2.checkpoint import make_checkpoint
from models.char_cnn.v2.config import CharCNNV2Config
from models.char_cnn.v2.data import EncodedSet, collate, epoch_batches, label_of, load_views, view_samples
from models.char_cnn.v2.model import CharCNNV2
from models.char_cnn.v2.preprocess import LeakGuardError, leak_guard
from models.char_cnn.v2.scoring import score_arrays
from models.evaluation import metrics as M
from models.evaluation.manifest import DEFAULT_MANIFEST, ROOT, Sample, load_manifest
from models.evaluation.provenance import atomic_write_bytes
from models.evaluation.report import RunContext
from models.evaluation.seed import seed_everything

__all__ = [
    "CHANNEL",
    "LEAK_GUARD_EXIT",
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
LEAK_GUARD_EXIT = 2
LEAK_GUARD_SCHEMA = "graphito.charcnn_leak_guard/v1"
LEAK_GUARD_THRESHOLD = 0.001
GUARD_VIEWS = ("train", "val", "test")  # representatives of every split
HISTORY_COLUMNS = ("epoch", "train_loss", "val_roc_auc", "val_pr_auc", "lr", "n_epoch_samples", "seconds")

OnText = Callable[[Sample, str, str], None]


@dataclass(frozen=True)
class TrainOptions:
    """Run inputs and hyperparameters (defaults: the legacy CLI and `CharCNNConfig` values)."""

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
    eval_batch_size: int = 32
    limit_per_class: Optional[int] = None

    def hyperparams(self) -> Dict[str, Any]:
        keys = (
            "seed", "epochs", "batch_size", "lr", "weight_decay", "early_stop", "lr_patience",
            "lr_factor", "eval_batch_size", "limit_per_class",
        )
        return {key: getattr(self, key) for key in keys}


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
        return roc_auc, pr_auc if _finite(pr_auc) else -math.inf

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


def resolve_device(name: Optional[str]) -> torch.device:
    """The requested device, else CUDA when available, else CPU."""
    return torch.device(name or ("cuda" if torch.cuda.is_available() else "cpu"))


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


def _write_json(path: Path, doc: Mapping[str, Any]) -> None:
    text = json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    atomic_write_bytes(path, (text + "\n").encode("utf-8"))


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


def update_run_config(ctx: RunContext, **fields_: Any) -> RunContext:
    """Rewrite the run's `config.json` with extra top-level fields (provenance completion, D12)."""
    doc = {**ctx.config, **fields_}
    _write_json(ctx.path / "config.json", doc)
    return replace(ctx, config=doc)


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
                run_dir / "best.pth",
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


def _limit(view: EncodedSet, per_class: int) -> EncodedSet:
    """Debug subset: the first `per_class` samples of each class, in view order."""
    seen = {0: 0, 1: 0}
    keep = []
    for i, label in enumerate(view.y.tolist()):
        if seen[label] < per_class:
            seen[label] += 1
            keep.append(i)
    return EncodedSet.build([view.samples[i] for i in keep], [view.arrays[i] for i in keep])


def data_summary(views: Mapping[str, EncodedSet]) -> Dict[str, Dict[str, int]]:
    return {
        name: {
            "n": len(view),
            "n_ai": int(view.y.sum()),
            "n_human": int(len(view) - view.y.sum()),
            "n_empty_after_normalize": sum(1 for a in view.arrays if len(a) == 1 and int(a[0]) == 1),
        }
        for name, view in views.items()
    }


# --- run -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RunResult:
    exit_code: int
    run_dir: Path
    fit: Optional[FitResult] = None


def run(
    options: TrainOptions,
    model_config: Optional[CharCNNV2Config] = None,
    argv: Optional[Sequence[str]] = None,
) -> RunResult:
    """Execute one training run (steps 1-6); returns exit code 0, or 2 on a leak-guard failure."""
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
    )

    guard_ids = {s.id for view in GUARD_VIEWS for s in view_samples(manifest, view)}
    guard = GuardCollector(guard_ids)
    views = load_views(manifest, root=options.root, on_text=_fan_out(guard))
    guard_doc = guard.check()
    _write_json(ctx.path / "leak_guard.json", guard_doc)
    ctx = update_run_config(
        ctx,
        leak_guard={"path": "leak_guard.json", "passed": guard_doc["passed"], "shares": guard_doc["shares"]},
    )
    if not guard_doc["passed"]:
        over = {k: v for k, v in guard_doc["shares"].items() if v > guard_doc["threshold"]}
        print(f"leak guard failed: {over}; see {ctx.path / 'leak_guard.json'}", file=sys.stderr)
        return RunResult(LEAK_GUARD_EXIT, ctx.path)

    if options.limit_per_class is not None:
        views = {name: _limit(view, options.limit_per_class) for name, view in views.items()}
    ctx = update_run_config(ctx, data_summary=data_summary(views))

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
        sampling={"ratio": "1:1", **{k: v for k, v in result.sampling.items() if k != "epoch"}},
        selection={
            "rule": "max (val_roc_auc, val_pr_auc); ties -> earlier epoch; null AUC never selected",
            "epoch": result.best_epoch,
            "val_roc_auc": result.best_val_roc_auc,
            "val_pr_auc": result.best_val_pr_auc,
            "epochs_run": result.epochs_run,
            "stopped_early": result.stopped_early,
            "checkpoint": "best.pth",
        },
    )
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
    p.add_argument("--limit-per-class", type=int, default=None, help="debug only: first N per class per view")
    p.add_argument("--model-config", type=Path, default=None, help="JSON object of CharCNNV2Config overrides")
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
        limit_per_class=args.limit_per_class,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    result = run(
        options_from_args(args),
        load_model_config(args.model_config),
        argv=["-m", "models.char_cnn.v2.train", *argv],
    )
    if result.exit_code == 0:
        print(f"run directory: {result.run_dir}")
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())

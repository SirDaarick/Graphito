"""Manifest-backed encoded data and the seeded 1:1 epoch sampler for CharCNN v2.

Samples come only from the `split_v1` manifest (`SplitManifest.samples(split,
representatives_only=True)`), labelled 1 iff `source == "ai"`; broken entries are excluded by the
loader default. Each file is read, normalized (`preprocess_v2`) and encoded to `uint8` once, and
`on_text(sample, raw, normalized)` lets the leak guard and shortcut audit run in the same pass.
Raw text is not kept.

Each epoch uses every AI train sample plus an equal number of humans drawn with
`stable_rng(seed, f"epoch{n}")`, a seeded crop of at most `window` chars per sample and sortish
length bucketing, so an epoch depends only on `(seed, epoch)` (no DataLoader workers or shuffle).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import torch

from models.char_cnn.v2.config import PAD_IDX, UNK_IDX
from models.char_cnn.v2.preprocess import encode, preprocess_v2
from models.char_cnn.v2.scoring import random_crop
from models.evaluation.manifest import ROOT, Sample, SplitManifest
from models.evaluation.seed import stable_rng

__all__ = [
    "VIEWS",
    "TRAINABLE_VIEWS",
    "EncodedSet",
    "Batch",
    "EpochPlan",
    "label_of",
    "read_source",
    "view_samples",
    "load_encoded",
    "load_views",
    "limit_per_class",
    "data_summary",
    "check_trainable",
    "epoch_batches",
    "collate",
]

# View name -> (manifest split, representatives only). Non-representative train files are never
# loaded; `test_all` is the secondary all-files test view.
VIEWS: Dict[str, Tuple[str, bool]] = {
    "train": ("train", True),
    "val": ("val", True),
    "test": ("test", True),
    "test_all": ("test", False),
}
# Views that must hold both classes: training needs AI and human files, and model selection plus
# calibration need a defined val ROC-AUC.
TRAINABLE_VIEWS = ("train", "val")

OnText = Callable[[Sample, str, str], None]


def label_of(sample: Sample) -> int:
    """1 for AI-generated files, 0 for human ones."""
    return int(sample.source == "ai")


@dataclass(frozen=True)
class EncodedSet:
    """Samples with their encoded (normalized) arrays and labels, index-aligned."""

    samples: Tuple[Sample, ...]
    arrays: Tuple[np.ndarray, ...]
    y: np.ndarray

    @classmethod
    def build(cls, samples: Sequence[Sample], arrays: Sequence[np.ndarray]) -> "EncodedSet":
        if len(samples) != len(arrays):
            raise ValueError("samples and arrays must have the same length")
        y = np.array([label_of(s) for s in samples], dtype=np.int64)
        return cls(tuple(samples), tuple(arrays), y)

    @property
    def ids(self) -> List[str]:
        return [s.id for s in self.samples]

    @property
    def lengths(self) -> np.ndarray:
        return np.array([len(a) for a in self.arrays], dtype=np.int64)

    def __len__(self) -> int:
        return len(self.samples)


def view_samples(manifest: SplitManifest, view: str) -> List[Sample]:
    """Samples of a named view (see `VIEWS`)."""
    if view not in VIEWS:
        raise ValueError(f"unknown view {view!r} (want one of {sorted(VIEWS)})")
    split, representatives = VIEWS[view]
    return manifest.samples(split, representatives_only=representatives)


def _manifest_split(manifest: SplitManifest, sample: Sample) -> Optional[str]:
    """The sample's split according to `manifest`, or None when the id is not in it."""
    try:
        return manifest.split_of(sample.id)
    except KeyError:
        return None


def _check_membership(manifest: SplitManifest, samples: Sequence[Sample]) -> None:
    """Raise `ValueError` for ids absent from `manifest` or tagged with another split."""
    foreign, moved = [], []
    for s in samples:
        split = _manifest_split(manifest, s)
        if split is None:
            foreign.append(s.id)
        elif split != s.split:
            moved.append(f"{s.id} (split {s.split!r} but the manifest has {split!r})")
    if foreign:
        raise ValueError(f"{len(foreign)} samples are not in the manifest {manifest.path} (first: {foreign[:3]})")
    if moved:
        raise ValueError(f"{len(moved)} samples disagree with the manifest split (first: {moved[:3]})")


def read_source(path: Path) -> str:
    """Raw file text: UTF-8 with `errors="replace"`, line endings untouched (U+FFFD is dropped by
    `preprocess_v2`)."""
    return Path(path).read_bytes().decode("utf-8", errors="replace")


def load_encoded(
    manifest: SplitManifest,
    samples: Iterable[Sample],
    root: "str | Path" = ROOT,
    on_text: Optional[OnText] = None,
) -> EncodedSet:
    """Read, normalize and encode `samples` (files at `root / sample.id`).

    Every sample must belong to `manifest` with the same split (`ValueError` otherwise). All
    missing files are counted before raising a single `FileNotFoundError`, so a wrong `root` is
    reported at once.
    """
    root = Path(root)
    samples = list(samples)
    _check_membership(manifest, samples)
    missing = [s.id for s in samples if not (root / s.id).is_file()]
    if missing:
        raise FileNotFoundError(
            f"{len(missing)} of {len(samples)} manifest files are missing under {root} (first: {missing[:3]})"
        )
    arrays = []
    for sample in samples:
        raw = read_source(root / sample.id)
        normalized = preprocess_v2(raw)
        if on_text is not None:
            on_text(sample, raw, normalized)
        arrays.append(encode(normalized))
    return EncodedSet.build(samples, arrays)


def load_views(
    manifest: SplitManifest,
    views: Sequence[str] = tuple(VIEWS),
    root: "str | Path" = ROOT,
    on_text: Optional[OnText] = None,
) -> Dict[str, EncodedSet]:
    """Load several views in one pass: each file is read once and views share its array.

    Raises `ValueError` if a sample id appears in more than one split.
    """
    selected = {view: view_samples(manifest, view) for view in views}
    owner: Dict[str, str] = {}
    unique: Dict[str, Sample] = {}
    for samples in selected.values():
        for s in samples:
            if owner.setdefault(s.id, s.split) != s.split:
                raise ValueError(f"sample {s.id} appears in splits {owner[s.id]} and {s.split}")
            unique.setdefault(s.id, s)
    encoded = load_encoded(manifest, unique.values(), root=root, on_text=on_text)
    by_id = dict(zip(encoded.ids, encoded.arrays))
    return {
        view: EncodedSet.build(samples, [by_id[s.id] for s in samples]) for view, samples in selected.items()
    }


def limit_per_class(view: EncodedSet, per_class: int) -> EncodedSet:
    """Debug subset: the first `per_class` samples of each class, in view order."""
    if per_class < 1:
        raise ValueError(f"per_class must be >= 1 (got {per_class})")
    seen = {0: 0, 1: 0}
    keep = []
    for i, label in enumerate(view.y.tolist()):
        if seen[label] < per_class:
            seen[label] += 1
            keep.append(i)
    return EncodedSet.build([view.samples[i] for i in keep], [view.arrays[i] for i in keep])


def data_summary(views: Mapping[str, EncodedSet]) -> Dict[str, Dict[str, int]]:
    """Per-view counts; an empty normalized text is encoded as `[UNK]` (see `encode`)."""
    return {
        name: {
            "n": len(view),
            "n_ai": int(view.y.sum()),
            "n_human": int(len(view) - view.y.sum()),
            "n_empty_after_normalize": sum(1 for a in view.arrays if len(a) == 1 and int(a[0]) == UNK_IDX),
        }
        for name, view in views.items()
    }


def check_trainable(views: Mapping[str, EncodedSet]) -> None:
    """Raise `ValueError` unless every `TRAINABLE_VIEWS` view holds both classes."""
    for name in TRAINABLE_VIEWS:
        view = views[name]
        n_ai = int(view.y.sum())
        n_human = len(view) - n_ai
        if n_ai == 0 or n_human == 0:
            raise ValueError(
                f"the {name} view needs both classes (n_ai={n_ai}, n_human={n_human}); "
                "check the manifest or --limit-per-class"
            )


@dataclass(frozen=True)
class Batch:
    """One training batch: set indices, their (cropped) arrays and labels."""

    indices: Tuple[int, ...]
    arrays: Tuple[np.ndarray, ...]
    labels: Tuple[int, ...]


@dataclass(frozen=True)
class EpochPlan:
    """The batches of one epoch plus the class counts that went into it."""

    epoch: int
    batches: Tuple[Batch, ...]
    n_ai: int
    n_human: int
    n_human_available: int

    @property
    def human_shortfall(self) -> int:
        """Humans missing for a 1:1 epoch (non-zero only when humans < AI)."""
        return self.n_ai - self.n_human

    def summary(self) -> Dict[str, int]:
        return {
            "epoch": self.epoch,
            "n_ai": self.n_ai,
            "n_human": self.n_human,
            "n_human_available": self.n_human_available,
            "human_shortfall": self.human_shortfall,
            "n_batches": len(self.batches),
        }


def epoch_batches(
    train: EncodedSet,
    epoch: int,
    seed: int,
    batch_size: int,
    *,
    window: int,
    bucket_batches: int = 50,
) -> EpochPlan:
    """Plan epoch `epoch`: all AI samples + an equal human draw, seeded crops, sortish batches.

    `window` is required (the run's `CharCNNV2Config.window`), so training crops can never
    silently disagree with the windows the model is scored on. The human draw is `stable_rng(seed, f"epoch{epoch}").sample(sorted human ids, n_ai)` (all
    humans when there are fewer). The same rng shuffles the pool, which is cut into chunks of
    `bucket_batches * batch_size`; each chunk is sorted by crop length and split into batches,
    and the batch order is shuffled. Crop offsets use `stable_rng(seed, f"epoch{epoch}:crop:{id}")`.
    """
    if batch_size < 1 or bucket_batches < 1 or window < 1:
        raise ValueError("batch_size, bucket_batches and window must be >= 1")
    ids = train.ids
    ai = sorted((i for i in range(len(train)) if train.y[i] == 1), key=lambda i: ids[i])
    humans = sorted((i for i in range(len(train)) if train.y[i] == 0), key=lambda i: ids[i])
    if not ai:
        raise ValueError("the train set has no AI samples")

    rng = stable_rng(seed, f"epoch{epoch}")
    chosen = rng.sample(humans, len(ai)) if len(humans) > len(ai) else list(humans)
    pool = ai + chosen
    rng.shuffle(pool)

    crops = {i: random_crop(train.arrays[i], window, seed, f"epoch{epoch}:crop:{ids[i]}") for i in pool}
    chunk = bucket_batches * batch_size
    batches: List[Batch] = []
    for start in range(0, len(pool), chunk):
        part = sorted(pool[start : start + chunk], key=lambda i: len(crops[i]))
        for b in range(0, len(part), batch_size):
            members = part[b : b + batch_size]
            batches.append(
                Batch(
                    indices=tuple(members),
                    arrays=tuple(crops[i] for i in members),
                    labels=tuple(int(train.y[i]) for i in members),
                )
            )
    rng.shuffle(batches)
    return EpochPlan(
        epoch=epoch,
        batches=tuple(batches),
        n_ai=len(ai),
        n_human=len(chosen),
        n_human_available=len(humans),
    )


def collate(arrays: Sequence[np.ndarray], labels: Sequence[int]) -> Tuple[torch.Tensor, torch.Tensor]:
    """Right-pad `arrays` with PAD (0) to the batch maximum: `(LongTensor (B, Lmax), LongTensor (B,))`."""
    width = max(1, max((len(a) for a in arrays), default=0))
    x = np.full((len(arrays), width), PAD_IDX, dtype=np.int64)
    for row, arr in enumerate(arrays):
        x[row, : len(arr)] = arr
    return torch.from_numpy(x), torch.as_tensor(list(labels), dtype=torch.long)

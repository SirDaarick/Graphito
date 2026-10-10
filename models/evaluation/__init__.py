"""Evaluation foundation: seeding, normalization, dedup, ground truth and reproducible splits.

The package is import-only and must import without torch. Consumers load splits through
`load_split` / `load_manifest`; the builder (`splits`) is never imported here.
"""

from .manifest import (
    ManifestError,
    ManifestHashError,
    PairSet,
    Sample,
    SplitManifest,
    load_manifest,
    load_split,
)
from .seed import seed_everything, stable_rng

__all__ = [
    "ManifestError",
    "ManifestHashError",
    "PairSet",
    "Sample",
    "SplitManifest",
    "load_manifest",
    "load_split",
    "seed_everything",
    "stable_rng",
]

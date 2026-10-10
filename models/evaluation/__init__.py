"""Evaluation foundation: seeding, normalization, dedup, ground truth and reproducible splits,
plus metrics, val-only calibration and run reporting.

The package is import-only and must import without torch or matplotlib. Consumers load splits
through `load_split` / `load_manifest`; the builder (`splits`) is never imported here.
scikit-learn/scipy (calibration) and matplotlib (plots) are imported lazily where used.
"""

from .calibration import (
    CalibrationError,
    LoadedCalibration,
    ScoredSet,
    build_calibration,
    load_calibration,
    save_calibration,
    select_threshold,
)
from .manifest import (
    ManifestError,
    ManifestHashError,
    PairSet,
    Sample,
    SplitManifest,
    load_manifest,
    load_split,
)
from .report import RunContext, compute_metrics, operating_points_from_calibration
from .seed import seed_everything, stable_rng

__all__ = [
    "CalibrationError",
    "LoadedCalibration",
    "ManifestError",
    "ManifestHashError",
    "PairSet",
    "RunContext",
    "Sample",
    "ScoredSet",
    "SplitManifest",
    "build_calibration",
    "compute_metrics",
    "load_calibration",
    "load_manifest",
    "load_split",
    "operating_points_from_calibration",
    "save_calibration",
    "seed_everything",
    "select_threshold",
    "stable_rng",
]

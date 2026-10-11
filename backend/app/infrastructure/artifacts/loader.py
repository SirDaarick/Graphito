"""Fail-closed loading of the deploy bundle (spec DA3.2-DA3.4; design D6).

`load_bundle` returns a complete `ArtifactBundle` or raises `ArtifactError`; it never returns a
partially verified bundle. Checks, in order: manifest schema and paths, sha256 of every listed
file, configured paths equal to the manifest entries, configured threshold keys equal to the
manifest keys, calibration schema (`graphito.calibration/v1`, fitted on val), calibration bytes
equal to the verified ones, non-null threshold for the configured key, threshold value equal to
the manifest's, and one split manifest across both calibrations and the deploy manifest.

Calibrations are applied with `models.evaluation.calibration` (numpy only; scikit-learn and scipy
are imported there only when fitting, never when loading or applying).
"""

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

import numpy as np

from app.infrastructure.artifacts.manifest import (
    ArtifactError,
    DeployManifest,
    manifest_number,
    read_manifest,
    verify_files,
)
from app.infrastructure.artifacts.models_path import PROJECT_ROOT, ensure_on_path

PathLike = Union[str, Path]


def resolve_setting_path(value: PathLike) -> Path:
    """Settings paths: absolute as given, relative to the project root otherwise."""
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _calibration_module():
    ensure_on_path()
    return importlib.import_module("models.evaluation.calibration")


@dataclass(frozen=True)
class ChannelCalibration:
    """One channel's frozen calibration and decision threshold (calibrated space)."""

    name: str
    threshold_key: str
    threshold: float
    calibration_sha256: str
    method: str
    fit_split: str
    split_manifest_sha256: str
    _loaded: Any = field(repr=False, compare=False)

    def apply(self, scores) -> np.ndarray:
        return np.asarray(self._loaded.apply(scores), dtype=np.float64)

    def calibrate(self, score: float) -> float:
        """One raw score in the calibrated space (`CalibratedChannel`)."""
        return float(self.apply([score])[0])

    def flag(self, score: float) -> bool:
        return bool(self.apply([score])[0] >= self.threshold)


@dataclass(frozen=True)
class ArtifactBundle:
    manifest_path: Path
    manifest_sha256: str
    split_manifest_sha256: str
    label: Optional[str]
    channel_a: ChannelCalibration
    channel_b: ChannelCalibration
    checkpoint_path: Path
    checkpoint_sha256: str
    gcb: Dict[str, Any]

    def summary(self) -> Dict[str, Any]:
        """Path-free description for `/health` and reports."""
        return {
            "manifest_sha256": self.manifest_sha256,
            "channel_a": {"threshold_key": self.channel_a.threshold_key, "threshold": self.channel_a.threshold,
                          "calibration_sha256": self.channel_a.calibration_sha256},
            "channel_b": {"threshold_key": self.channel_b.threshold_key, "threshold": self.channel_b.threshold,
                          "calibration_sha256": self.channel_b.calibration_sha256,
                          "checkpoint_sha256": self.checkpoint_sha256},
        }


def _entry(manifest: DeployManifest, section: Dict[str, Any], key: str, channel: str) -> str:
    rel = section.get(key)
    if rel is not None and not isinstance(rel, str):
        raise ArtifactError("manifest_invalid", f"{channel}.{key} must be a path string")
    if rel not in manifest.files:
        raise ArtifactError("not_in_manifest", f"{channel}.{key} is not listed in the manifest files")
    return rel


def _check_configured(manifest: DeployManifest, rel: str, configured: Optional[PathLike], what: str) -> None:
    if configured is None:
        return
    if resolve_setting_path(configured).resolve() != manifest.resolve(rel):
        raise ArtifactError("not_in_manifest", f"configured {what} is not the manifest entry {rel}")


def _load_channel(manifest: DeployManifest, name: str, key: str, configured: Optional[PathLike]) -> ChannelCalibration:
    section = manifest.channel(name)
    rel = _entry(manifest, section, "calibration", name)
    _check_configured(manifest, rel, configured, f"{name} calibration")
    if section.get("threshold_key") != key:
        raise ArtifactError(
            "threshold_key_mismatch", f"{name}: configured key {key!r} != manifest key {section.get('threshold_key')!r}"
        )
    cal = _calibration_module()
    try:
        loaded = cal.load_calibration(manifest.resolve(rel))
    except (cal.CalibrationError, OSError, KeyError, TypeError, ValueError) as exc:
        raise ArtifactError("calibration_invalid", f"{name} calibration: {exc}") from None
    if loaded.sha256 != manifest.files[rel]:
        raise ArtifactError("sha_mismatch", f"{name} calibration changed after verification")
    entry = loaded.artifact["thresholds"].get(key)
    if entry is None:
        raise ArtifactError("threshold_key_missing", f"{name} calibration has no threshold {key!r}")
    if entry.get("unachievable") or entry.get("threshold") is None:
        raise ArtifactError("threshold_unachievable", f"{name} threshold {key!r} is unachievable")
    threshold = float(entry["threshold"])
    manifest_threshold = section.get("threshold")
    if manifest_threshold is not None and manifest_number(manifest_threshold, f"{name}.threshold") != threshold:
        raise ArtifactError("manifest_inconsistent", f"{name} manifest threshold differs from its calibration")
    return ChannelCalibration(
        name=name,
        threshold_key=key,
        threshold=threshold,
        calibration_sha256=loaded.sha256,
        method=loaded.artifact["method"],
        fit_split=loaded.artifact["fit_set"]["split"],
        split_manifest_sha256=loaded.artifact["manifest"]["sha256"],
        _loaded=loaded,
    )


def load_bundle(
    manifest_path: PathLike,
    *,
    channel_a_key: str = "fpr_0.05",
    channel_b_key: str = "fpr_0.01",
    channel_a_method: Optional[str] = None,
    channel_a_calibration: Optional[PathLike] = None,
    charcnn_calibration: Optional[PathLike] = None,
    charcnn_checkpoint: Optional[PathLike] = None,
) -> ArtifactBundle:
    """Verify the deploy manifest and load both calibrations, or raise `ArtifactError`."""
    manifest = read_manifest(resolve_setting_path(manifest_path))
    verify_files(manifest)
    section_a, section_b = manifest.channel("channel_a"), manifest.channel("channel_b")
    if channel_a_method is not None and section_a.get("method") != channel_a_method:
        raise ArtifactError(
            "method_mismatch", f"configured Channel A method {channel_a_method!r} != manifest {section_a.get('method')!r}"
        )
    checkpoint_rel = _entry(manifest, section_b, "checkpoint", "channel_b")
    _check_configured(manifest, checkpoint_rel, charcnn_checkpoint, "CharCNN checkpoint")
    channel_a = _load_channel(manifest, "channel_a", channel_a_key, channel_a_calibration)
    channel_b = _load_channel(manifest, "channel_b", channel_b_key, charcnn_calibration)
    split = manifest.doc["split_manifest_sha256"]
    for channel in (channel_a, channel_b):
        if channel.split_manifest_sha256 != split:
            raise ArtifactError("split_mismatch", f"{channel.name} calibration was fitted on another split manifest")
    return ArtifactBundle(
        manifest_path=manifest.path,
        manifest_sha256=manifest.sha256,
        split_manifest_sha256=split,
        label=manifest.doc.get("label"),
        channel_a=channel_a,
        channel_b=channel_b,
        checkpoint_path=manifest.resolve(checkpoint_rel),
        checkpoint_sha256=manifest.files[checkpoint_rel],
        gcb=dict(manifest.doc.get("gcb") or {}),
    )


def load_bundle_from_settings(settings) -> ArtifactBundle:
    """`load_bundle` with the paths, keys and Channel A method from `app.config.Settings`."""
    return load_bundle(
        settings.DEPLOY_MANIFEST,
        channel_a_key=settings.CHANNEL_A_THRESHOLD_KEY,
        channel_b_key=settings.CHARCNN_THRESHOLD_KEY,
        channel_a_method=settings.CHANNEL_A_METHOD,
        channel_a_calibration=settings.CHANNEL_A_CALIBRATION,
        charcnn_calibration=settings.CHARCNN_CALIBRATION,
        charcnn_checkpoint=settings.CHARCNN_CHECKPOINT,
    )

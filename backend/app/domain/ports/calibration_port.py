"""Calibration port (design D4, D6): frozen per-channel calibrations and thresholds.

Thresholds live in the calibrated space and come only from the deploy artifacts (REAL) or from
fixed development defaults (STUB). Client-supplied thresholds never reach this port (D9).
"""

from abc import ABC, abstractmethod
from typing import Literal, Optional, Protocol, runtime_checkable

ChannelName = Literal["a", "b"]


@runtime_checkable
class CalibratedChannel(Protocol):
    threshold: float
    threshold_key: str
    calibration_sha256: Optional[str]

    def calibrate(self, score: float) -> float:
        """Map one raw score to the calibrated space."""
        ...


class CalibrationPort(ABC):
    """Per-channel calibrations plus the provenance shown in reports (AR1.1)."""

    #: "real" | "stub"
    engine: str = ""

    @abstractmethod
    def channel(self, name: ChannelName) -> Optional[CalibratedChannel]:
        """The channel's calibration, or None when it is uncalibrated (`ALLOW_UNCALIBRATED` only)."""

    @property
    def manifest_sha256(self) -> Optional[str]:
        return None

    @property
    def checkpoint_sha256(self) -> Optional[str]:
        return None

    @property
    def label(self) -> Optional[str]:
        return None

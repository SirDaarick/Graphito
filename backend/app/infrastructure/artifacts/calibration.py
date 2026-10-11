"""`CalibrationPort` over a verified deploy bundle (REAL mode; spec DA3.4)."""

from typing import Optional

from app.domain.ports.calibration_port import CalibratedChannel, CalibrationPort, ChannelName
from app.infrastructure.artifacts.loader import ArtifactBundle


class BundleCalibration(CalibrationPort):
    engine = "real"

    def __init__(self, bundle: ArtifactBundle):
        self.bundle = bundle
        self._channels = {"a": bundle.channel_a, "b": bundle.channel_b}

    def channel(self, name: ChannelName) -> Optional[CalibratedChannel]:
        return self._channels[name]

    @property
    def manifest_sha256(self) -> Optional[str]:
        return self.bundle.manifest_sha256

    @property
    def checkpoint_sha256(self) -> Optional[str]:
        return self.bundle.checkpoint_sha256

    @property
    def label(self) -> Optional[str]:
        return self.bundle.label

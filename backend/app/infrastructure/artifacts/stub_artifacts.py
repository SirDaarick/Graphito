"""Fixed development calibrations for `INFERENCE_MODE=STUB` (spec AS5.2, NF5).

Identity calibrations with fixed thresholds and no hashes: STUB results carry `engine == "stub"`
and never a `calibracion_sha_*` or `checkpoint_sha_b`. They need no artifact on disk.
"""

from dataclasses import dataclass
from typing import Optional

from app.domain.ports.calibration_port import CalibratedChannel, CalibrationPort, ChannelName

STUB_THRESHOLD_KEY = "stub_default"
STUB_THRESHOLD_A = 0.5
STUB_THRESHOLD_B = 0.5


@dataclass(frozen=True)
class StubChannel:
    threshold: float
    threshold_key: str = STUB_THRESHOLD_KEY
    calibration_sha256: Optional[str] = None

    def calibrate(self, score: float) -> float:
        return float(score)


class StubCalibration(CalibrationPort):
    engine = "stub"

    def __init__(self) -> None:
        self._channels = {"a": StubChannel(STUB_THRESHOLD_A), "b": StubChannel(STUB_THRESHOLD_B)}

    def channel(self, name: ChannelName) -> Optional[CalibratedChannel]:
        return self._channels[name]

    @property
    def label(self) -> Optional[str]:
        return "stub engine (development only): not a model result"

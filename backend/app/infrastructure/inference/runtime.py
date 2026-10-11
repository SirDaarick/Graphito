"""Inference runtime: engine + calibrations built once at startup, fail closed (design D5, D6, D10).

`build_runtime` never raises. In REAL mode it verifies the deploy bundle first and only then
constructs the engine; any failure yields a not-ready runtime with a stable, path-free reason
code. There is no stub fallback: the stub engine is selected only by `INFERENCE_MODE=STUB`
(spec AS6.1, AS7.1). `/health` reads `InferenceRuntime.health()`; the readiness gate returns 503
for scoring and indexing while the runtime is not ready.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from app.domain.errors import GraphitoError, NotReadyError
from app.domain.ports.calibration_port import CalibrationPort
from app.domain.ports.inference_port import InferencePort

logger = logging.getLogger(__name__)

EngineFactory = Callable[[Any, Any], InferencePort]


@dataclass(frozen=True)
class InferenceRuntime:
    mode: str
    engine_label: str
    ready: bool
    reason: Optional[str] = None
    engine: Optional[InferencePort] = None
    calibration: Optional[CalibrationPort] = None
    artifacts: Optional[Dict[str, Any]] = field(default=None)

    @property
    def calibration_state(self) -> str:
        if self.calibration is None:
            return "unavailable"
        if self.calibration.engine == "stub":
            return "stub"
        missing = [n for n in ("a", "b") if self.calibration.channel(n) is None]
        return "uncalibrated" if missing else "calibrated"

    def health(self) -> Dict[str, Any]:
        """Path-free readiness fields for `/health` (spec AS6.2, AS6.4)."""
        return {
            "engine": self.engine_label,
            "inference_ready": self.ready,
            "inference_error": self.reason,
            "calibration_state": self.calibration_state,
            "artifacts": self.artifacts,
        }

    def require_engine(self) -> InferencePort:
        if not self.ready or self.engine is None:
            raise NotReadyError(self.reason or "not_ready", "inference engine is not ready")
        return self.engine


def _default_engine_factory(settings, bundle) -> InferencePort:
    from app.infrastructure.inference.real_engine import create_real_engine

    return create_real_engine(settings, bundle)


def _not_ready(mode: str, label: str, reason: str) -> InferenceRuntime:
    return InferenceRuntime(mode=mode, engine_label=label, ready=False, reason=reason)


def build_runtime(settings=None, *, engine_factory: Optional[EngineFactory] = None) -> InferenceRuntime:
    """Build the runtime for `settings.INFERENCE_MODE`; never raises (blocking: call off the loop)."""
    if settings is None:
        from app.config import settings as default_settings

        settings = default_settings
    mode = str(settings.INFERENCE_MODE).strip().upper()
    if mode == "STUB":
        from app.infrastructure.artifacts.stub_artifacts import StubCalibration
        from app.infrastructure.inference.stub_engine import StubInferenceEngine

        return InferenceRuntime(
            mode=mode, engine_label="stub", ready=True, engine=StubInferenceEngine(), calibration=StubCalibration()
        )
    if mode != "REAL":
        logger.error("Inference not ready: unknown INFERENCE_MODE %r (expected STUB or REAL)", settings.INFERENCE_MODE)
        return _not_ready(mode, "unknown", "unknown_inference_mode")

    from app.infrastructure.artifacts import load_bundle_from_settings
    from app.infrastructure.artifacts.calibration import BundleCalibration

    try:
        bundle = load_bundle_from_settings(settings)
    except GraphitoError as exc:
        logger.error("Inference not ready (deploy artifacts): %s", exc)
        return _not_ready(mode, "real", exc.reason)
    except Exception as exc:  # defensive: any unexpected loader failure is still fail-closed
        logger.exception("Inference not ready (deploy artifacts): %s", type(exc).__name__)
        return _not_ready(mode, "real", "artifact_load_failed")
    try:
        engine = (engine_factory or _default_engine_factory)(settings, bundle)
    except GraphitoError as exc:
        logger.error("Inference not ready (engine): %s", exc)
        return _not_ready(mode, "real", exc.reason)
    except Exception as exc:
        logger.exception("Inference not ready (engine construction failed): %s", type(exc).__name__)
        return _not_ready(mode, "real", "engine_init_failed")
    readiness = engine.readiness()
    if not readiness.ready:
        logger.error("Inference not ready (engine readiness): %s", readiness.reason)
        return _not_ready(mode, "real", readiness.reason or "engine_not_ready")
    logger.info("Inference ready: engine=real manifest=%s", bundle.manifest_sha256[:12])
    return InferenceRuntime(
        mode=mode,
        engine_label="real",
        ready=True,
        engine=engine,
        calibration=BundleCalibration(bundle),
        artifacts=bundle.summary(),
    )


_runtime: Optional[InferenceRuntime] = None


def get_runtime() -> Optional[InferenceRuntime]:
    return _runtime


def set_runtime(runtime: Optional[InferenceRuntime]) -> None:
    global _runtime
    _runtime = runtime


def current_runtime() -> InferenceRuntime:
    """The started runtime, building it on first use (scripts without the app lifespan)."""
    global _runtime
    if _runtime is None:
        _runtime = build_runtime()
    return _runtime

from app.domain.ports.inference_port import InferencePort
from app.infrastructure.inference import runtime


def get_inference_engine() -> InferencePort:
    """The started engine. Raises `NotReadyError` (503) when it is not ready; never a stub fallback."""
    return runtime.current_runtime().require_engine()

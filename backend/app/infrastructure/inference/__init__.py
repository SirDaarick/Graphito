from app.config import settings
from app.domain.ports.inference_port import InferencePort
from app.infrastructure.inference.stub_engine import StubInferenceEngine

_engine_instance = None


def get_inference_engine() -> InferencePort:
    global _engine_instance
    if _engine_instance is None:
        if settings.INFERENCE_MODE.upper() == "REAL":
            from app.infrastructure.inference.real_engine import RealBimodalInferenceEngine
            _engine_instance = RealBimodalInferenceEngine()
        else:
            _engine_instance = StubInferenceEngine()
    return _engine_instance

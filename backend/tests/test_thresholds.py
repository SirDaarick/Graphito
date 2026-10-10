"""R3: one canonical source for the decision thresholds."""

import inspect
import uuid

from app.config import settings
from app.infrastructure.inference.stub_engine import StubInferenceEngine
from app.presentation.schemas.analysis import AnalysisRunRequest


def test_defaults_are_0_85_and_0_20():
    # Assumes no THRESHOLD_* override in the environment/.env used for the test run.
    req = AnalysisRunRequest(entrega_id=uuid.uuid4())
    assert req.threshold_sem == settings.THRESHOLD_SEM == 0.85
    assert req.threshold_ai == settings.THRESHOLD_AI == 0.20


def test_request_default_follows_settings(monkeypatch):
    monkeypatch.setattr(settings, "THRESHOLD_SEM", 0.70)
    monkeypatch.setattr(settings, "THRESHOLD_AI", 0.55)
    req = AnalysisRunRequest(entrega_id=uuid.uuid4())
    assert req.threshold_sem == 0.70
    assert req.threshold_ai == 0.55


def test_request_can_still_override_per_call():
    req = AnalysisRunRequest(entrega_id=uuid.uuid4(), threshold_sem=0.5)
    assert req.threshold_sem == 0.5


def test_compute_decision_thresholds_are_required_keyword_only():
    params = inspect.signature(StubInferenceEngine.compute_decision).parameters
    for name in ("threshold_sem", "threshold_ai"):
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert params[name].default is inspect.Parameter.empty

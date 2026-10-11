"""Decision thresholds come only from the calibration artifacts (spec AS5; design D6, D9).

Client thresholds are still accepted by the request schema for older clients, default to None and
never reach the decision (the API effect is covered in `test_api_flow.py`).
"""

import re
import uuid
from pathlib import Path

from app.infrastructure.inference.stub_engine import StubInferenceEngine
from app.presentation.schemas.analysis import AnalysisRunRequest

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_request_thresholds_are_optional_and_default_to_none():
    req = AnalysisRunRequest(entrega_id=uuid.uuid4())
    assert req.threshold_sem is None and req.threshold_ai is None


def test_request_still_accepts_legacy_thresholds():
    req = AnalysisRunRequest(entrega_id=uuid.uuid4(), threshold_sem=0.01, threshold_ai=0.01)
    assert req.threshold_sem == 0.01 and req.threshold_ai == 0.01


def test_no_app_module_calls_the_legacy_decision():
    # The stub keeps `compute_decision` only for legacy root tests/scripts; the backend never calls it.
    callers = [
        str(p.relative_to(APP_DIR)) for p in APP_DIR.rglob("*.py")
        if p.name != "stub_engine.py" and re.search(r"\.compute_decision\(|\.predict_synthetic_prob\(", p.read_text(encoding="utf-8"))
    ]
    assert callers == []
    assert "compute_decision" not in StubInferenceEngine.__abstractmethods__


def test_no_app_module_reads_legacy_threshold_settings():
    pattern = re.compile(r"\bTHRESHOLD_(SEM|AI)\b")
    readers = [
        str(p.relative_to(APP_DIR)) for p in APP_DIR.rglob("*.py")
        if p.name != "config.py" and pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert readers == []

"""Compose backend profile for the model integration settings (task 4.4; spec DA1.3, DA3.5, AS8.2)."""

import re
from pathlib import Path

import pytest

from app.config import Settings

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def _backend_block() -> str:
    text = COMPOSE.read_text(encoding="utf-8")
    match = re.search(r"^  backend:\n(.*?)(?=^  \S|^\S)", text, re.M | re.S)
    assert match, "backend service not found in docker-compose.yml"
    return match.group(1)


def test_compose_never_enables_uncalibrated_scoring():
    block = _backend_block()
    assert re.search(r"^\s*-\s*ALLOW_UNCALIBRATED=false\s*$", block, re.M)
    assert not re.search(r"ALLOW_UNCALIBRATED\s*[=:]\s*['\"]?true", COMPOSE.read_text(encoding="utf-8"), re.I)


def test_compose_documents_gcb_switch_and_mounts_artifacts_read_only():
    block = _backend_block()
    assert "GCB_SECONDARY_ENABLED=" in block
    assert "./models:/models:ro" in block
    assert "THRESHOLD_" not in block  # thresholds come only from the calibration artifacts


def test_production_refuses_uncalibrated():
    with pytest.raises(ValueError):
        Settings(_env_file=None, APP_ENV="production", ALLOW_UNCALIBRATED=True)

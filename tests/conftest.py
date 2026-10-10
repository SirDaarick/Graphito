"""Shared test configuration: auto-skip tests whose heavy dependencies are unavailable."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHARCNN_WEIGHTS = ROOT / "models" / "char_cnn" / "best_model.pth"


def _charcnn_weights_available() -> bool:
    return CHARCNN_WEIGHTS.exists()


def _graphcodebert_available() -> bool:
    try:
        from transformers import AutoConfig

        AutoConfig.from_pretrained("microsoft/graphcodebert-base", local_files_only=True)
        return True
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    charcnn_ok = None
    gcb_ok = None
    for item in items:
        if item.get_closest_marker("requires_charcnn_weights"):
            if charcnn_ok is None:
                charcnn_ok = _charcnn_weights_available()
            if not charcnn_ok:
                item.add_marker(
                    pytest.mark.skip(reason=f"CharCNN weights not found at {CHARCNN_WEIGHTS}")
                )
        if item.get_closest_marker("requires_graphcodebert"):
            if gcb_ok is None:
                gcb_ok = _graphcodebert_available()
            if not gcb_ok:
                item.add_marker(
                    pytest.mark.skip(reason="microsoft/graphcodebert-base is not cached locally")
                )

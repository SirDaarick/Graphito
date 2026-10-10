"""R5: golden-set manifest builder and benchmark metric suite (stub engine, synthetic fixture)."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "golden_set_tiny"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = _load("build_manifest", ROOT / "data" / "golden_set" / "build_manifest.py")
suite = _load("benchmark_suite", ROOT / "scripts" / "benchmark_suite.py")


# ---------------------------------------------------------------- metrics
def test_auc_f1_fpr_hand_computed():
    scores = [0.1, 0.4, 0.35, 0.8]
    labels = [False, False, True, True]
    assert suite.auc(scores, labels) == pytest.approx(0.75)

    preds = [s >= 0.5 for s in scores]  # [F, F, F, T]
    c = suite.confusion(preds, labels)
    assert c == {"tp": 1, "fp": 0, "tn": 2, "fn": 1}
    assert suite.f1_from(c) == pytest.approx(2 / 3)
    assert suite.fpr_from(c) == 0.0


def test_auc_ties_count_half():
    assert suite.auc([0.5, 0.5], [True, False]) == pytest.approx(0.5)


def test_single_class_auc_is_none_and_does_not_crash():
    m = suite.channel_metrics([0.2, 0.9], [False, True], [True, True])
    assert m["auc"] is None
    assert m["fpr"] is None  # no negatives


# Golden-set builder tests live in tests/test_golden_set_split.py.


# ---------------------------------------------------------------- end to end (stub)
def test_stub_run_emits_schema_for_both_thresholds():
    from app.infrastructure.inference.stub_engine import StubInferenceEngine

    manifest = builder.build_manifest(FIXTURE)
    manifest["synthetic"] = True
    result = suite.run_suite(manifest, FIXTURE, StubInferenceEngine(), "stub", manifest_label="fixture")

    assert result["synthetic"] is True
    assert result["engine"] == "stub"
    assert result["threshold_ai"] == 0.20
    all_runs = [r for r in result["runs"] if r["split"] == "all"]
    assert sorted(r["threshold_sem"] for r in all_runs) == [0.70, 0.85]
    for r in all_runs:
        for chan in ("channel_a", "channel_b", "fused"):
            assert {"auc", "f1", "fpr", "tp", "fp", "tn", "fn"} <= set(r[chan])

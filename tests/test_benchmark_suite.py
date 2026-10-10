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


# ---------------------------------------------------------------- builder
def test_builder_is_deterministic_with_seed():
    a = builder.build_manifest(FIXTURE, seed=42, test_ratio=0.3)
    b = builder.build_manifest(FIXTURE, seed=42, test_ratio=0.3)
    assert a == b


def test_no_problem_in_two_splits():
    m = builder.build_manifest(FIXTURE, seed=42, test_ratio=0.5)
    splits = {}
    for s in m["samples"]:
        splits.setdefault(s["problem_id"], set()).add(s["split"])
    assert splits  # fixture is not empty
    assert all(len(v) == 1 for v in splits.values())


def test_dedup_by_sha256():
    m = builder.build_manifest(FIXTURE, seed=42)
    hashes = [s["sha256"] for s in m["samples"]]
    assert len(hashes) == len(set(hashes))
    assert "p01_sum/copy/c1_dup.c" in m["duplicates_removed"]


def test_builder_labels_and_warnings():
    m = builder.build_manifest(FIXTURE, seed=42)
    assert m["counts"]["by_label"]["ai"] == 4
    assert m["counts"]["by_label"]["reference"] == 4
    assert m["warnings"], "fixture has < 6 LLM files per problem, a warning is expected"


# ---------------------------------------------------------------- end to end (stub)
def test_stub_run_emits_schema_for_both_thresholds():
    from app.infrastructure.inference.stub_engine import StubInferenceEngine

    manifest = builder.build_manifest(FIXTURE, seed=42, test_ratio=0.5)
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

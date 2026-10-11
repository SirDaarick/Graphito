"""`scripts/benchmark_student_archetypes.py` must use the current scoring API (spec AS1, AS5):
the deleted score maps, the legacy stub decision and the deprecated threshold settings are gone."""

from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_student_archetypes.py"


def test_benchmark_script_uses_the_shared_scoring_service():
    source = SCRIPT.read_text(encoding="utf-8")
    for removed in ("calibrate_semantic_similarity", "compute_decision", "THRESHOLD_SEM", "THRESHOLD_AI",
                    "prob_sintetico", "best_model.pth"):
        assert removed not in source, removed
    assert "ScoringService" in source and "build_runtime" in source

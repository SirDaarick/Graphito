"""Static scan of the frontend contract (spec AR2; behaviour is unit-tested with vitest in frontend/).

The UI must not invent scores (62/85 fallbacks), must not send thresholds, must not show the
deprecated discrepancy as a result, and must never map an unknown or missing verdict to
"Conforme". It must show Channel A's method, the engine (stub marker), the calibration state,
GraphCodeBERT as exploratory (never decisive) and the validation label.
"""

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"
pytestmark = pytest.mark.skipif(not SRC.is_dir(), reason="frontend sources not present")


def _read(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def _all_sources():
    return {p.relative_to(SRC).as_posix(): p.read_text(encoding="utf-8") for p in SRC.rglob("*.ts*")}


def test_no_invented_score_fallbacks():
    modal = _read("pages/SimilarityReportModal.tsx")
    assert not re.search(r"(\?\?|:)\s*(62|85)\s*[;)]", modal)
    assert "overallScore > 70" not in modal
    assert not re.search(r"\?\?\s*3\b", _read("components/xai/EvidenceDrawer.tsx"))
    for rel, text in _all_sources().items():
        # NULL scores are never coerced to 0% (`rep ? x * 100 : 0` and friends).
        assert not re.search(r"similitud_semantica\s*\*\s*100\)\s*:\s*0\b", text), rel


def test_api_client_sends_no_thresholds():
    api = _read("lib/api.ts")
    assert "threshold_sem" not in api and "threshold_ai" not in api
    assert "thresholdSem" not in api and "thresholdAi" not in api
    assert not re.search(r"analysis\.run\([^)]*0\.85", _read("pages/NewComparisonModal.tsx"))


def test_discrepancy_is_not_rendered():
    for rel, text in _all_sources().items():
        if rel.endswith(".tsx"):
            assert "discrepancia_score" not in text, rel
            assert not re.search(r">\s*Discrepancia\s*<", text), rel


def test_verdict_mapping_never_falls_back_to_conforme():
    mapping = _read("lib/dictamen.ts")
    for verdict in ("SIN_ALERTAS", "REVISION_ESTILOMETRICA", "REVISION_SEMANTICA", "DISCREPANCIA_DUAL",
                    "NO_EVALUABLE", "SIN_REFERENCIA"):
        assert verdict in mapping, verdict
    assert "Conforme" not in mapping and "No evaluable" in mapping and "Sin referencia" in mapping
    assert "Pendiente" in mapping
    modal = _read("pages/SimilarityReportModal.tsx")
    assert "Conforme (Sin Alertas)" not in modal and "getAuditInfo" not in modal

    # Non-judgment contract: the word 'dictamen' is forbidden in visible text/JSX in all .tsx UI files
    for rel, text in _all_sources().items():
        if rel.endswith(".tsx"):
            # Strip import statements and object property access like .dictamen
            sanitized = re.sub(r'import\s+[\s\S]*?from\s+[\'"][^\'"]+[\'"];?', '', text)
            sanitized = re.sub(r'\.\s*dictamen\b', '', sanitized)
            sanitized = re.sub(r'dictamen\s*:', '', sanitized)  # object keys in props
            assert not re.search(r"\bdictamen\b", sanitized, re.IGNORECASE), f"Forbidden word 'dictamen' found in UI rendered content: {rel}"



def test_indicators_default_to_neutral_and_lookups_ignore_prototype_keys():
    # A row without categoria/origen must not be promoted to a calibrated decision row.
    assert not re.search(r"categoria\s*\?\?\s*[\"']GENERAL[\"']", _read("pages/SimilarityReportModal.tsx"))
    assert not re.search(r"categoria\s*\?\?\s*[\"']GENERAL[\"']", _read("components/xai/EvidenceDrawer.tsx"))
    # Plain-object label maps indexed by backend strings resolve 'constructor', 'toString', ...
    for rel in ("lib/dictamen.ts", "lib/evidence.ts", "components/xai/EvidenceDrawer.tsx"):
        assert (SRC / rel).is_file(), f"contract file missing: {rel}"
        text = _read(rel)
        assert not re.search(r"[A-Z_]{4,}\[[^\]]+\]\s*\?\?", text), rel


def test_ui_shows_method_engine_calibration_gcb_and_label():
    texts = "\n".join(_all_sources().values())
    assert "Jaccard léxico, 5 tokens" in texts
    assert "Normalización de identificadores · exploratorio, no decide" in texts
    assert "zero-shot" not in texts  # the deployed model may carry the trained adapter: the label must not claim otherwise
    assert "No validado contra plagio derivado de la referencia" in texts
    assert "STUB" in _read("pages/SimilarityReportModal.tsx")
    assert "estado_calibracion" in _read("pages/SimilarityReportModal.tsx")
    assert "Heurística" in _read("components/xai/EvidenceDrawer.tsx")


def test_report_type_is_nullable_and_has_provenance():
    api = _read("lib/api.ts")
    for field in ("similitud_semantica", "probabilidad_ia", "dictamen"):
        assert re.search(rf"{field}\??:\s*[^;]*\bnull\b", api), field
    for field in ("engine", "canal_a_metodo", "estado_canal_a", "estado_canal_b", "flag_a", "flag_b", "umbral_a",
                  "umbral_b", "gcb_similarity", "etiqueta_validacion", "estado_calibracion"):
        assert re.search(rf"\b{field}\??:", api), field


def test_demo_data_is_labelled_demo_and_uses_the_new_shape():
    demo = _read("lib/demoData.ts")
    assert "DEMO" in demo and "engine: \"demo\"" in demo
    assert "PLAGIO_PROBABLE" not in demo and "SOSPECHA_IA" not in demo and "INTEGRO" not in demo

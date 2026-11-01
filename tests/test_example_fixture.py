"""The committed example fixture (`backend/app/data/examples/ejemplo_fixture.json`) keeps its contract.

The fixture holds frozen real measurements. No model is loaded here: the test only checks the stored
values against the selection criteria the builder (`scripts/build_example_fixture.py`) applied.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "backend" / "app" / "data" / "examples" / "ejemplo_fixture.json"
CASES = ["identical", "similar", "different", "ai"]
AUTHORS = {
    "identical": "Ejemplo: copia de la referencia",
    "similar": "Ejemplo: solución propia",
    "different": "Ejemplo: código de otro problema",
    "ai": "Ejemplo: generado con IA",
}

sys.path.insert(0, str(ROOT / "backend"))
from app.domain.scoring import ChannelResult, ScoringOutcome  # noqa: E402


@pytest.fixture(scope="module")
def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _cases(problem: dict) -> dict:
    return {e["caso"]: e for e in problem["entregas"]}


def _channels(entrega: dict):
    out = entrega["outcome"]
    return ChannelResult(**out["channel_a"]), ChannelResult(**out["channel_b"])


def test_top_level_contract(fixture):
    assert fixture["version"] == 1
    assert fixture["engine"] == "real"
    assert len(fixture["manifest_sha"]) == 64
    assert fixture["generated_at"]
    assert len(fixture["problems"]) >= 1


def test_every_problem_has_four_ordered_entregas(fixture):
    for p in fixture["problems"]:
        assert [e["caso"] for e in p["entregas"]] == CASES, p["key"]
        assert p["lenguaje"] == "c"
        assert p["titulo"] and p["descripcion"]
        assert p["referencia"]["autor"] == "Referencia del ejemplo"
        assert p["referencia"]["contenido"].strip()
        for e in p["entregas"]:
            assert e["autor"] == AUTHORS[e["caso"]]
            assert e["contenido"].strip()
            assert e["origen"].startswith("data/golden_set/corpus/")


def test_outcomes_rebuild_with_domain_types(fixture):
    for p in fixture["problems"]:
        for e in p["entregas"]:
            a, b = _channels(e)
            out = e["outcome"]
            assert "tiempos_ms" not in out["provenance"]
            assert {"canal_a_metodo", "manifest_sha", "checkpoint_sha_b", "gcb_estado", "label"} <= set(out["provenance"])
            assert out["engine"] == "real"
            built = ScoringOutcome.build(
                a, b, gcb_similarity=out["gcb_similarity"], engine=out["engine"], provenance=out["provenance"]
            )
            assert built.channel_a == a and built.channel_b == b
            assert a.evaluable and b.evaluable, (p["key"], e["caso"])


def test_gcb_similarity_was_measured_for_every_entrega(fixture):
    for p in fixture["problems"]:
        for e in p["entregas"]:
            out = e["outcome"]
            assert isinstance(out["gcb_similarity"], float), (p["key"], e["caso"])
            assert 0.0 <= out["gcb_similarity"] <= 1.0, (p["key"], e["caso"])
            assert out["provenance"]["gcb_estado"] in {"OK", "OK_SIN_NORM"}, (p["key"], e["caso"])


def test_selection_criteria_hold_on_stored_values(fixture):
    for p in fixture["problems"]:
        by = _cases(p)
        a = {c: _channels(by[c])[0] for c in CASES}
        b = {c: _channels(by[c])[1] for c in CASES}
        key = p["key"]
        assert a["identical"].flag is True and b["identical"].flag is False, key
        assert a["similar"].flag is False and b["similar"].flag is False, key
        assert a["different"].flag is False, key
        assert a["ai"].flag is False and b["ai"].flag is True, key
        # the different-problem code has the lowest raw Channel A of the four
        assert a["similar"].raw > a["different"].raw, key
        assert a["different"].raw == min(a[c].raw for c in CASES), key
        # the identical case uses the same calibrated threshold as the flag says
        assert a["identical"].calibrated >= a["identical"].threshold, key

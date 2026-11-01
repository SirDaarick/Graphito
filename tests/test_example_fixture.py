"""The committed example fixture (`backend/app/data/examples/ejemplo_fixture.json`) keeps its contract.

The fixture holds frozen real measurements. No model is loaded here: the test only checks the stored
values against the selection criteria the builder (`scripts/build_example_fixture.py`) applied.

Two kinds of problems live in it, told apart by the per-problem `fuente` field:
- `golden_set`: four entregas (identical, similar, different, ai) from `data/golden_set/corpus/`;
- `escom_catalogo`: three entregas (identical, similar, different). The identical and different ones are
  ESCOM catalog programs; the similar one is a hand-written human solution kept in
  `backend/app/data/examples/escom/` and flagged with `autor_humano`.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "backend" / "app" / "data" / "examples" / "ejemplo_fixture.json"
CATALOG = ROOT / "backend" / "app" / "data" / "catalog_escom.json"
HUMAN_DIR = ROOT / "backend" / "app" / "data" / "examples" / "escom"
HUMAN_NOTE = (
    " Nota: la solución propia de este ejemplo la escribió una persona sin ayuda de IA y aun así el "
    "estilo marca alto; la métrica de estilo no basta por sí sola."
)
CASES = ["identical", "similar", "different", "ai"]
ESCOM_CASES = ["identical", "similar", "different"]
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


def _golden(fixture: dict) -> list:
    return [p for p in fixture["problems"] if p.get("fuente") == "golden_set"]


def _escom(fixture: dict) -> list:
    return [p for p in fixture["problems"] if p.get("fuente") == "escom_catalogo"]


def test_top_level_contract(fixture):
    assert fixture["version"] == 1
    assert fixture["engine"] == "real"
    assert len(fixture["manifest_sha"]) == 64
    assert fixture["generated_at"]
    assert len(fixture["problems"]) >= 1


def test_every_problem_declares_its_fuente_and_the_tour_showcase_is_a_golden_set_problem(fixture):
    assert {p.get("fuente") for p in fixture["problems"]} == {"golden_set", "escom_catalogo"}
    assert fixture["problems"][0]["fuente"] == "golden_set"  # problems[0] is the tour showcase
    escom = _escom(fixture)
    assert len(escom) == 3
    assert fixture["problems"][3:] == escom  # appended last, after the golden-set problems
    assert len(_golden(fixture)) == 3


def test_every_golden_problem_has_four_ordered_entregas(fixture):
    problems = _golden(fixture)
    assert problems, "the golden-set problems are missing"
    for p in problems:
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
    problems = _golden(fixture)
    assert problems, "the golden-set problems are missing"
    for p in problems:
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


def test_escom_problems_have_three_ordered_entregas_with_a_human_solution(fixture):
    catalog = {p["nombre_archivo"]: p for p in json.loads(CATALOG.read_text(encoding="utf-8"))}
    problems = _escom(fixture)
    assert [p["key"] for p in problems] == [
        "escom:factorial_iterativo_for",
        "escom:01_ordenamiento_burbuja_iterativo",
        "escom:busqueda_lineal_arreglo",
    ]
    for p in problems:
        assert [e["caso"] for e in p["entregas"]] == ESCOM_CASES, p["key"]  # no AI case
        assert p["lenguaje"] == "c"
        assert p["titulo"] and p["descripcion"]
        assert p["referencia"]["autor"] == "Referencia del ejemplo"
        by = _cases(p)
        reference = by["identical"]["origen"].partition("#")[2]
        assert p["key"] == "escom:" + reference.rsplit(".", 1)[0]
        assert p["referencia"]["contenido"] == catalog[reference]["codigo"]
        assert by["identical"]["contenido"] == p["referencia"]["contenido"]  # the reference verbatim

        for case in ("identical", "different"):
            e = by[case]
            prefix, _, name = e["origen"].partition("#")
            assert prefix == "backend/app/data/catalog_escom.json", e["origen"]
            assert e["contenido"] == catalog[name]["codigo"], e["origen"]  # verbatim teacher program
            assert catalog[name]["lenguaje"] == "c"
            assert "autor_humano" not in e
        assert catalog[by["different"]["origen"].partition("#")[2]]["tema"] != catalog[reference]["tema"]
        for e in p["entregas"]:
            assert e["autor"] == AUTHORS[e["caso"]]

        human = by["similar"]
        assert human["autor_humano"] is True
        assert human["origen"].startswith("backend/app/data/examples/escom/") and human["origen"].endswith(".c")
        file = ROOT / human["origen"]
        assert human["contenido"] == file.read_bytes().decode("utf-8")  # the person's file, verbatim
        assert b"\r" not in file.read_bytes() and not file.read_bytes().startswith(b"\xef\xbb\xbf")
        assert len({e["origen"] for e in p["entregas"]}) == 3
    assert len({p["entregas"][2]["origen"] for p in problems}) >= 1
    others = {p["key"]: {q["referencia"]["contenido"] for q in problems if q is not p} for p in problems}
    for p in problems:  # a different-problem code is not another example's reference
        assert p["entregas"][2]["contenido"] not in others[p["key"]], p["key"]


def test_escom_problems_order_channel_a_and_graphcodebert_on_stored_values(fixture):
    problems = _escom(fixture)
    assert len(problems) == 3
    for p in problems:
        by = _cases(p)
        a = {c: _channels(by[c])[0].raw for c in ESCOM_CASES}
        g = {c: by[c]["outcome"]["gcb_similarity"] for c in ESCOM_CASES}
        key = p["key"]
        assert a["identical"] == 1.0, key  # the same code scores 100 in Channel A
        assert g["identical"] == pytest.approx(1.0, abs=1e-3), key
        assert a["identical"] > a["similar"] > a["different"], key
        assert g["identical"] > g["similar"] > g["different"], key
        assert a["different"] == min(a.values()) and g["different"] == min(g.values()), key


def test_description_warns_about_style_iff_the_human_solution_flags_in_channel_b(fixture):
    flagged = []
    for p in _escom(fixture):
        human_b = _channels(_cases(p)["similar"])[1]
        assert p["descripcion"].endswith(HUMAN_NOTE) == (human_b.flag is True), p["key"]
        assert (HUMAN_NOTE in p["descripcion"]) == (human_b.flag is True), p["key"]
        flagged.append(human_b.flag)
    assert any(flagged) and not all(flagged), "the fixture should show both outcomes"
    for p in _golden(fixture):
        assert HUMAN_NOTE not in p["descripcion"]

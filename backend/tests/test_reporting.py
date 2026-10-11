"""Reporting: additive API fields, honest PDF and flag-driven XAI (spec AR1, AR3, AR4; design D15).

- Every report carries the AR1.1 provenance fields and the validation label; NULL scores stay NULL.
- Legacy rows (no provenance) are served as `engine == "legacy"` and never rescored.
- The PDF prints method, calibration state, thresholds, abstention, engine and the label; it never
  falls back to a conformity verdict and has no discrepancy row (checked on extracted text and on
  the content model handed to the renderer).
- Rule-based XAI rows are labelled heuristic and gated on the decision flags; the file-level
  similarity row exists only when `flag_a` is true and carries the reference id.
"""

import re
import uuid
from pathlib import Path

import pytest

from app.application.services.pdf_service import PdfReportService, verdict_banner
from app.application.services.xai_service import XAIService
from app.config import Settings
from app.domain.scoring import ChannelResult, ScoringOutcome
from app.infrastructure.database.models import DictamenEnum, EstadoAnalisisEnum, ReporteAnalisis
from app.infrastructure.inference import get_inference_engine, runtime as rt
from app.infrastructure.vector_store import get_vector_store
from app.main import app

AR11_FIELDS = (
    "engine", "canal_a_metodo", "estado_canal_a", "estado_canal_b", "flag_a", "flag_b", "umbral_a", "umbral_b",
    "clave_umbral_a", "clave_umbral_b", "puntaje_calibrado_a", "calibracion_sha_a", "calibracion_sha_b",
    "checkpoint_sha_b", "manifest_sha", "gcb_similarity", "gcb_estado", "reference_id", "versiones_modelo",
    "etiqueta_validacion", "estado_calibracion", "similitud_semantica", "probabilidad_ia", "discrepancia_score",
)
LABEL = "No validado contra plagio derivado de la referencia"
REF_C = """#include <stdio.h>
int main(void) {
    int n, i, total = 0;
    scanf("%d", &n);
    for (i = 0; i < n; i++) { total += i; }
    printf("%d\\n", total);
    return 0;
}
"""
PLAIN_C = "int suma(int a, int b) {\n    int r = a + b;\n    return r;\n}\nint resta(int a, int b) { return a - b; }\n"


async def _login(client, email):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "PasswordSegura123!", "nombre": "P"})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "PasswordSegura123!"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _problem(client, headers, *, reference=True):
    prob = await client.post("/api/v1/problems/", json={"titulo": "Suma", "enunciado": "Suma.", "lenguaje": "c"}, headers=headers)
    problema_id = prob.json()["id"]
    if reference:
        ref = await client.post(
            f"/api/v1/problems/{problema_id}/references",
            params={"autor": "Docente", "contenido": REF_C, "lenguaje": "c"}, headers=headers,
        )
        assert ref.status_code == 201, ref.text
    return problema_id


async def _analyze(client, headers, problema_id, code):
    sub = await client.post(
        f"/api/v1/problems/{problema_id}/submissions",
        json={"problema_id": problema_id, "autor": "A1", "contenido": code, "lenguaje": "c"}, headers=headers,
    )
    assert sub.status_code == 201, sub.text
    res = await client.post("/api/v1/analysis/run", json={"entrega_id": sub.json()["id"]}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


# --- AR1: API fields ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_abstained_report_has_null_score_b_and_label(client):
    headers = await _login(client, "abst@escom.ipn.mx")
    problema_id = await _problem(client, headers)
    body = await _analyze(client, headers, problema_id, "int x;")
    for field in AR11_FIELDS:
        assert field in body, field
    assert body["probabilidad_ia"] is None and body["estado_canal_b"] == "ABSTENIDO" and body["flag_b"] is None
    assert body["dictamen"] == "NO_EVALUABLE" and LABEL in body["etiqueta_validacion"]
    assert body["engine"] == "stub" and body["estado_calibracion"] == "stub"
    assert body["discrepancia_score"] is None and body["discrepancia_etiqueta"] is None
    assert body["calibracion_sha_a"] is None and body["checkpoint_sha_b"] is None  # stub: no shas (AS5.2)


@pytest.mark.asyncio
async def test_legacy_row_is_served_as_legacy_with_null_provenance(client, db_session):
    headers = await _login(client, "legacy@escom.ipn.mx")
    problema_id = await _problem(client, headers, reference=False)
    sub = await client.post(
        f"/api/v1/problems/{problema_id}/submissions",
        json={"problema_id": problema_id, "autor": "A1", "contenido": PLAIN_C, "lenguaje": "c"}, headers=headers,
    )
    row = ReporteAnalisis(
        entrega_id=uuid.UUID(sub.json()["id"]), similitud_semantica=0.8, probabilidad_ia=0.3, discrepancia_score=0.24,
        dictamen=DictamenEnum.SIN_ALERTAS, estado=EstadoAnalisisEnum.COMPLETADO,
    )
    db_session.add(row)
    await db_session.commit()
    body = (await client.get(f"/api/v1/analysis/reports/{row.id}", headers=headers)).json()
    assert body["engine"] == "legacy" and body["estado_calibracion"] == "legacy"
    for field in ("canal_a_metodo", "estado_canal_a", "flag_a", "umbral_a", "calibracion_sha_a", "checkpoint_sha_b",
                  "manifest_sha", "versiones_modelo", "clave_umbral_a"):
        assert body[field] is None, field
    assert body["similitud_semantica"] == 0.8 and body["discrepancia_score"] == 0.24  # never rescored
    assert "No validado" in body["discrepancia_etiqueta"] and LABEL in body["etiqueta_validacion"]


class _FakeCharCNN:
    arch_version = 2
    preproc_version = 2

    def predict_text(self, code):
        return {"score": 0.3, "abstained": False, "ai_probability": 0.05, "prob_sintetico": 0.05}


class _FakeGCB:
    def predict_code(self, code, language="c"):
        return {"success": True, "embedding": [float((len(code) + i) % 7) + 1.0 for i in range(768)],
                "input_version": "v2", "pooling": "mean"}


def _real_runtime(fake_artifacts):
    from app.infrastructure.inference.real_engine import RealBimodalInferenceEngine

    root = fake_artifacts.root
    settings = Settings(
        _env_file=None, INFERENCE_MODE="REAL", DEPLOY_MANIFEST=str(fake_artifacts.manifest),
        CHANNEL_A_CALIBRATION=str(root / "channel_a" / "calibration.json"),
        CHARCNN_CALIBRATION=str(root / "channel_b" / "calibration.json"),
        CHARCNN_CHECKPOINT=str(root / "channel_b" / "best.pth"),
    )
    runtime = rt.build_runtime(settings, engine_factory=lambda s, b: RealBimodalInferenceEngine(
        b, s, charcnn_factory=lambda path: _FakeCharCNN(), gcb_factory=lambda kwargs: _FakeGCB(),
    ))
    assert runtime.ready, runtime.reason
    return runtime


@pytest.mark.asyncio
async def test_real_report_has_every_field_and_manifest_shas(client, fake_artifacts, monkeypatch):
    runtime = _real_runtime(fake_artifacts)
    monkeypatch.setattr(rt, "_runtime", runtime)
    monkeypatch.setitem(app.dependency_overrides, get_inference_engine, lambda: runtime.engine)
    try:
        headers = await _login(client, "realfields@escom.ipn.mx")
        problema_id = await _problem(client, headers)
        body = await _analyze(client, headers, problema_id, REF_C)
    finally:
        runtime.engine.close()
    manifest = fake_artifacts.read()
    for field in AR11_FIELDS:
        assert field in body, field
    assert body["engine"] == "real" and body["estado_calibracion"] == "calibrado"
    assert body["calibracion_sha_a"] == manifest["files"]["channel_a/calibration.json"]
    assert body["calibracion_sha_b"] == manifest["files"]["channel_b/calibration.json"]
    assert body["checkpoint_sha_b"] == manifest["files"]["channel_b/best.pth"]
    assert (body["clave_umbral_a"], body["clave_umbral_b"]) == ("fpr_0.05", "fpr_0.01")
    assert (body["umbral_a"], body["umbral_b"]) == (0.5, 0.1715)
    assert body["versiones_modelo"] == {
        "charcnn_arch_version": 2, "charcnn_preproc_version": 2, "gcb_input_version": "v2", "gcb_pooling": "mean",
    }
    assert body["canal_a_metodo"] == "jaccard" and body["reference_id"] == body["referencia_id"]
    assert body["probabilidad_ia"] != 0.05


@pytest.mark.asyncio
async def test_report_reads_do_not_need_a_ready_engine(client, db_session, fake_artifacts, monkeypatch):
    """Reads (report, PDF, code, batch status, verdict, problems) work while REAL is degraded."""
    headers = await _login(client, "degradedread@escom.ipn.mx")
    problema_id = await _problem(client, headers)
    body = await _analyze(client, headers, problema_id, PLAIN_C)
    fake_artifacts.write_file("channel_b/best.pth", b"tampered", update_manifest=False)
    degraded = rt.build_runtime(Settings(_env_file=None, INFERENCE_MODE="REAL", DEPLOY_MANIFEST=str(fake_artifacts.manifest),
                                         CHARCNN_CHECKPOINT=str(fake_artifacts.root / "channel_b" / "best.pth"),
                                         CHANNEL_A_CALIBRATION=str(fake_artifacts.root / "channel_a" / "calibration.json"),
                                         CHARCNN_CALIBRATION=str(fake_artifacts.root / "channel_b" / "calibration.json")))
    assert not degraded.ready
    monkeypatch.setattr(rt, "_runtime", degraded)
    monkeypatch.delitem(app.dependency_overrides, get_inference_engine)
    monkeypatch.delitem(app.dependency_overrides, get_vector_store)
    rid = body["id"]
    for path in (f"/api/v1/analysis/reports/{rid}", f"/api/v1/analysis/reports/{rid}/pdf",
                 f"/api/v1/analysis/reports/{rid}/code", f"/api/v1/problems/{problema_id}",
                 f"/api/v1/problems/{problema_id}/submissions", "/api/v1/problems/"):
        res = await client.get(path, headers=headers)
        assert res.status_code == 200, (path, res.text)
    verdict = await client.patch(f"/api/v1/analysis/reports/{rid}/verdict", json={"decision_docente": "APROBADO"}, headers=headers)
    assert verdict.status_code == 200, verdict.text


# --- AR3: PDF -------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pdf_of_abstained_no_evaluable_report_is_honest(client, pdf_text):
    headers = await _login(client, "pdfabst@escom.ipn.mx")
    problema_id = await _problem(client, headers)
    body = await _analyze(client, headers, problema_id, "int x;")
    pdf = await client.get(f"/api/v1/analysis/reports/{body['id']}/pdf", headers=headers)
    assert pdf.status_code == 200
    text = pdf_text(pdf.content)
    assert "ABSTENIDO" in text and "NO EVALUABLE" in text and LABEL in text
    assert "Jaccard lexico" in text and "stub" in text
    assert "CONFORMIDAD" not in text and "discrepancia" not in text.lower()


@pytest.mark.asyncio
async def test_pdf_of_sin_referencia_report_says_so(client, pdf_text):
    headers = await _login(client, "pdfnoref@escom.ipn.mx")
    problema_id = await _problem(client, headers, reference=False)
    body = await _analyze(client, headers, problema_id, PLAIN_C)
    assert body["dictamen"] == "SIN_REFERENCIA"
    text = pdf_text((await client.get(f"/api/v1/analysis/reports/{body['id']}/pdf", headers=headers)).content)
    assert "SIN REFERENCIA" in text and "CONFORMIDAD" not in text and "SIN ALERTAS" not in text


def test_content_model_prints_thresholds_calibration_and_no_discrepancy_row():
    from app.presentation.schemas.analysis import ReporteAnalisisResponse

    report = ReporteAnalisisResponse(
        id=1, entrega_id=uuid.uuid4(), fecha_analisis="2026-10-11T00:00:00Z", estado="COMPLETADO",
        dictamen="REVISION_SEMANTICA", engine="real", canal_a_metodo="jaccard", estado_canal_a="EVALUADO",
        estado_canal_b="EVALUADO", flag_a=True, flag_b=False, umbral_a=0.4321, umbral_b=0.1715,
        similitud_semantica=0.61, puntaje_calibrado_a=0.7, probabilidad_ia=0.1, calibracion_sha_a="a" * 64,
        calibracion_sha_b="b" * 64, checkpoint_sha_b="c" * 64, manifest_sha="d" * 64, discrepancia_score=0.3,
        gcb_estado="ERROR",
    )
    content = PdfReportService.build_content(report)
    flat = " ".join(" ".join(map(str, row)) for row in content.metric_rows + content.provenance_rows)
    assert "0.4321" in flat and "0.1715" in flat and "aaaaaaaaaaaa" in flat and "dddddddddddd" in flat
    assert "Jaccard lexico" in flat and "exploratorio" in flat.lower()
    assert "discrepancia" not in flat.lower() and "0.3" not in flat
    assert LABEL in content.label and "ALERTA" in content.verdict_text


@pytest.mark.parametrize("dictamen, estado, expected", [
    ("SIN_ALERTAS", "COMPLETADO", "SIN ALERTAS"),
    ("NO_EVALUABLE", "COMPLETADO", "NO EVALUABLE"),
    ("SIN_REFERENCIA", "COMPLETADO", "SIN REFERENCIA"),
    ("ALGO_NUEVO", "COMPLETADO", "NO EVALUABLE"),
    (None, "COMPLETADO", "SIN DICTAMEN"),
    (None, "ERROR", "SIN DICTAMEN"),
])
def test_verdict_banner_never_falls_back_to_conformity(dictamen, estado, expected):
    _, text = verdict_banner(dictamen, estado)
    assert expected in text and "CONFORMIDAD" not in text
    if dictamen != "SIN_ALERTAS":
        assert "SIN ALERTAS" not in text


# --- AR4: XAI -------------------------------------------------------------------------------------

LLM_CODE = "// Time complexity: O(n)\n#include <algorithm>\nint main(void) {\n    for (int i = 0; i < 3; i++) {}\n    return 0;\n}\n"


def _outcome(flag_a, b_state="flag_false", threshold_a=0.37):
    if flag_a is None:
        a = ChannelResult.not_evaluated("SIN_REFERENCIA")
    else:
        a = ChannelResult.evaluated(raw=0.62, calibrated=0.6 if flag_a else 0.1, threshold=threshold_a,
                                    threshold_key="fpr_0.05", calibration_sha256=None)
    if b_state == "abstained":
        b = ChannelResult.not_evaluated("ABSTENCION")
    else:
        b = ChannelResult.evaluated(raw=0.9, calibrated=0.9 if b_state == "flag_true" else 0.01, threshold=0.1715,
                                    threshold_key="fpr_0.01", calibration_sha256=None)
    return ScoringOutcome.build(a, b, reference_id="ref-123" if flag_a is not None else None,
                                provenance={"reference_author": "Docente"})


@pytest.mark.parametrize("flag_a", [False, None])
def test_no_similarity_row_without_flag_a(flag_a):
    rows = XAIService.extract_explanations(LLM_CODE, "c", _outcome(flag_a))
    assert not [r for r in rows if r["categoria"] in ("SIMILITUD_ARCHIVO", "ISOMORFISMO_DFG")]


def test_flag_a_adds_file_level_similarity_row_with_reference():
    rows = XAIService.extract_explanations(LLM_CODE, "c", _outcome(True))
    [row] = [r for r in rows if r["categoria"] == "SIMILITUD_ARCHIVO"]
    assert row["numero_linea"] is None and row["reference_id"] == "ref-123" and row["origen"] == "decision"
    assert "0.3700" in row["descripcion"] and "fpr_0.05" in row["descripcion"] and "Docente" in row["descripcion"]


@pytest.mark.parametrize("b_state", ["flag_false", "abstained"])
def test_no_synthetic_pattern_rows_without_flag_b(b_state):
    rows = XAIService.extract_explanations(LLM_CODE, "c", _outcome(False, b_state))
    assert rows == []


def test_flag_b_heuristic_rows_are_labelled_heuristic():
    rows = XAIService.extract_explanations(LLM_CODE, "c", _outcome(False, "flag_true"))
    assert {r["categoria"] for r in rows} == {"ESTILO_LLM", "NIVEL_AVANZADO"}
    for r in rows:
        assert r["origen"] == "heuristica" and "Heurística" in r["tipo_alerta"]
        assert "no es salida del modelo" in r["descripcion"]


def test_xai_has_no_hardcoded_decision_thresholds():
    source = Path(XAIService.__module__.replace(".", "/") + ".py")
    text = (Path(__file__).resolve().parents[1] / source).read_text(encoding="utf-8")
    assert not re.search(r"\b0\.(80|90|75)\b", text)


@pytest.mark.asyncio
async def test_api_indicators_carry_origin(client):
    headers = await _login(client, "origin@escom.ipn.mx")
    problema_id = await _problem(client, headers)
    body = await _analyze(client, headers, problema_id, "// Time complexity: O(n)\n" + REF_C)
    assert body["flag_a"] is True and body["flag_b"] is True
    origins = {(i["categoria"], i["origen"]) for i in body["indicadores"]}
    assert ("SIMILITUD_ARCHIVO", "decision") in origins and ("GENERAL", "decision") in origins
    assert ("ESTILO_LLM", "heuristica") in origins

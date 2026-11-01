"""Per-line style attribution (occlusion): an approximation of which lines move the CharCNN score.

Checked through the API with the stub engine (deterministic fake deltas, no models needed).
"""

import uuid

import pytest
from sqlalchemy import select

from app.domain.errors import NotReadyError
from app.infrastructure.database.models import CodigoFuente, EstadoAnalisisEnum, ReporteAnalisis
from app.infrastructure.inference import get_inference_engine
from app.main import app

PASSWORD = "PasswordSegura123!"
MANY_LINES = "#include <stdio.h>\nint main(void) {\n" + "".join(
    f"    printf(\"valor numero {i} = %d\\n\", {i} * {i + 3});\n" for i in range(40)
) + "    return 0;\n}\n"


async def _login(client, email):
    await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "nombre": "P"})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _report(client, db_session, email="owner@escom.ipn.mx", code=MANY_LINES):
    headers = await _login(client, email)
    prob = await client.post("/api/v1/problems/", json={"titulo": "T", "enunciado": "E", "lenguaje": "c"}, headers=headers)
    problema_id = prob.json()["id"]
    sub = await client.post(
        f"/api/v1/problems/{problema_id}/submissions",
        json={"problema_id": problema_id, "autor": "A1", "contenido": MANY_LINES, "lenguaje": "c"}, headers=headers,
    )
    entrega_id = uuid.UUID(sub.json()["id"])
    if code != MANY_LINES:
        row = (await db_session.execute(select(CodigoFuente).where(CodigoFuente.id == entrega_id))).scalar_one()
        row.contenido = code
    report = ReporteAnalisis(entrega_id=entrega_id, estado=EstadoAnalisisEnum.PENDIENTE, engine="stub")
    db_session.add(report)
    await db_session.commit()
    return headers, report.id


def _url(report_id):
    return f"/api/v1/analysis/reports/{report_id}/style-attribution"


@pytest.mark.asyncio
async def test_shape_positive_only_sorted_and_capped(client, db_session):
    headers, rid = await _report(client, db_session)
    res = await client.get(_url(rid), headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["metodo"] == "oclusion_por_linea"
    assert body["aproximacion"] is True
    assert isinstance(body["probabilidad"], float)
    lines = body["lineas"]
    assert 0 < len(lines) <= 8
    assert all(set(item) == {"numero_linea", "aporte"} for item in lines)
    assert all(item["aporte"] > 0 for item in lines)
    numbers = [item["numero_linea"] for item in lines]
    assert numbers == sorted(numbers)
    assert all(1 <= n <= MANY_LINES.count("\n") for n in numbers)


@pytest.mark.asyncio
async def test_is_deterministic_and_keeps_the_largest_contributions(client, db_session):
    headers, rid = await _report(client, db_session)
    first = (await client.get(_url(rid), headers=headers)).json()
    second = (await client.get(_url(rid), headers=headers)).json()
    assert first == second
    from app.application.services.style_attribution_service import StyleAttributionService
    from app.infrastructure.inference.stub_engine import StubInferenceEngine

    full = await StubInferenceEngine().attribute_stylometry_by_line(MANY_LINES, max_lines=300)
    positives = sorted((d for d in full.deltas.values() if d > 0), reverse=True)
    assert len(positives) > 8, "fixture must have more positive lines than the cap"
    kept = sorted((item["aporte"] for item in first["lineas"]), reverse=True)
    assert kept[0] == pytest.approx(positives[0], abs=1e-6)
    assert min(kept) >= round(positives[7], 6) - 1e-6
    assert StyleAttributionService.TOP_N == 8


@pytest.mark.asyncio
async def test_empty_code_has_no_lines(client, db_session):
    headers, rid = await _report(client, db_session, email="empty@escom.ipn.mx", code="")
    res = await client.get(_url(rid), headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["lineas"] == [] and body["aproximacion"] is True


@pytest.mark.asyncio
async def test_unknown_report_is_404(client, db_session):
    headers = await _login(client, "nobody@escom.ipn.mx")
    res = await client.get(_url(987654), headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_other_teacher_is_403_and_anonymous_is_rejected(client, db_session):
    _, rid = await _report(client, db_session)
    other = await _login(client, "other@escom.ipn.mx")
    assert (await client.get(_url(rid), headers=other)).status_code == 403
    assert (await client.get(_url(rid))).status_code in (401, 403)


@pytest.mark.asyncio
async def test_not_ready_engine_is_503(client, db_session):
    headers, rid = await _report(client, db_session)

    def not_ready():
        raise NotReadyError("artifacts_missing", "inference engine is not ready")

    app.dependency_overrides[get_inference_engine] = not_ready
    res = await client.get(_url(rid), headers=headers)
    assert res.status_code == 503


@pytest.mark.asyncio
async def test_existing_code_endpoint_is_unchanged(client, db_session):
    headers, rid = await _report(client, db_session)
    res = await client.get(f"/api/v1/analysis/reports/{rid}/code", headers=headers)
    assert res.status_code == 200
    assert "lineas" not in res.json()

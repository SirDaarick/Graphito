"""Reports without a verdict yet (PENDIENTE / PROCESANDO / ERROR) carry NULL scores and NULL
dictamen (design matrix, D8). Every consumer must handle them honestly: no crash, no invented
score and never a conformity verdict (spec AR1.2, AR3.1). Checked through the API.
"""

import uuid

import pytest
from sqlalchemy import select

from app.infrastructure.database.models import Docente, EstadoAnalisisEnum, LoteAnalisis, ReporteAnalisis

REF_C = "#include <stdio.h>\nint main(void) { int n; scanf(\"%d\", &n); printf(\"%d\\n\", n * 2); return 0; }\n"
STUDENT_C = "#include <stdio.h>\nint main(void) { int x; scanf(\"%d\", &x); printf(\"%d\\n\", x + x); return 0; }\n"
EMAIL = "nulls@escom.ipn.mx"


async def _setup(client, db_session):
    await client.post("/api/v1/auth/register", json={"email": EMAIL, "password": "PasswordSegura123!", "nombre": "P"})
    login = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "PasswordSegura123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    prob = await client.post("/api/v1/problems/", json={"titulo": "T", "enunciado": "E", "lenguaje": "c"}, headers=headers)
    problema_id = prob.json()["id"]
    sub = await client.post(
        f"/api/v1/problems/{problema_id}/submissions",
        json={"problema_id": problema_id, "autor": "A1", "contenido": STUDENT_C, "lenguaje": "c"}, headers=headers,
    )
    entrega_id = uuid.UUID(sub.json()["id"])
    docente = (await db_session.execute(select(Docente).where(Docente.email == EMAIL))).scalar_one()

    batch_id = uuid.uuid4()
    db_session.add(LoteAnalisis(
        id=batch_id, problema_id=problema_id, docente_id=docente.id, total_archivos=3, procesados=0, errores=1,
        estado="PROCESANDO",
    ))
    reports = {}
    for estado in (EstadoAnalisisEnum.PENDIENTE, EstadoAnalisisEnum.PROCESANDO, EstadoAnalisisEnum.ERROR):
        row = ReporteAnalisis(
            entrega_id=entrega_id, lote_id=batch_id, estado=estado, engine="real",
            error_mensaje="gcb_failed" if estado == EstadoAnalisisEnum.ERROR else None,
        )
        db_session.add(row)
        await db_session.flush()
        reports[estado.value] = row.id
    await db_session.commit()
    return headers, batch_id, reports


@pytest.mark.asyncio
async def test_unscored_reports_are_served_without_scores_or_verdict(client, db_session):
    headers, batch_id, reports = await _setup(client, db_session)
    for estado, report_id in reports.items():
        res = await client.get(f"/api/v1/analysis/reports/{report_id}", headers=headers)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["estado"] == estado and body["dictamen"] is None
        assert body["similitud_semantica"] is None and body["probabilidad_ia"] is None
        code = await client.get(f"/api/v1/analysis/reports/{report_id}/code", headers=headers)
        assert code.status_code == 200, code.text


@pytest.mark.asyncio
async def test_batch_status_counts_unscored_reports(client, db_session):
    headers, batch_id, _ = await _setup(client, db_session)
    res = await client.get(f"/api/v1/analysis/batch/{batch_id}/status", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["procesados"] == 0 and body["errores"] == 1 and body["reportes_completados"] == []


@pytest.mark.asyncio
async def test_pdf_of_unscored_report_states_it_and_never_claims_conformity(client, db_session, pdf_text):
    headers, _, reports = await _setup(client, db_session)
    for estado, report_id in reports.items():
        res = await client.get(f"/api/v1/analysis/reports/{report_id}/pdf", headers=headers)
        assert res.status_code == 200, res.text
        text = pdf_text(res.content)
        assert "CONFORMIDAD" not in text and "SIN ALERTAS" not in text, text
        assert estado in text and "SIN DICTAMEN" in text
        assert "No evaluado" in text

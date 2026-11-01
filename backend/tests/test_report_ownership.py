"""Report-scoped endpoints only serve the teacher who owns the problem behind the report.

Ownership chain: ReporteAnalisis.entrega_id -> CodigoFuente.problema_id -> Problema.docente_id.
Unknown report id -> 404; another teacher's report -> 403 (same as verdict / style-attribution).
"""

import pytest
import pytest_asyncio

PASSWORD = "PasswordSegura123!"
CODE = "#include <stdio.h>\nint main(void) {\n    printf(\"hola\\n\");\n    return 0;\n}\n"
BASE = "/api/v1/analysis/reports"
COMMENTS = "/api/v1/reports"


async def _login(client, email):
    await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "nombre": "P"})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest_asyncio.fixture
async def world(client):
    """Teacher A owns a problem, a submission and an analyzed report; teacher B owns nothing."""
    a = await _login(client, "a@escom.ipn.mx")
    b = await _login(client, "b@escom.ipn.mx")
    prob = await client.post("/api/v1/problems/", json={"titulo": "T", "enunciado": "E", "lenguaje": "c"}, headers=a)
    pid = prob.json()["id"]
    sub = await client.post(
        f"/api/v1/problems/{pid}/submissions",
        json={"problema_id": pid, "autor": "Ana", "contenido": CODE, "lenguaje": "c"}, headers=a,
    )
    entrega_id = sub.json()["id"]
    run = await client.post("/api/v1/analysis/run", json={"entrega_id": entrega_id}, headers=a)
    assert run.status_code == 201, run.text
    rid = run.json()["id"]
    comment = await client.post(f"{COMMENTS}/{rid}/comments", json={"contenido": "nota de A"}, headers=a)
    assert comment.status_code == 201, comment.text
    return {"a": a, "b": b, "rid": rid, "entrega_id": entrega_id, "comment_id": comment.json()["id"]}


def _endpoints(w):
    rid = w["rid"]
    return [
        ("get", f"{BASE}/{rid}", None),
        ("get", f"{BASE}/{rid}/code", None),
        ("get", f"{BASE}/{rid}/pdf", None),
        ("get", f"{BASE}/{rid}/style-attribution", None),
        ("patch", f"{BASE}/{rid}/verdict", {"decision_docente": "APROBADO"}),
        ("get", f"{COMMENTS}/{rid}/comments", None),
        ("post", f"{COMMENTS}/{rid}/comments", {"contenido": "intruso"}),
        ("delete", f"{COMMENTS}/{rid}/comments/{w['comment_id']}", None),
    ]


@pytest.mark.asyncio
async def test_other_teacher_is_forbidden_on_every_report_endpoint(client, world):
    for method, url, body in _endpoints(world):
        res = await client.request(method, url, json=body, headers=world["b"])
        assert res.status_code == 403, f"{method.upper()} {url} -> {res.status_code} {res.text[:120]}"
    # nothing leaked into or removed from A's data by B's attempts
    listed = await client.get(f"{COMMENTS}/{world['rid']}/comments", headers=world["a"])
    assert [c["contenido"] for c in listed.json()] == ["nota de A"]
    report = await client.get(f"{BASE}/{world['rid']}", headers=world["a"])
    assert report.json()["decision_docente"] == "PENDIENTE"


@pytest.mark.asyncio
async def test_other_teacher_cannot_run_analysis_on_foreign_submission(client, world):
    res = await client.post("/api/v1/analysis/run", json={"entrega_id": world["entrega_id"]}, headers=world["b"])
    assert res.status_code == 403, res.text
    res = await client.post(
        "/api/v1/analysis/run?async_mode=true", json={"entrega_id": world["entrega_id"]}, headers=world["b"]
    )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_unknown_report_is_404_for_every_endpoint(client, world):
    w = dict(world, rid=987654)
    for method, url, body in _endpoints(w):
        res = await client.request(method, url, json=body, headers=world["a"])
        assert res.status_code == 404, f"{method.upper()} {url} -> {res.status_code}"


@pytest.mark.asyncio
async def test_unauthenticated_requests_stay_401(client, world):
    for method, url, body in _endpoints(world):
        res = await client.request(method, url, json=body)
        assert res.status_code == 401, f"{method.upper()} {url} -> {res.status_code}"
    res = await client.post("/api/v1/analysis/run", json={"entrega_id": world["entrega_id"]})
    assert res.status_code == 401


# --- the owner's responses are unchanged -------------------------------------------------------------

@pytest.mark.asyncio
async def test_owner_get_report(client, world):
    res = await client.get(f"{BASE}/{world['rid']}", headers=world["a"])
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == world["rid"]
    assert body["entrega_id"] == world["entrega_id"]
    assert body["es_ejemplo"] is False
    assert "indicadores" in body


@pytest.mark.asyncio
async def test_owner_get_code(client, world):
    res = await client.get(f"{BASE}/{world['rid']}/code", headers=world["a"])
    assert res.status_code == 200
    body = res.json()
    assert body["reporte_id"] == world["rid"]
    assert body["student_code"] == CODE
    assert body["student_author"] == "Ana"
    assert {"reference_code", "reference_author", "language", "problem_title", "indicadores", "metricas_codigo"} <= set(body)


@pytest.mark.asyncio
async def test_owner_get_pdf(client, world):
    res = await client.get(f"{BASE}/{world['rid']}/pdf", headers=world["a"])
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")
    assert f"reporte_integridad_{world['rid']}.pdf" in res.headers["content-disposition"]


@pytest.mark.asyncio
async def test_owner_style_attribution(client, world):
    res = await client.get(f"{BASE}/{world['rid']}/style-attribution", headers=world["a"])
    assert res.status_code == 200
    assert res.json()["metodo"] == "oclusion_por_linea"


@pytest.mark.asyncio
async def test_owner_verdict(client, world):
    res = await client.patch(
        f"{BASE}/{world['rid']}/verdict", json={"decision_docente": "APROBADO"}, headers=world["a"]
    )
    assert res.status_code == 200, res.text
    assert res.json()["decision_docente"] == "APROBADO"


@pytest.mark.asyncio
async def test_owner_comments_list_create_delete(client, world):
    a, rid = world["a"], world["rid"]
    created = await client.post(f"{COMMENTS}/{rid}/comments", json={"contenido": "  otra  ", "numero_linea": 2}, headers=a)
    assert created.status_code == 201
    body = created.json()
    assert body["contenido"] == "otra" and body["numero_linea"] == 2 and body["reporte_id"] == rid
    listed = await client.get(f"{COMMENTS}/{rid}/comments", headers=a)
    assert listed.status_code == 200 and len(listed.json()) == 2
    deleted = await client.delete(f"{COMMENTS}/{rid}/comments/{body['id']}", headers=a)
    assert deleted.status_code == 204
    assert len((await client.get(f"{COMMENTS}/{rid}/comments", headers=a)).json()) == 1


@pytest.mark.asyncio
async def test_owner_run_analysis_still_works(client, world):
    res = await client.post("/api/v1/analysis/run", json={"entrega_id": world["entrega_id"]}, headers=world["a"])
    assert res.status_code == 201


@pytest.mark.asyncio
async def test_run_unknown_submission_is_still_404(client, world):
    res = await client.post(
        "/api/v1/analysis/run", json={"entrega_id": "00000000-0000-0000-0000-000000000001"}, headers=world["a"]
    )
    assert res.status_code == 404


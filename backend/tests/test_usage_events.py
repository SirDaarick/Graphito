"""Usage events: what teachers do and how long each stage takes, stored in `eventos_uso`.

Events carry ids, routes, durations and outcomes only: never source code, emails or names.
"""
import asyncio

import pytest
from sqlalchemy import select

from app.infrastructure.database.models import EventoUso

CODE = "#include <stdio.h>\nint main(void){int secreto_unico_xyz=3;printf(\"%d\",secreto_unico_xyz);return 0;}\n"
EMAIL = "uso@escom.ipn.mx"


async def _login(client, email=EMAIL):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "PasswordSegura123!", "nombre": "Nombre Privado"})
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": "PasswordSegura123!"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}, res.json()["docente"]["id"]


async def _events(db_session, **where):
    db_session.expire_all()
    query = select(EventoUso).order_by(EventoUso.id)
    for key, value in where.items():
        query = query.where(getattr(EventoUso, key) == value)
    return (await db_session.execute(query)).scalars().all()


async def _problem_with_submission(client, headers):
    prob = await client.post("/api/v1/problems/", json={"titulo": "Suma", "enunciado": "Suma.", "lenguaje": "c"}, headers=headers)
    pid = prob.json()["id"]
    await client.post(f"/api/v1/problems/{pid}/references", params={"autor": "ref", "contenido": CODE, "lenguaje": "c"}, headers=headers)
    sub = await client.post(
        f"/api/v1/problems/{pid}/submissions",
        json={"problema_id": pid, "autor": "A1", "contenido": CODE, "lenguaje": "c"}, headers=headers,
    )
    return pid, sub.json()["id"]


@pytest.mark.asyncio
async def test_authenticated_request_is_recorded_with_route_template_and_duration(client, db_session):
    headers, docente_id = await _login(client)
    pid, _ = await _problem_with_submission(client, headers)

    res = await client.get(f"/api/v1/problems/{pid}", headers=headers)
    assert res.status_code == 200

    [event] = [e for e in await _events(db_session, tipo="peticion") if e.metodo == "GET" and e.ruta.startswith("/api/v1/problems/")]
    assert event.ruta == "/api/v1/problems/{problem_id}"  # template, not the numeric id
    assert event.estado_http == 200 and event.docente_id == docente_id
    assert event.duracion_ms is not None and event.duracion_ms >= 0
    assert event.created_at is not None


@pytest.mark.asyncio
async def test_unauthenticated_request_is_recorded_without_docente(client, db_session):
    res = await client.get("/api/v1/problems/")
    assert res.status_code == 401

    [event] = await _events(db_session, tipo="peticion", estado_http=401)
    assert event.docente_id is None and event.ruta == "/api/v1/problems/"


@pytest.mark.asyncio
async def test_health_and_preflight_requests_are_not_recorded(client, db_session):
    await client.get("/health")
    await client.options("/api/v1/problems/", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})

    assert await _events(db_session) == []


@pytest.mark.asyncio
async def test_analysis_event_has_outcome_and_per_stage_timings(client, db_session):
    headers, docente_id = await _login(client)
    pid, entrega_id = await _problem_with_submission(client, headers)

    res = await client.post("/api/v1/analysis/run", json={"entrega_id": entrega_id}, headers=headers)
    assert res.status_code == 201, res.text

    [event] = await _events(db_session, tipo="analisis")
    assert event.docente_id == docente_id and event.duracion_ms >= 0
    detalle = event.detalle
    assert detalle["modo"] == "individual"
    assert detalle["dictamen"] == res.json()["dictamen"]
    assert detalle["estado_canal_a"] and detalle["estado_canal_b"]
    assert detalle["problema_id"] == pid and detalle["n_caracteres"] == len(CODE)
    assert set(detalle["tiempos_ms"]) == {"canal_a", "canal_b", "gcb", "puntuacion"}
    assert all(v >= 0 for v in detalle["tiempos_ms"].values())


@pytest.mark.asyncio
async def test_async_analysis_is_recorded_when_it_completes(client, db_session):
    headers, _ = await _login(client)
    _, entrega_id = await _problem_with_submission(client, headers)

    res = await client.post("/api/v1/analysis/run?async_mode=true", json={"entrega_id": entrega_id}, headers=headers)
    assert res.status_code == 201
    for _ in range(60):
        await asyncio.sleep(0.05)
        events = await _events(db_session, tipo="analisis")
        if events:
            break
    assert events and events[0].detalle["modo"] == "asincrono"


@pytest.mark.asyncio
async def test_batch_upload_and_each_batch_analysis_are_recorded(client, db_session):
    headers, _ = await _login(client)
    pid, _ = await _problem_with_submission(client, headers)

    res = await client.post(
        "/api/v1/analysis/batch", data={"problema_id": str(pid)}, headers=headers,
        files=[("files", ("a.c", CODE.encode(), "text/plain")), ("files", ("b.c", CODE.encode(), "text/plain")),
               ("files", ("notas.txt", b"x", "text/plain"))],
    )
    assert res.status_code == 202, res.text
    for _ in range(80):
        await asyncio.sleep(0.05)
        modes = [e.detalle["modo"] for e in await _events(db_session, tipo="analisis")]
        if len(modes) == 2:
            break

    [upload] = await _events(db_session, tipo="carga_lote")
    assert upload.detalle["n_archivos"] == 2 and upload.detalle["n_ignorados"] == 1
    assert upload.detalle["bytes"] == 2 * len(CODE.encode())
    assert modes == ["lote", "lote"], [(e.tipo, e.detalle) for e in await _events(db_session)]


@pytest.mark.asyncio
async def test_events_never_contain_code_email_or_name(client, db_session):
    headers, _ = await _login(client)
    _, entrega_id = await _problem_with_submission(client, headers)
    await client.post("/api/v1/analysis/run", json={"entrega_id": entrega_id}, headers=headers)

    dump = repr([(e.tipo, e.ruta, e.detalle) for e in await _events(db_session)])
    for private in ("secreto_unico_xyz", EMAIL, "Nombre Privado", "PasswordSegura123"):
        assert private not in dump


@pytest.mark.asyncio
async def test_a_failing_event_store_never_breaks_the_request(client, db_session, monkeypatch):
    import app.infrastructure.database.session as db_session_module

    def broken_maker():
        raise RuntimeError("events database down")

    monkeypatch.setattr(db_session_module, "async_session_maker", broken_maker)
    headers = {"Authorization": "Bearer nope"}
    res = await client.get("/api/v1/problems/", headers=headers)

    assert res.status_code == 401  # the normal answer, not a 500

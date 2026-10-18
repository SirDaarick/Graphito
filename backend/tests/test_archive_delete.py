import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.infrastructure.database.models import (
    CodigoFuente,
    GrupoProblema,
    LoteAnalisis,
    Problema,
    ReporteAnalisis,
)

P = "/api/v1/problems/"
G = "/api/v1/groups/"
CATALOG = "/api/v1/catalog/"
C_FILE = "23_arbol_binario_recorridos_recursivo.c"


async def _headers(client: AsyncClient, email: str = "prof@escom.ipn.mx") -> dict:
    payload = {"email": email, "password": "PasswordSegura123!", "nombre": "Prof. Prueba"}
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": payload["password"]})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _problem(client, headers, titulo="Ordenamiento") -> int:
    res = await client.post(P, headers=headers, json={"titulo": titulo, "enunciado": "Ordena", "lenguaje": "c"})
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _group(client, headers, codigo="1CM1") -> int:
    res = await client.post(
        G, headers=headers, json={"nombre": "Grupo A", "codigo_grupo": codigo, "periodo": "2026-1"}
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _reference(client, headers, problem_id) -> str:
    res = await client.post(
        f"{P}{problem_id}/references",
        headers=headers,
        params={"autor": "Ref", "contenido": "int main(){return 0;}", "lenguaje": "c"},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _count(db, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


# --- problems: archive / unarchive ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_archive_hides_problem_until_included(client: AsyncClient):
    headers = await _headers(client)
    pid = await _problem(client, headers)

    res = await client.post(f"{P}{pid}/archive", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["archivado"] is True

    assert (await client.get(P, headers=headers)).json() == []
    everything = (await client.get(P, headers=headers, params={"include_archived": True})).json()
    assert [p["id"] for p in everything] == [pid]
    assert everything[0]["archivado"] is True


@pytest.mark.asyncio
async def test_unarchive_restores_problem(client: AsyncClient):
    headers = await _headers(client)
    pid = await _problem(client, headers)
    await client.post(f"{P}{pid}/archive", headers=headers)

    res = await client.post(f"{P}{pid}/unarchive", headers=headers)
    assert res.status_code == 200
    assert res.json()["archivado"] is False
    assert [p["id"] for p in (await client.get(P, headers=headers)).json()] == [pid]


@pytest.mark.asyncio
async def test_new_problem_is_not_archived(client: AsyncClient):
    headers = await _headers(client)
    pid = await _problem(client, headers)
    assert (await client.get(f"{P}{pid}", headers=headers)).json()["archivado"] is False


@pytest.mark.asyncio
async def test_archived_problem_cannot_be_assigned_to_group(client: AsyncClient):
    headers = await _headers(client)
    pid = await _problem(client, headers)
    gid = await _group(client, headers)
    await client.post(f"{P}{pid}/archive", headers=headers)

    res = await client.post(f"{G}{gid}/assign", headers=headers, json={"problema_id": pid})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_problem_actions_are_owner_only(client: AsyncClient):
    owner = await _headers(client, "uno@escom.ipn.mx")
    other = await _headers(client, "dos@escom.ipn.mx")
    pid = await _problem(client, owner)

    for method, url in (
        ("POST", f"{P}{pid}/archive"),
        ("POST", f"{P}{pid}/unarchive"),
        ("DELETE", f"{P}{pid}"),
    ):
        res = await client.request(method, url, headers=other)
        assert res.status_code == 404, (method, url, res.text)
    assert (await client.get(f"{P}{pid}", headers=owner)).status_code == 200


@pytest.mark.asyncio
async def test_problem_actions_require_auth(client: AsyncClient):
    assert (await client.post(f"{P}1/archive")).status_code == 401
    assert (await client.delete(f"{P}1")).status_code == 401


# --- problems: delete -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_problem_cascades(client: AsyncClient, db_session, vector_store):
    headers = await _headers(client)
    pid = await _problem(client, headers)
    gid = await _group(client, headers)
    ref_id = await _reference(client, headers, pid)
    assert (await client.post(f"{G}{gid}/assign", headers=headers, json={"problema_id": pid})).status_code == 201
    sub = await client.post(
        f"{P}{pid}/submissions",
        headers=headers,
        json={"problema_id": pid, "grupo_id": gid, "autor": "Alumno", "contenido": "int x;", "lenguaje": "c"},
    )
    assert sub.status_code == 201, sub.text
    import uuid

    db_session.add(ReporteAnalisis(entrega_id=uuid.UUID(sub.json()["id"]), referencia_id=uuid.UUID(ref_id)))
    db_session.add(LoteAnalisis(problema_id=pid, docente_id=1, grupo_id=gid))
    await db_session.commit()
    assert ref_id in vector_store.store

    res = await client.delete(f"{P}{pid}", headers=headers)
    assert res.status_code == 204, res.text

    assert (await client.get(f"{P}{pid}", headers=headers)).status_code == 404
    for model in (Problema, CodigoFuente, ReporteAnalisis, LoteAnalisis, GrupoProblema):
        assert await _count(db_session, model) == 0, model.__name__
    assert vector_store.store == {}
    assert ref_id in vector_store.deleted
    # The group itself survives.
    assert [g["id"] for g in (await client.get(G, headers=headers)).json()] == [gid]


@pytest.mark.asyncio
async def test_delete_problem_keeps_other_problems(client: AsyncClient, db_session, vector_store):
    headers = await _headers(client)
    keep = await _problem(client, headers, "Se queda")
    drop = await _problem(client, headers, "Se va")
    keep_ref = await _reference(client, headers, keep)
    await _reference(client, headers, drop)

    assert (await client.delete(f"{P}{drop}", headers=headers)).status_code == 204
    assert [p["id"] for p in (await client.get(P, headers=headers)).json()] == [keep]
    assert list(vector_store.store) == [keep_ref]
    assert await _count(db_session, CodigoFuente) == 1


@pytest.mark.asyncio
async def test_delete_problem_aborts_when_vector_store_fails(client: AsyncClient, vector_store):
    headers = await _headers(client)
    pid = await _problem(client, headers)
    await _reference(client, headers, pid)

    vector_store.fail = True
    res = await client.delete(f"{P}{pid}", headers=headers)
    assert res.status_code == 503, res.text
    vector_store.fail = False
    assert (await client.get(f"{P}{pid}", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_catalog_program_can_be_readded_after_delete(client: AsyncClient, vector_store):
    headers = await _headers(client)
    listing = (await client.get(CATALOG, headers=headers)).json()
    entry_id = next(
        p["id"]
        for s in listing
        for u in s["unidades"]
        for p in u["programas"]
        if p["nombre_archivo"] == C_FILE
    )
    first = (await client.post(f"{CATALOG}{entry_id}/use", headers=headers)).json()
    assert (await client.delete(f"{P}{first['id']}", headers=headers)).status_code == 204
    assert vector_store.store == {}

    again = await client.post(f"{CATALOG}{entry_id}/use", headers=headers)
    assert again.status_code == 200, again.text
    assert again.json()["archivado"] is False
    assert len(vector_store.store) == 1
    assert len((await client.get(P, headers=headers)).json()) == 1


@pytest.mark.asyncio
async def test_catalog_use_unarchives_archived_program(client: AsyncClient, vector_store):
    headers = await _headers(client)
    listing = (await client.get(CATALOG, headers=headers)).json()
    entry_id = next(
        p["id"]
        for s in listing
        for u in s["unidades"]
        for p in u["programas"]
        if p["nombre_archivo"] == C_FILE
    )
    first = (await client.post(f"{CATALOG}{entry_id}/use", headers=headers)).json()
    await client.post(f"{P}{first['id']}/archive", headers=headers)

    again = await client.post(f"{CATALOG}{entry_id}/use", headers=headers)
    assert again.status_code == 200, again.text
    assert again.json()["id"] == first["id"]
    assert again.json()["archivado"] is False
    assert len(vector_store.store) == 1


# --- groups ---------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archive_and_unarchive_group(client: AsyncClient):
    headers = await _headers(client)
    gid = await _group(client, headers)

    res = await client.post(f"{G}{gid}/archive", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["archivado"] is True
    assert (await client.get(G, headers=headers)).json() == []
    listed = (await client.get(G, headers=headers, params={"include_archived": True})).json()
    assert [g["id"] for g in listed] == [gid] and listed[0]["archivado"] is True

    res = await client.post(f"{G}{gid}/unarchive", headers=headers)
    assert res.status_code == 200 and res.json()["archivado"] is False
    assert [g["id"] for g in (await client.get(G, headers=headers)).json()] == [gid]


@pytest.mark.asyncio
async def test_group_actions_are_owner_only(client: AsyncClient):
    owner = await _headers(client, "uno@escom.ipn.mx")
    other = await _headers(client, "dos@escom.ipn.mx")
    gid = await _group(client, owner)

    for method, url in (
        ("POST", f"{G}{gid}/archive"),
        ("POST", f"{G}{gid}/unarchive"),
        ("DELETE", f"{G}{gid}"),
    ):
        assert (await client.request(method, url, headers=other)).status_code == 404, (method, url)
    assert (await client.get(f"{G}{gid}", headers=owner)).status_code == 200


@pytest.mark.asyncio
async def test_delete_group_keeps_problems_and_submissions(client: AsyncClient, db_session):
    headers = await _headers(client)
    pid = await _problem(client, headers)
    gid = await _group(client, headers)
    await client.post(f"{G}{gid}/assign", headers=headers, json={"problema_id": pid})
    sub = await client.post(
        f"{P}{pid}/submissions",
        headers=headers,
        json={"problema_id": pid, "grupo_id": gid, "autor": "Alumno", "contenido": "int x;", "lenguaje": "c"},
    )
    assert sub.status_code == 201, sub.text

    assert (await client.delete(f"{G}{gid}", headers=headers)).status_code == 204

    assert (await client.get(f"{G}{gid}", headers=headers)).status_code == 404
    assert await _count(db_session, GrupoProblema) == 0
    assert await _count(db_session, Problema) == 1
    submissions = (await db_session.execute(select(CodigoFuente))).scalars().all()
    assert len(submissions) == 1 and submissions[0].grupo_id is None

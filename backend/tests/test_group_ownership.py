"""A submission can only be attached to a group owned by the calling teacher.

Same rule as batch creation: a group that is not the caller's answers 404 "Grupo {id} no encontrado en tu cuenta."
"""

import pytest
import pytest_asyncio

PASSWORD = "PasswordSegura123!"
CODE = "#include <stdio.h>\nint main(void) {\n    return 0;\n}\n"


async def _login(client, email):
    await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "nombre": "P"})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _group(client, headers, name):
    res = await client.post(
        "/api/v1/groups/", json={"nombre": name, "codigo_grupo": name, "periodo": "2026-1"}, headers=headers
    )
    assert res.status_code in (200, 201), res.text
    return res.json()["id"]


@pytest_asyncio.fixture
async def world(client):
    a = await _login(client, "ga@escom.ipn.mx")
    b = await _login(client, "gb@escom.ipn.mx")
    prob = await client.post("/api/v1/problems/", json={"titulo": "T", "enunciado": "E", "lenguaje": "c"}, headers=a)
    return {
        "a": a,
        "b": b,
        "pid": prob.json()["id"],
        "ga": await _group(client, a, "Grupo A"),
        "gb": await _group(client, b, "Grupo B"),
    }


def _body(pid, grupo_id=None):
    body = {"problema_id": pid, "autor": "Ana", "contenido": CODE, "lenguaje": "c"}
    if grupo_id is not None:
        body["grupo_id"] = grupo_id
    return body


async def _submissions(client, w):
    res = await client.get(f"/api/v1/problems/{w['pid']}/submissions", headers=w["a"])
    return res.json()


@pytest.mark.asyncio
async def test_foreign_group_is_rejected_and_nothing_is_written(client, world):
    w = world
    res = await client.post(
        f"/api/v1/problems/{w['pid']}/submissions", json=_body(w["pid"], w["gb"]), headers=w["a"]
    )
    assert res.status_code == 404, res.text
    assert res.json()["detail"] == f"Grupo {w['gb']} no encontrado en tu cuenta."
    assert await _submissions(client, w) == []
    group_b = await client.get(f"/api/v1/groups/{w['gb']}", headers=w["b"])
    assert group_b.status_code == 200
    assert "Ana" not in group_b.text


@pytest.mark.asyncio
async def test_own_group_and_no_group_still_succeed(client, world):
    w = world
    own = await client.post(
        f"/api/v1/problems/{w['pid']}/submissions", json=_body(w["pid"], w["ga"]), headers=w["a"]
    )
    assert own.status_code == 201, own.text
    assert own.json()["grupo_id"] == w["ga"]
    none = await client.post(f"/api/v1/problems/{w['pid']}/submissions", json=_body(w["pid"]), headers=w["a"])
    assert none.status_code == 201, none.text
    assert none.json()["grupo_id"] is None
    assert len(await _submissions(client, w)) == 2

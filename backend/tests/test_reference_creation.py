"""Embed before commit for references (spec RI1.1, RI1.2; design data flow).

Order: embed -> add row (explicit uuid4) -> flush -> vector store upsert -> commit. An embedding
failure writes nothing; an upsert failure rolls the row back; a commit failure after the upsert
removes the vector again (compensation). A placeholder embedding is never written.
"""

import uuid

import pytest
from sqlalchemy import func, select

from app.application.services.problem_service import ProblemService
from app.domain.errors import InferenceError
from app.infrastructure.database.models import CodigoFuente, Docente, Problema, TipoCodigoEnum
from app.infrastructure.inference import get_inference_engine
from app.infrastructure.inference.stub_engine import StubInferenceEngine
from app.main import app

REF_CODE = "#include <stdio.h>\nint main(void) { int n; scanf(\"%d\", &n); printf(\"%d\\n\", n * 2); return 0; }\n"


class RaisingEmbedder(StubInferenceEngine):
    def __init__(self, reason="gcb_failed"):
        self.reason = reason
        self.calls = 0

    async def extract_semantic_embedding(self, code, lang="c"):
        self.calls += 1
        raise InferenceError(self.reason, "model exploded")


async def _ref_count(db):
    q = select(func.count()).select_from(CodigoFuente).where(CodigoFuente.tipo == TipoCodigoEnum.REFERENCIA)
    return (await db.execute(q)).scalar_one()


async def _api_setup(client):
    await client.post("/api/v1/auth/register", json={"email": "refs@escom.ipn.mx", "password": "PasswordSegura123!", "nombre": "P"})
    login = await client.post("/api/v1/auth/login", json={"email": "refs@escom.ipn.mx", "password": "PasswordSegura123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    prob = await client.post("/api/v1/problems/", json={"titulo": "T", "enunciado": "E", "lenguaje": "c"}, headers=headers)
    return headers, prob.json()["id"]


async def _post_ref(client, headers, problema_id):
    return await client.post(
        f"/api/v1/problems/{problema_id}/references",
        params={"autor": "Docente", "contenido": REF_CODE, "lenguaje": "c"},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_embedder_failure_gives_503_and_writes_nothing(client, db_session, vector_store):
    headers, problema_id = await _api_setup(client)
    engine = RaisingEmbedder()
    app.dependency_overrides[get_inference_engine] = lambda: engine
    res = await _post_ref(client, headers, problema_id)
    assert res.status_code == 503, res.text
    assert res.json()["reason"] == "gcb_failed"
    assert engine.calls == 1
    assert await _ref_count(db_session) == 0
    assert vector_store.upserts == [] and vector_store.store == {}


@pytest.mark.asyncio
async def test_upsert_failure_rolls_back_the_row(client, db_session, vector_store):
    headers, problema_id = await _api_setup(client)
    vector_store.fail = True
    res = await _post_ref(client, headers, problema_id)
    assert res.status_code == 503, res.text
    assert res.json()["reason"] == "vector_store_write_failed"
    assert await _ref_count(db_session) == 0


@pytest.mark.asyncio
async def test_reference_row_and_vector_share_the_id(client, db_session, vector_store):
    headers, problema_id = await _api_setup(client)
    res = await _post_ref(client, headers, problema_id)
    assert res.status_code == 201, res.text
    ref_id = res.json()["id"]
    assert vector_store.upserts == [ref_id]
    assert vector_store.store[ref_id]["metadata"]["problema_id"] == problema_id
    assert await _ref_count(db_session) == 1


async def _service_setup(db_session):
    docente = Docente(email=f"{uuid.uuid4().hex}@x.mx", hashed_password="x", nombre="D")
    db_session.add(docente)
    await db_session.flush()
    problema = Problema(docente_id=docente.id, titulo="T", enunciado="E")
    db_session.add(problema)
    await db_session.commit()
    return docente.id, problema.id


@pytest.mark.asyncio
async def test_commit_failure_after_upsert_compensates(db_session, vector_store, monkeypatch):
    docente_id, problema_id = await _service_setup(db_session)

    async def failing_commit():
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", failing_commit)
    service = ProblemService(db_session, StubInferenceEngine(), vector_store)
    with pytest.raises(RuntimeError):
        await service.add_reference_code(docente_id, problema_id, "Docente", REF_CODE, "c")
    assert len(vector_store.upserts) == 1
    assert vector_store.deleted == vector_store.upserts  # compensation removed the vector
    assert vector_store.store == {}
    monkeypatch.undo()
    assert await _ref_count(db_session) == 0


@pytest.mark.asyncio
async def test_gcb_disabled_stores_row_without_vector(db_session, vector_store):
    docente_id, problema_id = await _service_setup(db_session)
    service = ProblemService(db_session, RaisingEmbedder("gcb_disabled"), vector_store)
    created = await service.add_reference_code(docente_id, problema_id, "Docente", REF_CODE, "c")
    assert created.tipo == TipoCodigoEnum.REFERENCIA
    assert vector_store.upserts == []  # no placeholder vector is ever written
    assert await _ref_count(db_session) == 1

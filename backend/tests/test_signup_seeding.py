"""Sign-up seeding runs after the response; ensure_examples is exclusive per teacher and re-uses the
example embeddings across teachers."""

import asyncio
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.services.example_service import ExampleService
from app.infrastructure.database.models import CodigoFuente, Docente, Grupo, Problema, TipoCodigoEnum
from app.infrastructure.inference.stub_engine import StubInferenceEngine
from app.main import app
from app.presentation.api.v1.endpoints import auth as auth_endpoint

FIXTURE = Path(__file__).parent / "fixtures" / "ejemplo_fixture_test.json"
DOC = json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _small_fixture(monkeypatch):
    monkeypatch.setattr(ExampleService, "DEFAULT_FIXTURE_PATH", FIXTURE)
    monkeypatch.setattr(ExampleService, "_embedding_cache", {})


@pytest.fixture
def seed_on_signup(monkeypatch):
    monkeypatch.setattr(auth_endpoint, "SEED_EXAMPLES_ON_SIGNUP", True)


async def _count(db, model, *where) -> int:
    return (await db.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


async def _new_docente(db, email: str) -> int:
    docente = Docente(email=email, hashed_password="x", nombre="T")
    db.add(docente)
    await db.commit()
    return docente.id


async def _asgi_register(email: str, on_response_sent):
    """Drive the app by hand and call `on_response_sent` the moment the full response was emitted
    (httpx's ASGITransport would wait for background tasks, hiding the difference)."""
    body = json.dumps({"email": email, "password": "PasswordSegura123!", "nombre": "T"}).encode()
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
        "path": "/api/v1/auth/register", "raw_path": b"/api/v1/auth/register", "query_string": b"",
        "headers": [(b"host", b"testserver"), (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode())],
        "client": ("test", 1), "server": ("testserver", 80), "scheme": "http", "root_path": "",
    }
    sent = []
    done = asyncio.Event()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body"):
            done.set()

    task = asyncio.create_task(app(scope, receive, send))
    await done.wait()
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    await on_response_sent(status)
    return task


@pytest.mark.asyncio
async def test_register_responds_before_the_seeding_finishes(client, db_session, seed_on_signup, monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    real = ExampleService.ensure_examples

    async def gated(self, docente_id):
        started.set()
        await release.wait()
        return await real(self, docente_id)

    monkeypatch.setattr(ExampleService, "ensure_examples", gated)
    observed = {}

    async def on_sent(status):
        observed["status"] = status
        observed["group_at_response"] = await _count(db_session, Grupo)

    task = await asyncio.wait_for(_asgi_register("bg@escom.ipn.mx", on_sent), timeout=10)
    assert observed == {"status": 201, "group_at_response": 0}
    await asyncio.wait_for(started.wait(), timeout=10)  # seeding began after the response
    assert not task.done()
    release.set()
    await asyncio.wait_for(task, timeout=30)
    assert await _count(db_session, Grupo, Grupo.es_ejemplo.is_(True)) == 1


@pytest.mark.asyncio
async def test_register_succeeds_when_background_seeding_raises(client, db_session, seed_on_signup, monkeypatch):
    async def boom(self, docente_id):
        raise RuntimeError("seeding exploded")

    monkeypatch.setattr(ExampleService, "ensure_examples", boom)
    res = await client.post(
        "/api/v1/auth/register", json={"email": "boom@escom.ipn.mx", "password": "PasswordSegura123!", "nombre": "T"}
    )
    assert res.status_code == 201, res.text
    assert await _count(db_session, Docente, Docente.email == "boom@escom.ipn.mx") == 1
    assert await _count(db_session, Grupo) == 0


@pytest.mark.asyncio
async def test_register_seeds_the_group_in_the_background(client, db_session, seed_on_signup):
    res = await client.post(
        "/api/v1/auth/register", json={"email": "ok@escom.ipn.mx", "password": "PasswordSegura123!", "nombre": "T"}
    )
    assert res.status_code == 201
    assert await _count(db_session, Grupo, Grupo.es_ejemplo.is_(True)) == 1
    assert await _count(db_session, Problema) == len(DOC["problems"])


@pytest.mark.asyncio
async def test_concurrent_ensure_creates_one_group_and_one_copy_of_each_problem(db_session, client, vector_store):
    docente_id = await _new_docente(db_session, "race@escom.ipn.mx")
    maker = async_sessionmaker(db_session.bind, class_=AsyncSession, expire_on_commit=False)

    async def run():
        async with maker() as session:
            return await ExampleService(session, StubInferenceEngine(), vector_store).ensure_examples(docente_id)

    first, second = await asyncio.gather(run(), run())
    assert first.grupo_id == second.grupo_id
    assert sorted([first.creado, second.creado]) == [False, True]
    assert await _count(db_session, Grupo, Grupo.es_ejemplo.is_(True)) == 1
    assert await _count(db_session, Problema) == len(DOC["problems"])
    assert await _count(db_session, CodigoFuente, CodigoFuente.tipo == TipoCodigoEnum.REFERENCIA) == len(DOC["problems"])


@pytest.mark.asyncio
async def test_second_teacher_reuses_the_cached_embeddings(db_session, client, vector_store):
    class Counting(StubInferenceEngine):
        calls = 0

        async def extract_semantic_embedding(self, code, lang="c"):
            Counting.calls += 1
            return await super().extract_semantic_embedding(code, lang)

    engine = Counting()
    n = len(DOC["problems"])
    for index, email in enumerate(["one@escom.ipn.mx", "two@escom.ipn.mx"]):
        docente_id = await _new_docente(db_session, email)
        await ExampleService(db_session, engine, vector_store).ensure_examples(docente_id)
        assert Counting.calls == n, f"after teacher {index + 1}"
    assert len(vector_store.upserts) == 2 * n  # Chroma still gets one vector per problem

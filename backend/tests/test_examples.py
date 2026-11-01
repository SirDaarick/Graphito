"""The example group "Ejemplo" (spec S1, S6; contracts C1-C3).

Every teacher gets a group with pre-analysed submissions loaded from a frozen fixture. These tests use
their own two-problem fixture (`fixtures/ejemplo_fixture_test.json`, C1 shape) and the in-memory
SQLite, STUB engine and in-memory vector store from conftest.
"""

import inspect
import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.application.services.example_service import ExampleService
from app.application.services.problem_service import ProblemService
from app.application.services.scoring_service import ScoringService
from app.domain.errors import VectorStoreError
from app.domain.scoring import ChannelResult, decide
from app.infrastructure.database.models import (
    CodigoFuente,
    Docente,
    Grupo,
    GrupoProblema,
    IndicadorIntegridad,
    Problema,
    ReporteAnalisis,
    TipoCodigoEnum,
)
from app.infrastructure.inference.stub_engine import StubInferenceEngine
from app.presentation.api.v1.endpoints import auth as auth_endpoint

FIXTURE = Path(__file__).parent / "fixtures" / "ejemplo_fixture_test.json"
DOC = json.loads(FIXTURE.read_text(encoding="utf-8"))
ENSURE = "/api/v1/examples/ensure"
CASOS = ["identical", "similar", "different", "ai"]


@pytest.fixture(autouse=True)
def example_fixture(monkeypatch):
    """Every example service in this module (also the one the app builds) reads the small fixture."""
    monkeypatch.setattr(ExampleService, "DEFAULT_FIXTURE_PATH", FIXTURE)


@pytest.fixture
def seed_on_signup(monkeypatch):
    monkeypatch.setattr(auth_endpoint, "SEED_EXAMPLES_ON_SIGNUP", True)


async def _headers(client: AsyncClient, email: str = "ejemplos@escom.ipn.mx") -> dict:
    payload = {"email": email, "password": "PasswordSegura123!", "nombre": "Prof. Ejemplos"}
    reg = await client.post("/api/v1/auth/register", json=payload)
    assert reg.status_code == 201, reg.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": payload["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _count(db, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def _ensure(client: AsyncClient, headers: dict) -> dict:
    res = await client.post(ENSURE, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.asyncio
async def test_ensure_creates_the_group_with_problems_and_preanalysed_submissions(
    client: AsyncClient, db_session, vector_store
):
    headers = await _headers(client)
    body = await _ensure(client, headers)

    assert body["creado"] is True
    groups = (await db_session.execute(select(Grupo))).scalars().all()
    assert len(groups) == 1
    group = groups[0]
    assert (group.nombre, group.es_ejemplo, group.id) == ("Ejemplo", True, body["grupo_id"])
    assert group.descripcion

    assert [p["titulo"] for p in body["problemas"]] == [p["titulo"] for p in DOC["problems"]]
    assert body["recorrido"]["problema_id"] == body["problemas"][0]["problema_id"]
    assert list(body["recorrido"]["casos"]) == CASOS

    assert await _count(db_session, Problema) == 2
    assert await _count(db_session, GrupoProblema) == 2
    assert await _count(db_session, ReporteAnalisis) == 8
    assert len(vector_store.upserts) == 2  # references go through the normal indexing path

    for fixture_problem in DOC["problems"]:
        problema = (
            await db_session.execute(select(Problema).where(Problema.catalogo_id == f"ejemplo:{fixture_problem['key']}"))
        ).scalar_one()
        assert (problema.titulo, problema.enunciado, problema.lenguaje) == (
            fixture_problem["titulo"], fixture_problem["descripcion"], fixture_problem["lenguaje"],
        )
        reference = (
            await db_session.execute(
                select(CodigoFuente).where(
                    CodigoFuente.problema_id == problema.id, CodigoFuente.tipo == TipoCodigoEnum.REFERENCIA
                )
            )
        ).scalar_one()
        assert reference.contenido == fixture_problem["referencia"]["contenido"]

        assert [e["caso"] for e in fixture_problem["entregas"]] == CASOS
        for fixture_entrega in fixture_problem["entregas"]:
            entrega = (
                await db_session.execute(
                    select(CodigoFuente).where(
                        CodigoFuente.problema_id == problema.id, CodigoFuente.autor == fixture_entrega["autor"]
                    )
                )
            ).scalar_one()
            assert entrega.tipo == TipoCodigoEnum.ENTREGA_ALUMNO
            assert entrega.grupo_id == group.id
            assert entrega.contenido == fixture_entrega["contenido"]
            reporte = (
                await db_session.execute(select(ReporteAnalisis).where(ReporteAnalisis.entrega_id == entrega.id))
            ).scalar_one()

            outcome = fixture_entrega["outcome"]
            a, b = outcome["channel_a"], outcome["channel_b"]
            assert reporte.engine == "real"
            assert reporte.referencia_id == reference.id
            assert reporte.similitud_semantica == round(a["raw"], 4)  # raw Channel A
            assert reporte.puntaje_calibrado_a == round(a["calibrated"], 4)
            assert reporte.probabilidad_ia == round(b["calibrated"], 4)  # calibrated Channel B
            assert (reporte.flag_a, reporte.flag_b) == (a["flag"], b["flag"])
            assert (reporte.umbral_a, reporte.umbral_b) == (a["threshold"], b["threshold"])
            assert reporte.gcb_similarity == outcome["gcb_similarity"]
            assert reporte.manifest_sha == outcome["provenance"]["manifest_sha"]
            assert reporte.dictamen.value == decide(ChannelResult(**a), ChannelResult(**b))

            kinds = {
                i.tipo_alerta
                for i in (
                    await db_session.execute(select(IndicadorIntegridad).where(IndicadorIntegridad.reporte_id == reporte.id))
                ).scalars()
            }
            assert ("CONVERGENCIA_ESTRUCTURAL" in kinds) == a["flag"]
            assert ("PATRON_SINTETICO" in kinds) == b["flag"]


@pytest.mark.asyncio
async def test_second_call_changes_nothing(client: AsyncClient, db_session, vector_store):
    headers = await _headers(client)
    first = await _ensure(client, headers)
    second = await _ensure(client, headers)

    assert first["creado"] is True and second["creado"] is False
    assert {k: v for k, v in second.items() if k != "creado"} == {k: v for k, v in first.items() if k != "creado"}
    assert await _count(db_session, Grupo) == 1
    assert await _count(db_session, Problema) == 2
    assert await _count(db_session, CodigoFuente) == 2 + 8
    assert await _count(db_session, ReporteAnalisis) == 8
    assert len(vector_store.upserts) == 2


@pytest.mark.asyncio
async def test_deleted_group_is_restored_without_duplicating_problems(client: AsyncClient, db_session, vector_store):
    headers = await _headers(client)
    first = await _ensure(client, headers)

    assert (await client.delete(f"/api/v1/groups/{first['grupo_id']}", headers=headers)).status_code == 204
    again = await _ensure(client, headers)

    assert again["creado"] is True
    assert again["problemas"] == first["problemas"]
    assert again["recorrido"] == first["recorrido"]
    assert await _count(db_session, Grupo) == 1
    assert await _count(db_session, Problema) == 2
    assert await _count(db_session, CodigoFuente) == 2 + 8
    assert await _count(db_session, ReporteAnalisis) == 8
    assert len(vector_store.upserts) == 2
    submissions = (
        await db_session.execute(select(CodigoFuente).where(CodigoFuente.tipo == TipoCodigoEnum.ENTREGA_ALUMNO))
    ).scalars().all()
    assert {s.grupo_id for s in submissions} == {again["grupo_id"]}


@pytest.mark.asyncio
async def test_a_deleted_problem_is_recreated_and_the_group_is_kept(client: AsyncClient, db_session):
    headers = await _headers(client)
    first = await _ensure(client, headers)
    gone = first["problemas"][1]["problema_id"]
    assert (await client.delete(f"/api/v1/problems/{gone}", headers=headers)).status_code == 204
    assert await _count(db_session, ReporteAnalisis) == 4

    again = await _ensure(client, headers)

    assert again["creado"] is False
    assert again["grupo_id"] == first["grupo_id"]
    assert again["problemas"][0] == first["problemas"][0]
    assert again["problemas"][1]["titulo"] == first["problemas"][1]["titulo"]
    assert await _count(db_session, Problema) == 2
    assert await _count(db_session, GrupoProblema) == 2
    assert await _count(db_session, ReporteAnalisis) == 8


@pytest.mark.asyncio
async def test_a_failing_reference_leaves_no_partial_rows(db_session, vector_store, monkeypatch):
    docente = Docente(email="falla@escom.ipn.mx", hashed_password="x", nombre="Prof. Falla")
    db_session.add(docente)
    await db_session.commit()
    await db_session.refresh(docente)
    docente_id = docente.id  # the cleanup's rollback expires ORM rows

    original = ProblemService.add_reference_code
    calls = {"n": 0}

    async def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # the first problem is complete by then
            raise VectorStoreError("vector_store_write_failed", "boom")
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(ProblemService, "add_reference_code", flaky)
    service = ExampleService(db_session, StubInferenceEngine(), vector_store)
    with pytest.raises(VectorStoreError):
        await service.ensure_examples(docente_id)

    for model in (Grupo, GrupoProblema, Problema, CodigoFuente, ReporteAnalisis, IndicadorIntegridad):
        assert await _count(db_session, model) == 0, model.__name__
    assert vector_store.store == {}

    monkeypatch.setattr(ProblemService, "add_reference_code", original)  # a retry starts clean
    summary = await service.ensure_examples(docente_id)
    assert summary.creado is True and len(summary.problemas) == 2


@pytest.mark.asyncio
async def test_register_creates_the_example_group(client: AsyncClient, seed_on_signup):
    headers = await _headers(client, "nuevo@escom.ipn.mx")

    groups = (await client.get("/api/v1/groups/", headers=headers)).json()
    assert [(g["nombre"], g["es_ejemplo"]) for g in groups] == [("Ejemplo", True)]
    assert (groups[0]["total_problemas"], groups[0]["total_entregas"]) == (2, 8)

    other = await _headers(client, "otro@escom.ipn.mx")  # each account gets its own group
    other_groups = (await client.get("/api/v1/groups/", headers=other)).json()
    assert [g["id"] for g in other_groups] != [g["id"] for g in groups]


@pytest.mark.asyncio
async def test_register_succeeds_when_seeding_raises(client: AsyncClient, seed_on_signup, monkeypatch, caplog):
    async def boom(self, docente_id):
        raise RuntimeError("seeding exploded")

    monkeypatch.setattr(ExampleService, "ensure_examples", boom)
    headers = await _headers(client, "sinejemplos@escom.ipn.mx")  # asserts 201 and a working login

    assert (await client.get("/api/v1/groups/", headers=headers)).json() == []
    assert "seeding exploded" in caplog.text or "ejemplo" in caplog.text.lower()


@pytest.mark.asyncio
async def test_ensure_requires_authentication(client: AsyncClient):
    assert (await client.post(ENSURE)).status_code == 401


@pytest.mark.asyncio
async def test_report_ids_open_with_es_ejemplo_true(client: AsyncClient):
    headers = await _headers(client)
    body = await _ensure(client, headers)

    first = DOC["problems"][0]
    for entrega in first["entregas"]:
        report_id = body["recorrido"]["casos"][entrega["caso"]]
        res = await client.get(f"/api/v1/analysis/reports/{report_id}", headers=headers)
        assert res.status_code == 200, res.text
        report = res.json()
        assert report["es_ejemplo"] is True
        assert report["engine"] == "real"
        assert report["similitud_semantica"] == round(entrega["outcome"]["channel_a"]["raw"], 4)
        assert report["probabilidad_ia"] == round(entrega["outcome"]["channel_b"]["calibrated"], 4)
        assert report["flag_a"] is entrega["outcome"]["channel_a"]["flag"]
        assert report["flag_b"] is entrega["outcome"]["channel_b"]["flag"]

        code = await client.get(f"/api/v1/analysis/reports/{report_id}/code", headers=headers)
        assert code.status_code == 200, code.text
        assert code.json()["reference_code"] == first["referencia"]["contenido"]


@pytest.mark.asyncio
async def test_group_list_shows_es_ejemplo(client: AsyncClient):
    headers = await _headers(client)
    example = await _ensure(client, headers)
    created = await client.post(
        "/api/v1/groups/",
        json={"nombre": "Mi grupo", "codigo_grupo": "1CM1", "periodo": "2026-1"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["es_ejemplo"] is False

    groups = (await client.get("/api/v1/groups/", headers=headers)).json()
    flags = {g["nombre"]: g["es_ejemplo"] for g in groups}
    assert flags == {"Ejemplo": True, "Mi grupo": False}

    detail = (await client.get(f"/api/v1/groups/{example['grupo_id']}", headers=headers)).json()
    assert detail["es_ejemplo"] is True


# --- behaviour that must not change ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_normal_analysis_run_still_persists_report_and_indicators(client: AsyncClient, db_session):
    assert isinstance(inspect.getattr_static(ScoringService, "persist"), staticmethod)

    headers = await _headers(client, "normal@escom.ipn.mx")
    problem = (
        await client.post(
            "/api/v1/problems/", json={"titulo": "Suma", "enunciado": "Sumar.", "lenguaje": "c"}, headers=headers
        )
    ).json()
    code = DOC["problems"][0]["referencia"]["contenido"]
    ref = await client.post(
        f"/api/v1/problems/{problem['id']}/references",
        params={"autor": "Docente", "contenido": code, "lenguaje": "c"},
        headers=headers,
    )
    assert ref.status_code == 201, ref.text
    sub = await client.post(
        f"/api/v1/problems/{problem['id']}/submissions",
        json={"problema_id": problem["id"], "autor": "Alumno", "contenido": code, "lenguaje": "c"},
        headers=headers,
    )
    assert sub.status_code == 201, sub.text

    run = await client.post("/api/v1/analysis/run", json={"entrega_id": sub.json()["id"]}, headers=headers)
    assert run.status_code == 201, run.text
    report = run.json()
    assert report["estado"] == "COMPLETADO"
    assert report["engine"] == "stub"
    assert report["es_ejemplo"] is False
    assert report["dictamen"] is not None
    assert report["indicadores"], "decision or XAI indicator rows are persisted with the report"

    fetched = (await client.get(f"/api/v1/analysis/reports/{report['id']}", headers=headers)).json()
    assert fetched["es_ejemplo"] is False
    assert fetched["indicadores"] == report["indicadores"]


# --- backfill script ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_script_backfills_every_teacher_once(db_session, vector_store):
    import importlib.util

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    script = Path(__file__).resolve().parents[2] / "scripts" / "seed_examples.py"
    spec = importlib.util.spec_from_file_location("seed_examples", script)
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)

    for email in ("uno@escom.ipn.mx", "dos@escom.ipn.mx"):
        db_session.add(Docente(email=email, hashed_password="x", nombre="Prof."))
    await db_session.commit()
    maker = async_sessionmaker(db_session.bind, class_=AsyncSession, expire_on_commit=False)

    first = await seed.seed_all(maker, StubInferenceEngine(), vector_store, fixture_path=FIXTURE)
    assert [(email, status) for _, email, status in first] == [
        ("uno@escom.ipn.mx", "created"), ("dos@escom.ipn.mx", "created"),
    ]
    assert seed.exit_code(first) == 0
    second = await seed.seed_all(maker, StubInferenceEngine(), vector_store, fixture_path=FIXTURE)
    assert {status for _, _, status in second} == {"skipped"}
    assert await _count(db_session, Grupo) == 2
    assert await _count(db_session, Problema) == 4
    assert await _count(db_session, ReporteAnalisis) == 16

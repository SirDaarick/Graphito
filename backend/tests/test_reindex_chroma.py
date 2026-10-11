"""`scripts/reindex_references.py --mode gcb-v2` (spec RI2.2, RI2.3).

References are read from the database (SQLite here), embedded with the injected engine and upserted
into the fingerprinted collection through the real adapter over a fake Chroma client. Reruns are
idempotent, legacy collections are untouched, and any failure gives a non-zero exit code.
"""

import importlib.util
import uuid
from pathlib import Path

import pytest

from app.domain.errors import InferenceError
from app.infrastructure.database.models import CodigoFuente, Docente, Problema, TipoCodigoEnum
from app.infrastructure.inference.stub_engine import StubInferenceEngine
from app.infrastructure.vector_store.chroma_adapter import (
    LEGACY_COLLECTIONS,
    ChromaVectorStoreAdapter,
    collection_name_for_engine,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_vector_store import FakeClient, FakeCollection

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "reindex_references.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("reindex_references", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reindex = _load_script()


class FlakyEngine(StubInferenceEngine):
    """Fails to embed one given code."""

    def __init__(self, bad_code):
        self.bad_code = bad_code

    async def extract_semantic_embedding(self, code, lang="c"):
        if code == self.bad_code:
            raise InferenceError("gcb_failed", "boom")
        return await super().extract_semantic_embedding(code, lang)


async def _seed(db_session, n=3):
    docente = Docente(email=f"{uuid.uuid4().hex}@x.mx", hashed_password="x", nombre="D")
    db_session.add(docente)
    await db_session.flush()
    problema = Problema(docente_id=docente.id, titulo="T", enunciado="E")
    db_session.add(problema)
    await db_session.flush()
    refs = [
        CodigoFuente(problema_id=problema.id, tipo=TipoCodigoEnum.REFERENCIA, autor=f"R{i}",
                     contenido=f"int main(void) {{ return {i}; }}", lenguaje="c")
        for i in range(n)
    ]
    db_session.add_all(refs)
    db_session.add(CodigoFuente(problema_id=problema.id, tipo=TipoCodigoEnum.ENTREGA_ALUMNO, autor="S",
                                contenido="int main(void) { return 9; }", lenguaje="c"))
    await db_session.commit()
    return [str(r.id) for r in refs]


def _maker(db_session):
    return async_sessionmaker(db_session.bind, class_=AsyncSession, expire_on_commit=False)


def _legacy():
    return [FakeCollection(n, {"old": {"embedding": [0.1] * 769, "metadata": {"problema_id": 1}}}) for n in LEGACY_COLLECTIONS]


@pytest.mark.asyncio
async def test_apply_is_idempotent_and_leaves_legacy_untouched(db_session):
    ids = await _seed(db_session)
    engine = StubInferenceEngine()
    legacy = _legacy()
    client = FakeClient(legacy)
    store = ChromaVectorStoreAdapter(collection_name_for_engine(engine), client=client)

    first = await reindex.reindex_references(_maker(db_session), engine, store, apply=True)
    second = await reindex.reindex_references(_maker(db_session), engine, store, apply=True)

    target = client.collections[collection_name_for_engine(engine)]
    assert first.total == second.total == 3 and first.indexed == second.indexed == 3
    assert first.failures == [] and reindex.exit_code(first) == 0
    assert sorted(target.records) == sorted(ids)  # only references, same ids on rerun
    assert all(len(c.records) == 1 for c in legacy)
    assert set(client.opened) == {collection_name_for_engine(engine)}


@pytest.mark.asyncio
async def test_dry_run_writes_nothing(db_session):
    await _seed(db_session)
    engine = StubInferenceEngine()
    client = FakeClient()
    store = ChromaVectorStoreAdapter(collection_name_for_engine(engine), client=client)
    report = await reindex.reindex_references(_maker(db_session), engine, store, apply=False)
    assert report.dry_run and report.total == 3 and report.indexed == 0
    assert client.collections[collection_name_for_engine(engine)].records == {}
    assert reindex.exit_code(report) == 0


@pytest.mark.asyncio
async def test_any_failure_is_reported_with_non_zero_exit(db_session):
    await _seed(db_session)
    engine = FlakyEngine("int main(void) { return 1; }")
    store = ChromaVectorStoreAdapter(collection_name_for_engine(engine), client=FakeClient())
    report = await reindex.reindex_references(_maker(db_session), engine, store, apply=True)
    assert report.indexed == 2 and len(report.failures) == 1
    assert report.failures[0][1] == "gcb_failed"
    assert reindex.exit_code(report) != 0


def test_cli_refuses_a_not_ready_runtime(monkeypatch, capsys):
    from app.infrastructure.inference.runtime import InferenceRuntime

    not_ready = InferenceRuntime(mode="REAL", engine_label="real", ready=False, reason="sha_mismatch")
    code = reindex.run(["--mode", "gcb-v2", "--apply"], runtime=not_ready)
    assert code == 2
    assert "sha_mismatch" in capsys.readouterr().err


def test_cli_only_offers_gcb_v2_mode():
    with pytest.raises(SystemExit):
        reindex.run(["--mode", "slice"])

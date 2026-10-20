"""GraphCodeBERT `v2_norm`: identifiers are canonicalized once, inside the REAL engine, before embedding.

Model loading is replaced by fake factories (no torch, no weights). Policy for code the canonicalizer
cannot handle: if it raises, the file is embedded RAW and the fallback is recorded (the
`CANONICALIZATION_FALLBACK` context flag, then `gcb_estado == "OK_SIN_NORM"`); it never fails the request.
Unparsable regions are left untouched by the canonicalizer itself (it skips ERROR subtrees).
"""

import asyncio
import hashlib
import importlib.util
from pathlib import Path

import pytest

from app.application.services.scoring_service import GCB_OK_RAW, ScoringService
from app.domain.errors import InferenceError
from app.domain.ports.inference_port import CANONICALIZATION_FALLBACK
from app.infrastructure.artifacts import load_bundle
from app.infrastructure.inference.real_engine import (
    CANONICALIZATION_VERSION,
    RealBimodalInferenceEngine,
    pipeline_fingerprint,
)
from app.infrastructure.inference.stub_engine import StubInferenceEngine
from app.infrastructure.vector_store.chroma_adapter import collection_name_for_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_inference_engines import FAKE_GCB_FIELDS, FakeCharCNN, _settings, fake_gcb_fingerprint
from test_reindex_chroma import _maker, _seed
from test_vector_store import FakeClient

OLD_COLLECTION = "gcb_v2_mean_359032419bac"
CODE_A = "int total(int items) { int acc = 0; for (int k = 0; k < items; k++) acc += k; return acc; }\n"
CODE_B = "int sumUp(int count) { int result = 0; for (int idx = 0; idx < count; idx++) result += idx; return result; }\n"


class SpyGCB:
    """Records the code it is asked to embed."""

    def __init__(self, kwargs):
        self.kwargs = kwargs
        self.seen = []

    def predict_code(self, code, language="c"):
        self.seen.append(code)
        return {"success": True, "embedding": [0.5] * 768, "input_version": "v2", "pooling": "mean"}


def _engine(fake_artifacts, spy, **kwargs):
    return RealBimodalInferenceEngine(
        load_bundle(fake_artifacts.manifest),
        _settings(fake_artifacts),
        charcnn_factory=lambda path: FakeCharCNN(),
        gcb_factory=lambda cfg: spy,
        **kwargs,
    )


# --- (a) canonicalization on both sides, one place ---------------------------------------------


@pytest.mark.asyncio
async def test_default_canonicalizer_renames_identifiers_before_embedding(fake_artifacts):
    spy = SpyGCB({})
    engine = _engine(fake_artifacts, spy)
    await engine.extract_semantic_embedding(CODE_A)
    await engine.extract_semantic_embedding(CODE_B)
    assert spy.seen[0] == spy.seen[1]  # same structure, different names: identical canonical input
    assert "total" not in spy.seen[0] and "acc" not in spy.seen[0]
    assert "f1" in spy.seen[0] and "v1" in spy.seen[0]


@pytest.mark.asyncio
async def test_injected_canonicalizer_is_used_for_every_embedding(fake_artifacts):
    spy = SpyGCB({})
    engine = _engine(fake_artifacts, spy, canonicalizer=lambda code, lang: f"CANON[{lang}]:{code}")
    await engine.extract_semantic_embedding("int a;", lang="cpp")
    assert spy.seen == ["CANON[cpp]:int a;"]


@pytest.mark.asyncio
async def test_references_are_indexed_through_the_same_canonicalization(fake_artifacts, db_session):
    """The reindex script embeds through the engine, so references get the same canonical input."""
    from app.infrastructure.vector_store.chroma_adapter import ChromaVectorStoreAdapter

    spec = importlib.util.spec_from_file_location(
        "reindex_references", Path(__file__).resolve().parents[2] / "scripts" / "reindex_references.py"
    )
    reindex = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reindex)

    await _seed(db_session, n=2)
    spy = SpyGCB({})
    engine = _engine(fake_artifacts, spy, canonicalizer=lambda code, lang: "CANON:" + code)
    store = ChromaVectorStoreAdapter(collection_name_for_engine(engine), client=FakeClient())
    report = await reindex.reindex_references(_maker(db_session), engine, store, apply=True)
    assert report.indexed == 2 and report.failures == []
    assert spy.seen and all(code.startswith("CANON:") for code in spy.seen)


# --- (b) fingerprint and collection name -------------------------------------------------------


def test_fingerprint_includes_canonicalization_and_changes_collection(fake_artifacts):
    engine = _engine(fake_artifacts, SpyGCB({}))
    base = fake_gcb_fingerprint(FAKE_GCB_FIELDS)
    assert engine.embedding_fingerprint != base
    assert engine.embedding_fingerprint == pipeline_fingerprint(base, CANONICALIZATION_VERSION)
    assert pipeline_fingerprint(base, "identifiers_v2") != engine.embedding_fingerprint
    name = collection_name_for_engine(engine)
    assert name == f"gcb_v2_mean_{engine.embedding_fingerprint[:12]}"
    assert name != f"gcb_v2_mean_{base[:12]}"
    assert engine.model_versions["gcb_canonicalization"] == CANONICALIZATION_VERSION == "identifiers_v1"
    assert engine.model_versions["gcb_input_version"] == "v2"


def test_manifest_fingerprint_is_still_verified_on_the_base_fields(fake_artifacts):
    doc = fake_artifacts.read()
    doc["gcb"]["fingerprint"] = hashlib.sha256(b"other").hexdigest()
    fake_artifacts.write(doc)
    with pytest.raises(InferenceError) as exc:
        _engine(fake_artifacts, SpyGCB({}))
    assert exc.value.reason == "gcb_fingerprint_mismatch"


def test_disabled_gcb_reports_no_canonicalization(fake_artifacts):
    engine = RealBimodalInferenceEngine(
        load_bundle(fake_artifacts.manifest),
        _settings(fake_artifacts, GCB_SECONDARY_ENABLED=False),
        charcnn_factory=lambda path: FakeCharCNN(),
    )
    assert engine.model_versions["gcb_canonicalization"] is None


# --- (c) single equals batch --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_and_sequential_embeddings_see_identical_input(fake_artifacts):
    spy = SpyGCB({})
    engine = _engine(fake_artifacts, spy)
    single = [await engine.extract_semantic_embedding(c) for c in (CODE_A, CODE_B)]
    seen_single = list(spy.seen)
    spy.seen.clear()
    batch = await asyncio.gather(*(engine.extract_semantic_embedding(c) for c in (CODE_A, CODE_B)))
    assert single == list(batch)
    assert sorted(spy.seen) == sorted(seen_single)


# --- (e) STUB is unchanged ----------------------------------------------------------------------


def test_stub_fingerprint_and_collection_name_are_unchanged():
    engine = StubInferenceEngine()
    expected = hashlib.sha256(b'{"engine":"stub","dims":768,"version":1}').hexdigest()
    assert engine.embedding_fingerprint == expected
    assert collection_name_for_engine(engine) == f"stub_{expected[:12]}"
    assert not hasattr(engine, "model_versions") or "gcb_canonicalization" not in (engine.model_versions or {})


# --- (f) failures and unparsable code -----------------------------------------------------------


@pytest.mark.asyncio
async def test_canonicalizer_failure_falls_back_to_raw_code_and_flags_it(fake_artifacts):
    spy = SpyGCB({})

    def boom(code, lang):
        raise RuntimeError("parser exploded")

    engine = _engine(fake_artifacts, spy, canonicalizer=boom)
    CANONICALIZATION_FALLBACK.set(False)
    await engine.extract_semantic_embedding(CODE_A)
    assert spy.seen == [CODE_A]
    assert CANONICALIZATION_FALLBACK.get() is True
    CANONICALIZATION_FALLBACK.set(False)
    ok_engine = _engine(fake_artifacts, SpyGCB({}), canonicalizer=lambda code, lang: code)
    await ok_engine.extract_semantic_embedding(CODE_A)
    assert CANONICALIZATION_FALLBACK.get() is False


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["", "int main( {{{ ;;; )) @@", "int x = ;\nvoid f( { int y = 1; }\n", "\x00\xff garbage"])
async def test_unparsable_code_never_crashes_the_embedding(fake_artifacts, code):
    spy = SpyGCB({})
    engine = _engine(fake_artifacts, spy)
    vector = await engine.extract_semantic_embedding(code)
    assert len(vector) == 768 and len(spy.seen) == 1


class _Store:
    async def query_nearest(self, embedding, problema_id, top_k):
        return [{"similarity": 0.9}]


@pytest.mark.asyncio
async def test_scoring_marks_raw_fallback_in_the_gcb_state(fake_artifacts):
    def boom(code, lang):
        raise RuntimeError("parser exploded")

    service = ScoringService(_engine(fake_artifacts, SpyGCB({}), canonicalizer=boom), None, _Store(), None)
    assert await service._gcb(CODE_A, "c", 1, True) == (0.9, GCB_OK_RAW)
    service = ScoringService(_engine(fake_artifacts, SpyGCB({})), None, _Store(), None)
    assert await service._gcb(CODE_A, "c", 1, True) == (0.9, "OK")

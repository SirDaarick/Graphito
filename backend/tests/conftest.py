import os
import sys
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Agregar backend al sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.main import app
from app.infrastructure.database.session import Base, get_db
from app.infrastructure.database.models import *  # ensure all models registered
from app.infrastructure.inference import get_inference_engine
from app.infrastructure.inference.stub_engine import StubInferenceEngine
from app.infrastructure.vector_store import get_vector_store
from app.domain.ports.vector_store_port import VectorStorePort


from app.domain.errors import VectorStoreError


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


# In-memory vector store for isolated tests: real cosine similarity (non-constant, spec RI3), strict
# errors like the Chroma adapter, and a `fail` switch that makes every call raise.
class InMemoryVectorStore(VectorStorePort):
    EXPECTED_DIM = 768

    def __init__(self):
        self.store = {}
        self.reset()

    def reset(self):
        self.store.clear()
        self.last_upsert_embedding = None
        self.last_query_embedding = None
        self.fail = False
        self.upserts = []
        self.queries = []
        self.deleted = []

    def _maybe_fail(self, op):
        if self.fail:
            raise VectorStoreError(f"vector_store_{op}_failed", "in-memory store switched to fail")

    async def upsert_reference(self, reference_id: str, embedding: list, metadata: dict, document=None):
        self._maybe_fail("write")
        self.last_upsert_embedding = list(embedding)
        assert len(embedding) == self.EXPECTED_DIM, (
            f"vector store received a {len(embedding)}-dim embedding, expected {self.EXPECTED_DIM}"
        )
        self.upserts.append(reference_id)
        self.store[reference_id] = {
            "embedding": list(embedding),
            "metadata": metadata,
            "document": document,
        }
        return True

    async def query_nearest(self, embedding: list, problema_id: int, top_k: int = 1):
        self.queries.append(problema_id)
        self._maybe_fail("query")
        self.last_query_embedding = list(embedding)
        assert len(embedding) == self.EXPECTED_DIM, (
            f"vector store queried with a {len(embedding)}-dim embedding, expected {self.EXPECTED_DIM}"
        )
        results = []
        for ref_id, data in self.store.items():
            if data["metadata"].get("problema_id") == problema_id:
                sim = max(0.0, min(1.0, _cosine(embedding, data["embedding"])))
                results.append({
                    "reference_id": ref_id,
                    "similarity": round(sim, 4),
                    "distance": round(1.0 - sim, 4),
                    "metadata": data["metadata"],
                })
        results.sort(key=lambda r: (-r["similarity"], r["reference_id"]))
        return results[:top_k]

    async def delete_reference(self, reference_id: str):
        self._maybe_fail("delete")
        self.deleted.append(reference_id)
        self.store.pop(reference_id, None)
        return True


test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    future=True,
)
test_session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
test_vector_store = InMemoryVectorStore()
test_inference_engine = StubInferenceEngine()


@pytest.fixture
def vector_store() -> InMemoryVectorStore:
    """The shared in-memory store injected into the app by the `client` fixture."""
    test_vector_store.reset()
    return test_vector_store


@pytest_asyncio.fixture(scope="function")
async def db_session()-> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_maker() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    def override_inference():
        return test_inference_engine

    def override_vector_store():
        return test_vector_store

    test_vector_store.reset()

    import app.infrastructure.database.session as db_session_module
    orig_maker = db_session_module.async_session_maker
    db_session_module.async_session_maker = test_session_maker

    # A ready STUB runtime, whatever INFERENCE_MODE a local .env sets (the lifespan does not run
    # under ASGITransport). Readiness tests swap it for a degraded one.
    from app.config import Settings
    from app.infrastructure.inference import runtime as inference_runtime
    orig_runtime = inference_runtime.get_runtime()
    inference_runtime.set_runtime(inference_runtime.build_runtime(Settings(_env_file=None, INFERENCE_MODE="STUB")))

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_inference_engine] = override_inference
    app.dependency_overrides[get_vector_store] = override_vector_store

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c

    app.dependency_overrides.clear()
    db_session_module.async_session_maker = orig_maker
    inference_runtime.set_runtime(orig_runtime)


# --- deploy artifacts (graphito.deploy-manifest/v1) ---------------------------------------------
# Tiny fake bundle: isotonic and Platt calibrations that pass `graphito.calibration/v1`, fake
# checkpoint bytes and a manifest carrying their real sha256. No real weights are involved.

import hashlib as _hashlib
import json as _json
from dataclasses import dataclass as _dataclass
from pathlib import Path as _Path

FAKE_SPLIT_SHA = "e" * 64
FAKE_CHECKPOINT_BYTES = b"fake-charcnn-v2-checkpoint"


FAKE_GCB_FIELDS = {
    "model_name": "microsoft/graphcodebert-base", "model_revision": "2b0488a7bb0eefc7041f1bb2cad1ab26b0da269d",
    "input_version": "v2", "walker_version": "c-cpp-2", "pooling": "mean", "use_dfg": True,
    "code_length": 384, "data_flow_length": 128, "max_windows": 16, "dtype": "float32",
}


def fake_gcb_fingerprint(fields):
    # Same canonical JSON as scripts/build_deploy_artifacts.py:gcb_fingerprint (design D12).
    canonical = _json.dumps({k: fields.get(k) for k in FAKE_GCB_FIELDS}, sort_keys=True, separators=(",", ":"))
    return _hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _fake_threshold(target, threshold):
    return {
        "target_fpr": target, "threshold": threshold,
        "achieved_fpr": None if threshold is None else target / 2, "tpr": None if threshold is None else 0.9,
        "n_neg": 1000, "n_pos": 50, "min_negatives": int(10 / target), "low_support": False,
        "unachievable": threshold is None, "reason": "no_threshold_meets_target" if threshold is None else None,
    }


def fake_calibration(method, params, thresholds, channel):
    return {
        "schema": "graphito.calibration/v1", "channel": channel, "score_name": f"{channel}_raw",
        "method": method, "params": params, "space": "calibrated",
        "thresholds": {f"fpr_{t:g}": _fake_threshold(t, thr) for t, thr in thresholds},
        "primary": f"fpr_{thresholds[0][0]:g}",
        "fit_set": {"split": "val", "n": 1050, "n_pos": 50, "n_neg": 1000, "ids_labels_sha256": "0" * 64},
        "manifest": {"path": "data/splits/split_v1.json.gz", "sha256": FAKE_SPLIT_SHA},
        "seed": 42, "provenance": {"git_sha": "unknown", "dirty": False, "seed": 42},
    }


@_dataclass
class FakeArtifacts:
    root: _Path

    @property
    def manifest(self) -> _Path:
        return self.root / "manifest.json"

    def read(self) -> dict:
        return _json.loads(self.manifest.read_text(encoding="utf-8"))

    def write(self, doc: dict) -> None:
        self.manifest.write_text(_json.dumps(doc, indent=2), encoding="utf-8")

    def write_file(self, rel: str, data: bytes, *, update_manifest: bool = True) -> None:
        """Write an artifact; by default also record its new sha256 in the manifest."""
        (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / rel).write_bytes(data)
        if update_manifest:
            doc = self.read()
            doc["files"][rel] = _hashlib.sha256(data).hexdigest()
            self.write(doc)


def build_fake_artifacts(root: _Path) -> FakeArtifacts:
    files = {
        "channel_a/calibration.json": _json.dumps(fake_calibration(
            "isotonic", {"x": [0.0, 0.5, 1.0], "y": [0.0, 0.25, 1.0]}, [(0.05, 0.5), (0.01, None)], "jaccard",
        )).encode("utf-8"),
        "channel_b/calibration.json": _json.dumps(fake_calibration(
            "platt", {"a": 1.0, "b": 0.0, "eps": 1e-7}, [(0.05, 0.05), (0.01, 0.1715)], "char_cnn",
        )).encode("utf-8"),
        "channel_b/best.pth": FAKE_CHECKPOINT_BYTES,
    }
    for rel, data in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    doc = {
        "schema": "graphito.deploy-manifest/v1",
        "build": {"script": "scripts/build_deploy_artifacts.py", "git_sha": "unknown", "dirty": False},
        "split_manifest_sha256": FAKE_SPLIT_SHA,
        "label": "not validated against reference-derived plagiarism",
        "files": {rel: _hashlib.sha256(data).hexdigest() for rel, data in files.items()},
        "channel_a": {"method": "jaccard", "shingle_k": 5, "calibration": "channel_a/calibration.json",
                      "calibration_method": "isotonic", "threshold_key": "fpr_0.05", "threshold": 0.5,
                      "source_run": "graphcodebert/fake"},
        "channel_b": {"method": "charcnn_v2", "checkpoint": "channel_b/best.pth",
                      "calibration": "channel_b/calibration.json", "calibration_method": "platt",
                      "threshold_key": "fpr_0.01", "threshold": 0.1715, "source_run": "char_cnn/fake"},
        "gcb": {"role": "secondary_non_deciding", **FAKE_GCB_FIELDS,
                "fingerprint": fake_gcb_fingerprint(FAKE_GCB_FIELDS), "source_run": "graphcodebert/fake"},
    }
    fake = FakeArtifacts(root)
    fake.write(doc)
    return fake


@pytest.fixture
def fake_artifacts(tmp_path) -> FakeArtifacts:
    """A valid deploy bundle in a tmp dir (see `build_fake_artifacts`)."""
    return build_fake_artifacts(tmp_path / "deploy")


# --- PDF text (spec AR3.2) ------------------------------------------------------------------------

import base64 as _base64
import re as _re
import zlib as _zlib


def pdf_text(data: bytes) -> str:
    """The text drawn by a reportlab PDF: inflate every content stream and join its `(...) Tj`
    strings with single spaces (no PDF library needed)."""
    fragments = []
    for match in _re.finditer(rb"stream\r?\n(.*?)endstream", data, _re.S):
        raw = match.group(1).strip()
        if raw.endswith(b"~>"):
            raw = _base64.a85decode(raw[:-2].replace(b"\n", b"").replace(b"\r", b""))
        try:
            raw = _zlib.decompress(raw)
        except _zlib.error:
            pass
        fragments.extend(_re.findall(rb"\(((?:[^()\\]|\\.)*)\)\s*Tj", raw, _re.S))
    text = " ".join(f.decode("latin-1").replace("\\(", "(").replace("\\)", ")") for f in fragments)
    return " ".join(text.split())


@pytest.fixture(name="pdf_text")
def pdf_text_fixture():
    """`pdf_text` as a fixture (a module import of conftest would clash with the root tests/)."""
    return pdf_text

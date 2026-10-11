"""Readiness and fail-closed 503 (spec AS6.2-AS6.4, AS7.1; design D5).

REAL mode with a corrupted artifact starts degraded: `/health` explains it with a path-free reason
code, and scoring/indexing endpoints return 503 before anything is written to the database or
the vector store.
"""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.config import Settings
from app.domain.errors import NotReadyError
from app.infrastructure.database.models import CodigoFuente, ReporteAnalisis
from app.infrastructure.inference import get_inference_engine, runtime as rt
from app.infrastructure.inference.stub_engine import StubInferenceEngine

REF_CODE = "#include <stdio.h>\nint main() { int n; scanf(\"%d\", &n); printf(\"%d\\n\", n * 2); return 0; }\n"
STUDENT_CODE = "#include <stdio.h>\nint main() { int x; scanf(\"%d\", &x); printf(\"%d\\n\", x + x); return 0; }\n"


def _real_settings(fake_artifacts, **overrides):
    root = fake_artifacts.root
    return Settings(
        _env_file=None,
        INFERENCE_MODE="REAL",
        DEPLOY_MANIFEST=str(fake_artifacts.manifest),
        CHANNEL_A_CALIBRATION=str(root / "channel_a" / "calibration.json"),
        CHARCNN_CALIBRATION=str(root / "channel_b" / "calibration.json"),
        CHARCNN_CHECKPOINT=str(root / "channel_b" / "best.pth"),
        **overrides,
    )


def _corrupted_runtime(fake_artifacts):
    fake_artifacts.write_file("channel_b/best.pth", b"tampered", update_manifest=False)
    built = []
    runtime = rt.build_runtime(_real_settings(fake_artifacts), engine_factory=lambda s, b: built.append(1))
    assert built == [], "the engine must not be constructed when the artifacts fail"
    return runtime


def test_stub_runtime_is_ready_without_artifacts():
    runtime = rt.build_runtime(Settings(_env_file=None, INFERENCE_MODE="STUB", DEPLOY_MANIFEST="nope/manifest.json"))
    assert runtime.ready and runtime.engine_label == "stub"
    assert isinstance(runtime.engine, StubInferenceEngine)
    assert runtime.calibration.engine == "stub"
    assert runtime.health()["calibration_state"] == "stub"


def test_corrupted_artifact_gives_not_ready_with_reason(fake_artifacts):
    runtime = _corrupted_runtime(fake_artifacts)
    assert not runtime.ready
    assert runtime.engine is None and runtime.calibration is None
    assert runtime.engine_label == "real" and runtime.reason == "sha_mismatch"


def test_unknown_mode_is_not_ready_and_never_stub():
    runtime = rt.build_runtime(Settings(_env_file=None, INFERENCE_MODE="MAYBE"))
    assert not runtime.ready and runtime.reason == "unknown_inference_mode" and runtime.engine is None


def test_real_runtime_ready_with_injected_engine(fake_artifacts):
    engine = StubInferenceEngine()
    runtime = rt.build_runtime(_real_settings(fake_artifacts), engine_factory=lambda s, b: engine)
    assert runtime.ready and runtime.engine is engine and runtime.engine_label == "real"
    health = runtime.health()
    assert health["inference_ready"] is True and health["calibration_state"] == "calibrated"
    assert health["artifacts"]["channel_b"]["threshold"] == 0.1715
    assert health["artifacts"]["manifest_sha256"] == runtime.calibration.manifest_sha256


def test_engine_factory_failure_is_not_ready(fake_artifacts):
    def boom(settings, bundle):
        raise RuntimeError("no weights at C:/secret/path.pth")

    runtime = rt.build_runtime(_real_settings(fake_artifacts), engine_factory=boom)
    assert not runtime.ready and runtime.reason == "engine_init_failed"
    assert "secret" not in json.dumps(runtime.health())


class _ClosableEngine(StubInferenceEngine):
    """An engine whose readiness is scripted; records `close()` (its inference pool shutdown)."""

    def __init__(self, readiness):
        self._readiness = readiness
        self.closed = 0

    def readiness(self):
        if isinstance(self._readiness, Exception):
            raise self._readiness
        return self._readiness

    def close(self):
        self.closed += 1


def test_engine_readiness_raising_is_not_ready_and_closes_engine(fake_artifacts):
    engine = _ClosableEngine(RuntimeError("probe failed at C:/secret/model"))
    runtime = rt.build_runtime(_real_settings(fake_artifacts), engine_factory=lambda s, b: engine)
    assert not runtime.ready and runtime.reason == "engine_readiness_failed"
    assert runtime.engine is None and engine.closed == 1
    assert "secret" not in json.dumps(runtime.health())


def test_engine_not_ready_is_discarded_and_closed(fake_artifacts):
    from app.domain.ports.inference_port import Readiness

    engine = _ClosableEngine(Readiness(ready=False, reason="gcb_load_failed"))
    runtime = rt.build_runtime(_real_settings(fake_artifacts), engine_factory=lambda s, b: engine)
    assert not runtime.ready and runtime.reason == "gcb_load_failed"
    assert runtime.engine is None and engine.closed == 1


def test_ready_engine_is_kept_open(fake_artifacts):
    from app.domain.ports.inference_port import Readiness

    engine = _ClosableEngine(Readiness(ready=True))
    runtime = rt.build_runtime(_real_settings(fake_artifacts), engine_factory=lambda s, b: engine)
    assert runtime.ready and runtime.engine is engine and engine.closed == 0


def test_get_inference_engine_raises_when_not_ready(fake_artifacts, monkeypatch):
    monkeypatch.setattr(rt, "_runtime", _corrupted_runtime(fake_artifacts))
    with pytest.raises(NotReadyError) as exc:
        get_inference_engine()
    assert exc.value.reason == "sha_mismatch"


async def _setup(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={"email": "ready@escom.ipn.mx", "password": "PasswordSegura123!", "nombre": "P"})
    login = await client.post("/api/v1/auth/login", json={"email": "ready@escom.ipn.mx", "password": "PasswordSegura123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    prob = await client.post("/api/v1/problems/", json={"titulo": "Doble", "enunciado": "Duplica un entero.", "lenguaje": "c"}, headers=headers)
    problema_id = prob.json()["id"]
    ref = await client.post(f"/api/v1/problems/{problema_id}/references", params={"autor": "D", "contenido": REF_CODE, "lenguaje": "c"}, headers=headers)
    assert ref.status_code == 201, ref.text
    sub = await client.post(
        f"/api/v1/problems/{problema_id}/submissions",
        json={"problema_id": problema_id, "autor": "A1", "contenido": STUDENT_CODE, "lenguaje": "c"},
        headers=headers,
    )
    assert sub.status_code == 201, sub.text
    return headers, problema_id, sub.json()["id"]


async def _counts(db_session):
    reports = (await db_session.execute(select(func.count()).select_from(ReporteAnalisis))).scalar_one()
    codes = (await db_session.execute(select(func.count()).select_from(CodigoFuente))).scalar_one()
    return reports, codes


@pytest.mark.asyncio
async def test_degraded_real_mode_returns_503_before_any_write(client, db_session, vector_store, fake_artifacts, monkeypatch):
    headers, problema_id, entrega_id = await _setup(client)
    monkeypatch.setattr(rt, "_runtime", _corrupted_runtime(fake_artifacts))
    before = await _counts(db_session)
    vector_store.last_upsert_embedding = None
    upserts = []
    original = vector_store.upsert_reference

    async def spy(*args, **kwargs):
        upserts.append(args)
        return await original(*args, **kwargs)

    monkeypatch.setattr(vector_store, "upsert_reference", spy)

    health = await client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["inference_ready"] is False and body["engine"] == "real"
    assert body["inference_error"] == "sha_mismatch" and body["status"] == "degraded"
    text = health.text
    assert str(fake_artifacts.root) not in text and str(fake_artifacts.root).replace("\\", "/") not in text
    assert ".pth" not in text and "manifest.json" not in text

    run = await client.post("/api/v1/analysis/run", json={"entrega_id": entrega_id}, headers=headers)
    batch = await client.post(
        "/api/v1/analysis/batch",
        data={"problema_id": str(problema_id)},
        files={"files": ("a.c", STUDENT_CODE.encode(), "text/plain")},
        headers=headers,
    )
    ref = await client.post(
        f"/api/v1/problems/{problema_id}/references",
        params={"autor": "D2", "contenido": REF_CODE + "// v2", "lenguaje": "c"},
        headers=headers,
    )
    for res in (run, batch, ref):
        assert res.status_code == 503, res.text
        assert res.json()["reason"] == "sha_mismatch" and res.json()["inference_ready"] is False

    assert await _counts(db_session) == before
    assert upserts == [] and vector_store.last_upsert_embedding is None

    # Reads and non-scoring writes are not gated.
    assert (await client.get(f"/api/v1/problems/{problema_id}", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_ready_runtime_health_reports_engine(client):
    body = (await client.get("/health")).json()
    assert body["inference_ready"] is True and body["status"] == "healthy"
    assert body["engine"] == "stub" and body["inference_error"] is None
    assert "inference_mode" in body

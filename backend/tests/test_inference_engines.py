"""Fail-closed REAL engine, inference thread pool and stub label (spec AS6.1, AS7.1, AS9, CI8.1;
design D10, D11, D12). Model loading is replaced by fake factories: no torch or weights needed."""

import asyncio
import hashlib
import json
import re
import threading
import time
from pathlib import Path

import pytest

from app.config import Settings
from app.domain.errors import InferenceError, NotReadyError
from app.domain.ports.inference_port import StylometryResult
from app.infrastructure.artifacts import load_bundle
from app.infrastructure.inference import get_inference_engine, real_engine, runtime as rt
from app.infrastructure.inference import stub_engine
from app.infrastructure.inference.real_engine import RealBimodalInferenceEngine, embedding_fingerprint, pipeline_fingerprint
from app.infrastructure.inference.stub_engine import STUB_MIN_NON_WS_CHARS, StubInferenceEngine

FAKE_GCB_FIELDS = {
    "model_name": "microsoft/graphcodebert-base", "model_revision": "2b0488a7bb0eefc7041f1bb2cad1ab26b0da269d",
    "input_version": "v2", "walker_version": "c-cpp-2", "pooling": "mean", "use_dfg": True,
    "code_length": 384, "data_flow_length": 128, "max_windows": 16, "dtype": "float32",
}


def fake_gcb_fingerprint(fields):
    # Independent re-statement of design D12 (canonical JSON, sorted keys, compact separators).
    canonical = json.dumps({k: fields.get(k) for k in FAKE_GCB_FIELDS}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


REAL_ENGINE_SOURCE = Path(real_engine.__file__).read_text(encoding="utf-8")
LONG_CODE = "#include <stdio.h>\nint main(void) {\n    int total = 0;\n    for (int i = 0; i < 10; i++) total += i;\n    printf(\"%d\\n\", total);\n    return 0;\n}\n"


class FakeCharCNN:
    arch_version = 2
    preproc_version = 2

    def __init__(self, result=None, sleep=0.0, threads=None):
        self.result = result or {"score": 0.7, "abstained": False, "prob_sintetico": 0.7, "ai_probability": 0.7}
        self.sleep = sleep
        self.threads = threads if threads is not None else []
        self.threads.append(("load", threading.current_thread().name))

    def predict_text(self, code):
        self.threads.append(("predict", threading.current_thread().name))
        if self.sleep:
            time.sleep(self.sleep)
        return dict(self.result)


class FakeGCB:
    def __init__(self, kwargs, threads=None, result=None):
        self.kwargs = kwargs
        self.threads = threads if threads is not None else []
        self.threads.append(("load", threading.current_thread().name))
        self.result = result

    def predict_code(self, code, language="c"):
        self.threads.append(("embed", threading.current_thread().name))
        if self.result is not None:
            return self.result
        return {"success": True, "embedding": [0.5] * 768, "input_version": "v2", "pooling": "mean"}


def _settings(fake_artifacts=None, **overrides):
    extra = {}
    if fake_artifacts is not None:
        root = fake_artifacts.root
        extra = dict(
            DEPLOY_MANIFEST=str(fake_artifacts.manifest),
            CHANNEL_A_CALIBRATION=str(root / "channel_a" / "calibration.json"),
            CHARCNN_CALIBRATION=str(root / "channel_b" / "calibration.json"),
            CHARCNN_CHECKPOINT=str(root / "channel_b" / "best.pth"),
        )
    return Settings(_env_file=None, INFERENCE_MODE="REAL", **{**extra, **overrides})


def _engine(fake_artifacts, *, charcnn=None, gcb=None, threads=None, **overrides):
    threads = threads if threads is not None else []
    return RealBimodalInferenceEngine(
        load_bundle(fake_artifacts.manifest),
        _settings(fake_artifacts, **overrides),
        charcnn_factory=charcnn or (lambda path: FakeCharCNN(threads=threads)),
        gcb_factory=gcb or (lambda kwargs: FakeGCB(kwargs, threads=threads)),
    )


# --- fail closed (AS6.1) --------------------------------------------------------------------------


def test_real_engine_source_has_no_stub_and_no_unverified_adapter():
    """Policy since 2026-10-23: a trained adapter is allowed only when it comes from the verified deploy bundle
    (`bundle.gcb_adapter_dir`, hashed in the manifest). The legacy adapter options stay out of the engine."""
    assert not re.search(r"stub", REAL_ENGINE_SOURCE, re.IGNORECASE)
    assert not re.search(r"adapter_path|adaptador|SHIPPED_ADAPTER", REAL_ENGINE_SOURCE, re.IGNORECASE)
    assert "bundle.gcb_adapter_dir" in REAL_ENGINE_SOURCE
    assert "best_model.pth" not in REAL_ENGINE_SOURCE


def test_real_construction_failure_raises_and_never_creates_a_stub(fake_artifacts, monkeypatch):
    created = []
    monkeypatch.setattr(stub_engine.StubInferenceEngine, "__init__", lambda self: created.append(self), raising=False)

    def boom(path):
        raise RuntimeError("weights missing")

    monkeypatch.setattr(real_engine, "load_charcnn", boom)
    import app.config as config_module

    for key, value in _settings(fake_artifacts).model_dump().items():
        monkeypatch.setattr(config_module.settings, key, value)
    monkeypatch.setattr(rt, "_runtime", None)
    with pytest.raises(NotReadyError) as exc:
        get_inference_engine()
    assert exc.value.reason == "charcnn_load_failed"
    assert created == []
    assert rt.get_runtime().engine is None


def test_charcnn_failure_raises_typed_error(fake_artifacts):
    def boom(path):
        raise OSError("bad checkpoint")

    with pytest.raises(InferenceError) as exc:
        _engine(fake_artifacts, charcnn=boom)
    assert exc.value.reason == "charcnn_load_failed"


def test_charcnn_must_be_v2(fake_artifacts):
    legacy = FakeCharCNN()
    legacy.arch_version = 1
    with pytest.raises(InferenceError) as exc:
        _engine(fake_artifacts, charcnn=lambda path: legacy)
    assert exc.value.reason == "charcnn_not_v2"


def test_charcnn_loads_the_manifest_checkpoint(fake_artifacts):
    seen = []
    _engine(fake_artifacts, charcnn=lambda path: seen.append(Path(path)) or FakeCharCNN())
    assert seen == [fake_artifacts.root / "channel_b" / "best.pth"]


def test_gcb_load_failure_blocks_unless_disabled(fake_artifacts):
    def boom(kwargs):
        raise RuntimeError("no HF cache")

    with pytest.raises(InferenceError) as exc:
        _engine(fake_artifacts, gcb=boom)
    assert exc.value.reason == "gcb_load_failed"
    engine = _engine(fake_artifacts, gcb=boom, GCB_SECONDARY_ENABLED=False)
    assert engine.readiness().ready and engine.readiness().details["gcb_enabled"] is False


@pytest.mark.asyncio
async def test_gcb_disabled_never_invents_an_embedding(fake_artifacts):
    engine = _engine(fake_artifacts, GCB_SECONDARY_ENABLED=False)
    with pytest.raises(InferenceError) as exc:
        await engine.extract_semantic_embedding(LONG_CODE)
    assert exc.value.reason == "gcb_disabled"


def test_gcb_is_built_v2_mean_without_adapter(fake_artifacts):
    seen = []
    _engine(fake_artifacts, gcb=lambda kwargs: seen.append(kwargs) or FakeGCB(kwargs))
    (kwargs,) = seen
    assert kwargs["input_version"] == "v2" and kwargs["pooling"] == "mean"
    assert kwargs["model_name"] == FAKE_GCB_FIELDS["model_name"]
    assert (kwargs["code_length"], kwargs["data_flow_length"], kwargs["max_windows"]) == (384, 128, 16)
    assert not any("adapter" in k for k in kwargs)


@pytest.mark.parametrize("override", [{"GCB_INPUT_VERSION": "legacy"}, {"GCB_POOLING": "cls"}])
def test_gcb_settings_must_match_the_manifest(fake_artifacts, override):
    with pytest.raises(InferenceError) as exc:
        _engine(fake_artifacts, **override)
    assert exc.value.reason == "gcb_config_mismatch"


def test_embedding_fingerprint_is_canonical_and_verified(fake_artifacts):
    engine = _engine(fake_artifacts)
    assert engine.embedding_fingerprint == pipeline_fingerprint(fake_gcb_fingerprint(FAKE_GCB_FIELDS), "identifiers_v1")
    assert embedding_fingerprint({**FAKE_GCB_FIELDS, "pooling": "cls"}) != engine.embedding_fingerprint
    doc = fake_artifacts.read()
    doc["gcb"]["fingerprint"] = "0" * 64
    fake_artifacts.write(doc)
    with pytest.raises(InferenceError) as exc:
        _engine(fake_artifacts)
    assert exc.value.reason == "gcb_fingerprint_mismatch"


@pytest.mark.asyncio
async def test_failed_or_wrong_embedding_raises(fake_artifacts):
    for result in (
        {"success": False, "embedding": []},
        {"success": True, "embedding": [0.1] * 767, "input_version": "v2", "pooling": "mean"},
        {"success": True, "embedding": [0.1] * 768, "input_version": "legacy", "pooling": "cls"},
    ):
        engine = _engine(fake_artifacts, gcb=lambda kwargs, r=result: FakeGCB(kwargs, result=r))
        with pytest.raises(InferenceError):
            await engine.extract_semantic_embedding(LONG_CODE)


# --- Channel B consumes score/abstained only (AS3, CI8.1) ----------------------------------------


@pytest.mark.asyncio
async def test_abstention_never_surfaces_the_legacy_probability(fake_artifacts):
    result = {"score": None, "abstained": True, "ai_probability": 0.05, "prob_sintetico": 0.05, "confidence": 0.95}
    engine = _engine(fake_artifacts, charcnn=lambda path: FakeCharCNN(result=result))
    out = await engine.predict_stylometry("int x;")
    assert out == StylometryResult(raw_score=None, abstained=True)
    assert "0.05" not in repr(out)


@pytest.mark.asyncio
async def test_score_key_is_used_not_legacy_keys(fake_artifacts):
    result = {"score": 0.42, "abstained": False, "ai_probability": 0.05, "prob_sintetico": 0.05}
    engine = _engine(fake_artifacts, charcnn=lambda path: FakeCharCNN(result=result))
    assert (await engine.predict_stylometry(LONG_CODE)).raw_score == 0.42


@pytest.mark.asyncio
async def test_malformed_charcnn_result_raises(fake_artifacts):
    engine = _engine(fake_artifacts, charcnn=lambda path: FakeCharCNN(result={"prob_sintetico": 0.9, "abstained": False}))
    with pytest.raises(InferenceError) as exc:
        await engine.predict_stylometry(LONG_CODE)
    assert exc.value.reason == "charcnn_result_invalid"


# --- thread pool (AS9.1, D10) -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_torch_never_runs_on_the_event_loop_thread(fake_artifacts):
    threads = []
    engine = _engine(fake_artifacts, threads=threads)
    await engine.predict_stylometry(LONG_CODE)
    await engine.extract_semantic_embedding(LONG_CODE)
    loop_thread = threading.current_thread().name
    assert {kind for kind, _ in threads} == {"load", "predict", "embed"}
    for kind, name in threads:
        assert name.startswith("inference") and name != loop_thread, (kind, name)
    engine.close()


@pytest.mark.asyncio
async def test_slow_inference_does_not_block_the_loop(fake_artifacts):
    engine = _engine(fake_artifacts, charcnn=lambda path: FakeCharCNN(sleep=0.3))
    ticks = 0
    done = asyncio.Event()

    async def ticker():
        nonlocal ticks
        while not done.is_set():
            ticks += 1
            await asyncio.sleep(0.02)

    task = asyncio.create_task(ticker())
    await asyncio.gather(engine.predict_stylometry(LONG_CODE), engine.predict_stylometry(LONG_CODE))
    done.set()
    await task
    assert ticks >= 10
    engine.close()


def test_pool_size_follows_settings(fake_artifacts):
    engine = _engine(fake_artifacts, INFERENCE_WORKERS=2)
    assert engine.workers == 2
    engine.close()


def test_runtime_default_factory_builds_the_real_engine(fake_artifacts, monkeypatch):
    monkeypatch.setattr(real_engine, "load_charcnn", lambda path: FakeCharCNN())
    monkeypatch.setattr(real_engine, "load_gcb", lambda kwargs: FakeGCB(kwargs))
    runtime = rt.build_runtime(_settings(fake_artifacts))
    assert runtime.ready and isinstance(runtime.engine, RealBimodalInferenceEngine)
    assert runtime.engine.engine == "real"
    assert runtime.engine.model_versions["charcnn_arch_version"] == 2
    runtime.engine.close()


# --- stub (AS7.1) -------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stub_is_labelled_and_abstains_below_the_charcnn_minimum():
    engine = StubInferenceEngine()
    assert engine.engine == "stub" and engine.readiness().ready
    assert STUB_MIN_NON_WS_CHARS == 60
    short = await engine.predict_stylometry("int x;")
    assert short.abstained and short.raw_score is None
    long = await engine.predict_stylometry(LONG_CODE)
    assert not long.abstained and 0.0 < long.raw_score < 1.0


def test_stub_minimum_matches_the_charcnn_constant():
    preprocess = pytest.importorskip("models.char_cnn.preprocess")
    assert STUB_MIN_NON_WS_CHARS == preprocess.MIN_NON_WS_CHARS

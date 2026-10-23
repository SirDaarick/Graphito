"""The REAL engine with the trained GraphCodeBERT adapter from the deploy bundle (`gcb.adapter`).

Model loading is replaced by fake factories (no torch, no weights). What is checked: which factory is used,
that the adapter identity enters the engine fingerprint (so the Chroma collection changes and old zero-shot
vectors are never mixed with adapter vectors), that the zero-shot fingerprint is unchanged, and that an
embedding that did not come from the adapter is refused instead of silently accepted.
"""

import pytest
from test_gcb_adapter_bundle import add_adapter
from test_inference_engines import FAKE_GCB_FIELDS, FakeCharCNN, _settings, fake_gcb_fingerprint

from app.domain.errors import InferenceError
from app.infrastructure.artifacts import load_bundle
from app.infrastructure.artifacts.models_path import PROJECT_ROOT
from app.infrastructure.inference.real_engine import CANONICALIZATION_VERSION, RealBimodalInferenceEngine, pipeline_fingerprint
from app.infrastructure.vector_store.chroma_adapter import collection_name_for_engine

CODE = "int total(int items) { int acc = 0; for (int k = 0; k < items; k++) acc += k; return acc; }\n"


class Spy:
    """A fake GraphCodeBERT model: records its construction and answers like the real facades do."""

    def __init__(self, adapter_loaded):
        self.adapter_loaded = adapter_loaded
        self.args = None

    def predict_code(self, code, language="c"):
        return {"success": True, "embedding": [0.25] * 768, "input_version": "v2", "pooling": "mean", "adapter_loaded": self.adapter_loaded}


def _engine(fake_artifacts, *, adapter=True, adapter_spy=None, zero_spy=None, enabled=True, adapter_factory=None):
    if adapter:
        section = add_adapter(fake_artifacts)
    else:
        section = None
    adapter_spy = adapter_spy or Spy(True)
    zero_spy = zero_spy or Spy(False)
    calls = {"adapter": [], "zero": []}

    def make_adapter(args):
        calls["adapter"].append(args)
        return adapter_spy

    def make_zero(cfg):
        calls["zero"].append(cfg)
        return zero_spy

    engine = RealBimodalInferenceEngine(
        load_bundle(fake_artifacts.manifest),
        _settings(fake_artifacts, GCB_ADAPTER_ENABLED=enabled),
        charcnn_factory=lambda path: FakeCharCNN(),
        gcb_factory=make_zero,
        gcb_adapter_factory=adapter_factory or make_adapter,
    )
    return engine, calls, section


def test_the_adapter_factory_is_used_with_the_verified_directory(fake_artifacts):
    engine, calls, _ = _engine(fake_artifacts)
    assert len(calls["adapter"]) == 1 and calls["zero"] == []
    args = calls["adapter"][0]
    assert args["adapter_dir"] == fake_artifacts.root / "gcb_adapter"
    assert args["config"]["input_version"] == "v2" and args["config"]["pooling"] == "mean"
    assert engine.gcb.adapter_loaded is True


def test_the_adapter_identity_enters_the_fingerprint_and_the_collection_name(fake_artifacts):
    engine, _, section = _engine(fake_artifacts)
    base = fake_gcb_fingerprint(FAKE_GCB_FIELDS)
    assert engine.embedding_fingerprint == pipeline_fingerprint(base, CANONICALIZATION_VERSION, adapter_sha256=section["sha256"])
    assert engine.embedding_fingerprint != pipeline_fingerprint(base, CANONICALIZATION_VERSION)
    assert collection_name_for_engine(engine) == f"gcb_v2_mean_{engine.embedding_fingerprint[:12]}"


def test_without_an_adapter_the_fingerprint_is_the_zero_shot_one(fake_artifacts):
    engine, calls, _ = _engine(fake_artifacts, adapter=False)
    assert calls["adapter"] == [] and len(calls["zero"]) == 1
    assert engine.embedding_fingerprint == pipeline_fingerprint(fake_gcb_fingerprint(FAKE_GCB_FIELDS), CANONICALIZATION_VERSION)
    assert "gcb_adapter" not in engine.model_versions and "gcb_adapter_sha256" not in engine.model_versions


def test_the_adapter_can_be_switched_off_by_setting_without_touching_the_bundle(fake_artifacts):
    engine, calls, _ = _engine(fake_artifacts, enabled=False)
    assert calls["adapter"] == [] and len(calls["zero"]) == 1
    assert engine.embedding_fingerprint == pipeline_fingerprint(fake_gcb_fingerprint(FAKE_GCB_FIELDS), CANONICALIZATION_VERSION)
    assert "gcb_adapter" not in engine.model_versions


def test_model_versions_name_the_adapter(fake_artifacts):
    engine, _, section = _engine(fake_artifacts)
    assert engine.model_versions["gcb_adapter"] == "B_s1"
    assert engine.model_versions["gcb_adapter_sha256"] == section["sha256"]
    assert engine.readiness().details["gcb_adapter"] == "B_s1"


@pytest.mark.asyncio
async def test_embeddings_come_from_the_adapter_model(fake_artifacts):
    engine, _, _ = _engine(fake_artifacts)
    assert await engine.extract_semantic_embedding(CODE) == [0.25] * 768


@pytest.mark.asyncio
async def test_an_embedding_not_made_with_the_adapter_is_refused(fake_artifacts):
    engine, _, _ = _engine(fake_artifacts, adapter_spy=Spy(False))
    with pytest.raises(InferenceError) as exc:
        await engine.extract_semantic_embedding(CODE)
    assert exc.value.reason == "gcb_config_mismatch"


def test_an_adapter_that_cannot_be_loaded_fails_closed(fake_artifacts):
    def boom(args):
        raise ValueError("incompatible adapter")

    with pytest.raises(InferenceError) as exc:
        _engine(fake_artifacts, adapter_factory=boom)
    assert exc.value.reason == "gcb_adapter_load_failed"


def test_the_deployed_bundle_yields_a_new_collection_name():
    """The real manifest: adapter installed, so the collection differs from the zero-shot v2_norm one."""
    bundle = load_bundle(PROJECT_ROOT / "models" / "deploy" / "manifest.json")
    settings = _settings(None, GCB_SECONDARY_ENABLED=True)
    engine = RealBimodalInferenceEngine(
        bundle, settings, charcnn_factory=lambda path: FakeCharCNN(), gcb_factory=lambda cfg: Spy(False), gcb_adapter_factory=lambda args: Spy(True)
    )
    zero_shot = pipeline_fingerprint(bundle.gcb["fingerprint"], CANONICALIZATION_VERSION)
    assert zero_shot[:12] == "5ae0c89a3576"  # `gcb_v2_mean_5ae0c89a3576`, the v2_norm collection before the adapter
    assert engine.embedding_fingerprint != zero_shot
    assert engine.embedding_fingerprint == pipeline_fingerprint(bundle.gcb["fingerprint"], CANONICALIZATION_VERSION, adapter_sha256=bundle.gcb_adapter_sha256)

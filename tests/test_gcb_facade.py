"""`GraphCodeBERTInference` facade contract (GE7, design D1/D13, tasks 6.1, 6.2, 6.5).

`RobertaModel`/`RobertaTokenizer` are replaced in `legacy_inference` by a tiny random model and a
deterministic fake tokenizer, so no weights are needed. One real-weights smoke runs under
`requires_graphcodebert`.
"""

import ast
import dataclasses
import importlib.util
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from transformers import RobertaConfig, RobertaModel

from models.graphcodebert import legacy_inference
from models.graphcodebert.config import GraphCodeBERTConfig
from models.graphcodebert.inference import GraphCodeBERTInference
from models.graphcodebert.v2.config import GCBV2Config

ROOT = Path(__file__).resolve().parent.parent


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_FakeTokenizer = _load("gcb_v2_encode_tests", Path(__file__).resolve().parent / "test_gcb_v2_encode.py").FakeTokenizer

LEGACY_KEYS = {"embedding", "language", "code_tokens_count", "dfg_node_count", "success", "used_graph"}
NEW_KEYS = {"dfg_nodes_used", "n_windows", "input_version", "pooling", "adapter_loaded", "truncated", "parse_errors"}
HIDDEN = 32

SHORT = "int f(int a){ int b = a; int c = b + a; return c; }"
NO_VARS = "void f(void){ return; }"
BROKEN = "int f(int a){ int b = a; if (b > ) { return b; }"
LONG = "\n".join(f"int g{i}(int a){{ int b = a + {i}; int c = b * a; return c - b; }}" for i in range(40))


class FacadeTokenizer(_FakeTokenizer):
    """Fake tokenizer with the extra calls the legacy pipeline makes (`encode`, `__call__`)."""

    def encode(self, text, add_special_tokens=True):
        ids = self.convert_tokens_to_ids(self.tokenize(text))
        return [self.cls_token_id] + ids + [self.sep_token_id] if add_special_tokens else ids

    def __call__(self, text, return_tensors=None, truncation=False, max_length=None, **kwargs):
        ids = self.encode(text, add_special_tokens=True)
        if truncation and max_length and len(ids) > max_length:
            ids = ids[: max_length - 1] + [self.sep_token_id]
        return {"input_ids": torch.tensor([ids])}


def tiny_roberta(seed=0):
    torch.manual_seed(seed)
    config = RobertaConfig(
        vocab_size=5010,
        hidden_size=HIDDEN,
        num_hidden_layers=2,
        num_attention_heads=4,
        intermediate_size=64,
        max_position_embeddings=514,
    )
    return RobertaModel(config)


def patch_hf(target):
    """Replace the HF loaders used by `legacy_inference` (pytest `monkeypatch` or any object with
    `setattr(obj, name, value)`). Returns the list of model load calls."""
    calls = []

    def load_model(name, **kwargs):
        calls.append((name, kwargs))
        return tiny_roberta()

    target.setattr(legacy_inference, "RobertaModel", SimpleNamespace(from_pretrained=load_model))
    target.setattr(legacy_inference, "RobertaTokenizer", SimpleNamespace(from_pretrained=lambda *a, **k: FacadeTokenizer()))
    return calls


@pytest.fixture()
def hf(monkeypatch):
    return patch_hf(monkeypatch)


def v2_config(**kw):
    return GraphCodeBERTConfig(input_version="v2", **kw)


# --- 6.1: v2 contract -----------------------------------------------------------------------


def test_v2_keys_are_legacy_keys_plus_honest_fields(hf):
    engine = GraphCodeBERTInference(config=v2_config(), device=torch.device("cpu"))
    res = engine.predict_code(SHORT, "c")
    assert set(res) == LEGACY_KEYS | NEW_KEYS
    assert res["input_version"] == "v2" and res["pooling"] == "cls"
    assert res["adapter_loaded"] is False and res["success"] is True
    assert len(res["embedding"]) == HIDDEN and res["language"] == "c"
    assert res["dfg_node_count"] > 0 and res["dfg_nodes_used"] == res["dfg_node_count"]
    assert res["used_graph"] is True and res["n_windows"] == 1
    assert res["truncated"] is False and res["parse_errors"] is False


def test_v2_used_graph_is_false_without_variables(hf):
    engine = GraphCodeBERTInference(config=v2_config())
    res = engine.predict_code(NO_VARS, "c")
    assert res["success"] and res["dfg_nodes_used"] == 0 and res["used_graph"] is False


def test_v2_used_graph_is_false_for_the_no_dfg_ablation(hf):
    engine = GraphCodeBERTInference(config=v2_config(use_dfg=False))
    res = engine.predict_code(SHORT, "c")
    assert res["dfg_node_count"] > 0 and res["dfg_nodes_used"] == 0 and res["used_graph"] is False


def test_v2_long_file_has_several_windows_and_the_same_shape(hf):
    engine = GraphCodeBERTInference(config=v2_config())
    short, long = engine.predict_code(SHORT, "c"), engine.predict_code(LONG, "c")
    assert long["n_windows"] > 1 and short["n_windows"] == 1
    assert len(long["embedding"]) == len(short["embedding"])


def test_v2_pooling_is_configurable_and_echoed(hf):
    cls_res = GraphCodeBERTInference(config=v2_config()).predict_code(SHORT, "c")
    mean_res = GraphCodeBERTInference(config=v2_config(pooling="mean")).predict_code(SHORT, "c")
    assert mean_res["pooling"] == "mean"
    assert not np.allclose(cls_res["embedding"], mean_res["embedding"])


def test_v2_success_is_honest(hf, monkeypatch):
    engine = GraphCodeBERTInference(config=v2_config())
    broken = engine.predict_code(BROKEN, "c")
    assert broken["success"] is True and broken["parse_errors"] is True
    empty = engine.predict_code("", "c")
    assert empty["success"] is False and empty["embedding"] == [] and empty["used_graph"] is False
    assert set(empty) == LEGACY_KEYS | NEW_KEYS

    def boom(inputs):
        raise RuntimeError("boom")

    monkeypatch.setattr(engine._v2_embedder().encoder, "encode", boom)
    failed = engine.predict_code(SHORT, "c")
    assert failed["success"] is False and failed["embedding"] == []


def test_v2_uses_the_shared_encoder_with_eager_attention(hf):
    engine = GraphCodeBERTInference(config=v2_config())
    engine.predict_code(SHORT, "c")
    assert engine._v2_embedder().encoder.roberta is engine.encoder
    assert engine.encoder.config._attn_implementation == "eager"
    assert len(hf) == 1  # one model load, shared by both paths


def test_real_engine_style_call(hf, tmp_path):
    # Mirrors backend real_engine.py: explicit adapter path, predict_code, success/embedding.
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    for config in (GraphCodeBERTConfig(adapter_path=adapter), v2_config(adapter_path=adapter)):
        engine = GraphCodeBERTInference(config=config)
        assert getattr(engine, "is_lora_loaded", False) is False
        res = engine.predict_code(SHORT, language="c")
        assert res.get("success") and "embedding" in res and res["adapter_loaded"] is False
        src = tmp_path / "a.cpp"
        src.write_text(SHORT, encoding="utf-8")
        by_file = engine.predict(src)
        assert by_file["language"] == "cpp" and by_file["success"]
        assert engine.config.embedding_dim == 768
        assert engine.config.charcnn_embedding_dim == 1024
        assert engine.config.fused_dim == 1792


# --- 6.2: legacy default --------------------------------------------------------------------


def test_default_dispatches_to_legacy_with_adapter_off(hf, monkeypatch):
    engine = GraphCodeBERTInference()
    assert engine.config.input_version == "legacy" and engine.is_lora_loaded is False

    def no_v2(*a, **k):
        raise AssertionError("v2 path used by default")

    monkeypatch.setattr(engine, "_predict_v2", no_v2)
    res = engine.predict_code(SHORT, "c")
    assert set(res) == LEGACY_KEYS | NEW_KEYS
    assert res["input_version"] == "legacy" and res["pooling"] == "cls"
    assert res["adapter_loaded"] is False and res["truncated"] is False
    assert res["n_windows"] == 1 and res["dfg_nodes_used"] == res["dfg_node_count"]
    assert res["parse_errors"] is False
    assert engine.predict_code(BROKEN, "c")["parse_errors"] is True


def test_legacy_values_equal_the_frozen_legacy_class(hf):
    facade = GraphCodeBERTInference(device=torch.device("cpu"))
    frozen = legacy_inference.LegacyGraphCodeBERTInference(device=torch.device("cpu"))
    a, b = facade.predict_code(SHORT, "c"), frozen.predict_code(SHORT, "c")
    assert {k: a[k] for k in b} == b  # legacy keys and values unchanged


def test_legacy_chunked_file_reports_chunks_as_windows(hf, monkeypatch):
    engine = GraphCodeBERTInference()
    monkeypatch.setattr(engine.config, "max_code_tokens", 60)
    res = engine.predict_code(LONG, "c")
    assert res["chunks"] > 1 and res["n_windows"] == res["chunks"]


# --- legacy `truncated` is reported honestly (slice-3 review follow-up) ------------------------


def test_legacy_truncated_when_dfg_nodes_exceed_the_position_budget(hf, monkeypatch):
    engine = GraphCodeBERTInference()
    tokens = engine._dfg_extractor.parse_code(SHORT, "c").code_tokens
    code_len = len(engine.tokenizer.encode(" ".join(tokens), add_special_tokens=True))
    monkeypatch.setattr(engine.config, "max_position_embeddings", code_len + 1)  # room for one node
    res = engine.predict_code(SHORT, "c")
    assert res["used_graph"] and res["dfg_node_count"] > 1
    assert res["truncated"] is True


def test_legacy_truncated_when_a_chunk_exceeds_max_code_tokens(hf, monkeypatch):
    engine = GraphCodeBERTInference()
    monkeypatch.setattr(engine.config, "max_code_tokens", 60)
    one_long_line = " ".join(f"int v{i} = {i};" for i in range(40))  # one line, > 60 subtokens
    res = engine.predict_code(one_long_line, "c")
    assert res["truncated"] is True


def test_legacy_truncated_is_unknown_for_untruncated_chunked_files(hf, monkeypatch):
    # Chunks whose parse fails are skipped inside the frozen class and are not observable here.
    engine = GraphCodeBERTInference()
    monkeypatch.setattr(engine.config, "max_code_tokens", 60)
    res = engine.predict_code(LONG, "c")
    assert res["chunks"] > 1 and res["truncated"] is None


def test_legacy_truncated_on_the_2000_char_fallback(hf, monkeypatch):
    engine = GraphCodeBERTInference()
    monkeypatch.setattr(engine.config, "max_code_tokens", 60)
    real_parse = engine._dfg_extractor.parse_code
    fallback = LONG[:2000]
    assert len(LONG) > 2000

    def parse(code, language):  # every chunk fails, only the fallback slice parses
        if code == fallback:
            return real_parse(code, language)
        return legacy_inference.DFGResult(success=False)

    monkeypatch.setattr(engine._dfg_extractor, "parse_code", parse)
    res = engine.predict_code(LONG, "c")
    assert "chunks" not in res and res["truncated"] is True


def test_legacy_truncation_probe_does_not_change_the_contrastive_api(hf):
    engine = GraphCodeBERTInference()
    frozen = legacy_inference.LegacyGraphCodeBERTInference.__dict__["_build_graph_aware_input"]
    tokens = engine._dfg_extractor.parse_code(SHORT, "c")
    a = engine._build_graph_aware_input(tokens.code_tokens, tokens.dfg_edges)
    b = frozen(engine, tokens.code_tokens, tokens.dfg_edges)
    for x, y in zip(a, b):
        assert torch.equal(x, y)


def test_contrastive_private_api_still_resolves_on_the_facade(hf):
    engine = GraphCodeBERTInference()
    for name in ("_build_graph_aware_input", "_inject_dfg_embeddings", "_dfg_extractor", "encoder", "tokenizer", "device"):
        assert hasattr(engine, name), name
    ids, pos, mask = engine._build_graph_aware_input(["int", "a", "=", "1", ";"], [])
    assert ids.shape == pos.shape == (1, engine.config.max_position_embeddings)


def test_contrastive_module_imports_against_the_facade():
    pytest.importorskip("peft")
    import models.graphcodebert.contrastive_graphcodebert as contrastive

    assert contrastive.GraphCodeBERTInference is GraphCodeBERTInference


# --- 6.4: config ----------------------------------------------------------------------------


def test_config_defaults_and_v2_config():
    cfg = GraphCodeBERTConfig()
    assert cfg.adapter_path is None
    assert (cfg.input_version, cfg.pooling, cfg.use_dfg) == ("legacy", "cls", True)
    assert (cfg.code_length, cfg.data_flow_length, cfg.max_windows, cfg.attn_implementation) == (384, 128, 16, "eager")
    v2 = GraphCodeBERTConfig(pooling="mean", max_windows=4).v2_config()
    assert v2 == GCBV2Config(pooling="mean", max_windows=4)


@pytest.mark.parametrize("bad", [dict(input_version="v3"), dict(pooling="max"), dict(code_length=450)])
def test_config_rejects_invalid_values(bad):
    with pytest.raises(ValueError):
        GraphCodeBERTConfig(**bad)


def test_fusion_config_fields_are_preserved():
    # GE7.6: the fields models/fusion.py reads keep their names and defaults.
    tree = ast.parse((ROOT / "models" / "fusion.py").read_text(encoding="utf-8"))
    used = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Attribute) and n.value.attr == "config"}
    assert used == {"embedding_dim", "charcnn_embedding_dim", "fused_dim"}
    defaults = {f.name: f.default for f in dataclasses.fields(GraphCodeBERTConfig)}
    assert (defaults["embedding_dim"], defaults["charcnn_embedding_dim"], defaults["fused_dim"]) == (768, 1024, 1792)
    assert defaults["model_name"] == "microsoft/graphcodebert-base"


# --- 6.5: documented deviation --------------------------------------------------------------


def test_legacy_default_is_a_documented_deviation_until_sdd4(hf):
    """Spec GE7.4/GE7.5 (amended by the user, 2026-10-11): the facade default stays the legacy
    pipeline with the adapter OFF so backend embeddings stay comparable with the indexed Chroma
    vectors. v2 is used only when requested explicitly (evaluation CLI, tests). SDD-4 flips this
    default to "v2" together with the Chroma reindex; this test must change then."""
    assert GraphCodeBERTConfig().input_version == "legacy"
    assert GraphCodeBERTInference().predict_code(SHORT, "c")["input_version"] == "legacy"
    assert GraphCodeBERTInference(config=v2_config()).predict_code(SHORT, "c")["input_version"] == "v2"


# --- real weights ---------------------------------------------------------------------------


@pytest.mark.requires_graphcodebert
def test_real_facade_v2_smoke():
    engine = GraphCodeBERTInference(config=v2_config(), device=torch.device("cpu"))
    res = engine.predict_code(SHORT, "c")
    assert res["success"] and len(res["embedding"]) == 768
    assert res["input_version"] == "v2" and res["used_graph"] is True and res["adapter_loaded"] is False
    assert np.isfinite(res["embedding"]).all()

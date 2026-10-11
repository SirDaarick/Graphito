"""GraphCodeBERT v2 pooling and file embedding pipeline (GE5.4, GE6, design D7-D9).

Offline on a tiny random eager `RobertaConfig` with the fake tokenizer; one real-weights smoke
under `requires_graphcodebert`.
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
import torch
from transformers import RobertaConfig, RobertaModel

from models.graphcodebert.v2 import model as v2_model
from models.graphcodebert.v2.config import GCBV2Config
from models.graphcodebert.v2.dfg import extract_dfg_v2
from models.graphcodebert.v2.embed import EmbedResult, GraphCodeBERTV2Embedder, pool_hidden
from models.graphcodebert.v2.encode import encode
from models.graphcodebert.v2.windows import build_windows


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FakeTokenizer = _load("gcb_v2_encode_tests", Path(__file__).resolve().parent / "test_gcb_v2_encode.py").FakeTokenizer
CFG = GCBV2Config(code_length=48, data_flow_length=16)  # window 46, stride 23
HIDDEN = 32

SHORT = "int f(int a){ int b = a; int c = b + a; return c; }"
LONG = "\n".join(f"int g{i}(int a){{ int b = a + {i}; int c = b * a; return c - b; }}" for i in range(12))


def _tiny_roberta(seed=0):
    torch.manual_seed(seed)
    config = RobertaConfig(
        vocab_size=5010,
        hidden_size=HIDDEN,
        num_hidden_layers=2,
        num_attention_heads=4,
        intermediate_size=64,
        max_position_embeddings=CFG.code_length + CFG.data_flow_length + 2,
        attn_implementation="eager",
    )
    return RobertaModel(config, add_pooling_layer=False)


@pytest.fixture(scope="module")
def encoder():
    return v2_model.GraphCodeBERTV2Encoder(_tiny_roberta())


@pytest.fixture()
def embedder(encoder):
    return GraphCodeBERTV2Embedder(FakeTokenizer(), encoder, CFG)


# --- pooling --------------------------------------------------------------------------------


def test_pool_hidden_cls_and_mean_over_code_positions_only():
    df = extract_dfg_v2(SHORT, "c")
    enc = encode(df.code_tokens, df.dfg, FakeTokenizer(), CFG)
    L = len(enc.input_ids)
    hidden = torch.zeros(1, L, 3)
    hidden[0, :, 0] = torch.arange(L, dtype=torch.float32)  # value = sequence position
    hidden[0, 0, 1] = 100.0  # CLS marker
    hidden[0, enc.n_code_kept + 1, 2] = 100.0  # SEP marker
    hidden[0, enc.node_index :, 2] = 50.0  # nodes and padding
    cls, mean = pool_hidden(hidden, [enc])
    assert torch.equal(cls[0], hidden[0, 0])
    code = hidden[0, 1 : 1 + enc.n_code_kept]
    assert torch.allclose(mean[0], code.mean(0))
    assert mean[0, 1] == 0 and mean[0, 2] == 0  # CLS, SEP, nodes and padding excluded
    assert mean[0, 0] == pytest.approx((1 + enc.n_code_kept) / 2)


def test_cls_and_mean_differ_and_come_from_one_forward_pass(embedder, monkeypatch):
    calls = []
    real = embedder.encoder.encode
    monkeypatch.setattr(embedder.encoder, "encode", lambda inputs: calls.append(len(inputs)) or real(inputs))
    res = embedder.embed(LONG, "c")
    assert len(calls) == 1 and calls[0] == res.n_windows > 1
    assert res.cls.shape == res.mean.shape == (HIDDEN,)
    assert not np.allclose(res.cls, res.mean)


def test_pooling_is_echoed_and_selects_the_embedding(encoder):
    for pooling in ("cls", "mean"):
        cfg = GCBV2Config(code_length=48, data_flow_length=16, pooling=pooling)
        res = GraphCodeBERTV2Embedder(FakeTokenizer(), encoder, cfg).embed(SHORT, "c")
        assert res.pooling == pooling
        assert np.array_equal(res.embedding, res.cls if pooling == "cls" else res.mean)


def test_file_embedding_is_the_unweighted_mean_of_window_poolings(embedder, encoder):
    res = embedder.embed(LONG, "c")
    df = extract_dfg_v2(LONG, "c")
    win = build_windows(df.code_tokens, df.dfg, FakeTokenizer(), CFG)
    hidden = encoder.encode(win.inputs)
    cls, mean = pool_hidden(hidden, win.inputs)
    assert res.n_windows == win.n_windows > 1
    assert np.allclose(res.cls, cls.mean(0).numpy(), atol=1e-6)
    assert np.allclose(res.mean, mean.mean(0).numpy(), atol=1e-6)


def test_short_and_long_files_have_the_same_embedding_shape(embedder):
    short, long = embedder.embed(SHORT, "c"), embedder.embed(LONG, "c")
    assert short.n_windows == 1 and long.n_windows > 1
    assert short.cls.shape == long.cls.shape and short.mean.shape == long.mean.shape


# --- result fields --------------------------------------------------------------------------


def test_result_counts_are_measured(embedder):
    res = embedder.embed(SHORT, "c")
    df = extract_dfg_v2(SHORT, "c")
    assert res.success and res.error is None
    assert res.code_tokens_count == len(df.code_tokens)
    assert res.dfg_node_count == len(df.dfg) > 0
    assert res.dfg_nodes_used == len(df.dfg)
    assert res.parse_errors is False and res.truncated is False
    assert res.input_version == "v2" and res.use_dfg is True


def test_no_dfg_ablation_reports_zero_nodes_used(encoder):
    cfg = GCBV2Config(code_length=48, data_flow_length=16, use_dfg=False)
    emb = GraphCodeBERTV2Embedder(FakeTokenizer(), encoder, cfg)
    res = emb.embed(LONG, "c")
    with_dfg = GraphCodeBERTV2Embedder(FakeTokenizer(), encoder, CFG).embed(LONG, "c")
    assert res.dfg_nodes_used == 0 and res.dfg_node_count > 0
    assert res.n_windows == with_dfg.n_windows  # same windows (D8)
    assert not np.allclose(res.cls, with_dfg.cls)


def test_code_without_variables_uses_no_graph(embedder):
    res = embedder.embed("void f(void){ return; }", "c")
    assert res.success and res.dfg_nodes_used == 0


def test_parse_errors_still_embed(embedder):
    res = embedder.embed("int f(int a){ int b = a; if (b > ) { return b; }", "c")
    assert res.success and res.parse_errors is True
    assert res.cls is not None


@pytest.mark.parametrize("code", ["", "   \n\t", "// only a comment\n"])
def test_empty_input_is_a_failure_result_without_exception(embedder, code):
    res = embedder.embed(code, "c")
    assert isinstance(res, EmbedResult)
    assert res.success is False and res.cls is None and res.mean is None and res.embedding is None
    assert res.error == "empty"
    assert res.n_windows == 0


def test_encoder_exception_is_a_failure_result(embedder, monkeypatch):
    def boom(inputs):
        raise RuntimeError("cuda exploded")

    monkeypatch.setattr(embedder.encoder, "encode", boom)
    res = embedder.embed(SHORT, "c")
    assert res.success is False and res.embedding is None
    assert "cuda exploded" in res.error


def test_language_aliases_and_bytes_input(embedder):
    a = embedder.embed(SHORT.encode("utf-8"), "C")
    b = embedder.embed(SHORT, "c")
    assert np.array_equal(a.cls, b.cls)
    assert embedder.embed("int main(){ std::vector<int> v; int x = v[0]; return x; }", "c++").success


def test_embed_is_deterministic(embedder):
    a, b = embedder.embed(LONG, "cpp"), embedder.embed(LONG, "cpp")
    assert np.array_equal(a.cls, b.cls) and np.array_equal(a.mean, b.mean)


def test_to_dict_is_json_friendly(embedder):
    import json

    d = embedder.embed(SHORT, "c").to_dict()
    json.dumps(d)
    assert set(d) >= {
        "success", "cls", "mean", "pooling", "n_windows", "truncated", "dfg_nodes_used",
        "dfg_node_count", "code_tokens_count", "parse_errors", "input_version",
    }


# --- real weights ---------------------------------------------------------------------------


@pytest.mark.requires_graphcodebert
def test_real_embedder_offline_smoke():
    emb = GraphCodeBERTV2Embedder.from_pretrained(local_files_only=True)
    assert emb.model_revision is None or len(emb.model_revision) >= 7
    res = emb.embed(LONG, "c")
    assert res.success and res.cls.shape == (768,) and res.mean.shape == (768,)
    assert np.isfinite(res.cls).all() and np.isfinite(res.mean).all()
    assert res.n_windows == 1  # fits the 384-subtoken upstream budget

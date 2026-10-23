"""`models.graphcodebert.v2.finetuned.FineTunedGraphCodeBERT`: the facade-compatible adapter model."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from models.graphcodebert.config import GraphCodeBERTConfig
from models.graphcodebert.v2.finetuned import FineTunedGraphCodeBERT

ROOT = Path(__file__).resolve().parents[1]
DEPLOYED_ADAPTER = ROOT / "models" / "deploy" / "gcb_adapter"


class _FakeEmbedder:
    """Stands in for `GraphCodeBERTV2Embedder`: no model is loaded."""

    def __init__(self, success=True):
        self.success = success
        self.encoder = SimpleNamespace(roberta=SimpleNamespace(config=SimpleNamespace(_commit_hash="abc")))
        self.calls = []

    def embed(self, code, language):
        self.calls.append((code, language))
        if not self.success:
            return SimpleNamespace(success=False, error="boom", code_tokens_count=0, dfg_node_count=0, use_dfg=True, dfg_nodes_used=0,
                                   n_windows=0, pooling="mean", truncated=False, parse_errors=True, embedding=None)
        return SimpleNamespace(success=True, error=None, code_tokens_count=7, dfg_node_count=3, use_dfg=True, dfg_nodes_used=3,
                               n_windows=1, pooling="mean", truncated=False, parse_errors=False, embedding=np.arange(4, dtype=np.float32))


def _model(tmp_path, success=True):
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    (adapter / "adapter_model.safetensors").write_bytes(b"x")
    config = GraphCodeBERTConfig(input_version="v2", pooling="mean")
    return FineTunedGraphCodeBERT(adapter, config=config, embedder=_FakeEmbedder(success))


def test_predict_code_keeps_the_facade_keys_and_marks_the_adapter(tmp_path):
    res = _model(tmp_path).predict_code("int main(){return 0;}", "c")
    assert res["success"] is True and res["embedding"] == [0.0, 1.0, 2.0, 3.0]
    assert res["input_version"] == "v2" and res["pooling"] == "mean"
    assert res["adapter_loaded"] is True
    for key in ("language", "code_tokens_count", "dfg_node_count", "used_graph", "dfg_nodes_used", "n_windows", "truncated", "parse_errors"):
        assert key in res


def test_failure_returns_an_empty_embedding_not_an_exception(tmp_path):
    res = _model(tmp_path, success=False).predict_code("x", "c")
    assert res["success"] is False and res["embedding"] == []


def test_exposes_the_encoder_for_the_revision_check_and_the_adapter_identity(tmp_path):
    model = _model(tmp_path)
    assert model.encoder.config._commit_hash == "abc"
    assert len(model.adapter_sha256) == 64


def test_a_missing_adapter_directory_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        FineTunedGraphCodeBERT(tmp_path / "nope", config=GraphCodeBERTConfig(input_version="v2", pooling="mean"), embedder=_FakeEmbedder())


@pytest.mark.skipif(not (DEPLOYED_ADAPTER / "adapter_model.safetensors").exists(), reason="adapter not in the deploy bundle")
def test_the_deployed_adapter_changes_the_embedding_of_the_zero_shot_model():
    from models.graphcodebert.inference import GraphCodeBERTInference

    config = GraphCodeBERTConfig(input_version="v2", pooling="mean")
    code = "int suma(int a, int b) { int t = a + b; return t; }\nint main() { return suma(1, 2); }\n"
    tuned = FineTunedGraphCodeBERT(DEPLOYED_ADAPTER, config=config).predict_code(code, "c")
    zero = GraphCodeBERTInference(config=config).predict_code(code, "c")
    a, b = np.asarray(tuned["embedding"]), np.asarray(zero["embedding"])
    assert tuned["success"] and a.shape == (768,) and tuned["adapter_loaded"] is True and zero["adapter_loaded"] is False
    assert float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b))) < 0.999  # the adapter really moved the vector

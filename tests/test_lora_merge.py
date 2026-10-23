"""`models.graphcodebert.v2.lora_merge`: LoRA merge without peft, equal to peft's `merge_and_unload`."""

import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")
safetensors_torch = pytest.importorskip("safetensors.torch")

from models.graphcodebert.v2 import lora_merge as lm  # noqa: E402


def _tiny_roberta(seed: int = 0):
    from transformers import RobertaConfig, RobertaModel

    torch.manual_seed(seed)
    cfg = RobertaConfig(vocab_size=50, hidden_size=32, num_hidden_layers=2, num_attention_heads=2, intermediate_size=64, max_position_embeddings=40)
    return RobertaModel(cfg, add_pooling_layer=False).eval()


def _peft_adapter(tmp_path: Path, rank: int = 4, alpha: int = 8) -> Path:
    peft = pytest.importorskip("peft")
    model = _tiny_roberta(0)
    wrapped = peft.get_peft_model(model, peft.LoraConfig(r=rank, lora_alpha=alpha, target_modules=["query", "value"], lora_dropout=0.0))
    gen = torch.Generator().manual_seed(1)
    for name, p in wrapped.named_parameters():
        if "lora_" in name:  # LoRA B starts at zero: give both factors real values
            p.data = torch.randn(p.shape, generator=gen) * 0.1
    out = tmp_path / "adapter"
    wrapped.save_pretrained(out)
    return out


def test_merge_equals_peft_merge_and_unload(tmp_path):
    peft = pytest.importorskip("peft")
    adapter = _peft_adapter(tmp_path)
    reference = peft.PeftModel.from_pretrained(_tiny_roberta(0), str(adapter)).merge_and_unload()
    mine = _tiny_roberta(0)
    merged = lm.merge_lora(mine, adapter)
    assert merged == 4  # 2 layers x (query, value)
    ref_state = reference.state_dict()
    for name, tensor in mine.state_dict().items():
        assert torch.allclose(tensor, ref_state[name], atol=1e-6), name


def test_merge_changes_only_query_and_value_weights(tmp_path):
    adapter = _peft_adapter(tmp_path)
    before = {k: v.clone() for k, v in _tiny_roberta(0).state_dict().items()}
    model = _tiny_roberta(0)
    lm.merge_lora(model, adapter)
    changed = {k for k, v in model.state_dict().items() if not torch.equal(v, before[k])}
    assert changed and all(k.endswith(("query.weight", "value.weight")) for k in changed)


def test_merge_with_zero_b_is_a_no_op(tmp_path):
    peft = pytest.importorskip("peft")
    model = _tiny_roberta(0)
    wrapped = peft.get_peft_model(model, peft.LoraConfig(r=4, lora_alpha=8, target_modules=["query", "value"]))
    out = tmp_path / "null"
    wrapped.save_pretrained(out)  # untrained LoRA: B = 0
    fresh = _tiny_roberta(0)
    before = {k: v.clone() for k, v in fresh.state_dict().items()}
    lm.merge_lora(fresh, out)
    assert all(torch.equal(v, before[k]) for k, v in fresh.state_dict().items())


def _rewrite_config(adapter: Path, **changes) -> None:
    path = adapter / "adapter_config.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg.update(changes)
    path.write_text(json.dumps(cfg), encoding="utf-8")


@pytest.mark.parametrize("change", [{"peft_type": "IA3"}, {"use_rslora": True}, {"fan_in_fan_out": True}, {"target_modules": ["query", "key"]}])
def test_merge_refuses_configs_it_does_not_implement(tmp_path, change):
    adapter = _peft_adapter(tmp_path)
    _rewrite_config(adapter, **change)
    with pytest.raises(ValueError):
        lm.merge_lora(_tiny_roberta(0), adapter)


def test_merge_refuses_weights_that_do_not_match_the_model(tmp_path):
    adapter = _peft_adapter(tmp_path)
    bigger = _tiny_roberta(0)
    bigger.encoder.layer = bigger.encoder.layer[:1]  # the adapter has weights for two layers
    with pytest.raises(ValueError):
        lm.merge_lora(bigger, adapter)


def test_merge_refuses_a_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        lm.merge_lora(_tiny_roberta(0), tmp_path / "nope")

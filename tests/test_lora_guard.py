import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")

from models.graphcodebert.inference import GraphCodeBERTInference, lora_weights_applied


class _FakeLora(torch.nn.Module):
    def __init__(self, b_fill: float):
        super().__init__()
        self.layer = torch.nn.Module()
        self.layer.lora_A = torch.nn.Parameter(torch.ones(2, 2))
        self.layer.lora_B = torch.nn.Parameter(torch.full((2, 2), b_fill))


def test_zero_lora_b_means_adapter_not_applied():
    assert lora_weights_applied(_FakeLora(0.0)) is False


def test_nonzero_lora_b_means_adapter_applied():
    assert lora_weights_applied(_FakeLora(0.5)) is True


def test_model_without_lora_params_is_not_applied():
    assert lora_weights_applied(torch.nn.Linear(2, 2)) is False


@pytest.mark.requires_graphcodebert
def test_inference_reports_lora_status_truthfully():
    engine = GraphCodeBERTInference()
    if engine.config.adapter_path is None:
        pytest.skip("no adapter configured")
    # The flag must reflect weights actually applied, never just a successful load call.
    assert engine.is_lora_loaded in (True, False)
    if not engine.is_lora_loaded:
        assert not any("lora_" in n for n, _ in engine.encoder.named_parameters())


@pytest.mark.requires_graphcodebert
def test_shipped_adapter_is_actually_applied():
    from pathlib import Path

    from models.graphcodebert.config import GraphCodeBERTConfig

    adapter = Path(__file__).resolve().parent.parent / "models/graphcodebert/adaptador-lora-20k/adaptador-lora-20k/final"
    if not adapter.exists():
        pytest.skip("shipped adapter not present")
    from transformers import RobertaModel

    tuned = GraphCodeBERTInference(config=GraphCodeBERTConfig(adapter_path=adapter))
    assert tuned.is_lora_loaded is True
    # Compare with a plain RobertaModel (GraphCodeBERTConfig(adapter_path=None) would
    # auto-load the default adapter). Merged weights must differ, otherwise the merge was a no-op.
    base = RobertaModel.from_pretrained(tuned.config.model_name)
    target = "encoder.layer.0.attention.output.dense.weight"  # a layer the adapter targets
    base_w = dict(base.named_parameters())[target]
    tuned_w = dict(tuned.encoder.named_parameters())[target].cpu()
    assert not torch.equal(base_w, tuned_w)

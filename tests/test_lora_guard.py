"""Adapter guard (GE7.1, GE7.2, TH1.2): the facade never loads the LoRA adapter.

The default config has no adapter path even though the shipped adapter exists; an explicit path
is ignored with a WARNING; `peft` is never imported on the facade path. The frozen legacy class
still applies the adapter when asked explicitly (`load_adapter=True`, baseline only).
"""

import logging
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")

from models.graphcodebert import legacy_inference
from models.graphcodebert.config import GraphCodeBERTConfig
from models.graphcodebert.inference import ADAPTER_IGNORED_WARNING, GraphCodeBERTInference, lora_weights_applied

ROOT = Path(__file__).resolve().parent.parent
TESTS = Path(__file__).resolve().parent


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


def test_lora_weights_applied_is_reexported_from_the_legacy_module():
    assert lora_weights_applied is legacy_inference.lora_weights_applied


# --- the facade never loads the adapter -----------------------------------------------------


def _facade_helpers():
    import importlib.util

    name = "gcb_facade_tests"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, TESTS / "test_gcb_facade.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


@pytest.fixture()
def hf(monkeypatch):
    _facade_helpers().patch_hf(monkeypatch)

    def never(*a, **k):
        raise AssertionError("adapter load attempted")

    monkeypatch.setattr(legacy_inference.LegacyGraphCodeBERTInference, "_load_merged_adapter", never)


def test_default_config_has_no_adapter_although_the_shipped_one_exists():
    assert GraphCodeBERTConfig().adapter_path is None
    if legacy_inference.SHIPPED_ADAPTER.exists():
        assert GraphCodeBERTConfig().adapter_path is None  # no auto-default any more


@pytest.mark.parametrize("input_version", ["legacy", "v2"])
def test_default_engine_does_not_load_the_adapter(hf, input_version):
    engine = GraphCodeBERTInference(config=GraphCodeBERTConfig(input_version=input_version))
    assert engine.is_lora_loaded is False
    assert engine.predict_code("int f(int a){ int b = a; return b; }", "c")["adapter_loaded"] is False


@pytest.mark.parametrize("input_version", ["legacy", "v2"])
def test_explicit_adapter_path_is_ignored_with_a_warning(hf, caplog, input_version):
    adapter = legacy_inference.SHIPPED_ADAPTER if legacy_inference.SHIPPED_ADAPTER.exists() else ROOT
    with caplog.at_level(logging.WARNING, logger="graphcodebert"):
        engine = GraphCodeBERTInference(config=GraphCodeBERTConfig(adapter_path=adapter, input_version=input_version))
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "adapter_path ignored" in r.getMessage()]
    assert len(warnings) == 1 and str(adapter) in warnings[0].getMessage()
    assert ADAPTER_IGNORED_WARNING.split("%")[0] in warnings[0].getMessage()
    assert engine.is_lora_loaded is False
    assert not any("lora_" in n for n, _ in engine.encoder.named_parameters())
    assert engine.predict_code("int f(int a){ int b = a; return b; }", "c")["adapter_loaded"] is False


def test_peft_is_never_imported_on_the_facade_path():
    # Fresh interpreter: sys.modules of this process may already hold peft from other tests.
    script = textwrap.dedent(
        f"""
        import importlib.util, sys
        sys.path.insert(0, {str(ROOT)!r})
        spec = importlib.util.spec_from_file_location("gcb_facade_tests", {str(TESTS / "test_gcb_facade.py")!r})
        helpers = importlib.util.module_from_spec(spec)
        sys.modules["gcb_facade_tests"] = helpers
        spec.loader.exec_module(helpers)

        class Patch:
            def setattr(self, obj, name, value):
                setattr(obj, name, value)

        helpers.patch_hf(Patch())
        from models.graphcodebert.config import GraphCodeBERTConfig
        from models.graphcodebert.inference import GraphCodeBERTInference
        for version in ("legacy", "v2"):
            cfg = GraphCodeBERTConfig(adapter_path={str(ROOT)!r}, input_version=version)
            engine = GraphCodeBERTInference(config=cfg)
            res = engine.predict_code("int f(int a){{ int b = a; return b; }}", "c")
            assert res["success"] and not res["adapter_loaded"]
        print("PEFT_LOADED", "peft" in sys.modules)
        """
    )
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd=ROOT, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    assert "PEFT_LOADED False" in out.stdout


# --- the frozen legacy class still applies the adapter when asked ---------------------------


@pytest.mark.requires_graphcodebert
def test_legacy_load_adapter_true_applies_the_shipped_adapter():
    pytest.importorskip("peft")
    if not legacy_inference.SHIPPED_ADAPTER.exists():
        pytest.skip("shipped adapter not present")
    from transformers import RobertaModel

    tuned = legacy_inference.LegacyGraphCodeBERTInference(load_adapter=True, device=torch.device("cpu"))
    assert tuned.is_lora_loaded is True
    assert tuned.config.adapter_path == legacy_inference.SHIPPED_ADAPTER
    base = RobertaModel.from_pretrained(tuned.config.model_name)
    target = "encoder.layer.0.attention.output.dense.weight"  # a layer the adapter targets
    base_w = dict(base.named_parameters())[target]
    tuned_w = dict(tuned.encoder.named_parameters())[target].cpu()
    assert not torch.equal(base_w, tuned_w)


def test_legacy_class_without_load_adapter_ignores_an_explicit_path(hf):
    engine = legacy_inference.LegacyGraphCodeBERTInference(config=GraphCodeBERTConfig(adapter_path=ROOT))
    assert engine.is_lora_loaded is False

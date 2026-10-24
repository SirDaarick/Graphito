"""Merge a PEFT LoRA adapter into a RoBERTa encoder without `peft`.

The production image ships `torch` and `transformers` only, so the adapter trained by
`scripts/contrastive_train.py` is applied here directly: for every adapted `Linear`,
`W <- W + (lora_alpha / r) * B @ A`, which is what `peft`'s `merge_and_unload` computes for a plain LoRA
(`tests/test_lora_merge.py` checks both against each other). Only what the project trains is implemented:
`peft_type == "LORA"` on the `query` and `value` projections, no rank-stabilised scaling, no DoRA, no
transposed weights. Anything else raises `ValueError` instead of being merged wrongly.
"""

import json
import re
from pathlib import Path
from typing import Dict, Union

import torch

ADAPTER_CONFIG = "adapter_config.json"
ADAPTER_WEIGHTS = "adapter_model.safetensors"
SUPPORTED_TARGETS = frozenset({"query", "value"})
_KEY = re.compile(r"^base_model\.model\.(?P<module>.+)\.lora_(?P<factor>[AB])\.weight$")


def _read_config(adapter_dir: Path) -> Dict:
    config_path = adapter_dir / ADAPTER_CONFIG
    if not config_path.is_file() or not (adapter_dir / ADAPTER_WEIGHTS).is_file():
        raise FileNotFoundError(f"{adapter_dir} lacks {ADAPTER_CONFIG} or {ADAPTER_WEIGHTS}")
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    if cfg.get("peft_type") != "LORA":
        raise ValueError(f"unsupported adapter type {cfg.get('peft_type')!r} (only LORA)")
    for flag in ("use_rslora", "use_dora", "fan_in_fan_out"):
        if cfg.get(flag):
            raise ValueError(f"unsupported adapter option {flag}=True")
    targets = cfg.get("target_modules")
    targets = {targets} if isinstance(targets, str) else set(targets or ())
    if not targets or not targets <= SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target_modules {sorted(targets)} (only {sorted(SUPPORTED_TARGETS)})")
    if not isinstance(cfg.get("r"), int) or cfg["r"] <= 0 or not isinstance(cfg.get("lora_alpha"), (int, float)):
        raise ValueError("adapter config lacks a valid r / lora_alpha")
    return cfg


def merge_lora(roberta: torch.nn.Module, adapter_dir: Union[str, Path]) -> int:
    """Add the adapter to `roberta` in place and return how many `Linear` weights were updated."""
    from safetensors.torch import load_file

    adapter_dir = Path(adapter_dir)
    cfg = _read_config(adapter_dir)
    rank, scale = cfg["r"], float(cfg["lora_alpha"]) / cfg["r"]
    factors: Dict[str, Dict[str, torch.Tensor]] = {}
    for key, tensor in load_file(str(adapter_dir / ADAPTER_WEIGHTS)).items():
        match = _KEY.match(key)
        if not match:
            raise ValueError(f"unexpected adapter tensor {key!r}")
        factors.setdefault(match["module"], {})[match["factor"]] = tensor
    if not factors:
        raise ValueError("the adapter holds no LoRA tensors")
    modules = dict(roberta.named_modules())
    merged = 0
    for name, pair in factors.items():
        if set(pair) != {"A", "B"}:
            raise ValueError(f"{name}: incomplete LoRA pair {sorted(pair)}")
        module = modules.get(name)
        if module is None or not isinstance(getattr(module, "weight", None), torch.Tensor):
            raise ValueError(f"the adapter has weights for {name!r}, which the model does not have")
        a, b = pair["A"], pair["B"]
        weight = module.weight
        if a.shape[0] != rank or b.shape[1] != rank or tuple(weight.shape) != (b.shape[0], a.shape[1]):
            raise ValueError(f"{name}: LoRA shapes {tuple(a.shape)} x {tuple(b.shape)} do not fit weight {tuple(weight.shape)}")
        with torch.no_grad():
            weight.add_((b.to(weight.dtype) @ a.to(weight.dtype)) * scale)
        merged += 1
    return merged

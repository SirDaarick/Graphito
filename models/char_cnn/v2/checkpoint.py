"""CharCNN checkpoint format, version resolution and safe loading.

A v2 checkpoint holds primitives only (`model_state_dict` plus a `config` dict built from
`CharCNNV2Config.to_dict()` and run metadata), so it loads with `torch.load(weights_only=True)`.
Version resolution fails closed: absent (or explicit 1) version fields mean the frozen legacy
path, `arch_version == preproc_version == 2` means v2, and anything else raises `ValueError`.
"""

import pickle
import warnings
from pathlib import Path
from typing import Any, Mapping

import torch
import torch.nn as nn

from models.char_cnn.v2.config import ARCH_VERSION, PREPROC_VERSION, CharCNNV2Config
from models.char_cnn.v2.model import CharCNNV2

__all__ = [
    "CHECKPOINT_FORMAT",
    "LEGACY_VERSION",
    "checkpoint_versions",
    "load_checkpoint",
    "make_checkpoint",
    "load_v2_model",
]

CHECKPOINT_FORMAT = "graphito.charcnn_checkpoint/v2"
LEGACY_VERSION = 1


def checkpoint_versions(config: Mapping[str, Any]) -> tuple[int, int]:
    """Return `(arch_version, preproc_version)` for a checkpoint config, or raise `ValueError`.

    A missing field reads as legacy (1). Only the pairs (1, 1) and (2, 2) are supported, so a
    future or mixed format is refused instead of being scored with the wrong pipeline.
    """
    arch = config.get("arch_version", LEGACY_VERSION)
    preproc = config.get("preproc_version", LEGACY_VERSION)
    supported = {(LEGACY_VERSION, LEGACY_VERSION), (ARCH_VERSION, PREPROC_VERSION)}
    if (type(arch), type(preproc)) != (int, int) or (arch, preproc) not in supported:
        raise ValueError(
            f"unsupported CharCNN checkpoint version: arch_version={arch!r}, "
            f"preproc_version={preproc!r} (supported: {sorted(supported)})"
        )
    return arch, preproc


def load_checkpoint(path: "str | Path", map_location: "str | torch.device | None" = None) -> dict:
    """Load a checkpoint with `weights_only=True`.

    Legacy checkpoints (no version fields) written by the old trainer may pickle extra objects;
    for those only, the load falls back to `weights_only=False` with a warning, which is what the
    legacy facade always did. A versioned checkpoint must load safely, otherwise `ValueError`.
    """
    try:
        return torch.load(path, map_location=map_location, weights_only=True)
    except pickle.UnpicklingError as exc:
        reason = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
    checkpoint = torch.load(path, map_location=map_location, weights_only=False)
    if not isinstance(checkpoint, Mapping):
        raise ValueError(f"{path}: not a CharCNN checkpoint dict")
    config = checkpoint.get("config") or {}
    if isinstance(config, Mapping) and ("arch_version" in config or "preproc_version" in config):
        raise ValueError(f"{path}: versioned CharCNN checkpoints must load with weights_only=True ({reason})")
    warnings.warn(
        f"{path}: legacy CharCNN checkpoint is not weights_only-loadable; loaded with "
        f"weights_only=False ({reason})",
        UserWarning,
        stacklevel=2,
    )
    return checkpoint


def make_checkpoint(model: CharCNNV2, **metadata: Any) -> dict:
    """Build a v2 checkpoint dict: the model's full config plus primitive run metadata."""
    return {
        "format": CHECKPOINT_FORMAT,
        "model_state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()},
        "config": {**model.config.to_dict(), **metadata},
    }


def load_v2_model(checkpoint: Mapping[str, Any], device: "str | torch.device" = "cpu") -> nn.Module:
    """Rebuild a `CharCNNV2` from the checkpoint's own config only, load it strictly, eval mode."""
    checkpoint_versions(checkpoint["config"])
    model = CharCNNV2(CharCNNV2Config.from_dict(checkpoint["config"])).to(device)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    return model.eval()

"""LoRA adapters of GraphCodeBERT v2 for the evaluation scripts (F4 of the contrastive CodeNet work).

An adapter trained by `scripts/contrastive_train.py` is merged into the base encoder and used through the
same `GraphCodeBERTV2Embedder` as the zero-shot model, so E1, E2 and the robustness experiment score it with
the unchanged v2 pipeline (identifier canonicalization is applied by the caller, as for `v2_norm`). Methods
that use an adapter are named `ft_<name>`; the embedding cache key includes the adapter's sha256.
"""

import hashlib
from pathlib import Path
from typing import Dict, Sequence

from models.graphcodebert.v2.baselines import V2FileEmbedder
from models.graphcodebert.v2.config import GCBV2Config

ADAPTER_PREFIX = "ft_"
ADAPTER_WEIGHTS = "adapter_model.safetensors"
ADAPTER_CONFIG = "adapter_config.json"


def is_adapter_method(method: str) -> bool:
    return method.startswith(ADAPTER_PREFIX)


def adapter_sha256(path: Path) -> str:
    """Identity of an adapter directory: sha256 over its config and weights (file names included)."""
    path = Path(path)
    digest = hashlib.sha256()
    for name in (ADAPTER_CONFIG, ADAPTER_WEIGHTS):
        file = path / name
        if not file.is_file():
            raise FileNotFoundError(f"{file} not found: not a PEFT adapter directory")
        digest.update(name.encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def parse_adapter_specs(specs: Sequence[str]) -> Dict[str, Path]:
    """`["ft_B_s1=path", ...]` -> `{name: Path}`; names must start with `ft_` and be unique."""
    out: Dict[str, Path] = {}
    for spec in specs:
        name, sep, raw = spec.partition("=")
        if not sep or not raw:
            raise ValueError(f"adapter spec {spec!r} must be NAME=PATH")
        if not is_adapter_method(name):
            raise ValueError(f"adapter name {name!r} must start with {ADAPTER_PREFIX!r}")
        if name in out:
            raise ValueError(f"duplicated adapter name {name!r}")
        out[name] = Path(raw)
    return out


class AdapterFileEmbedder(V2FileEmbedder):
    """`V2FileEmbedder` whose cache key also carries the adapter identity."""

    def __init__(self, embedder, adapter_sha: str):
        super().__init__(embedder, use_dfg=True)
        self.adapter_sha = adapter_sha

    def key_fields(self):
        fields = super().key_fields()
        fields.update(adapter_sha256=self.adapter_sha)
        return fields


def build_embedder(adapter: Path | None, device="cpu", batch_size: int = 16, local_files_only: bool = True):
    """`GraphCodeBERTV2Embedder` over the base encoder with `adapter` merged (zero-shot when None)."""
    import torch
    from transformers import RobertaModel, RobertaTokenizer

    from models.graphcodebert.v2.embed import GraphCodeBERTV2Embedder
    from models.graphcodebert.v2.model import DEFAULT_MODEL, GraphCodeBERTV2Encoder

    roberta = RobertaModel.from_pretrained(
        DEFAULT_MODEL, attn_implementation="eager", local_files_only=local_files_only, add_pooling_layer=False, dtype=torch.float32
    )
    revision = getattr(roberta.config, "_commit_hash", None)
    if adapter is not None:
        from peft import PeftModel

        roberta = PeftModel.from_pretrained(roberta, str(adapter)).merge_and_unload()
    tokenizer = RobertaTokenizer.from_pretrained(DEFAULT_MODEL, local_files_only=local_files_only)
    encoder = GraphCodeBERTV2Encoder(roberta, device=device, batch_size=batch_size)
    return GraphCodeBERTV2Embedder(tokenizer, encoder, GCBV2Config(), model_revision=revision)

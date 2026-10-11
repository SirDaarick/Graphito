from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

INPUT_VERSIONS = ("legacy", "v2")


@dataclass
class GraphCodeBERTConfig:

    model_name: str = "microsoft/graphcodebert-base"
    max_position_embeddings: int = 514
    max_code_tokens: int = 480
    embedding_dim: int = 768
    charcnn_embedding_dim: int = 1024
    fused_dim: int = 1792

    cache_dir: Optional[Path] = None
    # Never loaded by the `GraphCodeBERTInference` facade: an explicit path is ignored with a
    # warning (design D13). Only `LegacyGraphCodeBERTInference(load_adapter=True)` uses it.
    adapter_path: Optional[Path] = None

    fallback_to_text_only: bool = True

    # Facade dispatch. "legacy" (default until SDD-4 reindexes Chroma, user decision 2026-10-11)
    # keeps the frozen legacy encoding with the adapter off; "v2" selects the upstream-faithful
    # pipeline in `models.graphcodebert.v2`, configured by the fields below.
    input_version: str = "legacy"
    pooling: str = "cls"
    use_dfg: bool = True
    code_length: int = 384
    data_flow_length: int = 128
    max_windows: int = 16
    attn_implementation: str = "eager"

    def __post_init__(self):
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.input_version not in INPUT_VERSIONS:
            raise ValueError(f"input_version must be one of {INPUT_VERSIONS}, got {self.input_version!r}")
        self.v2_config()  # validates the v2 fields

    def v2_config(self):
        """The `GCBV2Config` for the v2 fields (raises `ValueError` on invalid values)."""
        from models.graphcodebert.v2.config import GCBV2Config

        return GCBV2Config(
            code_length=self.code_length,
            data_flow_length=self.data_flow_length,
            max_windows=self.max_windows,
            pooling=self.pooling,
            use_dfg=self.use_dfg,
            attn_implementation=self.attn_implementation,
        )

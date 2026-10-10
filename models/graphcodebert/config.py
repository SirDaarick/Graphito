from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GraphCodeBERTConfig:

    model_name: str = "microsoft/graphcodebert-base"
    max_position_embeddings: int = 514
    max_code_tokens: int = 480
    embedding_dim: int = 768
    charcnn_embedding_dim: int = 1024
    fused_dim: int = 1792

    cache_dir: Optional[Path] = None
    adapter_path: Optional[Path] = None

    fallback_to_text_only: bool = True

    def __post_init__(self):
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.adapter_path is None:
            default_lora = Path(__file__).parent / "adaptador-lora-20k" / "adaptador-lora-20k" / "final"
            if default_lora.exists():
                self.adapter_path = default_lora

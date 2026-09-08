from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GraphCodeBERTConfig:

    model_name: str = "microsoft/graphcodebert-base"
    max_position_embeddings: int = 514
    max_code_tokens: int = 480
    embedding_dim: int = 768
    charcnn_embedding_dim: int = 1024
    fused_dim: int = 1792

    cache_dir: Path = field(default_factory=lambda: Path("modelos/weights"))

    fallback_to_text_only: bool = True

    def __post_init__(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)

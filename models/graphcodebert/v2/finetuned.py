"""GraphCodeBERT v2 with the trained LoRA adapter, behind the facade's `predict_code` contract.

`models.graphcodebert.inference.GraphCodeBERTInference` is the zero-shot facade and refuses adapters on
purpose (`tests/test_lora_guard.py`). The deployed Channel A secondary signal is `v2_norm` plus the adapter
frozen in F3/F4 of the contrastive CodeNet work, so it gets its own class: same `predict_code` result keys
and `encoder` attribute the backend engine reads, `adapter_loaded=True`, and the adapter identity
(`adapter_sha256`) for the engine fingerprint. The adapter is merged into the weights at construction with
`lora_merge.merge_lora`; a missing or incompatible adapter raises, there is no silent zero-shot fallback.
"""

from pathlib import Path
from typing import Optional, Union

from models.graphcodebert.config import GraphCodeBERTConfig
from models.graphcodebert.v2.adapter import adapter_sha256

__all__ = ["FineTunedGraphCodeBERT"]


class FineTunedGraphCodeBERT:
    def __init__(
        self,
        adapter_dir: Union[str, Path],
        config: Optional[GraphCodeBERTConfig] = None,
        device=None,
        embedder=None,
    ):
        self.config = config or GraphCodeBERTConfig(input_version="v2", pooling="mean")
        if self.config.input_version != "v2":
            raise ValueError("the fine-tuned adapter only exists for the v2 input")
        self.adapter_dir = Path(adapter_dir)
        self.adapter_sha256 = adapter_sha256(self.adapter_dir)  # FileNotFoundError when it is not an adapter directory
        if embedder is None:
            import torch

            from models.graphcodebert.v2.adapter import build_embedder

            device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
            embedder = build_embedder(self.adapter_dir, device=device, config=self.config.v2_config())
        self._embedder = embedder
        self.encoder = embedder.encoder.roberta  # `encoder.config._commit_hash` is the revision check

    def predict_code(self, code: str, language: str = "c") -> dict:
        res = self._embedder.embed(code, language)
        return {
            "embedding": res.embedding.tolist() if res.success else [],
            "language": language,
            "code_tokens_count": res.code_tokens_count,
            "dfg_node_count": res.dfg_node_count,
            "success": res.success,
            "used_graph": bool(res.success and res.use_dfg and res.dfg_nodes_used > 0),
            "dfg_nodes_used": res.dfg_nodes_used,
            "n_windows": res.n_windows,
            "input_version": "v2",
            "pooling": res.pooling,
            "adapter_loaded": True,
            "truncated": res.truncated,
            "parse_errors": res.parse_errors,
        }

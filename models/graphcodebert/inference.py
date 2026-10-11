"""`GraphCodeBERTInference` facade (design D1, D13; spec GE7 as amended 2026-10-11).

Public API kept for the backend, fusion, scripts and tests: constructor `(config, device)`,
`predict(file_path)`, `predict_code(code, language)`, `config`, `encoder`, `tokenizer`, and the
private legacy methods `contrastive_graphcodebert.py` calls (inherited from the frozen
`LegacyGraphCodeBERTInference`).

Dispatch on `config.input_version`:

- `"legacy"` (default until SDD-4 reindexes Chroma): the frozen legacy encoding, adapter off;
- `"v2"`: `models.graphcodebert.v2` (DFG once per file, sliding windows, upstream mask and
  forward, eager fp32) on the same base encoder.

The adapter is never loaded here: an explicit `adapter_path` is ignored with a WARNING, and
`peft` is never imported. `predict_code` keeps the legacy keys and adds `dfg_nodes_used`,
`n_windows`, `input_version`, `pooling`, `adapter_loaded`, `truncated` and `parse_errors`.
"""

import logging
from typing import Optional

import torch

from models.graphcodebert.config import GraphCodeBERTConfig
from models.graphcodebert.legacy_inference import LegacyGraphCodeBERTInference, lora_weights_applied

__all__ = ["GraphCodeBERTInference", "lora_weights_applied", "ADAPTER_IGNORED_WARNING"]

logger = logging.getLogger("graphcodebert")

ADAPTER_IGNORED_WARNING = (
    "adapter_path ignored (zero-shot v2/legacy facade never loads adapters): %s"
)


class GraphCodeBERTInference(LegacyGraphCodeBERTInference):
    """Zero-shot GraphCodeBERT with legacy/v2 dispatch and no adapter."""

    def __init__(
        self,
        config: Optional[GraphCodeBERTConfig] = None,
        device: Optional[torch.device] = None,
    ):
        config = config or GraphCodeBERTConfig()
        if config.adapter_path is not None:
            logger.warning(ADAPTER_IGNORED_WARNING, config.adapter_path)
        super().__init__(config, device, load_adapter=False)
        self.is_lora_loaded = False
        self._v2 = None

    # --- dispatch -----------------------------------------------------------------------------

    def predict_code(self, code: str, language: str = "c") -> dict:
        if self.config.input_version == "v2":
            return self._predict_v2(code, language)
        return self._predict_legacy(code, language)

    def _predict_legacy(self, code: str, language: str) -> dict:
        res = super().predict_code(code, language)
        res.update(
            dfg_nodes_used=res["dfg_node_count"],
            n_windows=res.get("chunks", 1),
            input_version="legacy",
            pooling="cls",
            adapter_loaded=self.is_lora_loaded,
            truncated=False,
            parse_errors=self._legacy_parse_errors(code, language),
        )
        return res

    def _legacy_parse_errors(self, code: str, language: str) -> bool:
        """tree-sitter `has_error` with the legacy parser selection (`"c"` else C++)."""
        ext = self._dfg_extractor
        parser = ext._c_parser if language == "c" else ext._cpp_parser
        try:
            return bool(parser.parse(code.encode("utf-8")).root_node.has_error)
        except Exception:
            return True

    # --- v2 -----------------------------------------------------------------------------------

    def _v2_embedder(self):
        """The v2 embedder on the shared base encoder (switched to eager attention), built once."""
        if self._v2 is None:
            from models.graphcodebert.v2.embed import GraphCodeBERTV2Embedder
            from models.graphcodebert.v2.model import GraphCodeBERTV2Encoder

            if hasattr(self.encoder, "set_attn_implementation"):
                self.encoder.set_attn_implementation(self.config.attn_implementation)
            else:  # pragma: no cover - older transformers
                self.encoder.config._attn_implementation = self.config.attn_implementation
            encoder = GraphCodeBERTV2Encoder(self.encoder, device=self.device)
            revision = getattr(self.encoder.config, "_commit_hash", None)
            self._v2 = GraphCodeBERTV2Embedder(self.tokenizer, encoder, self.config.v2_config(), model_revision=revision)
        return self._v2

    def _predict_v2(self, code: str, language: str) -> dict:
        res = self._v2_embedder().embed(code, language)
        if not res.success:
            logger.warning("GraphCodeBERT v2 embedding failed: %s", res.error)
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
            "adapter_loaded": False,
            "truncated": res.truncated,
            "parse_errors": res.parse_errors,
        }

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
On the legacy path `truncated` may be None (unknown, see `_legacy_truncated`).
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
        self._truncation_log = []
        try:
            res = super().predict_code(code, language)
            log = self._truncation_log
        finally:
            self._truncation_log = None
        res.update(
            dfg_nodes_used=res["dfg_node_count"],
            n_windows=res.get("chunks", 1),
            input_version="legacy",
            pooling="cls",
            adapter_loaded=self.is_lora_loaded,
            truncated=self._legacy_truncated(code, res, log),
            parse_errors=self._legacy_parse_errors(code, language),
        )
        return res

    def _legacy_truncated(self, code: str, res: dict, log: list) -> Optional[bool]:
        """Whether the legacy encoding dropped content: True, False, or None when unknown.

        Observable losses: the tokenizer cut at `max_code_tokens`, DFG nodes beyond the
        `max_position_embeddings` budget (both recorded per `_build_graph_aware_input` call), and
        the `code[:2000]` fallback after every chunk failed. A chunked file whose chunks all fit is
        `None`: chunks whose parse fails are skipped inside the frozen class without a trace, so
        their loss cannot be ruled out from here.
        """
        if any(log):
            return True
        if "chunks" in res:
            return None
        if len(self.tokenizer.encode(code, add_special_tokens=True)) >= self.config.max_code_tokens:
            return len(code) > 2000  # the chunked path fell back to `code[:2000]`
        return False

    def _build_graph_aware_input(self, code_tokens, dfg_edges):
        """The frozen legacy input, unchanged; also records whether it truncated (code or nodes)
        while a facade `predict_code` call is in progress."""
        out = super()._build_graph_aware_input(code_tokens, dfg_edges)
        log = getattr(self, "_truncation_log", None)
        if log is not None:
            n_code = len(self.tokenizer.encode(" ".join(code_tokens), add_special_tokens=True))
            code_len = min(n_code, self.config.max_code_tokens)
            node_budget = max(0, self.config.max_position_embeddings - code_len)
            log.append(n_code > self.config.max_code_tokens or len(dfg_edges) > node_budget)
        return out

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

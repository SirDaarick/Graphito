"""Scoring methods of the GraphCodeBERT evaluation besides plain v2 (spec GV5; design "Baselines").

- Embedders (cached through `models.graphcodebert.v2.cache`): `V2FileEmbedder` (`dfg`, or the
  `nodfg` ablation with the same windows, design D8) and `LegacyFileEmbedder` (the frozen legacy
  pipeline via its explicit `load_adapter=True` entry point, labelled `legacy`).
- Lexical baselines: token Jaccard on 5-token shingles (the `models.evaluation` near-dup tokens and
  hashes) and winnowing (k=5 positional shingle hashes, window w=4, robust rightmost minimum),
  both scored per assignment block as a set Jaccard via a sparse incidence product.
"""

import importlib.util
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np
from scipy import sparse

from models.evaluation.dedup import MERSENNE_PRIME, SHINGLE_K, shingle_hashes, token_ids
from models.evaluation.normalize import shingle_tokens
from models.graphcodebert.config import GraphCodeBERTConfig
from models.graphcodebert.legacy_inference import LegacyGraphCodeBERTInference
from models.graphcodebert.v2.cache import FileEmbedding
from models.graphcodebert.v2.config import INPUT_VERSION

__all__ = [
    "SHINGLE_K",
    "WINNOW_W",
    "jaccard_set",
    "positional_hashes",
    "winnow_positions",
    "winnow",
    "winnowing_set",
    "SetSimilarity",
    "V2FileEmbedder",
    "LegacyFileEmbedder",
    "load_legacy",
]

WINNOW_W = 4
_SHINGLE_BASE = 1_000_003  # same base as `dedup.shingle_hashes` (parity is tested)


# --- lexical ------------------------------------------------------------------------------------


def jaccard_set(code: str, k: int = SHINGLE_K) -> np.ndarray:
    """Sorted unique hashes of the k-token shingles of the abstracted token stream."""
    return shingle_hashes(token_ids(shingle_tokens(code)), k)


def positional_hashes(ids: np.ndarray, k: int = SHINGLE_K) -> np.ndarray:
    """Hash of every k-token window in order (same rolling formula as `dedup.shingle_hashes`, not
    deduplicated, so positions are kept for winnowing). A stream shorter than k gives one hash."""
    ids = np.asarray(ids, dtype=np.uint64)
    n = ids.size
    if n == 0:
        return np.empty(0, dtype=np.uint64)
    k = min(k, n)
    windows = n - k + 1
    p, base = np.uint64(MERSENNE_PRIME), np.uint64(_SHINGLE_BASE)
    h = np.zeros(windows, dtype=np.uint64)
    for j in range(k):
        h = (h * base + ids[j : j + windows]) % p
    return h


def winnow_positions(hashes: np.ndarray, w: int = WINNOW_W) -> np.ndarray:
    """Positions selected by robust winnowing: the rightmost minimum of every window of `w`
    hashes, each position recorded once (Schleimer et al. 2003). Fewer than `w` hashes form one
    window."""
    h = np.asarray(hashes)
    if h.size == 0:
        return np.empty(0, dtype=np.int64)
    if h.size <= w:
        return np.array([h.size - 1 - int(np.argmin(h[::-1]))], dtype=np.int64)
    windows = np.lib.stride_tricks.sliding_window_view(h, w)
    rightmost = (w - 1) - np.argmin(windows[:, ::-1], axis=1)
    return np.unique(np.arange(windows.shape[0]) + rightmost).astype(np.int64)


def winnow(hashes: np.ndarray, w: int = WINNOW_W) -> np.ndarray:
    """Sorted unique fingerprint values selected by `winnow_positions`."""
    h = np.asarray(hashes)
    return np.unique(h[winnow_positions(h, w)]).astype(np.uint32) if h.size else np.empty(0, dtype=np.uint32)


def winnowing_set(code: str, k: int = SHINGLE_K, w: int = WINNOW_W) -> np.ndarray:
    return winnow(positional_hashes(token_ids(shingle_tokens(code)), k), w)


class SetSimilarity:
    """Block Jaccard of per-file hash sets: `|A∩B| / |A∪B|` from a sparse incidence product
    (`0` when both sets are empty; `1` on the diagonal of a non-empty set)."""

    def __init__(self, sets: Sequence[np.ndarray]):
        self.sets = [np.asarray(s) for s in sets]

    def __call__(self, start: int, stop: int) -> np.ndarray:
        block = self.sets[start:stop]
        n = len(block)
        sizes = np.array([s.size for s in block], dtype=np.float64)
        if n == 0 or sizes.sum() == 0:
            return np.zeros((n, n))
        values = np.concatenate(block)
        _, cols = np.unique(values, return_inverse=True)
        rows = np.repeat(np.arange(n), sizes.astype(np.int64))
        inc = sparse.csr_matrix((np.ones(cols.size), (rows, cols)), shape=(n, int(cols.max()) + 1))
        inter = (inc @ inc.T).toarray()
        union = sizes[:, None] + sizes[None, :] - inter
        return np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)


# --- embedders ----------------------------------------------------------------------------------


class V2FileEmbedder:
    """A `GraphCodeBERTV2Embedder` as a cached file embedder; `use_dfg=False` is the `nodfg`
    ablation. Both poolings are returned from the one forward pass."""

    poolings = ("cls", "mean")

    def __init__(self, embedder, use_dfg: bool = True):
        self.embedder = embedder
        self.use_dfg = use_dfg
        self.variant = "dfg" if use_dfg else "nodfg"

    def key_fields(self) -> Dict[str, Any]:
        fields = self.embedder.config.to_dict()
        fields.pop("pooling", None)
        fields.pop("use_dfg", None)
        fields.update(variant=self.variant, model_revision=self.embedder.model_revision)
        fields.setdefault("input_version", INPUT_VERSION)
        return fields

    def embed(self, code: str, language: str) -> FileEmbedding:
        res = self.embedder.embed(code, language, use_dfg=self.use_dfg)
        flags = {
            "n_windows": int(res.n_windows),
            "truncated": bool(res.truncated),
            "dfg_nodes_used": int(res.dfg_nodes_used),
            "dfg_node_count": int(res.dfg_node_count),
            "code_tokens_count": int(res.code_tokens_count),
            "parse_errors": bool(res.parse_errors),
            "dfg_error": res.dfg_error,
            "error": res.error,
        }
        if not res.success:
            return FileEmbedding(success=False, vectors={}, flags=flags)
        return FileEmbedding(
            success=True,
            vectors={"cls": np.asarray(res.cls, dtype=np.float32), "mean": np.asarray(res.mean, dtype=np.float32)},
            flags=flags,
        )


class LegacyFileEmbedder:
    """The frozen legacy pipeline (CLS only) as a cached file embedder."""

    poolings = ("cls",)

    def __init__(self, engine, variant: str):
        self.engine = engine
        self.variant = variant

    def key_fields(self) -> Dict[str, Any]:
        cfg = self.engine.config
        return {
            "input_version": "legacy",
            "variant": self.variant,
            "model_revision": getattr(self.engine.encoder.config, "_commit_hash", None),
            "max_code_tokens": getattr(cfg, "max_code_tokens", None),
            "max_position_embeddings": getattr(cfg, "max_position_embeddings", None),
            "adapter_path": str(cfg.adapter_path) if getattr(cfg, "adapter_path", None) else None,
            "dtype": "float32",
        }

    def embed(self, code: str, language: str) -> FileEmbedding:
        try:
            res = self.engine.predict_code(code, language)
        except Exception as exc:
            return FileEmbedding(success=False, vectors={}, flags={"error": f"{type(exc).__name__}: {exc}"})
        flags = {
            "n_windows": int(res.get("chunks", 1)),
            "dfg_node_count": int(res.get("dfg_node_count", 0)),
            "code_tokens_count": int(res.get("code_tokens_count", 0)),
            "used_graph": bool(res.get("used_graph", False)),
            "error": None if res.get("success") else "legacy_unsuccessful",
        }
        if not res.get("success") or not res.get("embedding"):
            return FileEmbedding(success=False, vectors={}, flags=flags)
        return FileEmbedding(success=True, vectors={"cls": np.asarray(res["embedding"], dtype=np.float32)}, flags=flags)


def _peft_available() -> bool:
    return importlib.util.find_spec("peft") is not None


def load_legacy(
    config: Optional[GraphCodeBERTConfig] = None, device=None
) -> Tuple[Optional[LegacyFileEmbedder], Dict[str, Any]]:
    """`(embedder, status)` for the labelled `legacy` method.

    Uses `LegacyGraphCodeBERTInference(load_adapter=True)`. When the adapter weights are not
    applied (`peft` missing, or no key matched) the base encoder is used and the variant is
    `legacy_base` with the reason recorded. When the model cannot be built at all the method is
    `skipped` (status with reason, embedder None), never an error (GV5.1)."""
    try:
        engine = LegacyGraphCodeBERTInference(config=config, device=device, load_adapter=True)
    except Exception as exc:
        return None, {"status": "skipped", "variant": None, "reason": f"{type(exc).__name__}: {exc}", "adapter_loaded": False}
    if engine.is_lora_loaded:
        variant, reason = "legacy_adapter", None
    else:
        variant = "legacy_base"
        reason = "adapter_weights_not_applied" if _peft_available() else "peft_unavailable"
    status = {"status": "ok", "variant": variant, "reason": reason, "adapter_loaded": bool(engine.is_lora_loaded)}
    return LegacyFileEmbedder(engine, variant), status

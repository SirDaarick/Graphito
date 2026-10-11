"""On-disk embedding cache for the GraphCodeBERT evaluation (spec GV2, NF6; design "Embed cache").

Layout: `<root>/<cache_key>/<sha[:2]>/<sha256>.npz`, where `cache_key` is the sha256 of the
canonical JSON of the embedder's key fields (`input_version`, `walker_version`, `variant`,
`model_revision`, budgets, `max_windows`, `dtype`, ...). A change in any field gives a new key
directory, so it can never hit an entry built under another configuration. `<root>/<key>/key.json`
records the fields for provenance.

Each entry stores every pooling the embedder produces (`cls` and `mean` for v2, `cls` for legacy),
so pooling is a field of the entry rather than part of the key: one forward pass serves both
poolings (design D9). Entries are keyed by the sha256 of the file bytes, so duplicate contents
share one entry, and a file is encoded at most once per key (GV2.2). Writes are atomic
(`provenance.atomic_write_bytes`); a failed write leaves no partial entry. Failed embeddings are
cached too (no vectors, flags with the error), so reruns do not retry them.
"""

import hashlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Protocol, Tuple

import numpy as np

from models.evaluation.provenance import atomic_write_bytes

__all__ = ["CACHE_SCHEMA", "FileEmbedding", "FileEmbedder", "cache_key", "EmbeddingCache", "CachedEmbedder"]

CACHE_SCHEMA = "graphcodebert.embed_cache/v1"
_VECTOR_PREFIX = "vec_"
_META = "meta"


@dataclass(frozen=True)
class FileEmbedding:
    """One file's embedding: `vectors` maps pooling name -> `[H]` float32 (empty when failed);
    `flags` are JSON-friendly bookkeeping (`n_windows`, `truncated`, `parse_errors`, `error`, ...)."""

    success: bool
    vectors: Dict[str, np.ndarray] = field(default_factory=dict)
    flags: Dict[str, Any] = field(default_factory=dict)


class FileEmbedder(Protocol):
    variant: str
    poolings: Tuple[str, ...]

    def key_fields(self) -> Dict[str, Any]: ...

    def embed(self, code: str, language: str) -> FileEmbedding: ...


def cache_key(fields: Mapping[str, Any]) -> str:
    """sha256 of the canonical JSON (sorted keys, compact) of the key fields."""
    text = json.dumps(dict(fields), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _encode(entry: FileEmbedding) -> bytes:
    meta = json.dumps({"schema": CACHE_SCHEMA, "success": entry.success, "flags": entry.flags}, sort_keys=True)
    arrays = {f"{_VECTOR_PREFIX}{name}": np.asarray(v, dtype=np.float32) for name, v in entry.vectors.items()}
    arrays[_META] = np.frombuffer(meta.encode("utf-8"), dtype=np.uint8)
    buf = io.BytesIO()
    np.savez(buf, **arrays)
    return buf.getvalue()


def _decode(data: bytes) -> FileEmbedding:
    with np.load(io.BytesIO(data), allow_pickle=False) as npz:
        meta = json.loads(bytes(npz[_META]).decode("utf-8"))
        vectors = {k[len(_VECTOR_PREFIX):]: npz[k].astype(np.float32) for k in npz.files if k.startswith(_VECTOR_PREFIX)}
    if meta.get("schema") != CACHE_SCHEMA:
        raise ValueError(f"unknown cache entry schema {meta.get('schema')!r}")
    return FileEmbedding(success=bool(meta["success"]), vectors=vectors, flags=dict(meta["flags"]))


class EmbeddingCache:
    """Entries of one key directory. `root=None` keeps entries in memory only (`--no-cache`)."""

    def __init__(self, root: Optional[Path], fields: Mapping[str, Any]):
        self.fields = dict(fields)
        self.key = cache_key(self.fields)
        self.directory = None if root is None else Path(root) / self.key
        self._memory: Dict[str, FileEmbedding] = {}
        self._key_written = False

    def path(self, sha256: str) -> Path:
        if self.directory is None:
            raise ValueError("memory-only cache has no paths")
        return self.directory / sha256[:2] / f"{sha256}.npz"

    def get(self, sha256: str) -> Optional[FileEmbedding]:
        if sha256 in self._memory:
            return self._memory[sha256]
        if self.directory is None:
            return None
        path = self.path(sha256)
        if not path.exists():
            return None
        try:
            entry = _decode(path.read_bytes())
        except Exception:  # unreadable entry: treat as a miss and rewrite it
            return None
        self._memory[sha256] = entry
        return entry

    def put(self, sha256: str, entry: FileEmbedding) -> None:
        if self.directory is not None:
            if not self._key_written:
                doc = {"schema": CACHE_SCHEMA, "key": self.key, "fields": self.fields}
                text = json.dumps(doc, sort_keys=True, indent=2) + "\n"
                atomic_write_bytes(self.directory / "key.json", text.encode("utf-8"))
                self._key_written = True
            atomic_write_bytes(self.path(sha256), _encode(entry))
        self._memory[sha256] = entry


class CachedEmbedder:
    """An embedder behind a cache: `embed(sha256, code, language)` encodes on a miss only."""

    def __init__(self, embedder: FileEmbedder, cache: EmbeddingCache):
        self.embedder = embedder
        self.cache = cache
        self.stats = {"hits": 0, "misses": 0}

    @property
    def variant(self) -> str:
        return self.embedder.variant

    @property
    def poolings(self) -> Tuple[str, ...]:
        return tuple(self.embedder.poolings)

    def embed(self, sha256: str, code: str, language: str) -> FileEmbedding:
        entry = self.cache.get(sha256)
        if entry is not None:
            self.stats["hits"] += 1
            return entry
        self.stats["misses"] += 1
        entry = self.embedder.embed(code, language)
        self.cache.put(sha256, entry)
        return entry

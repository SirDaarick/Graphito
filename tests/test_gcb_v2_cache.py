"""On-disk embedding cache for the GraphCodeBERT v2 evaluation (GV2, NF6)."""

import hashlib
from pathlib import Path

import numpy as np
import pytest

from models.evaluation import provenance
from models.graphcodebert.v2 import cache as C

FIELDS = {
    "input_version": "v2",
    "walker_version": "c-cpp-2",
    "variant": "dfg",
    "model_revision": "abc123",
    "code_length": 384,
    "data_flow_length": 128,
    "max_windows": 16,
    "dtype": "float32",
}


class CountingEmbedder:
    poolings = ("cls", "mean")

    def __init__(self, fields=FIELDS):
        self.fields = dict(fields)
        self.variant = self.fields["variant"]
        self.calls = []

    def key_fields(self):
        return dict(self.fields)

    def embed(self, code, language):
        self.calls.append(code)
        seed = int(hashlib.sha256(code.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        return C.FileEmbedding(
            success=True,
            vectors={"cls": rng.normal(size=8).astype(np.float32), "mean": rng.normal(size=8).astype(np.float32)},
            flags={"n_windows": 2, "truncated": False, "dfg_nodes_used": 5, "parse_errors": True},
        )


def sha(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def test_cache_key_is_order_independent_and_sensitive_to_every_component():
    base = C.cache_key(FIELDS)
    assert base == C.cache_key(dict(reversed(list(FIELDS.items()))))
    seen = {base}
    for name, value in FIELDS.items():
        changed = {**FIELDS, name: (value + 1) if isinstance(value, int) else f"{value}-x"}
        key = C.cache_key(changed)
        assert key not in seen, name
        seen.add(key)


def test_same_file_is_encoded_once_and_reloaded_from_disk(tmp_path):
    emb = CountingEmbedder()
    cached = C.CachedEmbedder(emb, C.EmbeddingCache(tmp_path, emb.key_fields()))
    first = cached.embed(sha("int a;"), "int a;", "c")
    again = cached.embed(sha("int a;"), "int a;", "c")
    assert len(emb.calls) == 1 and cached.stats == {"hits": 1, "misses": 1}
    fresh_emb = CountingEmbedder()
    fresh = C.CachedEmbedder(fresh_emb, C.EmbeddingCache(tmp_path, fresh_emb.key_fields()))
    loaded = fresh.embed(sha("int a;"), "int a;", "c")
    assert fresh_emb.calls == [] and fresh.stats == {"hits": 1, "misses": 0}
    for entry in (again, loaded):
        assert entry.success and set(entry.vectors) == {"cls", "mean"}
        np.testing.assert_array_equal(entry.vectors["cls"], first.vectors["cls"])
        np.testing.assert_array_equal(entry.vectors["mean"], first.vectors["mean"])
        assert entry.flags == first.flags


def test_changed_key_component_misses(tmp_path):
    emb = CountingEmbedder()
    C.CachedEmbedder(emb, C.EmbeddingCache(tmp_path, emb.key_fields())).embed(sha("x"), "x", "c")
    for name in ("variant", "model_revision", "input_version"):
        other = CountingEmbedder({**FIELDS, name: "other"})
        C.CachedEmbedder(other, C.EmbeddingCache(tmp_path, other.key_fields())).embed(sha("x"), "x", "c")
        assert len(other.calls) == 1, name


def test_duplicate_contents_share_one_entry(tmp_path):
    emb = CountingEmbedder()
    cache = C.EmbeddingCache(tmp_path, emb.key_fields())
    cached = C.CachedEmbedder(emb, cache)
    for _ in ("data/a.c", "data/b.c"):  # two ids, same bytes
        cached.embed(sha("same"), "same", "c")
    assert len(emb.calls) == 1
    assert len(list(cache.directory.rglob("*.npz"))) == 1
    assert (cache.directory / "key.json").exists()


def test_failed_embedding_is_cached_without_vectors(tmp_path):
    class Failing(CountingEmbedder):
        def embed(self, code, language):
            self.calls.append(code)
            return C.FileEmbedding(success=False, vectors={}, flags={"error": "empty"})

    emb = Failing()
    cached = C.CachedEmbedder(emb, C.EmbeddingCache(tmp_path, emb.key_fields()))
    cached.embed(sha(""), "", "c")
    entry = C.CachedEmbedder(emb, C.EmbeddingCache(tmp_path, emb.key_fields())).embed(sha(""), "", "c")
    assert len(emb.calls) == 1 and entry.success is False and entry.vectors == {}
    assert entry.flags == {"error": "empty"}


def test_writes_are_atomic(tmp_path, monkeypatch):
    emb = CountingEmbedder()
    cache = C.EmbeddingCache(tmp_path, emb.key_fields())
    cached = C.CachedEmbedder(emb, cache)
    cached.embed(sha("kept"), "kept", "c")
    before = sorted(p.name for p in cache.directory.rglob("*") if p.is_file())

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(provenance.os, "replace", boom)
    with pytest.raises(OSError):
        cached.embed(sha("new"), "new", "c")
    assert sorted(p.name for p in cache.directory.rglob("*") if p.is_file()) == before  # no partial or temp file


def test_memory_only_cache_writes_nothing(tmp_path):
    emb = CountingEmbedder()
    cache = C.EmbeddingCache(None, emb.key_fields())
    cached = C.CachedEmbedder(emb, cache)
    cached.embed(sha("a"), "a", "c")
    cached.embed(sha("a"), "a", "c")
    assert len(emb.calls) == 1 and cache.directory is None
    assert list(Path(tmp_path).iterdir()) == []


def test_entries_live_under_key_and_sha_prefix(tmp_path):
    emb = CountingEmbedder()
    cache = C.EmbeddingCache(tmp_path, emb.key_fields())
    digest = sha("int b;")
    C.CachedEmbedder(emb, cache).embed(digest, "int b;", "c")
    assert cache.path(digest) == tmp_path / C.cache_key(FIELDS) / digest[:2] / f"{digest}.npz"
    assert cache.path(digest).exists()

"""Strict, fingerprinted Chroma adapter (spec RI2.1, RI2.2, RI3; design D12).

A fake Chroma client stands in for the server: no Chroma process or network is needed.
"""

import pytest

from app.domain.errors import VectorStoreError
from app.infrastructure.inference.real_engine import embedding_fingerprint
from app.infrastructure.inference.stub_engine import StubInferenceEngine
from app.infrastructure.vector_store.chroma_adapter import (
    LEGACY_COLLECTIONS,
    ChromaVectorStoreAdapter,
    collection_name_for_engine,
    fingerprinted_collection_name,
)

GCB_FIELDS = {
    "model_name": "microsoft/graphcodebert-base", "model_revision": "2b0488a7bb0eefc7041f1bb2cad1ab26b0da269d",
    "input_version": "v2", "walker_version": "c-cpp-2", "pooling": "mean", "use_dfg": True,
    "code_length": 384, "data_flow_length": 128, "max_windows": 16, "dtype": "float32",
}
VEC = [1.0] + [0.0] * 767


class FakeCollection:
    def __init__(self, name, records=None):
        self.name = name
        self.records = dict(records or {})
        self.reads = 0
        self.query_result = None
        self.raise_on = set()

    def count(self):
        self.reads += 1
        return len(self.records)

    def upsert(self, ids, embeddings, metadatas=None, documents=None):
        if "upsert" in self.raise_on:
            raise RuntimeError("chroma write failed")
        for k, i in enumerate(ids):
            self.records[i] = {"embedding": embeddings[k], "metadata": (metadatas or [{}])[k]}

    def query(self, query_embeddings, n_results, where):
        if "query" in self.raise_on:
            raise RuntimeError("chroma query failed")
        if self.query_result is not None:
            return self.query_result
        ids = [i for i, r in self.records.items() if r["metadata"].get("problema_id") == where["problema_id"]]
        return {"ids": [ids[:n_results]], "distances": [[0.25] * len(ids[:n_results])],
                "metadatas": [[self.records[i]["metadata"] for i in ids[:n_results]]]}

    def delete(self, ids):
        if "delete" in self.raise_on:
            raise RuntimeError("chroma delete failed")
        for i in ids:
            self.records.pop(i, None)


class FakeClient:
    def __init__(self, collections=()):
        self.collections = {c.name: c for c in collections}
        self.opened = []

    def get_or_create_collection(self, name, metadata=None):
        self.opened.append(name)
        return self.collections.setdefault(name, FakeCollection(name))

    def get_collection(self, name):
        self.opened.append(name)
        return self.collections[name]


def _adapter(client=None, name="gcb_v2_mean_0123456789ab"):
    return ChromaVectorStoreAdapter(name, client=client or FakeClient())


def test_collection_name_changes_when_only_pooling_differs():
    fp_mean = embedding_fingerprint(GCB_FIELDS)
    fp_cls = embedding_fingerprint({**GCB_FIELDS, "pooling": "cls"})
    a = fingerprinted_collection_name(fp_mean, input_version="v2", pooling="mean")
    b = fingerprinted_collection_name(fp_cls, input_version="v2", pooling="cls")
    assert a != b
    assert a == f"gcb_v2_mean_{fp_mean[:12]}"
    # The fingerprint alone also separates them (same visible prefix, different hash).
    assert fingerprinted_collection_name(fp_cls, input_version="v2", pooling="mean") != a


def test_stub_collection_name():
    engine = StubInferenceEngine()
    assert collection_name_for_engine(engine) == f"stub_{engine.embedding_fingerprint[:12]}"


def test_real_engine_collection_name_uses_its_fields():
    class FakeReal:
        engine = "real"
        embedding_fingerprint = embedding_fingerprint(GCB_FIELDS)
        gcb_fields = GCB_FIELDS

    assert collection_name_for_engine(FakeReal()) == f"gcb_v2_mean_{FakeReal.embedding_fingerprint[:12]}"


@pytest.mark.parametrize("legacy", sorted(LEGACY_COLLECTIONS))
def test_legacy_collection_names_are_refused(legacy):
    with pytest.raises(ValueError):
        _adapter(name=legacy)


@pytest.mark.asyncio
async def test_legacy_collections_are_never_touched():
    legacy = [FakeCollection(n, {"x": {"embedding": [0.0] * 769, "metadata": {"problema_id": 1}}}) for n in LEGACY_COLLECTIONS]
    client = FakeClient(legacy)
    store = _adapter(client)
    await store.upsert_reference("r1", VEC, {"problema_id": 1})
    await store.query_nearest(VEC, problema_id=1)
    await store.delete_reference("r1")
    assert set(client.opened) == {"gcb_v2_mean_0123456789ab"}
    assert all(c.count() == 1 and c.reads == 1 for c in legacy)  # only this assertion read them


@pytest.mark.asyncio
async def test_result_without_distances_raises():
    store = _adapter()
    store.collection.records["r1"] = {"embedding": VEC, "metadata": {"problema_id": 1}}
    store.collection.query_result = {"ids": [["r1"]], "metadatas": [[{"problema_id": 1}]]}
    with pytest.raises(VectorStoreError) as exc:
        await store.query_nearest(VEC, problema_id=1)
    assert exc.value.reason == "vector_store_malformed"
    store.collection.query_result = {"ids": [["r1"]], "distances": [[]]}
    with pytest.raises(VectorStoreError):
        await store.query_nearest(VEC, problema_id=1)


@pytest.mark.asyncio
async def test_metadatas_shorter_than_ids_is_malformed():
    store = _adapter()
    store.collection.records["r1"] = {"embedding": VEC, "metadata": {"problema_id": 1}}
    store.collection.query_result = {
        "ids": [["r1", "r2"]], "distances": [[0.1, 0.2]], "metadatas": [[{"problema_id": 1}]],
    }
    with pytest.raises(VectorStoreError) as exc:
        await store.query_nearest(VEC, problema_id=1)
    assert exc.value.reason == "vector_store_malformed"


@pytest.mark.asyncio
@pytest.mark.parametrize("op", ["query", "upsert", "delete"])
async def test_failing_client_raises_not_empty(op):
    store = _adapter()
    store.collection.records["r1"] = {"embedding": VEC, "metadata": {"problema_id": 1}}
    store.collection.raise_on.add(op)
    with pytest.raises(VectorStoreError):
        if op == "query":
            await store.query_nearest(VEC, problema_id=1)
        elif op == "upsert":
            await store.upsert_reference("r2", VEC, {"problema_id": 1})
        else:
            await store.delete_reference("r1")


@pytest.mark.asyncio
async def test_empty_collection_is_a_valid_empty_result():
    store = _adapter()
    assert await store.query_nearest(VEC, problema_id=1) == []


@pytest.mark.asyncio
async def test_query_returns_cosine_similarity_from_distance():
    store = _adapter()
    await store.upsert_reference("r1", VEC, {"problema_id": 7})
    [match] = await store.query_nearest(VEC, problema_id=7)
    assert match["reference_id"] == "r1" and match["similarity"] == 0.75 and match["distance"] == 0.25


def test_client_construction_failure_is_typed():
    class Broken:
        def get_or_create_collection(self, name, metadata=None):
            raise ConnectionError("chroma down")

    with pytest.raises(VectorStoreError) as exc:
        ChromaVectorStoreAdapter("gcb_v2_mean_0123456789ab", client=Broken())
    assert exc.value.reason == "vector_store_unavailable"


@pytest.mark.asyncio
async def test_in_memory_double_returns_non_constant_similarities(vector_store):
    other = [0.6, 0.8] + [0.0] * 766
    await vector_store.upsert_reference("a", VEC, {"problema_id": 1})
    await vector_store.upsert_reference("b", other, {"problema_id": 1})
    sims = {m["reference_id"]: m["similarity"] for m in await vector_store.query_nearest(VEC, 1, top_k=2)}
    assert sims == {"a": 1.0, "b": 0.6}
    vector_store.fail = True
    with pytest.raises(VectorStoreError):
        await vector_store.query_nearest(VEC, 1)

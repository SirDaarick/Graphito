import pytest

from reindex_chroma import slice_embedding, slice_legacy_into_v2


class FakeCollection:
    def __init__(self, records=None):
        self.records = dict(records or {})

    def count(self):
        return len(self.records)

    def get(self, limit, offset, include):
        ids = list(self.records)[offset : offset + limit]
        return {
            "ids": ids,
            "embeddings": [self.records[i]["embedding"] for i in ids],
            "metadatas": [self.records[i]["metadata"] for i in ids],
            "documents": [self.records[i]["document"] for i in ids],
        }

    def upsert(self, ids, embeddings, metadatas=None, documents=None):
        for k, i in enumerate(ids):
            self.records[i] = {
                "embedding": embeddings[k],
                "metadata": metadatas[k],
                "document": documents[k],
            }


def test_slice_embedding_drops_ai_prob_component():
    vec = [0.1] * 768 + [0.9]
    out = slice_embedding(vec)
    assert len(out) == 768
    assert 0.9 not in out


def test_slice_embedding_rejects_short_vectors():
    with pytest.raises(ValueError):
        slice_embedding([0.0] * 767)


def test_slice_legacy_into_v2_is_idempotent():
    legacy = FakeCollection(
        {f"id{i}": {"embedding": [float(i)] * 768 + [0.5], "metadata": {"problema_id": 1}, "document": "c"} for i in range(5)}
    )
    v2 = FakeCollection()
    assert slice_legacy_into_v2(legacy, v2, batch_size=2) == 5
    assert slice_legacy_into_v2(legacy, v2, batch_size=2) == 5
    assert v2.count() == 5
    assert all(len(r["embedding"]) == 768 for r in v2.records.values())

from typing import Any, Dict, List, Optional

from app.domain.ports.vector_store_port import VectorStorePort
from app.infrastructure.vector_store.chroma_adapter import ChromaVectorStoreAdapter, collection_name_for_engine

_stores: Dict[str, VectorStorePort] = {}


class LazyVectorStore(VectorStorePort):
    """Connects to Chroma on the first vector operation, not when a request is wired.

    Requests that never touch vectors (reads, problem CRUD, a reference stored while the
    GraphCodeBERT secondary signal is disabled) therefore never need Chroma. The strict adapter
    still raises `VectorStoreError` on the first operation when Chroma is unreachable, and a
    failed connection is not cached, so a later request retries it.
    """

    def __init__(self, collection_name: str, fingerprint: Optional[str]):
        self.collection_name = collection_name
        self.fingerprint = fingerprint

    def _store(self) -> VectorStorePort:
        store = _stores.get(self.collection_name)
        if store is None:
            store = ChromaVectorStoreAdapter(self.collection_name, fingerprint=self.fingerprint)
            _stores[self.collection_name] = store
        return store

    async def upsert_reference(
        self, reference_id: str, embedding: List[float], metadata: Dict[str, Any], document: Optional[str] = None
    ) -> bool:
        return await self._store().upsert_reference(reference_id, embedding, metadata, document)

    async def query_nearest(self, embedding: List[float], problema_id: int, top_k: int = 1) -> List[Dict[str, Any]]:
        return await self._store().query_nearest(embedding, problema_id, top_k)

    async def delete_reference(self, reference_id: str) -> bool:
        return await self._store().delete_reference(reference_id)


def get_vector_store() -> VectorStorePort:
    """The vector store of the started engine's fingerprinted collection (design D12).

    Raises `NotReadyError` (503) while the inference runtime is not ready, since the collection
    depends on the engine's embedding fingerprint. Chroma itself is contacted lazily.
    """
    from app.infrastructure.inference import runtime

    engine = runtime.current_runtime().require_engine()
    return LazyVectorStore(collection_name_for_engine(engine), engine.embedding_fingerprint)

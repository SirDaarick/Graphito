from typing import Dict

from app.domain.ports.vector_store_port import VectorStorePort
from app.infrastructure.vector_store.chroma_adapter import ChromaVectorStoreAdapter, collection_name_for_engine

_stores: Dict[str, VectorStorePort] = {}


def get_vector_store() -> VectorStorePort:
    """The vector store of the started engine's fingerprinted collection (design D12).

    Raises `NotReadyError` (503) while the inference runtime is not ready, since the collection
    depends on the engine's embedding fingerprint.
    """
    from app.infrastructure.inference import runtime

    engine = runtime.current_runtime().require_engine()
    name = collection_name_for_engine(engine)
    store = _stores.get(name)
    if store is None:
        store = ChromaVectorStoreAdapter(name, fingerprint=engine.embedding_fingerprint)
        _stores[name] = store
    return store

from app.domain.ports.vector_store_port import VectorStorePort
from app.infrastructure.vector_store.chroma_adapter import ChromaVectorStoreAdapter

_vector_store_instance = None


def get_vector_store() -> VectorStorePort:
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = ChromaVectorStoreAdapter()
    return _vector_store_instance

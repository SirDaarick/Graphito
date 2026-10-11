"""Strict ChromaDB adapter over a fingerprinted GraphCodeBERT collection (spec RI2, RI3; design D12).

The collection name derives from the engine's embedding fingerprint
(`gcb_{input_version}_{pooling}_{fp[:12]}`, or `stub_{fp[:12]}` for the stub engine), so vectors
from different pipelines never mix and stub vectors never reach a real collection. The legacy
collections (`codigos_referencia`, `codigos_referencia_v2`) are never opened, read, written or
deleted here.

Every client or query error raises `VectorStoreError`; a result without distances is malformed and
raises too (no similarity default). An empty collection is a valid empty result.
"""

import logging
from typing import Any, Dict, List, Optional

from app.domain.errors import VectorStoreError
from app.domain.ports.vector_store_port import VectorStorePort

logger = logging.getLogger(__name__)

LEGACY_COLLECTIONS = frozenset({"codigos_referencia", "codigos_referencia_v2"})
EMBEDDING_DIM = 768


def fingerprinted_collection_name(
    fingerprint: str, *, input_version: Optional[str] = None, pooling: Optional[str] = None, stub: bool = False
) -> str:
    """Collection name for an embedding pipeline fingerprint (design D12)."""
    if not fingerprint or len(fingerprint) < 12:
        raise ValueError("an embedding fingerprint (sha256 hex) is required")
    if stub:
        return f"stub_{fingerprint[:12]}"
    if not input_version or not pooling:
        raise ValueError("input_version and pooling are required for a real collection name")
    return f"gcb_{input_version}_{pooling}_{fingerprint[:12]}"


def collection_name_for_engine(engine) -> str:
    """The fingerprinted collection of an inference engine (`InferencePort`)."""
    if engine.engine == "stub":
        return fingerprinted_collection_name(engine.embedding_fingerprint, stub=True)
    fields = getattr(engine, "gcb_fields", None) or {}
    return fingerprinted_collection_name(
        engine.embedding_fingerprint, input_version=fields.get("input_version"), pooling=fields.get("pooling")
    )


def _default_client():
    import chromadb

    from app.config import settings

    if settings.USE_CHROMA_SERVER:
        return chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
    return chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIRECTORY)


class ChromaVectorStoreAdapter(VectorStorePort):
    # Legacy names, kept only for `backend/reindex_chroma.py` (slice migration tooling). This
    # adapter refuses to open them.
    COLLECTION_NAME = "codigos_referencia_v2"
    LEGACY_COLLECTION_NAME = "codigos_referencia"
    EMBEDDING_DIM = EMBEDDING_DIM

    @classmethod
    def _check_dim(cls, embedding: List[float]) -> None:
        if len(embedding) != cls.EMBEDDING_DIM:
            raise ValueError(
                f"Embedding dimension {len(embedding)} != {cls.EMBEDDING_DIM} "
                "(only the semantic vector may be stored or queried)."
            )

    def __init__(self, collection_name: str, client=None, *, fingerprint: Optional[str] = None):
        if collection_name in LEGACY_COLLECTIONS:
            raise ValueError(f"legacy collection {collection_name!r} must not be used by the new code")
        self.collection_name = collection_name
        metadata: Dict[str, Any] = {"hnsw:space": "cosine", "embedding_dim": self.EMBEDDING_DIM}
        if fingerprint:
            metadata["embedding_fingerprint"] = fingerprint
        try:
            self.client = client if client is not None else _default_client()
            self.collection = self.client.get_or_create_collection(name=collection_name, metadata=metadata)
        except Exception as exc:
            logger.error("ChromaDB unavailable (%s): %s", collection_name, type(exc).__name__)
            raise VectorStoreError("vector_store_unavailable", f"{type(exc).__name__}: {exc}") from exc
        logger.info("ChromaDB collection '%s' ready.", collection_name)

    async def upsert_reference(
        self,
        reference_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        document: Optional[str] = None,
    ) -> bool:
        self._check_dim(embedding)
        try:
            self.collection.upsert(
                ids=[str(reference_id)],
                embeddings=[list(embedding)],
                metadatas=[metadata],
                documents=[document] if document else None,
            )
        except Exception as exc:
            raise VectorStoreError("vector_store_write_failed", f"{type(exc).__name__}: {exc}") from exc
        return True

    async def query_nearest(
        self,
        embedding: List[float],
        problema_id: int,
        top_k: int = 1,
    ) -> List[Dict[str, Any]]:
        self._check_dim(embedding)
        try:
            if self.collection.count() == 0:
                return []  # RI3.2: no references indexed yet is a valid empty result
            results = self.collection.query(
                query_embeddings=[list(embedding)],
                n_results=top_k,
                where={"problema_id": problema_id},
            )
        except Exception as exc:
            raise VectorStoreError("vector_store_query_failed", f"{type(exc).__name__}: {exc}") from exc
        return self._parse(results)

    @staticmethod
    def _parse(results) -> List[Dict[str, Any]]:
        if not isinstance(results, dict) or not results.get("ids"):
            raise VectorStoreError("vector_store_malformed", "query result lacks ids")
        ids = list(results["ids"][0] or [])
        if not ids:
            return []
        distances = results.get("distances")
        if not distances or distances[0] is None or len(distances[0]) != len(ids):
            raise VectorStoreError("vector_store_malformed", "query result lacks distances")
        metadatas = results.get("metadatas") or [[{}] * len(ids)]
        output = []
        for idx, ref_id in enumerate(ids):
            distance = distances[0][idx]
            if distance is None:
                raise VectorStoreError("vector_store_malformed", "query result has a null distance")
            # Cosine space: cosine_similarity = 1 - distance.
            similarity = max(0.0, min(1.0, 1.0 - float(distance)))
            output.append({
                "reference_id": ref_id,
                "similarity": round(similarity, 4),
                "distance": round(float(distance), 4),
                "metadata": (metadatas[0] or [{}] * len(ids))[idx] or {},
            })
        return output

    async def delete_reference(self, reference_id: str) -> bool:
        try:
            self.collection.delete(ids=[str(reference_id)])
        except Exception as exc:
            raise VectorStoreError("vector_store_delete_failed", f"{type(exc).__name__}: {exc}") from exc
        return True

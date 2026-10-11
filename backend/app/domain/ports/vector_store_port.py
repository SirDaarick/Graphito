from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class VectorStorePort(ABC):
    """Vector store port for the GraphCodeBERT v2 reference embeddings (768 dims).

    Implementations are strict (spec RI3): every client or query failure raises
    `app.domain.errors.VectorStoreError`, never an empty or default result. An empty collection is
    a valid empty result. The collection is selected by the engine's embedding fingerprint.
    """

    @abstractmethod
    async def upsert_reference(
        self,
        reference_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        document: Optional[str] = None,
    ) -> bool:
        """Store or update one reference embedding. Raises `VectorStoreError` on failure."""

    @abstractmethod
    async def query_nearest(
        self,
        embedding: List[float],
        problema_id: int,
        top_k: int = 1,
    ) -> List[Dict[str, Any]]:
        """Nearest references of one problem (`reference_id`, `similarity`, `distance`, `metadata`)."""

    @abstractmethod
    async def delete_reference(self, reference_id: str) -> bool:
        """Remove one reference. Raises `VectorStoreError` on failure."""

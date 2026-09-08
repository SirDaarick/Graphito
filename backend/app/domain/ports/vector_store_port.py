from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class VectorStorePort(ABC):
    """Puerto abstracto para la persistencia vectorial (ChromaDB)."""

    @abstractmethod
    async def upsert_reference(
        self,
        reference_id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        document: Optional[str] = None,
    ) -> bool:
        """Almacena o actualiza un embedding de referencia (769 dimensiones)."""
        pass

    @abstractmethod
    async def query_nearest(
        self,
        embedding: List[float],
        problema_id: int,
        top_k: int = 1,
    ) -> List[Dict[str, Any]]:
        """Busca las referencias más cercanas para un problema específico."""
        pass

    @abstractmethod
    async def delete_reference(self, reference_id: str) -> bool:
        """Elimina una referencia del almacén vectorial."""
        pass

from abc import ABC, abstractmethod
from typing import Dict, List, Any


class InferencePort(ABC):
    """Puerto abstracto para el motor de inferencia bimodal (GraphCodeBERT + CharCNN)."""

    @abstractmethod
    async def extract_semantic_embedding(self, code: str, lang: str = "c") -> List[float]:
        """Extrae el vector semántico (768 dimensiones) del código fuente usando Canal A."""
        pass

    @abstractmethod
    async def predict_synthetic_prob(self, code: str) -> float:
        """Predice la probabilidad (0.0 a 1.0) de que el código sea generado por IA usando Canal B."""
        pass

    @abstractmethod
    async def generate_hybrid_embedding(self, code: str, lang: str = "c") -> List[float]:
        """DEPRECATED: hybrid 769-dim embedding (768 semantic + 1 stylometric).

        Do not use for indexing or querying the vector store: the stylometry channel
        must not leak into semantic similarity. Use `extract_semantic_embedding` (768 dims).
        """
        pass

    @abstractmethod
    def compute_decision(
        self,
        semantic_similarity: float,
        synthetic_prob: float,
        *,
        threshold_sem: float,
        threshold_ai: float,
    ) -> Dict[str, Any]:
        """Calcula discrepancia, dictamen e indicadores de integridad."""
        pass

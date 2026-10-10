import logging
from typing import Dict, List, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings
from app.domain.ports.vector_store_port import VectorStorePort

logger = logging.getLogger(__name__)


class ChromaVectorStoreAdapter(VectorStorePort):
    """
    Adaptador de persistencia vectorial utilizando ChromaDB.
    Maneja la colección 'codigos_referencia_v2' (solo vectores semánticos de 768 dims,
    distancia coseno). La colección legacy 'codigos_referencia' (769 dims) no se toca;
    se migra con backend/reindex_chroma.py.
    """

    COLLECTION_NAME = "codigos_referencia_v2"
    LEGACY_COLLECTION_NAME = "codigos_referencia"
    EMBEDDING_DIM = 768

    @classmethod
    def _check_dim(cls, embedding: List[float]) -> None:
        if len(embedding) != cls.EMBEDDING_DIM:
            raise ValueError(
                f"Embedding dimension {len(embedding)} != {cls.EMBEDDING_DIM} "
                "(only the semantic vector may be stored or queried)."
            )

    def __init__(self):
        self._init_client()

    def _init_client(self):
        try:
            if settings.USE_CHROMA_SERVER:
                self.client = chromadb.HttpClient(
                    host=settings.CHROMA_HOST,
                    port=settings.CHROMA_PORT,
                )
            else:
                self.client = chromadb.PersistentClient(
                    path=settings.CHROMA_PERSIST_DIRECTORY,
                )
            
            # Obtener o crear colección con métrica de similitud del coseno
            self.collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine", "embedding_dim": self.EMBEDDING_DIM},
            )
            logger.info(f"ChromaDB colección '{self.COLLECTION_NAME}' lista.")
            self._warn_if_legacy_unmigrated()
        except Exception as e:
            logger.error(f"Error inicializando ChromaDB: {e}")
            raise

    def _warn_if_legacy_unmigrated(self) -> None:
        try:
            legacy = self.client.get_collection(name=self.LEGACY_COLLECTION_NAME)
            if legacy.count() > 0 and self.collection.count() == 0:
                logger.warning(
                    "Legacy collection '%s' has %d vectors (769 dims) but '%s' is empty. "
                    "Run `python reindex_chroma.py --mode slice` to migrate.",
                    self.LEGACY_COLLECTION_NAME,
                    legacy.count(),
                    self.COLLECTION_NAME,
                )
        except Exception:
            # Legacy collection absent (fresh install) or not readable: nothing to warn about.
            pass

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
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[document] if document else None,
            )
            return True
        except Exception as e:
            logger.error(f"Error al guardar referencia en ChromaDB: {e}")
            return False

    async def query_nearest(
        self,
        embedding: List[float],
        problema_id: int,
        top_k: int = 1,
    ) -> List[Dict[str, Any]]:
        self._check_dim(embedding)
        try:
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=top_k,
                where={"problema_id": problema_id},
            )
            
            output = []
            if results and results.get("ids") and len(results["ids"][0]) > 0:
                for idx in range(len(results["ids"][0])):
                    ref_id = results["ids"][0][idx]
                    distance = results["distances"][0][idx] if results.get("distances") else 0.0
                    meta = results["metadatas"][0][idx] if results.get("metadatas") else {}
                    # En distancia coseno de ChromaDB: cosine_similarity = 1.0 - distance
                    cosine_sim = max(0.0, min(1.0, 1.0 - distance))
                    output.append({
                        "reference_id": ref_id,
                        "similarity": round(cosine_sim, 4),
                        "distance": round(distance, 4),
                        "metadata": meta,
                    })
            return output
        except Exception as e:
            logger.error(f"Error al consultar vecinos en ChromaDB: {e}")
            return []

    async def delete_reference(self, reference_id: str) -> bool:
        try:
            self.collection.delete(ids=[str(reference_id)])
            return True
        except Exception as e:
            logger.error(f"Error al eliminar referencia en ChromaDB: {e}")
            return False

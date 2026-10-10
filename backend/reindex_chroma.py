"""Migrate reference vectors from the legacy 769-dim Chroma collection to the 768-dim v2 collection.

Modes:
  slice   (default) copy legacy embeddings truncated to [:768]. Exact, because the 769th
          component was ai_prob. Needs no models and no Postgres.
  reembed recompute 768-dim embeddings from the REFERENCIA rows in Postgres using the
          configured inference engine (INFERENCE_MODE). Use when the legacy collection is
          missing or the model changed.

The upsert is idempotent. `--drop-legacy` deletes the legacy collection afterwards (opt-in).

Usage (from backend/ or inside the backend container):
  python reindex_chroma.py --mode slice
  python reindex_chroma.py --mode reembed
"""

import argparse
import asyncio
import logging
from typing import Any, Dict, List

TARGET_DIM = 768
BATCH_SIZE = 200

logger = logging.getLogger("reindex_chroma")


def slice_embedding(embedding: List[float], dim: int = TARGET_DIM) -> List[float]:
    """Return the first `dim` components. Raises ValueError if the vector is too short."""
    if len(embedding) < dim:
        raise ValueError(f"Embedding has {len(embedding)} dims, cannot slice to {dim}.")
    return [float(x) for x in embedding[:dim]]


def slice_legacy_into_v2(legacy, v2, batch_size: int = BATCH_SIZE) -> int:
    """Copy every legacy record into `v2` truncated to 768 dims. Returns the copied count.

    `legacy` and `v2` only need Chroma-like `count()`, `get(...)` and `upsert(...)`.
    """
    total = legacy.count()
    copied = 0
    offset = 0
    while offset < total:
        batch = legacy.get(
            limit=batch_size,
            offset=offset,
            include=["embeddings", "metadatas", "documents"],
        )
        ids = list(batch["ids"])
        if not ids:
            break
        embeddings = [slice_embedding(list(e)) for e in batch["embeddings"]]
        v2.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=batch.get("metadatas"),
            documents=batch.get("documents"),
        )
        copied += len(ids)
        offset += len(ids)
    return copied


def _chroma_client():
    import chromadb
    from app.config import settings

    if settings.USE_CHROMA_SERVER:
        return chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
    return chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIRECTORY)


def _v2_collection(client):
    from app.infrastructure.vector_store.chroma_adapter import ChromaVectorStoreAdapter as A

    return client.get_or_create_collection(
        name=A.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "embedding_dim": A.EMBEDDING_DIM},
    )


async def _reembed(v2) -> int:
    from sqlalchemy import select
    from app.infrastructure.database.models import CodigoFuente, TipoCodigoEnum
    from app.infrastructure.database.session import async_session_maker
    from app.infrastructure.inference import get_inference_engine

    engine = get_inference_engine()
    count = 0
    async with async_session_maker() as session:
        res = await session.execute(
            select(CodigoFuente).where(CodigoFuente.tipo == TipoCodigoEnum.REFERENCIA)
        )
        for ref in res.scalars().all():
            vec = await engine.extract_semantic_embedding(ref.contenido, lang=ref.lenguaje)
            if len(vec) != TARGET_DIM:
                raise ValueError(f"Engine returned {len(vec)} dims for {ref.id}, expected {TARGET_DIM}.")
            metadata: Dict[str, Any] = {
                "problema_id": ref.problema_id,
                "autor": ref.autor,
                "tipo": TipoCodigoEnum.REFERENCIA.value,
                "lenguaje": ref.lenguaje,
            }
            v2.upsert(
                ids=[str(ref.id)],
                embeddings=[vec],
                metadatas=[metadata],
                documents=[ref.contenido],
            )
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["slice", "reembed"], default="slice")
    parser.add_argument("--drop-legacy", action="store_true", help="Delete the legacy collection afterwards.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    from app.infrastructure.vector_store.chroma_adapter import ChromaVectorStoreAdapter as A

    client = _chroma_client()
    v2 = _v2_collection(client)

    if args.mode == "slice":
        legacy = client.get_collection(name=A.LEGACY_COLLECTION_NAME)
        n = slice_legacy_into_v2(legacy, v2)
    else:
        n = asyncio.run(_reembed(v2))

    logger.info("Indexed %d vectors into '%s' (now %d total).", n, A.COLLECTION_NAME, v2.count())

    if args.drop_legacy:
        client.delete_collection(name=A.LEGACY_COLLECTION_NAME)
        logger.info("Dropped legacy collection '%s'.", A.LEGACY_COLLECTION_NAME)


if __name__ == "__main__":
    main()

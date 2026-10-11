"""Reindex reference code from Postgres into the fingerprinted GraphCodeBERT v2 collection.

Spec RI2.2-RI2.3, design D12. Reads every `REFERENCIA` row from the configured database, embeds it
with the configured engine (`INFERENCE_MODE`; REAL needs the deploy bundle and the HF cache for
`microsoft/graphcodebert-base@2b0488a7`) and upserts it into `gcb_{input_version}_{pooling}_{fp[:12]}`
(or `stub_{fp[:12]}` in STUB mode). The legacy collections `codigos_referencia` and
`codigos_referencia_v2` are never opened. Upserts are keyed by the reference id, so reruns give the
same ids and count.

Dry run by default: it reports the target collection and how many references would be indexed,
without embedding or writing. `--apply` performs the reindex. Exit codes: 0 ok, 1 at least one
reference failed (counts and failures are printed), 2 the engine or vector store is not usable.

Usage (repository root, with the backend settings in `.env` or the environment):
  python scripts/reindex_references.py --mode gcb-v2            # dry run
  python scripts/reindex_references.py --mode gcb-v2 --apply
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@dataclass
class ReindexReport:
    collection: str
    dry_run: bool
    total: int = 0
    indexed: int = 0
    failures: List[Tuple[str, str]] = field(default_factory=list)


def exit_code(report: ReindexReport) -> int:
    return 1 if report.failures else 0


async def reindex_references(session_maker, engine, store, *, apply: bool) -> ReindexReport:
    """Embed and upsert every reference (`apply=True`), or only count them (dry run)."""
    from sqlalchemy import select

    from app.domain.errors import GraphitoError
    from app.infrastructure.database.models import CodigoFuente, TipoCodigoEnum

    report = ReindexReport(collection=getattr(store, "collection_name", "?"), dry_run=not apply)
    async with session_maker() as session:
        res = await session.execute(
            select(CodigoFuente)
            .where(CodigoFuente.tipo == TipoCodigoEnum.REFERENCIA)
            .order_by(CodigoFuente.created_at, CodigoFuente.id)
        )
        refs = [(str(r.id), r.problema_id, r.autor, r.contenido, r.lenguaje) for r in res.scalars().all()]
    report.total = len(refs)
    if not apply:
        return report
    for ref_id, problema_id, autor, contenido, lenguaje in refs:
        try:
            vector = await engine.extract_semantic_embedding(contenido, lang=lenguaje)
            await store.upsert_reference(
                reference_id=ref_id,
                embedding=vector,
                metadata={"problema_id": problema_id, "autor": autor, "tipo": "REFERENCIA", "lenguaje": lenguaje},
                document=contenido,
            )
        except GraphitoError as exc:
            report.failures.append((ref_id, exc.reason))
        except Exception as exc:  # report every failure; the run still exits non-zero
            report.failures.append((ref_id, type(exc).__name__))
        else:
            report.indexed += 1
    return report


def _parse(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["gcb-v2"], default="gcb-v2", help="Only GraphCodeBERT v2 (fingerprinted).")
    parser.add_argument("--apply", action="store_true", help="Embed and write (default: dry run).")
    return parser.parse_args(argv)


def run(argv: Optional[Sequence[str]] = None, *, runtime=None, session_maker=None, store=None) -> int:
    args = _parse(argv)
    if runtime is None:
        from app.infrastructure.inference.runtime import build_runtime

        runtime = build_runtime()
    if not runtime.ready or runtime.engine is None:
        print(f"ERROR: inference engine not ready ({runtime.reason}); nothing indexed.", file=sys.stderr)
        return 2
    engine = runtime.engine
    if getattr(engine, "engine", None) == "real" and not getattr(engine, "gcb_enabled", True):
        print("ERROR: GCB_SECONDARY_ENABLED=false; there is nothing to index.", file=sys.stderr)
        return 2

    from app.domain.errors import VectorStoreError
    from app.infrastructure.vector_store.chroma_adapter import ChromaVectorStoreAdapter, collection_name_for_engine

    name = collection_name_for_engine(engine)
    if store is None:
        try:
            store = ChromaVectorStoreAdapter(name, fingerprint=engine.embedding_fingerprint)
        except VectorStoreError as exc:
            print(f"ERROR: vector store unavailable ({exc.reason}).", file=sys.stderr)
            return 2
    if session_maker is None:
        from app.infrastructure.database.session import async_session_maker as session_maker

    report = asyncio.run(reindex_references(session_maker, engine, store, apply=args.apply))
    mode = "DRY RUN (use --apply to write)" if report.dry_run else "applied"
    print(f"{mode}: collection={name} references={report.total} indexed={report.indexed} failures={len(report.failures)}")
    for ref_id, reason in report.failures:
        print(f"  failed {ref_id}: {reason}", file=sys.stderr)
    return exit_code(report)


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())

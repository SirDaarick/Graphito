"""Give every existing teacher the example group "Ejemplo" (backfill for accounts that predate it).

New accounts get the group at sign-up; this script loops over all `Docente` rows and calls
`ExampleService.ensure_examples` for each. It is idempotent: a teacher who already has the complete
group is reported as skipped, a partial or deleted group is completed. References are embedded with
the configured engine (`INFERENCE_MODE`) and indexed in the fingerprinted vector-store collection,
exactly like a catalog adoption, so run it with the same settings as the backend.

Each teacher is seeded in its own session, so one failure does not stop the rest. Exit codes: 0 ok,
1 at least one teacher failed (printed), 2 the engine or vector store is not usable.

Usage (repository root, with the backend settings in `.env` or the environment):
  python scripts/seed_examples.py
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# (docente_id, email, "created" | "skipped" | "failed: <reason>")
Result = Tuple[int, str, str]


async def seed_all(session_maker, engine, store, *, fixture_path: Optional[Path] = None) -> List[Result]:
    """Ensure the example group for every teacher, one session each."""
    from sqlalchemy import select

    from app.application.services.example_service import ExampleService
    from app.infrastructure.database.models import Docente

    async with session_maker() as session:
        teachers = [(d.id, d.email) for d in (await session.execute(select(Docente).order_by(Docente.id))).scalars()]

    results: List[Result] = []
    for docente_id, email in teachers:
        async with session_maker() as session:
            try:
                summary = await ExampleService(session, engine, store, fixture_path).ensure_examples(docente_id)
            except Exception as exc:  # ensure_examples already removed what it created; keep going
                reason = getattr(exc, "reason", None) or type(exc).__name__
                results.append((docente_id, email, f"failed: {reason}"))
            else:
                results.append((docente_id, email, "created" if summary.creado else "skipped"))
    return results


def exit_code(results: Sequence[Result]) -> int:
    return 1 if any(status.startswith("failed") for _, _, status in results) else 0


def run(argv: Optional[Sequence[str]] = None, *, runtime=None, session_maker=None, store=None, fixture_path=None) -> int:
    if runtime is None:
        from app.infrastructure.inference.runtime import build_runtime

        runtime = build_runtime()
    if not runtime.ready or runtime.engine is None:
        print(f"ERROR: inference engine not ready ({runtime.reason}); nothing seeded.", file=sys.stderr)
        return 2
    engine = runtime.engine

    if store is None:
        from app.domain.errors import VectorStoreError
        from app.infrastructure.vector_store.chroma_adapter import ChromaVectorStoreAdapter, collection_name_for_engine

        try:
            store = ChromaVectorStoreAdapter(collection_name_for_engine(engine), fingerprint=engine.embedding_fingerprint)
        except VectorStoreError as exc:
            print(f"ERROR: vector store unavailable ({exc.reason}).", file=sys.stderr)
            return 2
    if session_maker is None:
        from app.infrastructure.database.session import async_session_maker as session_maker

    results = asyncio.run(seed_all(session_maker, engine, store, fixture_path=fixture_path))
    for docente_id, email, status in results:
        print(f"teacher {docente_id} ({email}): {status}")
    created = sum(1 for _, _, s in results if s == "created")
    skipped = sum(1 for _, _, s in results if s == "skipped")
    failed = len(results) - created - skipped
    print(f"teachers={len(results)} created={created} skipped={skipped} failed={failed}")
    return exit_code(results)


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())

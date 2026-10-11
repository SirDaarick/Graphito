"""Apply `migrations/migration_features.sql` to the configured database (spec MG1; design D13).

Each statement runs on its own on an AUTOCOMMIT connection, so `ALTER TYPE ... ADD VALUE` is never
inside a transaction block and one failure cannot silently abort the statements after it. The run
stops at the first failing statement and exits 1; nothing after it is executed. Every statement in
the file is idempotent, so a successful run can be repeated.

Order: start the backend once (`create_all` creates missing tables), then run this script.

Usage (from backend/ or inside the backend container):
  python apply_migrations.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Awaitable, Callable, List, Sequence

MIGRATION_FILE = Path(__file__).parent / "migrations" / "migration_features.sql"

Execute = Callable[[str], Awaitable[object]]


def split_statements(sql: str) -> List[str]:
    """Split a SQL script into single statements (pure).

    Full-line `--` comments and blank lines are dropped. A statement ends at a line ending in `;`
    outside a `$$ ... $$` block (an odd number of `$$` on a line toggles the block).
    """
    statements: List[str] = []
    current: List[str] = []
    in_dollar_block = False
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or (stripped.startswith("--") and not current):
            continue
        if line.count("$$") % 2 == 1:
            in_dollar_block = not in_dollar_block
        current.append(line.rstrip())
        if not in_dollar_block and stripped.endswith(";"):
            statement = "\n".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
    if current:
        tail = "\n".join(current).strip()
        if tail:
            statements.append(tail)
    return statements


async def run_statements(statements: Sequence[str], execute: Execute) -> int:
    """Run statements in order; on the first failure report it and return 1 (later ones never run)."""
    for index, statement in enumerate(statements, start=1):
        try:
            await execute(statement)
        except Exception as exc:
            print(
                f"ERROR: statement {index}/{len(statements)} failed; nothing after it was run.\n"
                f"{statement[:200]}\nDetail: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 1
        print(f"ok {index}/{len(statements)}: {' '.join(statement.split())[:80]}")
    print(f"Migration completed: {len(statements)} statements applied.")
    return 0


async def run_migrations(path: Path = MIGRATION_FILE, engine=None) -> int:
    if not path.exists():
        print(f"ERROR: migration file not found: {path}", file=sys.stderr)
        return 1
    statements = split_statements(path.read_text(encoding="utf-8"))
    owns_engine = engine is None  # a caller-provided engine is never disposed here
    if owns_engine:
        from app.infrastructure.database import session as session_module

        engine = session_module.engine
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")

            async def execute(statement: str):
                # AUTOCOMMIT: every statement is its own transaction.
                return await conn.execute(text(statement))

            return await run_statements(statements, execute)
    except Exception as exc:
        print(f"ERROR: could not connect or run migrations: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if owns_engine:
            await engine.dispose()


def main() -> int:
    return asyncio.run(run_migrations())


if __name__ == "__main__":
    sys.exit(main())

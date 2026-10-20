from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from app.config import settings

def build_engine_options(cfg) -> dict:
    """Engine options derived from settings (pure).

    Remote Postgres (Supabase) drops idle connections, so every checkout is pinged first.
    Behind a transaction-mode pooler (pgbouncer, port 6543) asyncpg's prepared statements break,
    so `DB_POOLER_COMPAT` turns their caches off. SQLite (tests) gets neither option.
    """
    if not cfg.DATABASE_URL.startswith("postgresql"):
        return {}
    options: dict = {"pool_pre_ping": True}
    if cfg.DB_POOLER_COMPAT:
        options["connect_args"] = {"statement_cache_size": 0, "prepared_statement_cache_size": 0}
    return options


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    **build_engine_options(settings),
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

from types import SimpleNamespace

from app.infrastructure.database.session import build_engine_options


def _settings(url: str, pooler_compat: bool) -> SimpleNamespace:
    return SimpleNamespace(DATABASE_URL=url, DB_POOLER_COMPAT=pooler_compat)


def test_postgres_always_pings_connections_before_use():
    options = build_engine_options(_settings("postgresql+asyncpg://u:p@h:5432/db", False))
    assert options["pool_pre_ping"] is True
    assert "connect_args" not in options


def test_pooler_compat_disables_asyncpg_statement_cache():
    options = build_engine_options(_settings("postgresql+asyncpg://u:p@h:6543/db", True))
    assert options["connect_args"] == {"statement_cache_size": 0, "prepared_statement_cache_size": 0}


def test_sqlite_never_receives_postgres_only_options():
    options = build_engine_options(_settings("sqlite+aiosqlite:///:memory:", True))
    assert "pool_pre_ping" not in options
    assert "connect_args" not in options

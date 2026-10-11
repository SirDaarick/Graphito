"""Schema migration (spec MG1.1-MG1.4; design D13, D14).

`apply_migrations.py` splits the SQL file into single statements, runs each in its own AUTOCOMMIT
transaction and stops at the first failure with a non-zero exit code. The SQL file is checked
statically (idempotent DDL); the fresh-database shape is checked through `create_all` on SQLite.
"""

import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import inspect as sa_inspect, select

import apply_migrations
from app.infrastructure.database.models import (
    CodigoFuente,
    DictamenEnum,
    Docente,
    Problema,
    ReporteAnalisis,
    TipoCodigoEnum,
)

SQL_FILE = Path(apply_migrations.__file__).parent / "migrations" / "migration_features.sql"
SQL = SQL_FILE.read_text(encoding="utf-8")
STATEMENTS = apply_migrations.split_statements(SQL)

NEW_COLUMNS = {
    "puntaje_calibrado_a", "engine", "estado_canal_a", "estado_canal_b", "flag_a", "flag_b", "umbral_a",
    "umbral_b", "calibracion_sha_a", "calibracion_sha_b", "checkpoint_sha_b", "canal_a_metodo",
    "gcb_similarity", "gcb_estado", "manifest_sha",
}
NULLABLE_SCORES = ("similitud_semantica", "probabilidad_ia", "discrepancia_score", "dictamen")


def test_split_statements_is_pure_and_keeps_enum_additions_separate():
    assert apply_migrations.split_statements(SQL) == STATEMENTS  # deterministic, no side effects
    enum_adds = [s for s in STATEMENTS if re.match(r"(?is)^ALTER\s+TYPE\s+dictamenenum\s+ADD\s+VALUE", s)]
    assert [re.search(r"'(\w+)'", s).group(1) for s in enum_adds] == ["NO_EVALUABLE", "SIN_REFERENCIA"]
    assert all(s.count(";") == 1 and s.endswith(";") for s in enum_adds)
    do_blocks = [s for s in STATEMENTS if s.startswith("DO $$")]
    assert len(do_blocks) == 1 and do_blocks[0].rstrip().endswith("END $$;")
    assert not any(s.lstrip().startswith("--") for s in STATEMENTS)


def test_split_statements_handles_inline_dollar_blocks_and_comments():
    sql = "-- c\nA;\nDO $$ BEGIN PERFORM 1; END $$;\nB\n  ;\n"
    assert apply_migrations.split_statements(sql) == ["A;", "DO $$ BEGIN PERFORM 1; END $$;", "B\n  ;"]


@pytest.mark.asyncio
async def test_stops_at_first_failing_statement():
    executed = []

    async def execute(stmt):
        executed.append(stmt)
        if len(executed) == 3:
            raise RuntimeError("boom")

    code = await apply_migrations.run_statements(["s1;", "s2;", "s3;", "s4;", "s5;"], execute)
    assert code != 0
    assert executed == ["s1;", "s2;", "s3;"]  # statements 4+ never run


@pytest.mark.asyncio
async def test_all_statements_succeed_exit_zero():
    executed = []

    async def execute(stmt):
        executed.append(stmt)

    assert await apply_migrations.run_statements(["a;", "b;"], execute) == 0
    assert executed == ["a;", "b;"]


def test_main_propagates_failure_exit_code(monkeypatch):
    async def failing(path=None, engine=None):
        return 1

    monkeypatch.setattr(apply_migrations, "run_migrations", failing)
    assert apply_migrations.main() == 1


def test_sql_enum_additions_and_columns_are_idempotent():
    for stmt in STATEMENTS:
        flat = " ".join(stmt.split()).upper()
        if "ADD VALUE" in flat:
            assert "ADD VALUE IF NOT EXISTS" in flat, stmt
        if re.search(r"\bADD COLUMN\b", flat):
            assert "ADD COLUMN IF NOT EXISTS" in flat, stmt
        if flat.startswith("CREATE TABLE") or flat.startswith("CREATE INDEX"):
            assert "IF NOT EXISTS" in flat, stmt


def test_sql_section_8_shape():
    flat = [" ".join(s.split()) for s in STATEMENTS]
    added = {m.group(1) for s in flat for m in [re.search(r"reportes_analisis ADD COLUMN IF NOT EXISTS (\w+)", s)] if m}
    assert NEW_COLUMNS <= added
    for col in NULLABLE_SCORES:
        assert f"ALTER TABLE reportes_analisis ALTER COLUMN {col} DROP NOT NULL;" in flat
    assert "UPDATE reportes_analisis SET engine = 'legacy' WHERE engine IS NULL;" in flat
    # enum values are added before anything can use them, and the legacy marking runs last
    assert flat.index("UPDATE reportes_analisis SET engine = 'legacy' WHERE engine IS NULL;") == len(flat) - 1


def test_model_defines_the_migrated_columns():
    columns = ReporteAnalisis.__table__.columns
    assert NEW_COLUMNS <= set(columns.keys())
    for col in (*NEW_COLUMNS, *NULLABLE_SCORES):
        assert columns[col].nullable, col
    assert {"NO_EVALUABLE", "SIN_REFERENCIA"} <= {m.value for m in DictamenEnum}


@pytest.mark.asyncio
async def test_create_all_round_trips_null_scores_and_no_evaluable(db_session):
    docente = Docente(email=f"{uuid.uuid4().hex}@x.mx", hashed_password="x", nombre="D")
    db_session.add(docente)
    await db_session.flush()
    problema = Problema(docente_id=docente.id, titulo="T", enunciado="E")
    db_session.add(problema)
    await db_session.flush()
    entrega = CodigoFuente(problema_id=problema.id, tipo=TipoCodigoEnum.ENTREGA_ALUMNO, autor="A", contenido="int x;")
    db_session.add(entrega)
    await db_session.flush()
    db_session.add(ReporteAnalisis(
        entrega_id=entrega.id, similitud_semantica=None, probabilidad_ia=None, discrepancia_score=None,
        dictamen=DictamenEnum.NO_EVALUABLE, engine="stub", estado_canal_a="SIN_REFERENCIA",
        estado_canal_b="ABSTENIDO", flag_a=None, flag_b=None, gcb_similarity=None,
    ))
    await db_session.commit()
    db_session.expunge_all()

    row = (await db_session.execute(select(ReporteAnalisis))).scalar_one()
    assert row.similitud_semantica is None and row.probabilidad_ia is None and row.discrepancia_score is None
    assert row.dictamen == DictamenEnum.NO_EVALUABLE and row.engine == "stub"
    assert row.estado_canal_b == "ABSTENIDO" and row.flag_b is None

    # A row persisted before scoring (PENDIENTE) has no dictamen yet.
    db_session.add(ReporteAnalisis(entrega_id=entrega.id))
    await db_session.commit()
    rows = (await db_session.execute(select(ReporteAnalisis).order_by(ReporteAnalisis.id))).scalars().all()
    assert rows[-1].dictamen is None

    async with db_session.bind.connect() as conn:
        names = await conn.run_sync(lambda c: {col["name"] for col in sa_inspect(c).get_columns("reportes_analisis")})
    assert NEW_COLUMNS <= names

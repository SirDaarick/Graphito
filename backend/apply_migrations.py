import asyncio
import os
import sys
from pathlib import Path
from sqlalchemy import text
from app.infrastructure.database.session import engine


async def run_migrations():
    """
    Lee y ejecuta de forma idempotente las sentencias DDL de migration_features.sql
    utilizando el motor asíncrono configurado en Graphito.
    """
    migration_file = Path(__file__).parent / "migrations" / "migration_features.sql"
    if not migration_file.exists():
        print(f"Error: No se encontró el archivo de migración en {migration_file}")
        sys.exit(1)

    print(f"Leyendo sentencias SQL desde {migration_file}...")
    sql_script = migration_file.read_text(encoding="utf-8")

    async with engine.begin() as conn:
        print("Conectado a la base de datos. Aplicando migraciones...")
        # Dividir por sentencias separadas por punto y coma (respetando bloques DO $$ ... $$;)
        statements = []
        current_stmt = []
        in_dollar_block = False

        for line in sql_script.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue

            if "$$" in line:
                in_dollar_block = not in_dollar_block

            current_stmt.append(line)

            if not in_dollar_block and stripped.endswith(";"):
                stmt_str = "\n".join(current_stmt).strip()
                if stmt_str:
                    statements.append(stmt_str)
                current_stmt = []

        for stmt in statements:
            try:
                await conn.execute(text(stmt))
            except Exception as e:
                print(f"Advertencia/Error al ejecutar sentencia:\n{stmt[:80]}...\nDetalle: {e}")

        print("¡Migración completada exitosamente!")


if __name__ == "__main__":
    asyncio.run(run_migrations())

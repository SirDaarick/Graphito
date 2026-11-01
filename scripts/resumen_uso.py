"""Summarize platform usage from the `eventos_uso` table (the monitoring chapter's source of numbers).

Reads the database in `DATABASE_URL` (the backend's `.env`) and prints a JSON summary: active
teachers, requests per day, HTTP errors, analyses by verdict and mode, and p50/p95/max durations
per stage. The proportion of flagged analyses per week comes from `reportes_analisis`, to spot
drift in what the models flag.

Usage (from the repository root):
    python scripts/resumen_uso.py [--desde 2026-11-01] [--hasta 2026-11-30] [--zona America/Mexico_City]
                                  [--salida resumen.json]

Days, weeks and the --desde/--hasta bounds use --zona (Mexico City by default); the database stores UTC.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from zoneinfo import ZoneInfo  # noqa: E402

from sqlalchemy import select, text  # noqa: E402

from app.application.services.usage_summary import in_zone, summarize_events  # noqa: E402
from app.infrastructure.database.models import EventoUso  # noqa: E402
from app.infrastructure.database.session import async_session_maker, engine  # noqa: E402


def _parse_day(value: str, tz, end: bool = False) -> datetime:
    """Start (or end) of a calendar day in `tz`, as an aware datetime."""
    day = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=tz)
    return day.replace(hour=23, minute=59, second=59) if end else day


async def _weekly_flag_rate(session, since, until, tz) -> list:
    """Share of completed analyses with a style or similarity alert, per ISO week."""
    rows = (await session.execute(text(
        "SELECT fecha_analisis, flag_a, flag_b FROM reportes_analisis "
        "WHERE estado = 'COMPLETADO' AND fecha_analisis >= :since AND fecha_analisis <= :until"
    ), {"since": since, "until": until})).all()
    weeks: dict = {}
    for fecha, flag_a, flag_b in rows:
        if isinstance(fecha, str):
            fecha = datetime.fromisoformat(fecha)
        key = "%d-W%02d" % in_zone(fecha, tz).isocalendar()[:2]
        n, a, b = weeks.get(key, (0, 0, 0))
        weeks[key] = (n + 1, a + bool(flag_a), b + bool(flag_b))
    return [
        {"semana": k, "analisis": n, "con_alerta_similitud": a, "con_alerta_estilo": b}
        for k, (n, a, b) in sorted(weeks.items())
    ]


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--desde", default="1970-01-01")
    ap.add_argument("--hasta", default="2999-12-31")
    ap.add_argument("--salida", type=Path)
    ap.add_argument("--zona", default="America/Mexico_City",
                    help="IANA time zone for days, weeks and --desde/--hasta (default: America/Mexico_City; UTC for raw)")
    args = ap.parse_args()
    tz = ZoneInfo(args.zona)
    since = _parse_day(args.desde, tz).astimezone(timezone.utc)
    until = _parse_day(args.hasta, tz, end=True).astimezone(timezone.utc)

    async with async_session_maker() as session:
        res = await session.execute(
            select(EventoUso).where(EventoUso.created_at >= since, EventoUso.created_at <= until).order_by(EventoUso.id)
        )
        events = [
            {
                "tipo": e.tipo, "created_at": e.created_at, "docente_id": e.docente_id,
                "duracion_ms": e.duracion_ms, "estado_http": e.estado_http, "ruta": e.ruta, "detalle": e.detalle,
            }
            for e in res.scalars().all()
        ]
        summary = summarize_events(events, tz=tz)
        summary["zona_horaria"] = args.zona
        summary["alertas_por_semana"] = await _weekly_flag_rate(session, since, until, tz)
    await engine.dispose()

    out = json.dumps(summary, indent=2, ensure_ascii=False, default=str)
    if args.salida:
        args.salida.write_text(out, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    asyncio.run(main())

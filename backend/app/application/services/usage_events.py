"""Usage events: a best-effort audit trail of what teachers do and how long the models take.

`record_event` opens its own session and never raises, so a broken event store can slow nothing
down and fail nothing. Events hold ids, routes, durations and outcomes only (see `EventoUso`).
"""
import logging
import time
from typing import Any, Awaitable, Dict, Optional, TypeVar

import app.infrastructure.database.session as db_session
from app.infrastructure.database.models import EventoUso

logger = logging.getLogger("graphito-events")

T = TypeVar("T")


async def record_event(
    tipo: str,
    *,
    docente_id: Optional[int] = None,
    metodo: Optional[str] = None,
    ruta: Optional[str] = None,
    estado_http: Optional[int] = None,
    duracion_ms: Optional[float] = None,
    detalle: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        async with db_session.async_session_maker() as session:
            session.add(
                EventoUso(
                    tipo=tipo,
                    docente_id=docente_id,
                    metodo=metodo,
                    ruta=ruta[:200] if ruta else None,
                    estado_http=estado_http,
                    duracion_ms=None if duracion_ms is None else round(duracion_ms, 2),
                    detalle=detalle,
                )
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001 - the event log must never break a request
        logger.warning("No se pudo registrar el evento %s: %s", tipo, type(exc).__name__)


async def record_analysis(
    modo: str,
    *,
    docente_id: Optional[int],
    outcome: Any,
    entrega: Any,
    duracion_ms: float,
) -> None:
    """One `analisis` event: how it ended, how long each stage took, never the code itself."""
    await record_event(
        "analisis",
        docente_id=docente_id,
        duracion_ms=duracion_ms,
        detalle={
            "modo": modo,  # individual | asincrono | lote
            "problema_id": entrega.problema_id,
            "lenguaje": entrega.lenguaje,
            "n_caracteres": len(entrega.contenido or ""),
            "dictamen": outcome.dictamen,
            "estado_canal_a": outcome.estado_canal_a,
            "estado_canal_b": outcome.estado_canal_b,
            "gcb_estado": outcome.provenance.get("gcb_estado"),
            "tiempos_ms": outcome.provenance.get("tiempos_ms"),
        },
    )


def route_template(path: str, path_params: Optional[Dict[str, Any]]) -> str:
    """`/problems/5` -> `/problems/{problem_id}`: the route as declared, so ids never reach the log.

    Replaces the path segment equal to each matched parameter value with `{name}`.
    """
    segments = path.split("/")
    for name, value in (path_params or {}).items():
        for i, segment in enumerate(segments):
            if segment == str(value):
                segments[i] = "{" + name + "}"
                break
    return "/".join(segments)


def elapsed_ms(start: float) -> float:
    """Milliseconds since `start` (a `time.perf_counter()` value)."""
    return (time.perf_counter() - start) * 1000.0


async def timed(timings: Dict[str, float], stage: str, awaitable: Awaitable[T]) -> T:
    """Await `awaitable` and store its duration in ms under `timings[stage]`, also when it raises."""
    start = time.perf_counter()
    try:
        return await awaitable
    finally:
        timings[stage] = round(elapsed_ms(start), 2)

"""Summary of the usage-event log: who used the platform, how much, and how long the stages took.

Pure functions over event dicts (`tipo`, `created_at`, `docente_id`, `duracion_ms`, `estado_http`,
`ruta`, `detalle`), so they run on any database and are easy to test.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone, tzinfo
from typing import Any, Dict, Iterable, List, Optional


def percentile(values: List[float], q: float) -> Optional[float]:
    """Linear-interpolation percentile (`q` in 0..100); None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * q / 100.0
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _stats(values: List[float]) -> Optional[Dict[str, Any]]:
    if not values:
        return None
    return {
        "n": len(values),
        "p50": round(percentile(values, 50), 2),
        "p95": round(percentile(values, 95), 2),
        "max": round(max(values), 2),
    }


def in_zone(moment: datetime, tz: Optional[tzinfo]) -> datetime:
    """`moment` in `tz` (UTC when None); a naive datetime (SQLite) is taken as UTC."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(tz or timezone.utc)


def summarize_events(events: Iterable[Dict[str, Any]], tz: Optional[tzinfo] = None) -> Dict[str, Any]:
    """Summary of the log; the per-day counts use `tz` days (UTC by default)."""
    rows = list(events)
    by_type = Counter(r["tipo"] for r in rows)
    teachers = {r["docente_id"] for r in rows if r.get("docente_id") is not None}

    requests = [r for r in rows if r["tipo"] == "peticion"]
    per_day = Counter(in_zone(r["created_at"], tz).strftime("%Y-%m-%d") for r in requests)
    http_errors = Counter(str(r["estado_http"]) for r in requests if (r.get("estado_http") or 0) >= 400)

    analyses = [r for r in rows if r["tipo"] == "analisis"]
    totals = [float(r["duracion_ms"]) for r in analyses if r.get("duracion_ms") is not None]
    stages: Dict[str, List[float]] = defaultdict(list)
    for r in analyses:
        for stage, ms in ((r.get("detalle") or {}).get("tiempos_ms") or {}).items():
            stages[stage].append(float(ms))

    uploads = [r.get("detalle") or {} for r in rows if r["tipo"] == "carga_lote"]
    return {
        "eventos_por_tipo": dict(by_type),
        "docentes_activos": len(teachers),
        "peticiones_por_dia": dict(sorted(per_day.items())),
        "peticiones_con_error": dict(http_errors),
        "peticion_duracion_ms": _stats([float(r["duracion_ms"]) for r in requests if r.get("duracion_ms") is not None]),
        "analisis": {
            "total": len(analyses),
            "errores": by_type.get("analisis_error", 0),
            "por_dictamen": dict(Counter((r.get("detalle") or {}).get("dictamen") for r in analyses)),
            "por_modo": dict(Counter((r.get("detalle") or {}).get("modo") for r in analyses)),
            "duracion_ms": _stats(totals),
            "tiempos_por_etapa_ms": {stage: _stats(vals) for stage, vals in stages.items()},
        },
        "cargas": {
            "lotes": len(uploads),
            "archivos": sum(u.get("n_archivos", 0) for u in uploads),
            "bytes": sum(u.get("bytes", 0) for u in uploads),
            "ignorados": sum(u.get("n_ignorados", 0) for u in uploads),
        },
    }

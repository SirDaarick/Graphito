from datetime import datetime, timezone

from app.application.services.usage_summary import percentile, summarize_events


def _ev(tipo, day, docente=1, ms=None, estado=None, ruta=None, detalle=None):
    return {
        "tipo": tipo, "created_at": datetime(2026, 11, day, 10, tzinfo=timezone.utc), "docente_id": docente,
        "duracion_ms": ms, "estado_http": estado, "ruta": ruta, "detalle": detalle or {},
    }


def _analysis(day, docente, total, dictamen, modo="individual", b=10.0):
    return _ev("analisis", day, docente, total, detalle={
        "modo": modo, "dictamen": dictamen, "estado_canal_a": "EVALUADO", "estado_canal_b": "EVALUADO",
        "tiempos_ms": {"canal_a": 5.0, "canal_b": b, "gcb": 20.0, "puntuacion": total - 1},
    })


def test_percentile_is_linear_and_handles_empty_and_single_values():
    assert percentile([], 50) is None
    assert percentile([7.0], 95) == 7.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5
    assert percentile([1.0, 2.0, 3.0, 4.0, 5.0], 100) == 5.0


def test_summary_counts_people_days_and_analyses():
    rows = [
        _ev("peticion", 1, 1, 12.0, 200, "/api/v1/problems/"),
        _ev("peticion", 1, 2, 30.0, 200, "/api/v1/problems/"),
        _ev("peticion", 2, 1, 50.0, 503, "/api/v1/analysis/run"),
        _ev("peticion", 2, None, 3.0, 401, "/api/v1/problems/"),
        _analysis(1, 1, 100.0, "SIN_ALERTAS"),
        _analysis(2, 2, 300.0, "REVISION_ESTILOMETRICA", modo="lote", b=40.0),
        _ev("carga_lote", 2, 2, None, detalle={"n_archivos": 12, "bytes": 2048, "n_ignorados": 1}),
        _ev("analisis_error", 2, 1, 9.0, detalle={"error": "InferenceError"}),
    ]

    s = summarize_events(rows)

    assert s["docentes_activos"] == 2
    assert s["eventos_por_tipo"] == {"peticion": 4, "analisis": 2, "carga_lote": 1, "analisis_error": 1}
    assert s["peticiones_por_dia"] == {"2026-11-01": 2, "2026-11-02": 2}
    assert s["peticiones_con_error"] == {"401": 1, "503": 1}
    assert s["analisis"]["total"] == 2 and s["analisis"]["errores"] == 1
    assert s["analisis"]["por_dictamen"] == {"SIN_ALERTAS": 1, "REVISION_ESTILOMETRICA": 1}
    assert s["analisis"]["por_modo"] == {"individual": 1, "lote": 1}
    assert s["analisis"]["duracion_ms"]["p50"] == 200.0
    assert s["analisis"]["tiempos_por_etapa_ms"]["canal_b"] == {"n": 2, "p50": 25.0, "p95": 38.5, "max": 40.0}
    assert s["cargas"] == {"lotes": 1, "archivos": 12, "bytes": 2048, "ignorados": 1}


def test_summary_of_an_empty_log_is_all_zeros_not_an_error():
    s = summarize_events([])

    assert s["docentes_activos"] == 0 and s["analisis"]["total"] == 0 and s["analisis"]["duracion_ms"] is None
    assert s["eventos_por_tipo"] == {} and s["cargas"]["lotes"] == 0

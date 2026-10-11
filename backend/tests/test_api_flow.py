import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "inference_mode" in data


@pytest.mark.asyncio
async def test_complete_graphito_flow(client: AsyncClient):
    # 1. Registro de Docente
    reg_payload = {
        "email": "erick.profesor@escom.ipn.mx",
        "password": "PasswordSegura123!",
        "nombre": "Prof. Erick Daniel",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201, reg_res.text
    docente_data = reg_res.json()
    assert docente_data["email"] == reg_payload["email"]

    # 2. Login
    login_payload = {
        "email": reg_payload["email"],
        "password": reg_payload["password"],
    }
    login_res = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    token_data = login_res.json()
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. S1: Crear Problema / Ejercicio
    prob_payload = {
        "titulo": "Suma de Arreglos Dinámicos en C",
        "enunciado": "Escriba un programa en C que solicite N enteros y calcule la suma total en memoria dinámica.",
        "lenguaje": "c",
    }
    prob_res = await client.post("/api/v1/problems/", json=prob_payload, headers=headers)
    assert prob_res.status_code == 201
    prob_data = prob_res.json()
    problema_id = prob_data["id"]

    # 4. Agregar Código de Referencia (Indexación Vectorial 769-d)
    ref_code = """
    #include <stdio.h>
    #include <stdlib.h>
    int main() {
        int n, sum = 0;
        scanf("%d", &n);
        int *arr = (int*)malloc(n * sizeof(int));
        for(int i = 0; i < n; i++) {
            scanf("%d", &arr[i]);
            sum += arr[i];
        }
        printf("%d\\n", sum);
        free(arr);
        return 0;
    }
    """
    ref_res = await client.post(
        f"/api/v1/problems/{problema_id}/references",
        params={"autor": "Solucion_Oficial_Docente", "contenido": ref_code, "lenguaje": "c"},
        headers=headers,
    )
    assert ref_res.status_code == 201
    ref_data = ref_res.json()
    assert ref_data["tipo"] == "REFERENCIA"
    assert ref_data["id"] is not None

    # 5. S2: Cargar Entrega de Alumno
    student_code = """
    // Entrega del Alumno
    #include <stdio.h>
    #include <stdlib.h>
    int main() {
        int cantidad;
        scanf("%d", &cantidad);
        int *datos = malloc(cantidad * sizeof(int));
        int total = 0;
        for(int j = 0; j < cantidad; j++) {
            scanf("%d", &datos[j]);
            total += datos[j];
        }
        printf("%d\\n", total);
        free(datos);
        return 0;
    }
    """
    sub_payload = {
        "problema_id": problema_id,
        "autor": "Boleta_2020630001",
        "contenido": student_code,
        "lenguaje": "c",
    }
    sub_res = await client.post(
        f"/api/v1/problems/{problema_id}/submissions",
        json=sub_payload,
        headers=headers,
    )
    assert sub_res.status_code == 201
    sub_data = sub_res.json()
    entrega_id = sub_data["id"]

    # 6. S3 a S7: Disparar Análisis Bimodal (Inferencia Concurrente + ChromaDB + Reporte)
    analysis_payload = {
        "entrega_id": entrega_id,
        "threshold_sem": 0.85,
        "threshold_ai": 0.70,
    }
    an_res = await client.post("/api/v1/analysis/run", json=analysis_payload, headers=headers)
    assert an_res.status_code == 201, an_res.text
    report_data = an_res.json()
    
    assert report_data["id"] is not None
    assert "similitud_semantica" in report_data
    assert "probabilidad_ia" in report_data
    assert "discrepancia_score" in report_data
    assert "dictamen" in report_data
    assert isinstance(report_data["indicadores"], list)
    assert len(report_data["indicadores"]) > 0

    # 7. Consultar Reporte por ID
    report_id = report_data["id"]
    get_rep_res = await client.get(f"/api/v1/analysis/reports/{report_id}", headers=headers)
    assert get_rep_res.status_code == 200
    fetched_report = get_rep_res.json()
    assert fetched_report["id"] == report_id
    assert fetched_report["entrega_id"] == entrega_id
    assert fetched_report["estado"] == "COMPLETADO"

    # 8. Descargar Reporte en PDF
    pdf_res = await client.get(f"/api/v1/analysis/reports/{report_id}/pdf", headers=headers)
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF")
    assert len(pdf_res.content) > 500

    # 9. Ejecutar Inferencia Asíncrona (async_mode=true)
    async_res = await client.post(
        "/api/v1/analysis/run?async_mode=true",
        json=analysis_payload,
        headers=headers,
    )
    assert async_res.status_code == 201
    async_data = async_res.json()
    async_report_id = async_data["id"]
    assert async_data["estado"] in ("PROCESANDO", "COMPLETADO")

    # Esperar y verificar que la tarea asíncrona concluya
    import asyncio
    for _ in range(20):
        await asyncio.sleep(0.1)
        poll_res = await client.get(f"/api/v1/analysis/reports/{async_report_id}", headers=headers)
        if poll_res.status_code == 200 and poll_res.json()["estado"] == "COMPLETADO":
            break
    poll_final = await client.get(f"/api/v1/analysis/reports/{async_report_id}", headers=headers)
    assert poll_final.status_code == 200
    assert poll_final.json()["estado"] == "COMPLETADO"
    assert len(poll_final.json()["indicadores"]) > 0


# --- shared ScoringService across single, async and batch (spec AS1, AS4.4, AS5, AS8, BF1.2) ------

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.infrastructure.database.models import ReporteAnalisis

AS12_FIELDS = (
    "similitud_semantica", "puntaje_calibrado_a", "probabilidad_ia", "flag_a", "flag_b", "estado_canal_a",
    "estado_canal_b", "umbral_a", "umbral_b", "dictamen", "referencia_id", "engine", "canal_a_metodo",
    "calibracion_sha_a", "calibracion_sha_b", "checkpoint_sha_b", "manifest_sha", "gcb_similarity",
    "gcb_estado", "discrepancia_score",
)
REF_C = """#include <stdio.h>
int main(void) {
    int n, i, total = 0;
    scanf("%d", &n);
    for (i = 0; i < n; i++) { total += i; }
    printf("%d\\n", total);
    return 0;
}
"""
STUDENT_C = """#include <stdio.h>
int main(void) {
    int n, i, total = 0;
    scanf("%d", &n);
    for (i = 0; i < n; i++) { total += i * 2; }
    printf("%d\\n", total);
    return 0;
}
"""
# >= 60 non-whitespace chars and no stub "synthetic" keywords: Channel B evaluated, not flagged.
PLAIN_C = "int suma(int a, int b) {\n    int r = a + b;\n    return r;\n}\nint resta(int a, int b) { return a - b; }\n"


async def _login(client, email):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "PasswordSegura123!", "nombre": "P"})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "PasswordSegura123!"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _problem(client, headers, *, reference=True):
    prob = await client.post("/api/v1/problems/", json={"titulo": "Suma", "enunciado": "Suma.", "lenguaje": "c"}, headers=headers)
    problema_id = prob.json()["id"]
    if reference:
        ref = await client.post(
            f"/api/v1/problems/{problema_id}/references",
            params={"autor": "Docente", "contenido": REF_C, "lenguaje": "c"}, headers=headers,
        )
        assert ref.status_code == 201, ref.text
    return problema_id


async def _submit(client, headers, problema_id, code):
    sub = await client.post(
        f"/api/v1/problems/{problema_id}/submissions",
        json={"problema_id": problema_id, "autor": "A1", "contenido": code, "lenguaje": "c"}, headers=headers,
    )
    assert sub.status_code == 201, sub.text
    return sub.json()["id"]


async def _row(db_session, report_id):
    """A detached snapshot of the persisted report and its indicators (safe after later expiries)."""
    db_session.expire_all()
    res = await db_session.execute(
        select(ReporteAnalisis).options(selectinload(ReporteAnalisis.indicadores)).where(ReporteAnalisis.id == report_id)
    )
    row = res.scalar_one()
    snap = {c.key: getattr(row, c.key) for c in ReporteAnalisis.__table__.columns}
    snap["indicadores"] = [
        SimpleNamespace(tipo_alerta=i.tipo_alerta, descripcion=i.descripcion, severidad=i.severidad, categoria=i.categoria)
        for i in row.indicadores
    ]
    return SimpleNamespace(**snap)


def _fields(row):
    return {f: getattr(row, f) for f in AS12_FIELDS}


def _decision_indicators(row):
    return sorted((i.tipo_alerta, i.descripcion, i.severidad) for i in row.indicadores if i.categoria == "GENERAL")


async def _wait_batch(db_session, batch_id):
    for _ in range(50):
        await asyncio.sleep(0.05)
        db_session.expire_all()
        res = await db_session.execute(select(ReporteAnalisis).where(ReporteAnalisis.lote_id == batch_id))
        rows = res.scalars().all()
        if rows and all(r.estado.value in ("COMPLETADO", "ERROR") for r in rows):
            return rows
    raise AssertionError("batch did not finish")


@pytest.mark.asyncio
async def test_single_async_and_batch_share_one_scoring(client, db_session):
    headers = await _login(client, "parity@escom.ipn.mx")
    problema_id = await _problem(client, headers)
    entrega_id = await _submit(client, headers, problema_id, STUDENT_C)

    single = await client.post("/api/v1/analysis/run", json={"entrega_id": entrega_id}, headers=headers)
    assert single.status_code == 201, single.text
    single_row = await _row(db_session, single.json()["id"])
    assert single_row.engine == "stub" and single_row.estado_canal_a == "EVALUADO"
    assert single_row.discrepancia_score is None

    started = await client.post("/api/v1/analysis/run?async_mode=true", json={"entrega_id": entrega_id}, headers=headers)
    assert started.status_code == 201 and started.json()["dictamen"] is None  # no placeholder verdict
    for _ in range(50):
        await asyncio.sleep(0.05)
        async_row = await _row(db_session, started.json()["id"])
        if async_row.estado.value == "COMPLETADO":
            break
    assert async_row.estado.value == "COMPLETADO"

    batch = await client.post(
        "/api/v1/analysis/batch", data={"problema_id": str(problema_id)},
        files={"files": ("2020630001_ana_perez.c", STUDENT_C.encode("utf-8"), "text/plain")}, headers=headers,
    )
    assert batch.status_code == 202, batch.text
    [batch_row] = await _wait_batch(db_session, uuid_from(batch.json()["batch_id"]))
    batch_row = await _row(db_session, batch_row.id)

    assert _fields(async_row) == _fields(single_row)
    assert _fields(batch_row) == _fields(single_row)
    assert _decision_indicators(batch_row) == _decision_indicators(single_row)  # AS1.3
    if single_row.flag_a or single_row.flag_b:
        assert _decision_indicators(batch_row), "batch must persist decision indicators for flagged results"


def uuid_from(value):
    import uuid

    return uuid.UUID(value)


@pytest.mark.asyncio
async def test_batch_persists_decision_indicators_for_flagged_results(client, db_session):
    headers = await _login(client, "batchflag@escom.ipn.mx")
    problema_id = await _problem(client, headers)
    batch = await client.post(
        "/api/v1/analysis/batch", data={"problema_id": str(problema_id)},
        files={"files": ("copia.c", REF_C.encode("utf-8"), "text/plain")}, headers=headers,
    )
    [row] = await _wait_batch(db_session, uuid_from(batch.json()["batch_id"]))
    row = await _row(db_session, row.id)
    assert row.flag_a is True and row.flag_b is True and row.dictamen.value == "DISCREPANCIA_DUAL"
    assert [t for t, _, _ in _decision_indicators(row)] == ["DISCREPANCIA_ESTILOMETRICA"]


@pytest.mark.asyncio
async def test_client_thresholds_have_no_effect(client, db_session):
    headers = await _login(client, "thr@escom.ipn.mx")
    problema_id = await _problem(client, headers)
    entrega_id = await _submit(client, headers, problema_id, PLAIN_C)
    plain = await client.post("/api/v1/analysis/run", json={"entrega_id": entrega_id}, headers=headers)
    low = await client.post(
        "/api/v1/analysis/run", json={"entrega_id": entrega_id, "threshold_sem": 0.01, "threshold_ai": 0.01}, headers=headers,
    )
    assert plain.status_code == low.status_code == 201
    a, b = await _row(db_session, plain.json()["id"]), await _row(db_session, low.json()["id"])
    assert _fields(a) == _fields(b)
    assert a.umbral_a == 0.5 and a.umbral_b == 0.5  # stub calibration thresholds, not the client's


@pytest.mark.asyncio
async def test_gcb_signal_never_decides_and_failure_is_null(client, db_session, vector_store, monkeypatch):
    headers = await _login(client, "gcb@escom.ipn.mx")
    problema_id = await _problem(client, headers)
    entrega_id = await _submit(client, headers, problema_id, STUDENT_C)
    rows = []
    for sim in (0.99, 0.0):
        async def fixed(embedding, problema_id, top_k=1, sim=sim):
            return [{"reference_id": "x", "similarity": sim, "distance": 1 - sim, "metadata": {}}]

        monkeypatch.setattr(vector_store, "query_nearest", fixed)
        res = await client.post("/api/v1/analysis/run", json={"entrega_id": entrega_id}, headers=headers)
        assert res.status_code == 201, res.text
        rows.append(await _row(db_session, res.json()["id"]))
    monkeypatch.undo()
    hi, lo = rows
    assert (hi.gcb_similarity, lo.gcb_similarity) == (0.99, 0.0)
    assert (hi.flag_a, hi.flag_b, hi.dictamen) == (lo.flag_a, lo.flag_b, lo.dictamen)

    vector_store.fail = True
    res = await client.post("/api/v1/analysis/run", json={"entrega_id": entrega_id}, headers=headers)
    assert res.status_code == 201, res.text
    failed = await _row(db_session, res.json()["id"])
    assert failed.gcb_similarity is None and failed.gcb_estado == "ERROR"
    assert failed.dictamen == hi.dictamen


@pytest.mark.asyncio
async def test_no_conformidad_indicator_for_sin_referencia_or_no_evaluable(client, db_session):
    headers = await _login(client, "noref@escom.ipn.mx")
    problema_id = await _problem(client, headers, reference=False)
    for code, expected in ((PLAIN_C, "SIN_REFERENCIA"), ("int x;", "NO_EVALUABLE")):
        entrega_id = await _submit(client, headers, problema_id, code)
        res = await client.post("/api/v1/analysis/run", json={"entrega_id": entrega_id}, headers=headers)
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["dictamen"] == expected and body["similitud_semantica"] is None
        row = await _row(db_session, body["id"])
        assert row.estado_canal_a == "SIN_REFERENCIA"
        assert not any(i.tipo_alerta == "CONFORMIDAD_BASE" for i in row.indicadores)
        assert _decision_indicators(row) == []
        if expected == "NO_EVALUABLE":
            assert row.probabilidad_ia is None and row.estado_canal_b == "ABSTENIDO"
            assert body["probabilidad_ia"] is None
        pdf = await client.get(f"/api/v1/analysis/reports/{body['id']}/pdf", headers=headers)
        assert pdf.status_code == 200


def test_no_backend_module_imports_models_fusion():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    pattern = re.compile(r"^\s*(from\s+models(\.fusion\b|\s+import\s+[^#\n]*\bfusion\b)|import\s+models\.fusion\b)", re.M)
    offenders = [str(p) for p in app_dir.rglob("*.py") if pattern.search(p.read_text(encoding="utf-8"))]
    assert offenders == []

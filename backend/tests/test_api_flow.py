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

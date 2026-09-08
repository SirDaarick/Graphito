#!/usr/bin/env python3
"""
test_e2e_analysis.py - Prueba de integración End-to-End del pipeline bimodal con PostgreSQL y ChromaDB.
Verifica:
  1. Persistencia relacional de Docente, Problema, Código Fuente.
  2. Indexación vectorial en ChromaDB (769 dimensiones).
  3. Ejecución del orquestador de análisis con inferencia real (GraphCodeBERT + MultiScaleCharCNN).
  4. Generación de ReporteAnalisis e Indicadores de Integridad según diseño de tesis.
"""

import asyncio
import uuid
from sqlalchemy import select
from app.infrastructure.database.session import async_session_maker, engine, Base
import app.infrastructure.database.models as db_models
from app.infrastructure.database.models import (
    Docente, Problema, CodigoFuente, ReporteAnalisis, IndicadorIntegridad,
    TipoCodigoEnum, DictamenEnum, EstadoAnalisisEnum
)
from app.infrastructure.inference.real_engine import RealBimodalInferenceEngine
from app.infrastructure.vector_store.chroma_adapter import ChromaVectorStoreAdapter
from app.application.orchestrator.analysis_orchestrator import AnalysisOrchestrator
from app.presentation.schemas.analysis import AnalysisRunRequest
from app.config import settings

# Configurar para usar servidor ChromaDB local
settings.USE_CHROMA_SERVER = True
settings.CHROMA_HOST = "localhost"
settings.CHROMA_PORT = 8001


async def run_e2e_test():
    print("=" * 60)
    print("INICIANDO PRUEBA END-TO-END DE PERSISTENCIA Y ANÁLISIS BIMODAL")
    print("=" * 60)

    # 1. Asegurar tablas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tablas PostgreSQL verificadas.")

    # 2. Inicializar adaptadores
    inference_engine = RealBimodalInferenceEngine()
    vector_store = ChromaVectorStoreAdapter()
    print("✅ Motores de inferencia y almacenamiento vectorial inicializados.")

    async with async_session_maker() as session:
        # 3. Crear Docente de prueba si no existe
        res = await session.execute(select(Docente).where(Docente.email == "profesor_test@escom.ipn.mx"))
        docente = res.scalar_one_or_none()
        if not docente:
            docente = Docente(
                email="profesor_test@escom.ipn.mx",
                hashed_password="fakehashedpassword",
                nombre="Profesor Auditor ESCOM"
            )
            session.add(docente)
            await session.commit()
            await session.refresh(docente)
        print(f"✅ Docente registrado: ID={docente.id}, Nombre='{docente.nombre}'")

        # 4. Crear Problema
        problema = Problema(
            docente_id=docente.id,
            titulo="Cálculo de Factorial Recursivo e Iterativo",
            enunciado="Escribir una función en C que calcule el factorial de un entero n positivo.",
            lenguaje="c"
        )
        session.add(problema)
        await session.commit()
        await session.refresh(problema)
        print(f"✅ Problema creado: ID={problema.id}, Título='{problema.titulo}'")

        # 5. Crear Código de Referencia
        ref_code_str = """
#include <stdio.h>

long long factorial(int n) {
    long long fact = 1;
    for (int i = 1; i <= n; i++) {
        fact *= i;
    }
    return fact;
}

int main() {
    int n = 5;
    printf("%lld\\n", factorial(n));
    return 0;
}
"""
        ref_code = CodigoFuente(
            id=uuid.uuid4(),
            problema_id=problema.id,
            tipo=TipoCodigoEnum.REFERENCIA,
            autor="Cátedra ESCOM",
            contenido=ref_code_str,
            lenguaje="c"
        )
        session.add(ref_code)
        await session.commit()
        await session.refresh(ref_code)

        # Indexar en ChromaDB con tensor híbrido (769 dims)
        ref_hybrid_emb = await inference_engine.generate_hybrid_embedding(ref_code.contenido, lang="c")
        assert len(ref_hybrid_emb) == 769, f"Esperado 769 dims, obtenido {len(ref_hybrid_emb)}"
        await vector_store.upsert_reference(
            reference_id=str(ref_code.id),
            embedding=ref_hybrid_emb,
            metadata={"problema_id": problema.id, "lenguaje": "c"},
            document=ref_code.contenido
        )
        print(f"✅ Código de Referencia indexado en PostgreSQL y ChromaDB (769 dims, UUID={ref_code.id})")

        # 6. Crear Entrega de Alumno (variación de factorial con punteros y while)
        student_code_str = """
#include <stdio.h>

void calcular_factorial(int *n, long long *res) {
    *res = 1;
    int i = 1;
    while (i <= *n) {
        *res = (*res) * i;
        i++;
    }
}

int main() {
    int num = 5;
    long long r;
    calcular_factorial(&num, &r);
    printf("%lld\\n", r);
    return 0;
}
"""
        entrega = CodigoFuente(
            id=uuid.uuid4(),
            problema_id=problema.id,
            tipo=TipoCodigoEnum.ENTREGA_ALUMNO,
            autor="Boleta 2026630001",
            contenido=student_code_str,
            lenguaje="c"
        )
        session.add(entrega)
        await session.commit()
        await session.refresh(entrega)
        print(f"✅ Entrega de Alumno persistida en PostgreSQL: UUID={entrega.id}")

        # 7. Ejecutar Análisis Orquestado Bimodal
        orchestrator = AnalysisOrchestrator(
            db=session,
            inference_engine=inference_engine,
            vector_store=vector_store
        )

        print("\n--- Ejecutando Orquestación del Análisis ---")
        request = AnalysisRunRequest(entrega_id=entrega.id)
        reporte_response = await orchestrator.execute_analysis(
            docente_id=docente.id,
            request=request
        )

        print(f"✅ Análisis completado con éxito:")
        print(f"  Reporte ID:             {reporte_response.id}")
        print(f"  Referencia Coincidente: {reporte_response.referencia_id}")
        print(f"  Similitud Semántica:    {reporte_response.similitud_semantica:.4f}")
        print(f"  Probabilidad Sintética: {reporte_response.probabilidad_ia:.4f}")
        print(f"  Dictamen:               {reporte_response.dictamen}")
        print(f"  Estado:                 {reporte_response.estado}")
        print(f"  Indicadores de Alerta:  {len(reporte_response.indicadores)}")

        # 8. Verificaciones de Integridad
        assert reporte_response.referencia_id == ref_code.id, "ChromaDB no recuperó la referencia correcta!"
        assert reporte_response.similitud_semantica > 0.80, f"Similitud semántica baja ({reporte_response.similitud_semantica})"
        assert reporte_response.estado == EstadoAnalisisEnum.COMPLETADO

        # Verificar persistencia en base de datos
        db_rep = (await session.execute(select(ReporteAnalisis).where(ReporteAnalisis.id == reporte_response.id))).scalar_one()
        assert db_rep is not None
        assert db_rep.entrega_id == entrega.id
        assert db_rep.referencia_id == ref_code.id

        print("\n" + "=" * 60)
        print("🎉 PRUEBA END-TO-END EXITOSA: El sistema real funciona de punta a punta!")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_e2e_test())

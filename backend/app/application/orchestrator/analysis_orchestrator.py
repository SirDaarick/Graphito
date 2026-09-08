import uuid
import asyncio
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.infrastructure.database.models import (
    CodigoFuente,
    ReporteAnalisis,
    IndicadorIntegridad,
    TipoCodigoEnum,
    DictamenEnum,
)
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.presentation.schemas.analysis import (
    AnalysisRunRequest,
    ReporteAnalisisResponse,
    IndicadorResponse,
)


class AnalysisOrchestrator:
    """
    Orquestador del Ciclo de Vida del Análisis Bimodal (Estados S1 a S7).
    Coordina la bifurcación, inferencia concurrente, búsqueda en ChromaDB y generación del reporte.
    """

    def __init__(
        self,
        db: AsyncSession,
        inference_engine: InferencePort,
        vector_store: VectorStorePort,
    ):
        self.db = db
        self.inference = inference_engine
        self.vector_store = vector_store

    async def execute_analysis(
        self,
        docente_id: int,
        request: AnalysisRunRequest,
    ) -> ReporteAnalisisResponse:
        # S2: Validar entrega
        result = await self.db.execute(
            select(CodigoFuente).where(CodigoFuente.id == request.entrega_id)
        )
        entrega = result.scalar_one_or_none()
        if not entrega or entrega.tipo != TipoCodigoEnum.ENTREGA_ALUMNO:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entrega de alumno no encontrada.",
            )

        # S3, S4, S5: Inferencia Concurrente Bimodal
        # Ejecutar en paralelo Canal A (Semántica) y Canal B (Estilometría)
        semantic_task = self.inference.extract_semantic_embedding(
            entrega.contenido, lang=entrega.lenguaje
        )
        prob_task = self.inference.predict_synthetic_prob(entrega.contenido)
        
        semantic_vector, ai_prob = await asyncio.gather(semantic_task, prob_task)
        hybrid_vector = semantic_vector + [ai_prob]

        # S6: Búsqueda Vectorial de la Referencia más Cercana
        target_ref_id: Optional[uuid.UUID] = None
        semantic_sim = 0.0

        if request.referencia_id:
            # Caso referencia específica
            target_ref_id = request.referencia_id
            # Calcular similitud directa usando el vector híbrido
            ref_res = await self.db.execute(
                select(CodigoFuente).where(CodigoFuente.id == request.referencia_id)
            )
            ref_code = ref_res.scalar_one_or_none()
            if ref_code:
                ref_sem = await self.inference.extract_semantic_embedding(
                    ref_code.contenido, lang=ref_code.lenguaje
                )
                # Cosine similarity
                dot = sum(a * b for a, b in zip(semantic_vector, ref_sem))
                norm_a = sum(a * a for a in semantic_vector) ** 0.5 or 1.0
                norm_b = sum(b * b for b in ref_sem) ** 0.5 or 1.0
                semantic_sim = max(0.0, min(1.0, dot / (norm_a * norm_b)))
        else:
            # Consulta por vecinos más cercanos en ChromaDB para el problema
            matches = await self.vector_store.query_nearest(
                embedding=hybrid_vector,
                problema_id=entrega.problema_id,
                top_k=1,
            )
            if matches:
                matched_str_id = matches[0]["reference_id"]
                target_ref_id = uuid.UUID(matched_str_id)
                semantic_sim = matches[0]["similarity"]
            else:
                # Si no hay referencias cargadas aún para el problema
                semantic_sim = 0.0

        # Cálculo de Decisión e Indicadores
        decision = self.inference.compute_decision(
            semantic_similarity=semantic_sim,
            synthetic_prob=ai_prob,
            threshold_sem=request.threshold_sem,
            threshold_ai=request.threshold_ai,
        )

        # S7: Consolidar y Persistir Reporte
        reporte = ReporteAnalisis(
            entrega_id=entrega.id,
            referencia_id=target_ref_id,
            similitud_semantica=round(semantic_sim, 4),
            probabilidad_ia=round(ai_prob, 4),
            discrepancia_score=decision["discrepancia_score"],
            dictamen=DictamenEnum(decision["dictamen"]),
        )
        self.db.add(reporte)
        await self.db.flush()

        for ind in decision["indicadores"]:
            indicador_obj = IndicadorIntegridad(
                reporte_id=reporte.id,
                tipo_alerta=ind["tipo_alerta"],
                descripcion=ind["descripcion"],
                severidad=ind["severidad"],
            )
            self.db.add(indicador_obj)

        await self.db.commit()

        # Cargar con relaciones para la respuesta
        final_res = await self.db.execute(
            select(ReporteAnalisis)
            .options(selectinload(ReporteAnalisis.indicadores))
            .where(ReporteAnalisis.id == reporte.id)
        )
        saved_report = final_res.scalar_one()

        return ReporteAnalisisResponse(
            id=saved_report.id,
            entrega_id=saved_report.entrega_id,
            referencia_id=saved_report.referencia_id,
            similitud_semantica=saved_report.similitud_semantica,
            probabilidad_ia=saved_report.probabilidad_ia,
            discrepancia_score=saved_report.discrepancia_score,
            dictamen=saved_report.dictamen,
            fecha_analisis=saved_report.fecha_analisis,
            indicadores=[
                IndicadorResponse(
                    id=i.id,
                    tipo_alerta=i.tipo_alerta,
                    descripcion=i.descripcion,
                    severidad=i.severidad,
                )
                for i in saved_report.indicadores
            ],
        )

    async def get_report(self, report_id: int) -> ReporteAnalisisResponse:
        res = await self.db.execute(
            select(ReporteAnalisis)
            .options(selectinload(ReporteAnalisis.indicadores))
            .where(ReporteAnalisis.id == report_id)
        )
        report = res.scalar_one_or_none()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reporte de análisis no encontrado.",
            )
        return ReporteAnalisisResponse.model_validate(report)

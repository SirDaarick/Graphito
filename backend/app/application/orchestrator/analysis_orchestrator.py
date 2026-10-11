import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import logging
from app.infrastructure.database.models import (
    CodigoFuente,
    ReporteAnalisis,
    ComentarioRevision,
    TipoCodigoEnum,
    EstadoAnalisisEnum,
    DecisionDocenteEnum,
)
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.application.services.scoring_service import ScoringService
from app.presentation.schemas.analysis import (
    AnalysisRunRequest,
    ReporteAnalisisResponse,
)

logger = logging.getLogger("graphito-backend")


class AnalysisOrchestrator:
    """
    Orquestador del ciclo de vida del análisis (S1 a S7).
    La medición y el dictamen los produce únicamente `ScoringService` (spec AS1.1); este
    orquestador solo valida, crea o carga la fila del reporte, delega y confirma la transacción.
    """

    def __init__(
        self,
        db: AsyncSession,
        inference_engine: Optional[InferencePort] = None,
        vector_store: Optional[VectorStorePort] = None,
        scoring: Optional[ScoringService] = None,
    ):
        self.db = db
        self.inference = inference_engine
        self.vector_store = vector_store
        self.scoring = scoring

    def _require_scoring(self) -> ScoringService:
        if self.scoring is None:
            raise RuntimeError("AnalysisOrchestrator needs a ScoringService to run analyses")
        return self.scoring

    async def _load_entrega(self, entrega_id: uuid.UUID) -> CodigoFuente:
        result = await self.db.execute(select(CodigoFuente).where(CodigoFuente.id == entrega_id))
        entrega = result.scalar_one_or_none()
        if not entrega or entrega.tipo != TipoCodigoEnum.ENTREGA_ALUMNO:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entrega de alumno no encontrada.",
            )
        return entrega

    async def execute_analysis(
        self,
        docente_id: int,
        request: AnalysisRunRequest,
    ) -> ReporteAnalisisResponse:
        scoring = self._require_scoring()
        scoring.warn_client_thresholds(request.threshold_sem, request.threshold_ai)
        entrega = await self._load_entrega(request.entrega_id)

        # S3-S6: medir y decidir antes de escribir nada (un error aquí no deja filas).
        outcome = await scoring.score(self.db, entrega, request.referencia_id)

        # S7: persistir reporte, indicadores de decisión y filas XAI heurísticas.
        reporte = ReporteAnalisis(entrega_id=entrega.id, estado=EstadoAnalisisEnum.PROCESANDO, engine=outcome.engine)
        self.db.add(reporte)
        await self.db.flush()
        scoring.persist(self.db, reporte, outcome, entrega)
        await self.db.commit()
        return await self.get_report(reporte.id)

    async def start_async_analysis(
        self,
        docente_id: int,
        request: AnalysisRunRequest,
    ) -> ReporteAnalisisResponse:
        scoring = self._require_scoring()
        scoring.warn_client_thresholds(request.threshold_sem, request.threshold_ai)
        entrega = await self._load_entrega(request.entrega_id)
        # A pinned reference from another problem is rejected before anything is written.
        await scoring.resolve_references(self.db, entrega, request.referencia_id)

        # Fila en PROCESANDO sin puntajes ni dictamen (NULL hasta que se evalúe).
        reporte = ReporteAnalisis(
            entrega_id=entrega.id,
            referencia_id=request.referencia_id,
            estado=EstadoAnalisisEnum.PROCESANDO,
            engine=scoring.engine_label,
        )
        self.db.add(reporte)
        await self.db.commit()
        response = await self.get_report(reporte.id)  # snapshot before the task can complete it

        asyncio.create_task(
            self._process_async_task(
                report_id=reporte.id,
                entrega_id=entrega.id,
                referencia_id=request.referencia_id,
            )
        )
        return response

    async def _process_async_task(
        self,
        report_id: int,
        entrega_id: uuid.UUID,
        referencia_id: Optional[uuid.UUID],
    ):
        from app.infrastructure.database.session import async_session_maker

        scoring = self._require_scoring()
        async with async_session_maker() as session:
            try:
                res = await session.execute(select(CodigoFuente).where(CodigoFuente.id == entrega_id))
                entrega = res.scalar_one_or_none()
                if not entrega:
                    raise ValueError(f"Entrega {entrega_id} no encontrada en tarea asíncrona")
                outcome = await scoring.score(session, entrega, referencia_id)
                rep_res = await session.execute(select(ReporteAnalisis).where(ReporteAnalisis.id == report_id))
                reporte = rep_res.scalar_one()
                scoring.persist(session, reporte, outcome, entrega)
                await session.commit()
                logger.info(f"Reporte {report_id} completado con éxito de forma asíncrona.")
            except Exception as e:
                logger.error(f"Error en inferencia asíncrona para reporte {report_id}: {e}", exc_info=True)
                await session.rollback()
                rep_res = await session.execute(select(ReporteAnalisis).where(ReporteAnalisis.id == report_id))
                reporte = rep_res.scalar_one_or_none()
                if reporte:
                    reporte.estado = EstadoAnalisisEnum.ERROR
                    reporte.dictamen = None
                    reporte.error_mensaje = str(getattr(e, "reason", None) or type(e).__name__)
                    await session.commit()

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

    async def update_verdict(
        self,
        docente_id: int,
        report_id: int,
        verdict: DecisionDocenteEnum,
        notas: Optional[str] = None,
    ) -> ReporteAnalisisResponse:
        """
        Registra la decisión humana final del docente (Human-in-the-Loop)
        para active learning y seguimiento pedagógico institucional.
        """
        report = await self.get_report_model(report_id)
        # Validar que el reporte pertenezca al docente que creó el problema
        if (
            report.entrega
            and report.entrega.problema
            and report.entrega.problema.docente_id != docente_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para emitir dictamen sobre esta entrega.",
            )

        report.decision_docente = verdict
        report.fecha_decision = datetime.now(timezone.utc)
        if notas is not None:
            report.notas_docente = notas

        await self.db.commit()
        await self.db.refresh(report)

        return await self.get_report(report_id)

    async def get_report_model(self, report_id: int) -> ReporteAnalisis:
        res = await self.db.execute(
            select(ReporteAnalisis)
            .options(
                selectinload(ReporteAnalisis.indicadores),
                selectinload(ReporteAnalisis.entrega).selectinload(CodigoFuente.problema),
                selectinload(ReporteAnalisis.referencia),
                selectinload(ReporteAnalisis.comentarios).selectinload(ComentarioRevision.docente),
            )
            .where(ReporteAnalisis.id == report_id)
        )
        report = res.scalar_one_or_none()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reporte de análisis no encontrado.",
            )
        return report

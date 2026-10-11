import uuid
import asyncio
import logging

from typing import List, Tuple, Optional, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.infrastructure.database.models import (
    Docente,
    Problema,
    Grupo,
    CodigoFuente,
    ReporteAnalisis,
    LoteAnalisis,
    TipoCodigoEnum,
    EstadoAnalisisEnum,
)
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.application.services.scoring_service import ScoringService
from app.presentation.schemas.batch import BatchStatusResponse

logger = logging.getLogger("graphito-batch")


class BatchAnalysisService:
    def __init__(
        self,
        db: AsyncSession,
        inference: Optional[InferencePort] = None,
        vector_store: Optional[VectorStorePort] = None,
        scoring: Optional[ScoringService] = None,
    ):
        self.db = db
        self.inference = inference
        self.vector_store = vector_store
        self.scoring = scoring

    @property
    def engine_label(self) -> Optional[str]:
        if self.scoring is not None:
            return self.scoring.engine_label
        return getattr(self.inference, "engine", None) or None

    async def create_batch(
        self,
        docente_id: int,
        problema_id: int,
        grupo_id: Optional[int],
        files_data: List[Tuple[str, str, str]],  # (filename, content, author)
    ) -> uuid.UUID:
        # 1. Validar propiedad del problema
        prob_res = await self.db.execute(
            select(Problema).where(
                and_(Problema.id == problema_id, Problema.docente_id == docente_id)
            )
        )
        problema = prob_res.scalar_one_or_none()
        if not problema:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Problema {problema_id} no encontrado en tu biblioteca.",
            )

        # 2. Validar grupo si fue provisto
        if grupo_id:
            grp_res = await self.db.execute(
                select(Grupo).where(
                    and_(Grupo.id == grupo_id, Grupo.docente_id == docente_id)
                )
            )
            if not grp_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Grupo {grupo_id} no encontrado en tu cuenta.",
                )

        batch_id = uuid.uuid4()
        lote = LoteAnalisis(
            id=batch_id,
            problema_id=problema_id,
            docente_id=docente_id,
            grupo_id=grupo_id,
            total_archivos=len(files_data),
            procesados=0,
            errores=0,
            estado="PROCESANDO",
        )
        self.db.add(lote)

        # 3. Registrar archivos como CodigoFuente y ReporteAnalisis en estado PENDIENTE
        for filename, content, author in files_data:
            lenguaje = "cpp" if filename.lower().endswith((".cpp", ".cc")) else "c"
            codigo = CodigoFuente(
                problema_id=problema_id,
                grupo_id=grupo_id,
                tipo=TipoCodigoEnum.ENTREGA_ALUMNO,
                autor=author,
                contenido=content,
                lenguaje=lenguaje,
            )
            self.db.add(codigo)
            await self.db.flush()

            # Sin puntajes ni dictamen hasta que el worker lo evalúe (NULL, nunca 0).
            reporte = ReporteAnalisis(
                entrega_id=codigo.id,
                lote_id=batch_id,
                estado=EstadoAnalisisEnum.PENDIENTE,
                engine=self.engine_label,
            )
            self.db.add(reporte)

        await self.db.commit()
        return batch_id

    async def get_batch_status(
        self, docente_id: int, batch_id: uuid.UUID
    ) -> BatchStatusResponse:
        stmt = (
            select(LoteAnalisis)
            .options(selectinload(LoteAnalisis.reportes))
            .where(
                and_(
                    LoteAnalisis.id == batch_id,
                    LoteAnalisis.docente_id == docente_id,
                )
            )
        )
        res = await self.db.execute(stmt)
        lote = res.scalar_one_or_none()
        if not lote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lote de análisis {batch_id} no encontrado.",
            )

        total = lote.total_archivos
        completados = [
            r.id
            for r in lote.reportes
            if r.estado == EstadoAnalisisEnum.COMPLETADO
        ]
        procesados = len(completados)
        porcentaje = round((procesados / max(total, 1)) * 100, 1)

        return BatchStatusResponse(
            batch_id=lote.id,
            problema_id=lote.problema_id,
            total_archivos=total,
            procesados=procesados,
            errores=lote.errores,
            estado=lote.estado,
            porcentaje=porcentaje,
            reportes_completados=completados,
        )

    @classmethod
    def dispatch_batch_worker(
        cls,
        batch_id: uuid.UUID,
        problema_id: int,
        scoring: ScoringService,
    ):
        """
        Lanza la tarea en segundo plano no bloqueante usando asyncio.create_task.
        """
        asyncio.create_task(
            cls._process_batch_pipeline(
                batch_id=batch_id,
                problema_id=problema_id,
                scoring=scoring,
            )
        )

    @classmethod
    async def _process_batch_pipeline(
        cls,
        batch_id: uuid.UUID,
        problema_id: int,
        scoring: ScoringService,
    ):
        """Score every pending report of the batch with the shared ScoringService (spec AS1)."""
        from app.infrastructure.database.session import async_session_maker
        logger.info(f"Iniciando pipeline asíncrono para lote {batch_id}...")
        semaphore = asyncio.Semaphore(3)  # Máximo 3 análisis concurrentes (la inferencia se encola en el pool)

        async with async_session_maker() as session:
            stmt = (
                select(ReporteAnalisis)
                .where(
                    and_(
                        ReporteAnalisis.lote_id == batch_id,
                        ReporteAnalisis.estado == EstadoAnalisisEnum.PENDIENTE,
                    )
                )
            )
            res = await session.execute(stmt)
            reportes = [(r.id, r.entrega_id) for r in res.scalars().all()]

        async def _process_single_report(rep_id: int, entrega_id: uuid.UUID):
            async with semaphore:
                async with async_session_maker() as inner_session:
                    try:
                        ent_res = await inner_session.execute(
                            select(CodigoFuente).where(CodigoFuente.id == entrega_id)
                        )
                        entrega = ent_res.scalar_one_or_none()
                        if not entrega:
                            return

                        # Misma medición, dictamen e indicadores que el análisis individual.
                        outcome = await scoring.score(inner_session, entrega)

                        r_res = await inner_session.execute(
                            select(ReporteAnalisis).where(ReporteAnalisis.id == rep_id)
                        )
                        reporte = r_res.scalar_one()
                        scoring.persist(inner_session, reporte, outcome, entrega)

                        l_res = await inner_session.execute(
                            select(LoteAnalisis).where(LoteAnalisis.id == batch_id)
                        )
                        lote_obj = l_res.scalar_one_or_none()
                        if lote_obj:
                            lote_obj.procesados += 1

                        await inner_session.commit()
                    except Exception as err:
                        logger.error(f"Error procesando reporte {rep_id} del lote {batch_id}: {err}", exc_info=True)
                        try:
                            await inner_session.rollback()
                            r_res = await inner_session.execute(
                                select(ReporteAnalisis).where(ReporteAnalisis.id == rep_id)
                            )
                            reporte = r_res.scalar_one_or_none()
                            if reporte:
                                reporte.estado = EstadoAnalisisEnum.ERROR
                                reporte.dictamen = None
                                reporte.error_mensaje = str(getattr(err, "reason", None) or type(err).__name__)

                            l_res = await inner_session.execute(
                                select(LoteAnalisis).where(LoteAnalisis.id == batch_id)
                            )
                            lote_obj = l_res.scalar_one_or_none()
                            if lote_obj:
                                lote_obj.errores += 1

                            await inner_session.commit()
                        except Exception:
                            logger.exception(f"No se pudo marcar el reporte {rep_id} como ERROR.")

        tasks = [_process_single_report(rep_id, entrega_id) for rep_id, entrega_id in reportes]
        await asyncio.gather(*tasks)

        # Marcar lote como COMPLETADO
        async with async_session_maker() as final_session:
            l_res = await final_session.execute(
                select(LoteAnalisis).where(LoteAnalisis.id == batch_id)
            )
            lote_final = l_res.scalar_one_or_none()
            if lote_final:
                lote_final.estado = "COMPLETADO"
                await final_session.commit()
                logger.info(f"Lote {batch_id} completado con éxito.")

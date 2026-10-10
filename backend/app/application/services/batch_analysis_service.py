import uuid
import asyncio
import logging

from app.config import settings
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
    IndicadorIntegridad,
    LoteAnalisis,
    TipoCodigoEnum,
    DictamenEnum,
    EstadoAnalisisEnum,
)
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.application.services.xai_service import XAIService
from app.presentation.schemas.batch import BatchStatusResponse

logger = logging.getLogger("graphito-batch")


class BatchAnalysisService:
    def __init__(
        self,
        db: AsyncSession,
        inference: InferencePort,
        vector_store: VectorStorePort,
    ):
        self.db = db
        self.inference = inference
        self.vector_store = vector_store

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

            reporte = ReporteAnalisis(
                entrega_id=codigo.id,
                lote_id=batch_id,
                similitud_semantica=0.0,
                probabilidad_ia=0.0,
                discrepancia_score=0.0,
                dictamen=DictamenEnum.SIN_ALERTAS,
                estado=EstadoAnalisisEnum.PENDIENTE,
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
        inference: InferencePort,
        vector_store: VectorStorePort,
    ):
        """
        Lanza la tarea en segundo plano no bloqueante usando asyncio.create_task.
        """
        asyncio.create_task(
            cls._process_batch_pipeline(
                batch_id=batch_id,
                problema_id=problema_id,
                inference=inference,
                vector_store=vector_store,
            )
        )

    @classmethod
    async def _process_batch_pipeline(
        cls,
        batch_id: uuid.UUID,
        problema_id: int,
        inference: InferencePort,
        vector_store: VectorStorePort,
    ):
        from app.infrastructure.database.session import async_session_maker
        logger.info(f"Iniciando pipeline asíncrono para lote {batch_id}...")
        semaphore = asyncio.Semaphore(3)  # Máximo 3 inferencias concurrentes

        async with async_session_maker() as session:
            # Consultar todos los reportes pendientes del lote
            stmt = (
                select(ReporteAnalisis)
                .options(selectinload(ReporteAnalisis.entrega))
                .where(
                    and_(
                        ReporteAnalisis.lote_id == batch_id,
                        ReporteAnalisis.estado == EstadoAnalisisEnum.PENDIENTE,
                    )
                )
            )
            res = await session.execute(stmt)
            reportes = res.scalars().all()

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

                        # 1. Inferencia concurrente bimodal
                        sem_task = inference.extract_semantic_embedding(
                            entrega.contenido, lang=entrega.lenguaje
                        )
                        prob_task = inference.predict_synthetic_prob(entrega.contenido)
                        sem_vec, ai_prob = await asyncio.gather(sem_task, prob_task)

                        # 2. Búsqueda de referencia canónica en ChromaDB (768-dim semantic only)
                        matches = await vector_store.query_nearest(
                            embedding=sem_vec,
                            problema_id=problema_id,
                            top_k=1,
                        )
                        target_ref_id = None
                        raw_sim = 0.0
                        if matches:
                            target_ref_id = uuid.UUID(matches[0]["reference_id"])
                            raw_sim = matches[0]["similarity"]

                        # 3. Calibración de similitud semántica
                        baseline = 0.75
                        calibrated_sim = (
                            max(0.0, (raw_sim - baseline) / (1.0 - baseline))
                            if raw_sim > baseline
                            else 0.0
                        )

                        # 4. Decisión del orquestador
                        decision = inference.compute_decision(
                            semantic_similarity=calibrated_sim,
                            synthetic_prob=ai_prob,
                            threshold_sem=settings.THRESHOLD_SEM,
                            threshold_ai=settings.THRESHOLD_AI,
                        )

                        # 5. Generar explicaciones XAI línea por línea
                        xai_explanations = XAIService.extract_explanations(
                            code=entrega.contenido,
                            language=entrega.lenguaje,
                            semantic_sim=calibrated_sim,
                            ai_prob=ai_prob,
                        )

                        # 6. Actualizar reporte
                        r_res = await inner_session.execute(
                            select(ReporteAnalisis).where(ReporteAnalisis.id == rep_id)
                        )
                        reporte = r_res.scalar_one()
                        reporte.referencia_id = target_ref_id
                        reporte.similitud_semantica = round(calibrated_sim, 4)
                        reporte.probabilidad_ia = round(ai_prob, 4)
                        reporte.discrepancia_score = decision["discrepancia_score"]
                        reporte.dictamen = DictamenEnum(decision["dictamen"])
                        reporte.estado = EstadoAnalisisEnum.COMPLETADO

                        # Combinar indicadores básicos con explicaciones XAI
                        all_indicators = decision.get("indicadores", [])
                        for exp in xai_explanations:
                            ind_obj = IndicadorIntegridad(
                                reporte_id=reporte.id,
                                tipo_alerta=exp["tipo_alerta"],
                                descripcion=exp["descripcion"],
                                severidad=exp["severidad"],
                                numero_linea=exp["numero_linea"],
                                categoria=exp["categoria"],
                            )
                            inner_session.add(ind_obj)

                        # También actualizar contador en LoteAnalisis
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
                            r_res = await inner_session.execute(
                                select(ReporteAnalisis).where(ReporteAnalisis.id == rep_id)
                            )
                            reporte = r_res.scalar_one_or_none()
                            if reporte:
                                reporte.estado = EstadoAnalisisEnum.ERROR
                                reporte.error_mensaje = str(err)

                            l_res = await inner_session.execute(
                                select(LoteAnalisis).where(LoteAnalisis.id == batch_id)
                            )
                            lote_obj = l_res.scalar_one_or_none()
                            if lote_obj:
                                lote_obj.errores += 1

                            await inner_session.commit()
                        except Exception:
                            pass

        # Procesar secuencialmente o en grupos controlados
        tasks = [_process_single_report(r.id, r.entrega_id) for r in reportes]
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

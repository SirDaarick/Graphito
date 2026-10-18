import logging
from typing import List, Optional
import uuid
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.infrastructure.database.models import (
    CodigoFuente,
    ComentarioRevision,
    GrupoProblema,
    IndicadorIntegridad,
    LoteAnalisis,
    Problema,
    ReporteAnalisis,
    TipoCodigoEnum,
)
from app.domain.errors import InferenceError, VectorStoreError
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.presentation.schemas.problem import ProblemaCreate, ProblemaResponse
from app.presentation.schemas.submission import CodigoFuenteCreate, CodigoFuenteResponse
from app.presentation.schemas.analysis import ReporteAnalisisResponse

logger = logging.getLogger(__name__)

class ProblemService:
    def __init__(
        self,
        db: AsyncSession,
        inference_engine: Optional[InferencePort] = None,
        vector_store: Optional[VectorStorePort] = None,
    ):
        # Only reference creation needs the engine and the vector store; reads and problem or
        # submission CRUD work while inference is not ready.
        self.db = db
        self.inference = inference_engine
        self.vector_store = vector_store

    async def create_problem(self, docente_id: int, data: ProblemaCreate) -> ProblemaResponse:
        problema = Problema(
            docente_id=docente_id,
            titulo=data.titulo,
            enunciado=data.enunciado,
            lenguaje=data.lenguaje,
        )
        self.db.add(problema)
        await self.db.commit()
        await self.db.refresh(problema)
        return ProblemaResponse.model_validate(problema)

    async def list_problems(
        self, docente_id: int, include_archived: bool = False
    ) -> List[ProblemaResponse]:
        stmt = select(Problema).where(Problema.docente_id == docente_id)
        if not include_archived:
            stmt = stmt.where(Problema.archivado.is_(False))
        result = await self.db.execute(stmt)
        problemas = result.scalars().all()
        return [ProblemaResponse.model_validate(p) for p in problemas]

    async def set_archived(self, docente_id: int, problema_id: int, archived: bool) -> ProblemaResponse:
        problema = await self.get_problem(docente_id, problema_id)
        problema.archivado = archived
        await self.db.commit()
        await self.db.refresh(problema)
        return ProblemaResponse.model_validate(problema)

    async def delete_problem(self, docente_id: int, problema_id: int) -> None:
        """Delete a problem with its submissions, reports, batches, assignments and reference vectors.

        Vectors go first: if the store fails nothing is deleted (`VectorStoreError`, 503) and the
        teacher can retry. A failure after that leaves rows without vectors, which is harmless
        because queries are scoped by `problema_id`.
        """
        await self.get_problem(docente_id, problema_id)

        code_ids = (
            await self.db.execute(select(CodigoFuente.id).where(CodigoFuente.problema_id == problema_id))
        ).scalars().all()
        reference_ids = (
            await self.db.execute(
                select(CodigoFuente.id).where(
                    CodigoFuente.problema_id == problema_id,
                    CodigoFuente.tipo == TipoCodigoEnum.REFERENCIA,
                )
            )
        ).scalars().all()

        if reference_ids:
            if self.vector_store is None:
                raise VectorStoreError("vector_store_unavailable", "no vector store configured")
            for reference_id in reference_ids:
                try:
                    await self.vector_store.delete_reference(str(reference_id))
                except VectorStoreError:
                    raise
                except Exception as exc:
                    raise VectorStoreError(
                        "vector_store_delete_failed", f"{type(exc).__name__}: {exc}"
                    ) from exc

        # Explicit deletes: they do not depend on the DB enforcing ON DELETE (SQLite does not).
        if code_ids:
            report_ids = select(ReporteAnalisis.id).where(
                or_(
                    ReporteAnalisis.entrega_id.in_(code_ids),
                    ReporteAnalisis.referencia_id.in_(code_ids),
                )
            )
            await self.db.execute(delete(IndicadorIntegridad).where(IndicadorIntegridad.reporte_id.in_(report_ids)))
            await self.db.execute(delete(ComentarioRevision).where(ComentarioRevision.reporte_id.in_(report_ids)))
            await self.db.execute(
                delete(ReporteAnalisis).where(
                    or_(
                        ReporteAnalisis.entrega_id.in_(code_ids),
                        ReporteAnalisis.referencia_id.in_(code_ids),
                    )
                )
            )
            await self.db.execute(delete(CodigoFuente).where(CodigoFuente.id.in_(code_ids)))
        await self.db.execute(delete(LoteAnalisis).where(LoteAnalisis.problema_id == problema_id))
        await self.db.execute(delete(GrupoProblema).where(GrupoProblema.problema_id == problema_id))
        await self.db.execute(delete(Problema).where(Problema.id == problema_id))
        await self.db.commit()

    async def get_problem(self, docente_id: int, problema_id: int) -> Problema:
        result = await self.db.execute(
            select(Problema).where(Problema.id == problema_id, Problema.docente_id == docente_id)
        )
        problema = result.scalar_one_or_none()
        if not problema:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problema no encontrado.")
        return problema

    async def add_reference_code(
        self, docente_id: int, problema_id: int, autor: str, contenido: str, lenguaje: str = "c"
    ) -> CodigoFuenteResponse:
        """Embed before commit (spec RI1): embed -> add row (explicit id) -> flush -> upsert -> commit.

        An embedding failure raises `InferenceError` (503) with nothing written; an upsert failure
        rolls the row back (`VectorStoreError`, 503); a commit failure after the upsert removes the
        vector again. With the GraphCodeBERT secondary signal disabled (`gcb_disabled`) the row is
        stored without any vector; a placeholder embedding is never written.
        """
        await self.get_problem(docente_id, problema_id)

        semantic_vector: Optional[List[float]] = None
        try:
            semantic_vector = await self.inference.extract_semantic_embedding(contenido, lang=lenguaje)
        except InferenceError as exc:
            if exc.reason != "gcb_disabled":
                raise
            logger.info("GraphCodeBERT disabled: reference stored without a vector.")

        codigo = CodigoFuente(
            id=uuid.uuid4(),
            problema_id=problema_id,
            tipo=TipoCodigoEnum.REFERENCIA,
            autor=autor,
            contenido=contenido,
            lenguaje=lenguaje,
        )
        self.db.add(codigo)
        await self.db.flush()

        upserted = False
        if semantic_vector is not None:
            metadata = {
                "problema_id": problema_id,
                "autor": autor,
                "tipo": TipoCodigoEnum.REFERENCIA.value,
                "lenguaje": lenguaje,
            }
            try:
                await self.vector_store.upsert_reference(
                    reference_id=str(codigo.id),
                    embedding=semantic_vector,
                    metadata=metadata,
                    document=contenido,
                )
            except Exception as exc:
                await self.db.rollback()
                if isinstance(exc, VectorStoreError):
                    raise
                raise VectorStoreError("vector_store_write_failed", f"{type(exc).__name__}: {exc}") from exc
            upserted = True

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            if upserted:
                try:
                    await self.vector_store.delete_reference(str(codigo.id))
                except Exception as cleanup_exc:
                    logger.error(
                        "Compensation failed: vector %s stays in the store without a row (%s).",
                        codigo.id, type(cleanup_exc).__name__,
                    )
            raise
        await self.db.refresh(codigo)
        return CodigoFuenteResponse.model_validate(codigo)

    async def add_submission(
        self, docente_id: int, data: CodigoFuenteCreate
    ) -> CodigoFuenteResponse:
        # Validar problema
        await self.get_problem(docente_id, data.problema_id)

        codigo = CodigoFuente(
            problema_id=data.problema_id,
            grupo_id=data.grupo_id,
            tipo=TipoCodigoEnum.ENTREGA_ALUMNO,
            autor=data.autor,
            contenido=data.contenido,
            lenguaje=data.lenguaje,
        )
        self.db.add(codigo)
        await self.db.commit()
        await self.db.refresh(codigo)
        return CodigoFuenteResponse.model_validate(codigo)

    async def list_submissions(self, docente_id: int, problema_id: int) -> List[CodigoFuenteResponse]:
        await self.get_problem(docente_id, problema_id)
        result = await self.db.execute(
            select(CodigoFuente)
            .options(
                selectinload(CodigoFuente.reportes_entrega).selectinload(ReporteAnalisis.indicadores)
            )
            .where(
                CodigoFuente.problema_id == problema_id,
                CodigoFuente.tipo == TipoCodigoEnum.ENTREGA_ALUMNO,
            )
            .order_by(CodigoFuente.created_at.desc())
        )
        codigos = result.scalars().all()
        response_list: List[CodigoFuenteResponse] = []
        for c in codigos:
            resp = CodigoFuenteResponse.model_validate(c)
            if c.reportes_entrega:
                sorted_reports = sorted(
                    c.reportes_entrega,
                    key=lambda r: r.fecha_analisis,
                    reverse=True,
                )
                resp.reporte = ReporteAnalisisResponse.model_validate(sorted_reports[0])
            response_list.append(resp)
        return response_list

from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.infrastructure.database.models import Problema, CodigoFuente, TipoCodigoEnum
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.presentation.schemas.problem import ProblemaCreate, ProblemaResponse
from app.presentation.schemas.submission import CodigoFuenteCreate, CodigoFuenteResponse


class ProblemService:
    def __init__(
        self,
        db: AsyncSession,
        inference_engine: InferencePort,
        vector_store: VectorStorePort,
    ):
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

    async def list_problems(self, docente_id: int) -> List[ProblemaResponse]:
        result = await self.db.execute(select(Problema).where(Problema.docente_id == docente_id))
        problemas = result.scalars().all()
        return [ProblemaResponse.model_validate(p) for p in problemas]

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
        # Validar pertenencia del problema
        await self.get_problem(docente_id, problema_id)

        # 1. Guardar en PostgreSQL
        codigo = CodigoFuente(
            problema_id=problema_id,
            tipo=TipoCodigoEnum.REFERENCIA,
            autor=autor,
            contenido=contenido,
            lenguaje=lenguaje,
        )
        self.db.add(codigo)
        await self.db.commit()
        await self.db.refresh(codigo)

        # 2. Extraer vector híbrido (769 dimensiones)
        vector_769 = await self.inference.generate_hybrid_embedding(contenido, lang=lenguaje)

        # 3. Indexar en ChromaDB
        metadata = {
            "problema_id": problema_id,
            "autor": autor,
            "tipo": TipoCodigoEnum.REFERENCIA.value,
            "lenguaje": lenguaje,
        }
        await self.vector_store.upsert_reference(
            reference_id=str(codigo.id),
            embedding=vector_769,
            metadata=metadata,
            document=contenido,
        )

        return CodigoFuenteResponse.model_validate(codigo)

    async def add_submission(
        self, docente_id: int, data: CodigoFuenteCreate
    ) -> CodigoFuenteResponse:
        # Validar problema
        await self.get_problem(docente_id, data.problema_id)

        codigo = CodigoFuente(
            problema_id=data.problema_id,
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
            select(CodigoFuente).where(
                CodigoFuente.problema_id == problema_id,
                CodigoFuente.tipo == TipoCodigoEnum.ENTREGA_ALUMNO,
            )
        )
        return [CodigoFuenteResponse.model_validate(c) for c in result.scalars().all()]

import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.application.services.problem_service import ProblemService
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.infrastructure.catalog import CatalogEntry, get_catalog_entry, load_catalog
from app.infrastructure.catalog.json_catalog import unit_sort_key
from app.infrastructure.database.models import Problema
from app.presentation.schemas.catalog import (
    CatalogEntryDetail,
    CatalogEntrySummary,
    CatalogSubject,
    CatalogUnit,
)
from app.presentation.schemas.problem import ProblemaResponse

logger = logging.getLogger(__name__)

CATALOG_AUTHOR = "Catálogo ESCOM"

SUBJECT_ORDER = {
    "fundamentos_programación": 0,
    "algoritmos_estructuras_datos": 1,
    "analisis_diseño_algoritmos": 2,
}


class CatalogService:
    def __init__(
        self,
        db: AsyncSession,
        inference: Optional[InferencePort] = None,
        vector_store: Optional[VectorStorePort] = None,
    ):
        self.db = db
        self.inference = inference
        self.vector_store = vector_store

    def list_catalog(self) -> List[CatalogSubject]:
        """Programs grouped by subject then unit (units in numeral order); code is never included."""
        subjects: dict = {}
        for entry in load_catalog():
            subject = subjects.setdefault(
                entry.materia,
                CatalogSubject(materia=entry.materia, materia_nombre=entry.materia_nombre, total=0, unidades=[]),
            )
            unit = next((u for u in subject.unidades if u.unidad == entry.unidad), None)
            if unit is None:
                unit = CatalogUnit(unidad=entry.unidad, unidad_nombre=entry.unidad_nombre, programas=[])
                subject.unidades.append(unit)
            unit.programas.append(
                CatalogEntrySummary(
                    id=entry.id,
                    titulo=entry.titulo,
                    lenguaje=entry.lenguaje,
                    nombre_archivo=entry.nombre_archivo,
                    tema=entry.tema,
                )
            )
            subject.total += 1
        for subject in subjects.values():
            subject.unidades.sort(key=lambda u: unit_sort_key(u.unidad))
        return sorted(subjects.values(), key=lambda s: SUBJECT_ORDER.get(s.materia, 999))

    def _require_entry(self, entry_id: str) -> CatalogEntry:
        entry = get_catalog_entry(entry_id)
        if entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa de catálogo no encontrado.")
        return entry

    def get_entry(self, entry_id: str) -> CatalogEntryDetail:
        entry = self._require_entry(entry_id)
        return CatalogEntryDetail(
            id=entry.id,
            titulo=entry.titulo,
            lenguaje=entry.lenguaje,
            nombre_archivo=entry.nombre_archivo,
            materia=entry.materia,
            materia_nombre=entry.materia_nombre,
            unidad=entry.unidad,
            unidad_nombre=entry.unidad_nombre,
            codigo=entry.codigo,
            descripcion=entry.descripcion,
            tema=entry.tema,
        )

    async def use_entry(self, docente_id: int, entry_id: str) -> ProblemaResponse:
        """Adopt a catalog program: one Problema + REFERENCIA per (teacher, program), idempotent."""
        entry = self._require_entry(entry_id)

        existing = await self.db.execute(
            select(Problema)
            .where(Problema.docente_id == docente_id, Problema.catalogo_id == entry.id)
            .order_by(Problema.id)
            .limit(1)
        )
        problema = existing.scalars().first()
        if problema is not None:
            if problema.archivado:
                problema.archivado = False
                await self.db.commit()
                await self.db.refresh(problema)
            return ProblemaResponse.model_validate(problema)

        problema = Problema(
            docente_id=docente_id,
            titulo=entry.titulo,
            enunciado=entry.descripcion,
            lenguaje=entry.lenguaje,
            catalogo_id=entry.id,
        )
        self.db.add(problema)
        await self.db.commit()
        await self.db.refresh(problema)
        problema_id = problema.id

        try:
            await ProblemService(self.db, self.inference, self.vector_store).add_reference_code(
                docente_id, problema_id, CATALOG_AUTHOR, entry.codigo, entry.lenguaje
            )
        except Exception:
            # Leave nothing half-adopted so a retry starts clean; the original error keeps propagating
            # (InferenceError / VectorStoreError map to 503).
            await self.db.rollback()
            try:
                created = await self.db.get(Problema, problema_id)
                if created is not None:
                    await self.db.delete(created)
                    await self.db.commit()
            except Exception:
                await self.db.rollback()
                logger.error("Could not remove problem %s after a failed catalog adoption.", problema_id)
            raise

        await self.db.refresh(problema)
        return ProblemaResponse.model_validate(problema)

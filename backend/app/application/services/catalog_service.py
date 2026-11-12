import logging
from typing import List, Optional, Sequence
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.application.services.problem_service import ProblemService
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.infrastructure.catalog import CatalogEntry, get_catalog_entry, load_catalog
from app.infrastructure.catalog.json_catalog import unit_sort_key
from app.infrastructure.database.models import (
    CatalogoDocente,
    CodigoFuente,
    Problema,
    ProgramaCatalogo,
    TipoCodigoEnum,
    VarianteCatalogo,
    VarianteReferencia,
)
from app.presentation.schemas.catalog import (
    CatalogEntryDetail,
    CatalogEntrySummary,
    CatalogSubject,
    CatalogUnit,
)
from app.presentation.schemas.my_catalog import MyCatalogResponse, MyProgramCreate
from app.presentation.schemas.problem import ProblemaResponse

logger = logging.getLogger(__name__)

CATALOG_AUTHOR = "Catálogo ESCOM"
OWN_AUTHOR = "Catálogo propio"
OWN_PREFIX = "mio-"  # ids of a teacher's own programs; ESCOM ids are "<materia>--<slug>" so they never collide


def _file_name(program: ProgramaCatalogo) -> str:
    return f"{program.titulo}.{'cpp' if program.lenguaje == 'cpp' else 'c'}"


def _own_summary(program: ProgramaCatalogo) -> CatalogEntrySummary:
    return CatalogEntrySummary(
        id=f"{OWN_PREFIX}{program.id}",
        titulo=program.titulo,
        lenguaje=program.lenguaje,
        nombre_archivo=_file_name(program),
        tema="",
    )


def _own_entry(program: ProgramaCatalogo, catalog: CatalogoDocente) -> CatalogEntry:
    return CatalogEntry(
        id=f"{OWN_PREFIX}{program.id}",
        titulo=program.titulo,
        materia=f"{OWN_PREFIX}{catalog.id}",
        materia_nombre=catalog.nombre,
        unidad="",
        unidad_nombre="Catálogo propio",
        lenguaje=program.lenguaje,
        nombre_archivo=_file_name(program),
        codigo=program.codigo,
        descripcion=program.enunciado,
        tema="",
    )

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

    async def _require_entry(self, docente_id: int, entry_id: str) -> CatalogEntry:
        """ESCOM entry, or one of the teacher's own programs (id "mio-<n>"); others' programs are 404."""
        if entry_id.startswith(OWN_PREFIX):
            row = await self._own_program(docente_id, entry_id[len(OWN_PREFIX):])
            if row is not None:
                program, catalog = row
                return _own_entry(program, catalog)
            entry = None
        else:
            entry = get_catalog_entry(entry_id)
        if entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa de catálogo no encontrado.")
        return entry

    async def _own_program(self, docente_id: int, raw_id: str):
        if not raw_id.isdigit():
            return None
        result = await self.db.execute(
            select(ProgramaCatalogo, CatalogoDocente)
            .join(CatalogoDocente, CatalogoDocente.id == ProgramaCatalogo.catalogo_id)
            .where(ProgramaCatalogo.id == int(raw_id), CatalogoDocente.docente_id == docente_id)
        )
        return result.first()

    async def _own_variants(self, entry_id: str) -> Sequence[VarianteCatalogo]:
        """Saved AI variants of an own program (none for ESCOM entries)."""
        if not entry_id.startswith(OWN_PREFIX):
            return ()
        result = await self.db.execute(
            select(VarianteCatalogo)
            .where(VarianteCatalogo.programa_id == int(entry_id[len(OWN_PREFIX):]))
            .order_by(VarianteCatalogo.id)
        )
        return result.scalars().all()

    async def _own_catalog(self, docente_id: int, catalog_id: int) -> CatalogoDocente:
        catalog = (
            await self.db.execute(
                select(CatalogoDocente).where(CatalogoDocente.id == catalog_id, CatalogoDocente.docente_id == docente_id)
            )
        ).scalar_one_or_none()
        if catalog is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catálogo no encontrado.")
        return catalog

    async def list_own(self, docente_id: int) -> List[MyCatalogResponse]:
        catalogs = (
            await self.db.execute(
                select(CatalogoDocente).where(CatalogoDocente.docente_id == docente_id).order_by(CatalogoDocente.id)
            )
        ).scalars().all()
        programs = (
            await self.db.execute(
                select(ProgramaCatalogo)
                .where(ProgramaCatalogo.catalogo_id.in_([c.id for c in catalogs]))
                .order_by(ProgramaCatalogo.id)
            )
        ).scalars().all()
        return [
            MyCatalogResponse(
                id=c.id,
                nombre=c.nombre,
                programas=[_own_summary(p) for p in programs if p.catalogo_id == c.id],
            )
            for c in catalogs
        ]

    async def create_own(self, docente_id: int, nombre: str) -> MyCatalogResponse:
        catalog = CatalogoDocente(docente_id=docente_id, nombre=nombre)
        self.db.add(catalog)
        await self.db.commit()
        await self.db.refresh(catalog)
        return MyCatalogResponse(id=catalog.id, nombre=catalog.nombre, programas=[])

    async def delete_own(self, docente_id: int, catalog_id: int) -> None:
        catalog = await self._own_catalog(docente_id, catalog_id)
        # Explicit deletes: SQLite does not enforce ON DELETE CASCADE.
        program_ids = select(ProgramaCatalogo.id).where(ProgramaCatalogo.catalogo_id == catalog.id)
        await self.db.execute(delete(VarianteCatalogo).where(VarianteCatalogo.programa_id.in_(program_ids)))
        await self.db.execute(delete(ProgramaCatalogo).where(ProgramaCatalogo.catalogo_id == catalog.id))
        await self.db.execute(delete(CatalogoDocente).where(CatalogoDocente.id == catalog.id))
        await self.db.commit()

    async def add_own_program(
        self, docente_id: int, catalog_id: int, data: MyProgramCreate, variants: Sequence[VarianteReferencia] = ()
    ) -> CatalogEntrySummary:
        catalog = await self._own_catalog(docente_id, catalog_id)
        program = ProgramaCatalogo(
            catalogo_id=catalog.id,
            titulo=data.titulo.strip(),
            enunciado=data.enunciado.strip() or data.titulo.strip(),
            lenguaje=data.lenguaje,
            codigo=data.codigo,
        )
        self.db.add(program)
        await self.db.flush()
        for v in variants:
            self.db.add(
                VarianteCatalogo(programa_id=program.id, titulo=v.titulo, instrucciones=v.instrucciones, contenido=v.contenido)
            )
        await self.db.commit()
        await self.db.refresh(program)
        return _own_summary(program)

    async def save_problem_to_catalog(
        self, docente_id: int, catalog_id: int, problema_id: int
    ) -> CatalogEntrySummary:
        """Copy a library problem (statement + its first reference code) into one of the teacher's catalogs."""
        await self._own_catalog(docente_id, catalog_id)
        problema = await ProblemService(self.db).get_problem(docente_id, problema_id)
        reference = (
            await self.db.execute(
                select(CodigoFuente)
                .where(CodigoFuente.problema_id == problema.id, CodigoFuente.tipo == TipoCodigoEnum.REFERENCIA)
                .order_by(CodigoFuente.created_at)
                .limit(1)
            )
        ).scalars().first()
        if reference is None:
            raise HTTPException(
                status_code=422,
                detail="El problema no tiene código de referencia que guardar.",
            )
        variants = (
            await self.db.execute(
                select(VarianteReferencia)
                .where(VarianteReferencia.problema_id == problema.id)
                .order_by(VarianteReferencia.created_at)
            )
        ).scalars().all()
        return await self.add_own_program(
            docente_id,
            catalog_id,
            MyProgramCreate(
                titulo=problema.titulo,
                enunciado=problema.enunciado,
                lenguaje="cpp" if problema.lenguaje == "cpp" else "c",
                codigo=reference.contenido,
            ),
            variants,
        )

    async def delete_own_program(self, docente_id: int, program_id: int) -> None:
        row = await self._own_program(docente_id, str(program_id))
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa no encontrado.")
        await self.db.execute(delete(VarianteCatalogo).where(VarianteCatalogo.programa_id == program_id))
        await self.db.execute(delete(ProgramaCatalogo).where(ProgramaCatalogo.id == program_id))
        await self.db.commit()

    async def get_entry(self, docente_id: int, entry_id: str) -> CatalogEntryDetail:
        entry = await self._require_entry(docente_id, entry_id)
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
        entry = await self._require_entry(docente_id, entry_id)
        autor = OWN_AUTHOR if entry.id.startswith(OWN_PREFIX) else CATALOG_AUTHOR

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

        problems = ProblemService(self.db, self.inference, self.vector_store)
        try:
            await problems.add_reference_code(docente_id, problema_id, autor, entry.codigo, entry.lenguaje)
            for v in await self._own_variants(entry.id):
                await problems.add_stored_variant(docente_id, problema_id, v.titulo, v.instrucciones, v.contenido)
        except Exception:
            # Leave nothing half-adopted so a retry starts clean; the original error keeps propagating
            # (InferenceError / VectorStoreError map to 503).
            await self.db.rollback()
            try:
                # Also drops the vectors of whatever was already indexed (reference, earlier variants).
                await problems.delete_problem(docente_id, problema_id)
            except Exception:
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

"""The example group "Ejemplo": pre-analysed submissions every teacher can open (spec S1, S6).

The numbers come from a frozen fixture (`app/data/examples/ejemplo_fixture.json`, contract C1)
measured once with the real models, so a STUB server shows the same values. Report rows are written
through the normal scoring persistence (`ScoringService.persist`) with `engine == "real"`, so
indicators and XAI rows match a regular run. References go through `ProblemService.add_reference_code`
like a catalog adoption, so they are embedded and indexed in the vector store.

`ensure_examples` is a reconcile: it creates only what is missing (the group, a problem, its
reference, a submission, a report), so it is idempotent and also repairs a partial or deleted group.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.problem_service import ProblemService
from app.application.services.scoring_service import ScoringService
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.domain.scoring import ChannelResult, ScoringOutcome
from app.infrastructure.database.models import (
    CodigoFuente,
    EstadoAnalisisEnum,
    Grupo,
    GrupoProblema,
    Problema,
    ReporteAnalisis,
    TipoCodigoEnum,
)
from app.presentation.schemas.examples import ExampleProblem, ExampleSummary, ExampleTour

logger = logging.getLogger(__name__)

GROUP_NAME = "Ejemplo"
GROUP_CODE = "EJEMPLO"
GROUP_PERIOD = "Ejemplo"
GROUP_DESCRIPTION = (
    "Entregas de muestra ya analizadas para que pruebes Graphito: un código idéntico a la referencia, "
    "una solución propia del mismo problema, código de otro problema y código generado con IA. "
    "Estos ejemplos vienen del mismo corpus con el que se entrenaron los modelos, pero sus códigos no se "
    "usaron en el entrenamiento. Se eligieron porque muestran bien cada caso; con otros códigos los "
    "resultados pueden variar."
)
CATALOG_PREFIX = "ejemplo:"
FIXTURE_VERSION = 1


@dataclass
class _Created:
    """What one `ensure_examples` call wrote, so a failure can remove exactly that."""

    group_id: Optional[int] = None
    problem_ids: List[int] = field(default_factory=list)
    entrega_ids: List[uuid.UUID] = field(default_factory=list)  # only in problems that already existed
    report_ids: List[int] = field(default_factory=list)  # only for submissions that already existed


class ExampleService:
    DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "data" / "examples" / "ejemplo_fixture.json"

    def __init__(
        self,
        db: AsyncSession,
        inference: InferencePort,
        vector_store: VectorStorePort,
        fixture_path: Optional[Path] = None,
    ):
        self.db = db
        self.inference = inference
        self.vector_store = vector_store
        self.fixture_path = Path(fixture_path) if fixture_path is not None else Path(self.DEFAULT_FIXTURE_PATH)

    # --- fixture ----------------------------------------------------------------------------

    def _load_fixture(self) -> Dict[str, Any]:
        fixture = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        if fixture.get("version") != FIXTURE_VERSION or not fixture.get("problems"):
            raise ValueError(f"unsupported example fixture: {self.fixture_path.name}")
        return fixture

    @staticmethod
    def _outcome(data: Dict[str, Any], reference_id: uuid.UUID) -> ScoringOutcome:
        return ScoringOutcome.build(
            ChannelResult(**data["channel_a"]),
            ChannelResult(**data["channel_b"]),
            reference_id=str(reference_id),
            gcb_similarity=data.get("gcb_similarity"),
            engine=data.get("engine") or "real",
            provenance=dict(data.get("provenance") or {}),
        )

    # --- public API -------------------------------------------------------------------------

    async def ensure_examples(self, docente_id: int) -> ExampleSummary:
        """Make sure the teacher has the example group with every example problem and report."""
        fixture = self._load_fixture()
        created = _Created()
        resolved: List[tuple] = []
        try:
            grupo, group_created = await self._get_or_create_group(docente_id, created)
            for fixture_problem in fixture["problems"]:
                problema = await self._get_or_create_problem(docente_id, fixture_problem, created)
                reference_id = await self._get_or_create_reference(docente_id, problema, fixture_problem)
                await self._link_problem(grupo, problema)
                await self._ensure_submissions(grupo, problema, reference_id, fixture_problem, created)
                await self.db.commit()
                resolved.append((fixture_problem, problema))
        except Exception:
            logger.exception("Could not create the example group for teacher %s; removing what was created.", docente_id)
            await self._cleanup(docente_id, created)
            raise
        return await self._summary(grupo.id, group_created, resolved)

    # --- steps ------------------------------------------------------------------------------

    async def _get_or_create_group(self, docente_id: int, created: _Created):
        res = await self.db.execute(
            select(Grupo).where(Grupo.docente_id == docente_id, Grupo.es_ejemplo.is_(True)).order_by(Grupo.id).limit(1)
        )
        grupo = res.scalars().first()
        if grupo is not None:
            return grupo, False
        grupo = Grupo(
            docente_id=docente_id,
            nombre=GROUP_NAME,
            codigo_grupo=GROUP_CODE,
            periodo=GROUP_PERIOD,
            descripcion=GROUP_DESCRIPTION,
            es_ejemplo=True,
        )
        self.db.add(grupo)
        await self.db.commit()
        created.group_id = grupo.id
        return grupo, True

    async def _get_or_create_problem(self, docente_id: int, fixture_problem: Dict[str, Any], created: _Created) -> Problema:
        catalogo_id = f"{CATALOG_PREFIX}{fixture_problem['key']}"
        res = await self.db.execute(
            select(Problema)
            .where(Problema.docente_id == docente_id, Problema.catalogo_id == catalogo_id)
            .order_by(Problema.id)
            .limit(1)
        )
        problema = res.scalars().first()
        if problema is not None:
            return problema
        problema = Problema(
            docente_id=docente_id,
            titulo=fixture_problem["titulo"],
            enunciado=fixture_problem["descripcion"],
            lenguaje=fixture_problem["lenguaje"],
            catalogo_id=catalogo_id,
        )
        self.db.add(problema)
        await self.db.commit()
        created.problem_ids.append(problema.id)
        return problema

    async def _get_or_create_reference(
        self, docente_id: int, problema: Problema, fixture_problem: Dict[str, Any]
    ) -> uuid.UUID:
        res = await self.db.execute(
            select(CodigoFuente.id)
            .where(CodigoFuente.problema_id == problema.id, CodigoFuente.tipo == TipoCodigoEnum.REFERENCIA)
            .order_by(CodigoFuente.id)
            .limit(1)
        )
        existing = res.scalars().first()
        if existing is not None:
            return existing
        reference = fixture_problem["referencia"]
        stored = await ProblemService(self.db, self.inference, self.vector_store).add_reference_code(
            docente_id, problema.id, reference["autor"], reference["contenido"], fixture_problem["lenguaje"]
        )
        return stored.id

    async def _link_problem(self, grupo: Grupo, problema: Problema) -> None:
        res = await self.db.execute(
            select(GrupoProblema.id).where(GrupoProblema.grupo_id == grupo.id, GrupoProblema.problema_id == problema.id)
        )
        if res.scalars().first() is None:
            self.db.add(GrupoProblema(grupo_id=grupo.id, problema_id=problema.id))
            await self.db.flush()

    async def _ensure_submissions(
        self,
        grupo: Grupo,
        problema: Problema,
        reference_id: uuid.UUID,
        fixture_problem: Dict[str, Any],
        created: _Created,
    ) -> None:
        res = await self.db.execute(
            select(CodigoFuente).where(
                CodigoFuente.problema_id == problema.id, CodigoFuente.tipo == TipoCodigoEnum.ENTREGA_ALUMNO
            )
        )
        by_author = {c.autor: c for c in res.scalars().all()}
        new_problem = problema.id in created.problem_ids
        for fixture_entrega in fixture_problem["entregas"]:
            entrega = by_author.get(fixture_entrega["autor"])
            if entrega is None:
                entrega = CodigoFuente(
                    id=uuid.uuid4(),
                    problema_id=problema.id,
                    grupo_id=grupo.id,
                    tipo=TipoCodigoEnum.ENTREGA_ALUMNO,
                    autor=fixture_entrega["autor"],
                    contenido=fixture_entrega["contenido"],
                    lenguaje=fixture_problem["lenguaje"],
                )
                self.db.add(entrega)
                await self.db.flush()
                if not new_problem:
                    created.entrega_ids.append(entrega.id)
            elif entrega.grupo_id is None:  # the group was deleted and is being restored
                entrega.grupo_id = grupo.id

            has_report = (
                await self.db.execute(select(ReporteAnalisis.id).where(ReporteAnalisis.entrega_id == entrega.id).limit(1))
            ).scalars().first()
            if has_report is not None:
                continue
            outcome = self._outcome(fixture_entrega["outcome"], reference_id)
            reporte = ReporteAnalisis(entrega_id=entrega.id, estado=EstadoAnalisisEnum.PROCESANDO, engine=outcome.engine)
            self.db.add(reporte)
            await self.db.flush()
            ScoringService.persist(self.db, reporte, outcome, entrega)
            await self.db.flush()
            if entrega.id not in created.entrega_ids and not new_problem:
                created.report_ids.append(reporte.id)

    # --- result and cleanup ----------------------------------------------------------------

    async def _summary(self, grupo_id: int, creado: bool, resolved: List[tuple]) -> ExampleSummary:
        problemas = [ExampleProblem(problema_id=p.id, titulo=p.titulo) for _, p in resolved]
        showcase_fixture, showcase = resolved[0]
        casos: Dict[str, int] = {}
        for fixture_entrega in showcase_fixture["entregas"]:
            res = await self.db.execute(
                select(ReporteAnalisis.id)
                .join(CodigoFuente, ReporteAnalisis.entrega_id == CodigoFuente.id)
                .where(
                    CodigoFuente.problema_id == showcase.id,
                    CodigoFuente.tipo == TipoCodigoEnum.ENTREGA_ALUMNO,
                    CodigoFuente.autor == fixture_entrega["autor"],
                )
                .order_by(ReporteAnalisis.id)
                .limit(1)
            )
            casos[fixture_entrega["caso"]] = res.scalars().first()
        return ExampleSummary(
            grupo_id=grupo_id,
            creado=creado,
            problemas=problemas,
            recorrido=ExampleTour(problema_id=showcase.id, casos=casos),
        )

    async def _cleanup(self, docente_id: int, created: _Created) -> None:
        """Delete what this call created (best effort, like a failed catalog adoption)."""
        try:
            await self.db.rollback()
        except Exception:
            logger.error("Could not roll back after a failed example seeding for teacher %s.", docente_id)
        for model, ids in ((ReporteAnalisis, created.report_ids), (CodigoFuente, created.entrega_ids)):
            for row_id in ids:
                await self._delete_row(model, row_id)
        problems = ProblemService(self.db, self.inference, self.vector_store)
        for problema_id in reversed(created.problem_ids):
            try:
                await problems.delete_problem(docente_id, problema_id)
            except Exception:
                await self.db.rollback()
                logger.error("Could not remove example problem %s after a failed seeding.", problema_id)
        if created.group_id is not None:
            await self._delete_row(Grupo, created.group_id)

    async def _delete_row(self, model, row_id) -> None:
        try:
            row = await self.db.get(model, row_id)
            if row is not None:
                await self.db.delete(row)
                await self.db.commit()
        except Exception:
            await self.db.rollback()
            logger.error("Could not remove %s %s after a failed example seeding.", model.__name__, row_id)

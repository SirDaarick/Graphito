"""The one scoring path for single, async and batch analysis (spec AS1-AS5, AS8; design D8, D9, D15).

`score` measures both channels and decides; `persist` writes the outcome, the decision indicators
and the heuristic XAI rows onto a report row. Callers (orchestrator, batch worker) only load rows,
call these two methods and commit, so the same submission yields the same persisted fields on
every path (AS1.2, AS1.3).

- Channel A: max 5-token shingle Jaccard against the problem's references read from the database
  (or the pinned one), argmax reference, ties to the lowest reference id; isotonic calibration;
  flag iff calibrated >= artifact threshold. No references -> `SIN_REFERENCIA` and no vector query.
- Channel B: CharCNN v2 `score`/`abstained` (never legacy probability keys); Platt calibration.
- GraphCodeBERT: exploratory cosine against the fingerprinted collection; any runtime error gives
  `gcb_similarity = None`. It never reaches `decide()`.
- Thresholds come only from the calibration port; client thresholds are ignored with a warning.
"""

import asyncio
import dataclasses
import logging
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.xai_service import XAIService
from app.domain.errors import InferenceError
from app.domain.ports.calibration_port import CalibrationPort
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.lexical_similarity_port import LexicalSimilarityPort
from app.domain.ports.vector_store_port import VectorStorePort
from app.domain.scoring import (
    A_SIN_REFERENCIA,
    A_VACIO,
    B_ABSTENCION,
    DISCREPANCIA_DUAL,
    SIN_CALIBRACION,
    ChannelResult,
    ScoringOutcome,
)
from app.infrastructure.database.models import (
    CodigoFuente,
    DictamenEnum,
    EstadoAnalisisEnum,
    IndicadorIntegridad,
    ReporteAnalisis,
    TipoCodigoEnum,
)

logger = logging.getLogger(__name__)

GCB_OK = "OK"
GCB_ERROR = "ERROR"
GCB_DISABLED = "DESHABILITADO"
GCB_NO_REFERENCES = "SIN_REFERENCIA"
GCB_NOT_INDEXED = "SIN_INDICE"


def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(float(value), 4)


class ScoringService:
    def __init__(
        self,
        inference: InferencePort,
        calibration: CalibrationPort,
        vector_store: VectorStorePort,
        lexical: LexicalSimilarityPort,
    ):
        self.inference = inference
        self.calibration = calibration
        self.vector_store = vector_store
        self.lexical = lexical

    @property
    def engine_label(self) -> str:
        return self.inference.engine or "unknown"

    @staticmethod
    def warn_client_thresholds(threshold_sem: Optional[float], threshold_ai: Optional[float]) -> None:
        """Client thresholds never reach the decision (design D9); say so in the log."""
        if threshold_sem is not None or threshold_ai is not None:
            logger.warning(
                "Client thresholds ignored (threshold_sem=%s, threshold_ai=%s): the decision uses the "
                "calibration artifact thresholds.", threshold_sem, threshold_ai,
            )

    # --- references -------------------------------------------------------------------------

    async def resolve_references(
        self, db: AsyncSession, entrega: CodigoFuente, referencia_id: Optional[uuid.UUID] = None
    ) -> List[CodigoFuente]:
        """The problem's references, or the pinned one (422 if it is not a reference of this problem)."""
        if referencia_id is not None:
            ref = (await db.execute(select(CodigoFuente).where(CodigoFuente.id == referencia_id))).scalar_one_or_none()
            if ref is None or ref.tipo != TipoCodigoEnum.REFERENCIA or ref.problema_id != entrega.problema_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="La referencia indicada no pertenece al problema de la entrega.",
                )
            return [ref]
        res = await db.execute(
            select(CodigoFuente).where(
                CodigoFuente.problema_id == entrega.problema_id,
                CodigoFuente.tipo == TipoCodigoEnum.REFERENCIA,
            )
        )
        return sorted(res.scalars().all(), key=lambda r: str(r.id))

    # --- channels ---------------------------------------------------------------------------

    def _lexical_scores(self, code: str, refs: Sequence[Tuple[str, str]]) -> List[Optional[float]]:
        return [self.lexical.similarity(code, content) for _, content in refs]

    async def _channel_a(self, code: str, refs: Sequence[Tuple[str, str]]) -> Tuple[ChannelResult, Optional[str]]:
        cal = self.calibration.channel("a")
        info = {} if cal is None else dict(
            threshold=cal.threshold, threshold_key=cal.threshold_key, calibration_sha256=cal.calibration_sha256
        )
        if not refs:
            return ChannelResult.not_evaluated(A_SIN_REFERENCIA, **info), None
        scores = await asyncio.to_thread(self._lexical_scores, code, refs)
        if any(s is None for s in scores):
            return ChannelResult.not_evaluated(A_VACIO, **info), None
        # refs are sorted by id: the first maximum is the lowest id among ties.
        best = max(range(len(refs)), key=lambda i: (scores[i], -i))
        raw, reference_id = float(scores[best]), refs[best][0]
        if cal is None:
            return ChannelResult.not_evaluated(SIN_CALIBRACION, raw=raw), reference_id
        return ChannelResult.evaluated(raw=raw, calibrated=cal.calibrate(raw), **info), reference_id

    async def _channel_b(self, code: str) -> ChannelResult:
        cal = self.calibration.channel("b")
        info = {} if cal is None else dict(
            threshold=cal.threshold, threshold_key=cal.threshold_key, calibration_sha256=cal.calibration_sha256
        )
        result = await self.inference.predict_stylometry(code)
        if result.abstained:
            return ChannelResult.not_evaluated(B_ABSTENCION, **info)
        raw = float(result.raw_score)
        if cal is None:
            return ChannelResult.not_evaluated(SIN_CALIBRACION, raw=raw)
        return ChannelResult.evaluated(raw=raw, calibrated=cal.calibrate(raw), **info)

    async def _gcb(
        self, code: str, language: str, problema_id: Optional[int], has_references: bool
    ) -> Tuple[Optional[float], str]:
        """Exploratory secondary signal; never raises (AS8.2)."""
        if not has_references:
            return None, GCB_NO_REFERENCES
        try:
            vector = await self.inference.extract_semantic_embedding(code, lang=language)
            matches = await self.vector_store.query_nearest(embedding=vector, problema_id=problema_id, top_k=1)
        except InferenceError as exc:
            if exc.reason == "gcb_disabled":
                return None, GCB_DISABLED
            logger.warning("GraphCodeBERT secondary signal unavailable: %s", exc.reason)
            return None, GCB_ERROR
        except Exception as exc:
            logger.warning("GraphCodeBERT secondary signal unavailable: %s", type(exc).__name__)
            return None, GCB_ERROR
        if not matches:
            return None, GCB_NOT_INDEXED
        return _round(matches[0]["similarity"]), GCB_OK

    # --- public API -------------------------------------------------------------------------

    async def score(
        self, db: AsyncSession, entrega: CodigoFuente, referencia_id: Optional[uuid.UUID] = None
    ) -> ScoringOutcome:
        """Measure and decide for one submission. Writes nothing."""
        refs = await self.resolve_references(db, entrega, referencia_id)
        outcome = await self.score_code(
            entrega.contenido,
            [(str(r.id), r.contenido) for r in refs],
            language=entrega.lenguaje,
            problema_id=entrega.problema_id,
        )
        if outcome.reference_id is None and referencia_id is not None:
            outcome = dataclasses.replace(outcome, reference_id=str(referencia_id))
        author = next((r.autor for r in refs if str(r.id) == outcome.reference_id), None)
        if author is not None:
            outcome = dataclasses.replace(outcome, provenance={**outcome.provenance, "reference_author": author})
        return outcome

    async def score_code(
        self,
        code: str,
        ref_pairs: Sequence[Tuple[str, str]],
        *,
        language: str = "c",
        problema_id: Optional[int] = None,
    ) -> ScoringOutcome:
        """Measure and decide for raw code against `(reference_id, content)` pairs, sorted by id.

        The database-free core of `score` (also used by offline scripts). Writes nothing.
        """
        (channel_a, reference_id), channel_b, (gcb, gcb_estado) = await asyncio.gather(
            self._channel_a(code, ref_pairs),
            self._channel_b(code),
            self._gcb(code, language, problema_id, bool(ref_pairs)),
        )
        provenance: Dict[str, Any] = {
            "canal_a_metodo": self.lexical.method,
            "manifest_sha": self.calibration.manifest_sha256,
            "checkpoint_sha_b": self.calibration.checkpoint_sha256,
            "gcb_estado": gcb_estado,
            "label": self.calibration.label,
        }
        return ScoringOutcome.build(
            channel_a, channel_b, reference_id=reference_id, gcb_similarity=gcb,
            engine=self.engine_label, provenance=provenance,
        )

    @staticmethod
    def apply_outcome(reporte: ReporteAnalisis, outcome: ScoringOutcome) -> None:
        """Copy the outcome onto a report row (design D8, D15)."""
        a, b, prov = outcome.channel_a, outcome.channel_b, outcome.provenance
        reporte.referencia_id = uuid.UUID(outcome.reference_id) if outcome.reference_id else None
        reporte.similitud_semantica = _round(a.raw)  # raw Jaccard
        reporte.puntaje_calibrado_a = _round(a.calibrated)
        # Calibrated CharCNN; raw only when uncalibrated (state NO_CALIBRADO says so).
        reporte.probabilidad_ia = _round(b.calibrated if b.calibrated is not None else b.raw)
        reporte.discrepancia_score = None
        reporte.dictamen = DictamenEnum(outcome.dictamen)
        reporte.estado = EstadoAnalisisEnum.COMPLETADO
        reporte.error_mensaje = None
        reporte.engine = outcome.engine
        reporte.canal_a_metodo = prov.get("canal_a_metodo")
        reporte.estado_canal_a = outcome.estado_canal_a
        reporte.estado_canal_b = outcome.estado_canal_b
        reporte.flag_a = outcome.flag_a
        reporte.flag_b = outcome.flag_b
        reporte.umbral_a = a.threshold
        reporte.umbral_b = b.threshold
        reporte.calibracion_sha_a = a.calibration_sha256
        reporte.calibracion_sha_b = b.calibration_sha256
        reporte.checkpoint_sha_b = prov.get("checkpoint_sha_b")
        reporte.manifest_sha = prov.get("manifest_sha")
        reporte.gcb_similarity = outcome.gcb_similarity
        reporte.gcb_estado = prov.get("gcb_estado")

    @staticmethod
    def build_indicators(outcome: ScoringOutcome) -> List[Dict[str, Any]]:
        """Decision indicators, only for true flags (AS4.4): never a fabricated conformity row."""
        a, b = outcome.channel_a, outcome.channel_b

        def channel_text(name: str, ch: ChannelResult) -> str:
            return f"{name}: {ch.calibrated:.4f} >= umbral {ch.threshold:.4f} ({ch.threshold_key})"

        if outcome.dictamen == DISCREPANCIA_DUAL:
            return [{
                "tipo_alerta": "DISCREPANCIA_ESTILOMETRICA",
                "descripcion": (
                    "Bandera dual: "
                    + channel_text("Canal A (Jaccard léxico, 5 tokens)", a) + "; "
                    + channel_text("Canal B (CharCNN v2)", b) + ". Revisión docente sugerida."
                ),
                "severidad": "ALTA",
            }]
        indicators = []
        if a.flag is True:
            indicators.append({
                "tipo_alerta": "CONVERGENCIA_ESTRUCTURAL",
                "descripcion": "Bandera semántica: " + channel_text("Canal A (Jaccard léxico, 5 tokens)", a) + ".",
                "severidad": "MEDIA",
            })
        if b.flag is True:
            indicators.append({
                "tipo_alerta": "PATRON_SINTETICO",
                "descripcion": "Bandera estilométrica: " + channel_text("Canal B (CharCNN v2)", b) + ".",
                "severidad": "MEDIA",
            })
        return indicators

    def persist(self, db: AsyncSession, reporte: ReporteAnalisis, outcome: ScoringOutcome, entrega: CodigoFuente) -> None:
        """Apply the outcome and add decision + heuristic XAI indicators (the caller commits)."""
        self.apply_outcome(reporte, outcome)
        for ind in self.build_indicators(outcome):
            db.add(IndicadorIntegridad(reporte_id=reporte.id, numero_linea=None, categoria="GENERAL", **ind))
        # XAI rows are derived from the decision flags so they never contradict them (AR4.2, AR4.3).
        explanations = XAIService.extract_explanations(entrega.contenido, entrega.lenguaje, outcome)
        for exp in explanations:
            db.add(IndicadorIntegridad(
                reporte_id=reporte.id,
                tipo_alerta=exp["tipo_alerta"],
                descripcion=exp["descripcion"],
                severidad=exp["severidad"],
                numero_linea=exp["numero_linea"],
                categoria=exp["categoria"],
            ))

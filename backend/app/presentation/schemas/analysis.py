from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator
from app.infrastructure.database.models import (
    DictamenEnum,
    EstadoAnalisisEnum,
    DecisionDocenteEnum,
)

# Spec AR1.4: present on every report, including NO_EVALUABLE and unscored ones.
ETIQUETA_VALIDACION = (
    "No validado contra plagio derivado de la referencia: los umbrales se calibraron con pares "
    "estudiante-estudiante. Apoyo a la decisión docente, no un dictamen automático."
)
# Spec AR1.3: a legacy discrepancy value is shown only with this label; it never decides.
ETIQUETA_DISCREPANCIA = "No validado; no interviene en el dictamen (métrica heredada)."

# Indicator categories produced from the decision flags; every other category is a rule-based
# heuristic (spec AR4.1).
DECISION_CATEGORIES = frozenset({"GENERAL", "SIMILITUD_ARCHIVO"})


class AnalysisRunRequest(BaseModel):
    entrega_id: uuid.UUID
    # Si es None, el Canal A usa todas las referencias del problema.
    referencia_id: Optional[uuid.UUID] = None
    # Deprecated and ignored (design D9, spec AS5): thresholds come only from the calibration
    # artifacts. Still accepted so older clients keep working; a warning is logged.
    threshold_sem: Optional[float] = None
    threshold_ai: Optional[float] = None


class IndicadorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    tipo_alerta: str
    descripcion: str
    severidad: str
    numero_linea: Optional[int] = None
    categoria: Optional[str] = "GENERAL"

    @computed_field
    @property
    def origen(self) -> str:
        """`decision` for flag-driven rows, `heuristica` for rule-based ones (never model output)."""
        return "decision" if (self.categoria or "GENERAL") in DECISION_CATEGORIES else "heuristica"


class ReporteAnalisisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entrega_id: uuid.UUID
    referencia_id: Optional[uuid.UUID] = None
    lote_id: Optional[uuid.UUID] = None
    # NULL means "not evaluated", never 0 (spec AR1.2); dictamen is NULL until scored.
    # `similitud_semantica` is the raw Channel A Jaccard; `probabilidad_ia` the calibrated CharCNN.
    similitud_semantica: Optional[float] = None
    probabilidad_ia: Optional[float] = None
    discrepancia_score: Optional[float] = Field(
        None, description="Deprecated (design D15): NULL for new reports, never used by the decision."
    )
    dictamen: Optional[DictamenEnum] = None
    estado: EstadoAnalisisEnum = EstadoAnalisisEnum.COMPLETADO
    decision_docente: DecisionDocenteEnum = DecisionDocenteEnum.PENDIENTE
    fecha_decision: Optional[datetime] = None
    notas_docente: Optional[str] = None
    error_mensaje: Optional[str] = None
    fecha_analisis: datetime
    indicadores: List[IndicadorResponse] = []

    # --- provenance and decision inputs (spec AR1.1, additive) -----------------------------------
    # A row without an engine predates SDD-4: it is served as "legacy" and never rescored (AR1.5).
    engine: Optional[str] = None
    canal_a_metodo: Optional[str] = None
    estado_canal_a: Optional[str] = None
    estado_canal_b: Optional[str] = None
    flag_a: Optional[bool] = None
    flag_b: Optional[bool] = None
    umbral_a: Optional[float] = None
    umbral_b: Optional[float] = None
    puntaje_calibrado_a: Optional[float] = None
    calibracion_sha_a: Optional[str] = None
    calibracion_sha_b: Optional[str] = None
    checkpoint_sha_b: Optional[str] = None
    manifest_sha: Optional[str] = None
    # GraphCodeBERT v2 zero-shot cosine: exploratory, never decides (spec AS8).
    gcb_similarity: Optional[float] = None
    gcb_estado: Optional[str] = None
    # Resolved from the running engine when the report's manifest is the loaded one (the manifest
    # pins the checkpoint, the calibration keys and the GraphCodeBERT pipeline); NULL otherwise.
    clave_umbral_a: Optional[str] = None
    clave_umbral_b: Optional[str] = None
    versiones_modelo: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def _provenance(self) -> "ReporteAnalisisResponse":
        if not self.engine:
            self.engine = "legacy"
        if self.engine != "legacy" and self.clave_umbral_a is None and self.versiones_modelo is None:
            from app.infrastructure.inference import runtime as inference_runtime

            context = inference_runtime.report_context(self.engine, self.manifest_sha)
            if context:
                self.clave_umbral_a = context.get("clave_umbral_a") if self.umbral_a is not None else None
                self.clave_umbral_b = context.get("clave_umbral_b") if self.umbral_b is not None else None
                self.versiones_modelo = context.get("versiones_modelo")
        return self

    @computed_field
    @property
    def reference_id(self) -> Optional[uuid.UUID]:
        """Channel A argmax reference (alias of `referencia_id`, spec AR1.1)."""
        return self.referencia_id

    @computed_field
    @property
    def etiqueta_validacion(self) -> str:
        return ETIQUETA_VALIDACION

    @computed_field
    @property
    def discrepancia_etiqueta(self) -> Optional[str]:
        return None if self.discrepancia_score is None else ETIQUETA_DISCREPANCIA

    @computed_field
    @property
    def estado_calibracion(self) -> Optional[str]:
        """`legacy`, `stub`, `no_calibrado` (AS4.3), `calibrado`, or NULL while unscored."""
        if self.engine == "legacy":
            return "legacy"
        if self.engine == "stub":
            return "stub"
        if self.dictamen is None:
            return None
        if "NO_CALIBRADO" in (self.estado_canal_a, self.estado_canal_b):
            return "no_calibrado"
        return "calibrado"


class ReportCodeComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reporte_id: int
    student_author: str
    student_code: str
    reference_author: str
    reference_code: str
    language: str
    problem_title: str
    indicadores: List[IndicadorResponse] = []
    metricas_codigo: Optional[Dict[str, Any]] = None

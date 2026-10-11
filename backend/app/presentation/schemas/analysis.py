from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid
from pydantic import BaseModel, ConfigDict
from app.infrastructure.database.models import (
    DictamenEnum,
    EstadoAnalisisEnum,
    DecisionDocenteEnum,
)


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


class ReporteAnalisisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entrega_id: uuid.UUID
    referencia_id: Optional[uuid.UUID] = None
    lote_id: Optional[uuid.UUID] = None
    # NULL means "not evaluated", never 0 (spec AR1.2); dictamen is NULL until scored.
    similitud_semantica: Optional[float] = None
    probabilidad_ia: Optional[float] = None
    # Deprecated (design D15): NULL for new reports.
    discrepancia_score: Optional[float] = None
    dictamen: Optional[DictamenEnum] = None
    estado: EstadoAnalisisEnum = EstadoAnalisisEnum.COMPLETADO
    decision_docente: DecisionDocenteEnum = DecisionDocenteEnum.PENDIENTE
    fecha_decision: Optional[datetime] = None
    notas_docente: Optional[str] = None
    error_mensaje: Optional[str] = None
    fecha_analisis: datetime
    indicadores: List[IndicadorResponse] = []


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

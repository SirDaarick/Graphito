from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid
from pydantic import BaseModel, ConfigDict, Field
from app.config import settings
from app.infrastructure.database.models import (
    DictamenEnum,
    EstadoAnalisisEnum,
    DecisionDocenteEnum,
)


class AnalysisRunRequest(BaseModel):
    entrega_id: uuid.UUID
    referencia_id: Optional[uuid.UUID] = None  # Si es None, busca la más cercana en ChromaDB
    threshold_sem: float = Field(default_factory=lambda: settings.THRESHOLD_SEM)
    threshold_ai: float = Field(default_factory=lambda: settings.THRESHOLD_AI)


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
    similitud_semantica: float = 0.0
    probabilidad_ia: float = 0.0
    discrepancia_score: float = 0.0
    dictamen: DictamenEnum = DictamenEnum.SIN_ALERTAS
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

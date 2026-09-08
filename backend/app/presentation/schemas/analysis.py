from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict
from app.infrastructure.database.models import DictamenEnum, EstadoAnalisisEnum


class AnalysisRunRequest(BaseModel):
    entrega_id: uuid.UUID
    referencia_id: Optional[uuid.UUID] = None  # Si es None, busca la más cercana en ChromaDB
    threshold_sem: float = 0.85
    threshold_ai: float = 0.70


class IndicadorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    tipo_alerta: str
    descripcion: str
    severidad: str


class ReporteAnalisisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entrega_id: uuid.UUID
    referencia_id: Optional[uuid.UUID] = None
    similitud_semantica: float = 0.0
    probabilidad_ia: float = 0.0
    discrepancia_score: float = 0.0
    dictamen: DictamenEnum = DictamenEnum.INTEGRO
    estado: EstadoAnalisisEnum = EstadoAnalisisEnum.COMPLETADO
    error_mensaje: Optional[str] = None
    fecha_analisis: datetime
    indicadores: List[IndicadorResponse] = []

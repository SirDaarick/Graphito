import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.infrastructure.database.models import DecisionDocenteEnum


class BatchUploadResponse(BaseModel):
    batch_id: uuid.UUID
    problema_id: int
    total_archivos: int
    mensaje: str


class BatchStatusResponse(BaseModel):
    batch_id: uuid.UUID
    problema_id: int
    total_archivos: int
    procesados: int
    errores: int
    estado: str
    porcentaje: float
    reportes_completados: List[int] = []


class VerdictUpdateRequest(BaseModel):
    decision_docente: DecisionDocenteEnum
    notas_docente: Optional[str] = None

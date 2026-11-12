from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field
from app.presentation.schemas.submission import CodigoFuenteResponse


class VarianteCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=120)  # short label, e.g. "Usando factorial"
    instrucciones: str = Field(min_length=1, max_length=2000)  # prompt for the LLM


class VarianteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problema_id: int
    titulo: str
    instrucciones: str
    contenido: str
    lenguaje: str
    created_at: datetime


class ProblemaCreate(BaseModel):
    titulo: str
    enunciado: str
    lenguaje: str = "c"  # "c" o "cpp"


class ProblemaUpdate(BaseModel):
    titulo: Optional[str] = None
    enunciado: Optional[str] = None
    lenguaje: Optional[str] = None


class ProblemaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    docente_id: int
    titulo: str
    enunciado: str
    lenguaje: str
    fecha_creacion: datetime
    catalogo_id: Optional[str] = None
    archivado: bool = False
    entregas: Optional[List[CodigoFuenteResponse]] = None
    # Ids of the groups the problem is assigned to; only filled by the list with submissions.
    grupo_ids: Optional[List[int]] = None

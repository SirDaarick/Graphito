from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ComentarioCreate(BaseModel):
    numero_linea: Optional[int] = None
    contenido: str


class ComentarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reporte_id: int
    docente_id: int
    numero_linea: Optional[int] = None
    contenido: str
    created_at: datetime
    autor_nombre: Optional[str] = None

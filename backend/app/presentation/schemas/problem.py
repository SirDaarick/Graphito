from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


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

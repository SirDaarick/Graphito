from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict
from app.infrastructure.database.models import TipoCodigoEnum


class CodigoFuenteCreate(BaseModel):
    problema_id: int
    autor: str
    contenido: str
    tipo: TipoCodigoEnum = TipoCodigoEnum.ENTREGA_ALUMNO
    lenguaje: str = "c"


class CodigoFuenteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    problema_id: int
    tipo: TipoCodigoEnum
    autor: str
    contenido: str
    lenguaje: str
    created_at: datetime

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.presentation.schemas.problem import ProblemaResponse


class GrupoCreate(BaseModel):
    nombre: str
    codigo_grupo: str
    periodo: str
    descripcion: Optional[str] = None


class GrupoUpdate(BaseModel):
    nombre: Optional[str] = None
    codigo_grupo: Optional[str] = None
    periodo: Optional[str] = None
    descripcion: Optional[str] = None


class AsignarProblemaRequest(BaseModel):
    problema_id: int
    fecha_limite: Optional[datetime] = None


class GrupoProblemaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    grupo_id: int
    problema_id: int
    fecha_limite: Optional[datetime] = None
    activo: bool
    created_at: datetime
    problema: Optional[ProblemaResponse] = None


class GrupoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    docente_id: int
    nombre: str
    codigo_grupo: str
    periodo: str
    descripcion: Optional[str] = None
    created_at: datetime
    archivado: bool = False
    total_problemas: Optional[int] = 0
    total_entregas: Optional[int] = 0


class GrupoDetailResponse(GrupoResponse):
    asignaciones: List[GrupoProblemaResponse] = []

from typing import List
from pydantic import BaseModel


class CatalogEntrySummary(BaseModel):
    id: str
    titulo: str
    lenguaje: str
    nombre_archivo: str
    tema: str


class CatalogUnit(BaseModel):
    unidad: str
    unidad_nombre: str
    programas: List[CatalogEntrySummary]


class CatalogSubject(BaseModel):
    materia: str
    materia_nombre: str
    total: int
    unidades: List[CatalogUnit]


class CatalogEntryDetail(CatalogEntrySummary):
    materia: str
    materia_nombre: str
    unidad: str
    unidad_nombre: str
    codigo: str
    descripcion: str

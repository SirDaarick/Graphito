from typing import List, Literal
from pydantic import BaseModel, Field, field_validator
from app.presentation.schemas.catalog import CatalogEntrySummary


class MyCatalogCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)

    @field_validator("nombre")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre no puede estar vacío.")
        return v


class MyProgramCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=255)
    enunciado: str = ""
    lenguaje: Literal["c", "cpp"] = "c"
    codigo: str = Field(min_length=1)


class MyCatalogResponse(BaseModel):
    id: int
    nombre: str
    programas: List[CatalogEntrySummary]

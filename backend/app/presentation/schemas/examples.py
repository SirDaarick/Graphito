from typing import Dict, List

from pydantic import BaseModel


class ExampleProblem(BaseModel):
    problema_id: int
    titulo: str


class ExampleTour(BaseModel):
    """Reports of the showcase problem (the first one of the fixture), keyed by case."""

    problema_id: int
    # identical | similar | different | ai -> ReporteAnalisis.id (openable at /reporte/:id)
    casos: Dict[str, int]


class ExampleSummary(BaseModel):
    grupo_id: int
    # False when the group already existed (it may still have been completed on this call).
    creado: bool
    problemas: List[ExampleProblem]
    recorrido: ExampleTour

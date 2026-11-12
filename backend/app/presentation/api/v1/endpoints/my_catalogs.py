from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.application.services.catalog_service import CatalogService
from app.infrastructure.database.models import Docente
from app.infrastructure.database.session import get_db
from app.presentation.api.v1.deps import get_current_docente
from app.presentation.schemas.catalog import CatalogEntrySummary
from app.presentation.schemas.my_catalog import MyCatalogCreate, MyCatalogResponse, MyProgramCreate

router = APIRouter()


@router.get("/", response_model=List[MyCatalogResponse])
async def list_my_catalogs(current_user: Docente = Depends(get_current_docente), db: AsyncSession = Depends(get_db)):
    return await CatalogService(db).list_own(current_user.id)


@router.post("/", response_model=MyCatalogResponse, status_code=status.HTTP_201_CREATED)
async def create_my_catalog(
    data: MyCatalogCreate, current_user: Docente = Depends(get_current_docente), db: AsyncSession = Depends(get_db)
):
    return await CatalogService(db).create_own(current_user.id, data.nombre)


@router.delete("/programs/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_program(
    program_id: int, current_user: Docente = Depends(get_current_docente), db: AsyncSession = Depends(get_db)
):
    await CatalogService(db).delete_own_program(current_user.id, program_id)


@router.delete("/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_catalog(
    catalog_id: int, current_user: Docente = Depends(get_current_docente), db: AsyncSession = Depends(get_db)
):
    await CatalogService(db).delete_own(current_user.id, catalog_id)


@router.post("/{catalog_id}/programs", response_model=CatalogEntrySummary, status_code=status.HTTP_201_CREATED)
async def add_my_program(
    catalog_id: int,
    data: MyProgramCreate,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    return await CatalogService(db).add_own_program(current_user.id, catalog_id, data)


@router.post(
    "/{catalog_id}/programs/from-problem/{problem_id}",
    response_model=CatalogEntrySummary,
    status_code=status.HTTP_201_CREATED,
)
async def save_problem_to_my_catalog(
    catalog_id: int,
    problem_id: int,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    return await CatalogService(db).save_problem_to_catalog(current_user.id, catalog_id, problem_id)

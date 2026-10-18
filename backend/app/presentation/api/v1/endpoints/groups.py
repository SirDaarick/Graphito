from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database.session import get_db
from app.infrastructure.database.models import Docente
from app.presentation.api.v1.deps import get_current_docente
from app.application.services.group_service import GroupService
from app.presentation.schemas.group import (
    GrupoCreate,
    GrupoUpdate,
    GrupoResponse,
    GrupoDetailResponse,
    AsignarProblemaRequest,
    GrupoProblemaResponse,
)

router = APIRouter()


@router.post("/", response_model=GrupoResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: GrupoCreate,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    grupo = await service.create_group(current_user.id, data)
    return GrupoResponse(
        id=grupo.id,
        docente_id=grupo.docente_id,
        nombre=grupo.nombre,
        codigo_grupo=grupo.codigo_grupo,
        periodo=grupo.periodo,
        descripcion=grupo.descripcion,
        created_at=grupo.created_at,
        total_problemas=0,
        total_entregas=0,
    )


@router.get("/", response_model=List[GrupoResponse])
async def list_groups(
    include_archived: bool = False,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    return await service.list_groups(current_user.id, include_archived)


async def _group_response(service: GroupService, docente_id: int, group_id: int) -> GrupoResponse:
    grupos = await service.list_groups(docente_id, include_archived=True)
    return next(g for g in grupos if g.id == group_id)


@router.post("/{group_id}/archive", response_model=GrupoResponse)
async def archive_group(
    group_id: int,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    await service.set_archived(current_user.id, group_id, True)
    return await _group_response(service, current_user.id, group_id)


@router.post("/{group_id}/unarchive", response_model=GrupoResponse)
async def unarchive_group(
    group_id: int,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    await service.set_archived(current_user.id, group_id, False)
    return await _group_response(service, current_user.id, group_id)


@router.get("/{group_id}", response_model=GrupoDetailResponse)
async def get_group(
    group_id: int,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    grupo = await service.get_group(current_user.id, group_id)
    return GrupoDetailResponse.model_validate(grupo)


@router.put("/{group_id}", response_model=GrupoResponse)
async def update_group(
    group_id: int,
    data: GrupoUpdate,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    grupo = await service.update_group(current_user.id, group_id, data)
    return GrupoResponse.model_validate(grupo)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    await service.delete_group(current_user.id, group_id)
    return None


@router.post(
    "/{group_id}/assign",
    response_model=GrupoProblemaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_problem(
    group_id: int,
    data: AsignarProblemaRequest,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    return await service.assign_problem(
        current_user.id, group_id, data.problema_id, data.fecha_limite
    )


@router.delete("/{group_id}/assign/{problem_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_problem(
    group_id: int,
    problem_id: int,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    await service.unassign_problem(current_user.id, group_id, problem_id)
    return None

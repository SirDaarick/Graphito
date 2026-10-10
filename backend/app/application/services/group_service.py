from typing import List, Optional
from datetime import datetime
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.infrastructure.database.models import (
    Grupo,
    GrupoProblema,
    Problema,
    CodigoFuente,
    TipoCodigoEnum,
)
from app.presentation.schemas.group import GrupoCreate, GrupoUpdate, GrupoResponse


class GroupService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_group(self, docente_id: int, data: GrupoCreate) -> Grupo:
        # Verificar si ya existe un grupo con el mismo código para este docente y periodo
        stmt = select(Grupo).where(
            and_(
                Grupo.docente_id == docente_id,
                Grupo.codigo_grupo == data.codigo_grupo,
                Grupo.periodo == data.periodo,
            )
        )
        res = await self.db.execute(stmt)
        if res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un grupo con el código '{data.codigo_grupo}' para el periodo '{data.periodo}'.",
            )

        nuevo_grupo = Grupo(
            docente_id=docente_id,
            nombre=data.nombre,
            codigo_grupo=data.codigo_grupo,
            periodo=data.periodo,
            descripcion=data.descripcion,
        )
        self.db.add(nuevo_grupo)
        await self.db.commit()
        await self.db.refresh(nuevo_grupo)
        return nuevo_grupo

    async def list_groups(self, docente_id: int) -> List[GrupoResponse]:
        stmt = (
            select(Grupo)
            .options(
                selectinload(Grupo.asignaciones),
                selectinload(Grupo.entregas),
            )
            .where(Grupo.docente_id == docente_id)
            .order_by(Grupo.created_at.desc())
        )
        res = await self.db.execute(stmt)
        grupos = res.scalars().all()

        responses = []
        for g in grupos:
            total_problemas = len(g.asignaciones) if g.asignaciones else 0
            # Contar solo entregas de alumnos
            total_entregas = (
                sum(1 for e in g.entregas if e.tipo == TipoCodigoEnum.ENTREGA_ALUMNO)
                if g.entregas
                else 0
            )
            responses.append(
                GrupoResponse(
                    id=g.id,
                    docente_id=g.docente_id,
                    nombre=g.nombre,
                    codigo_grupo=g.codigo_grupo,
                    periodo=g.periodo,
                    descripcion=g.descripcion,
                    created_at=g.created_at,
                    total_problemas=total_problemas,
                    total_entregas=total_entregas,
                )
            )
        return responses

    async def get_group(self, docente_id: int, group_id: int) -> Grupo:
        stmt = (
            select(Grupo)
            .options(
                selectinload(Grupo.asignaciones).selectinload(GrupoProblema.problema),
                selectinload(Grupo.entregas),
            )
            .where(and_(Grupo.id == group_id, Grupo.docente_id == docente_id))
        )
        res = await self.db.execute(stmt)
        grupo = res.scalar_one_or_none()
        if not grupo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Grupo con ID {group_id} no encontrado o no pertenece a tu cuenta.",
            )
        return grupo

    async def update_group(self, docente_id: int, group_id: int, data: GrupoUpdate) -> Grupo:
        grupo = await self.get_group(docente_id, group_id)
        if data.nombre is not None:
            grupo.nombre = data.nombre
        if data.codigo_grupo is not None:
            grupo.codigo_grupo = data.codigo_grupo
        if data.periodo is not None:
            grupo.periodo = data.periodo
        if data.descripcion is not None:
            grupo.descripcion = data.descripcion

        await self.db.commit()
        await self.db.refresh(grupo)
        return grupo

    async def delete_group(self, docente_id: int, group_id: int) -> bool:
        grupo = await self.get_group(docente_id, group_id)
        await self.db.delete(grupo)
        await self.db.commit()
        return True

    async def assign_problem(
        self,
        docente_id: int,
        group_id: int,
        problema_id: int,
        fecha_limite: Optional[datetime] = None,
    ) -> GrupoProblema:
        # 1. Validar que el grupo pertenece al docente
        grupo = await self.get_group(docente_id, group_id)

        # 2. Validar que el problema pertenece al docente
        prob_stmt = select(Problema).where(
            and_(Problema.id == problema_id, Problema.docente_id == docente_id)
        )
        prob_res = await self.db.execute(prob_stmt)
        problema = prob_res.scalar_one_or_none()
        if not problema:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Problema con ID {problema_id} no encontrado en tu biblioteca.",
            )

        # 3. Validar si ya está asignado
        exist_stmt = select(GrupoProblema).where(
            and_(
                GrupoProblema.grupo_id == group_id,
                GrupoProblema.problema_id == problema_id,
            )
        )
        exist_res = await self.db.execute(exist_stmt)
        asignacion = exist_res.scalar_one_or_none()
        if asignacion:
            # Si ya existía, actualizar fecha_limite o reactivar
            asignacion.activo = True
            if fecha_limite is not None:
                asignacion.fecha_limite = fecha_limite
        else:
            asignacion = GrupoProblema(
                grupo_id=group_id,
                problema_id=problema_id,
                fecha_limite=fecha_limite,
                activo=True,
            )
            self.db.add(asignacion)

        await self.db.commit()
        await self.db.refresh(asignacion)
        asignacion.problema = problema
        return asignacion

    async def unassign_problem(
        self,
        docente_id: int,
        group_id: int,
        problema_id: int,
    ) -> bool:
        await self.get_group(docente_id, group_id)
        stmt = select(GrupoProblema).where(
            and_(
                GrupoProblema.grupo_id == group_id,
                GrupoProblema.problema_id == problema_id,
            )
        )
        res = await self.db.execute(stmt)
        asignacion = res.scalar_one_or_none()
        if not asignacion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La asignación no existe en este grupo.",
            )
        await self.db.delete(asignacion)
        await self.db.commit()
        return True

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.infrastructure.database.session import get_db
from app.infrastructure.database.models import Docente, ReporteAnalisis, ComentarioRevision
from app.presentation.api.v1.deps import get_current_docente
from app.presentation.schemas.comment import ComentarioCreate, ComentarioResponse

router = APIRouter()


@router.get("/{reporte_id}/comments", response_model=List[ComentarioResponse])
async def list_comments(
    reporte_id: int,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    # Verificar que el reporte exista
    res = await db.execute(
        select(ReporteAnalisis).where(ReporteAnalisis.id == reporte_id)
    )
    reporte = res.scalar_one_or_none()
    if not reporte:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reporte no encontrado.",
        )

    stmt = (
        select(ComentarioRevision)
        .options(selectinload(ComentarioRevision.docente))
        .where(ComentarioRevision.reporte_id == reporte_id)
        .order_by(ComentarioRevision.created_at.asc())
    )
    result = await db.execute(stmt)
    comments = result.scalars().all()

    return [
        ComentarioResponse(
            id=c.id,
            reporte_id=c.reporte_id,
            docente_id=c.docente_id,
            numero_linea=c.numero_linea,
            contenido=c.contenido,
            created_at=c.created_at,
            autor_nombre=c.docente.nombre if c.docente else "Docente",
        )
        for c in comments
    ]


@router.post(
    "/{reporte_id}/comments",
    response_model=ComentarioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    reporte_id: int,
    data: ComentarioCreate,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    # Verificar existencia de reporte
    res = await db.execute(
        select(ReporteAnalisis).where(ReporteAnalisis.id == reporte_id)
    )
    reporte = res.scalar_one_or_none()
    if not reporte:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reporte no encontrado.",
        )

    comentario = ComentarioRevision(
        reporte_id=reporte_id,
        docente_id=current_user.id,
        numero_linea=data.numero_linea,
        contenido=data.contenido.strip(),
    )
    db.add(comentario)
    await db.commit()
    await db.refresh(comentario)

    return ComentarioResponse(
        id=comentario.id,
        reporte_id=comentario.reporte_id,
        docente_id=comentario.docente_id,
        numero_linea=comentario.numero_linea,
        contenido=comentario.contenido,
        created_at=comentario.created_at,
        autor_nombre=current_user.nombre,
    )


@router.delete(
    "/{reporte_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comment(
    reporte_id: int,
    comment_id: int,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ComentarioRevision).where(
        ComentarioRevision.id == comment_id,
        ComentarioRevision.reporte_id == reporte_id,
    )
    res = await db.execute(stmt)
    comentario = res.scalar_one_or_none()
    if not comentario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comentario no encontrado.",
        )

    if comentario.docente_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar este comentario.",
        )

    await db.delete(comentario)
    await db.commit()
    return None

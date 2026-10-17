from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database.session import get_db
from app.infrastructure.database.models import Docente
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.infrastructure.inference import get_inference_engine
from app.infrastructure.vector_store import get_vector_store
from app.application.services.catalog_service import CatalogService
from app.presentation.api.v1.deps import get_current_docente
from app.presentation.schemas.catalog import CatalogEntryDetail, CatalogSubject
from app.presentation.schemas.problem import ProblemaResponse

router = APIRouter()


@router.get("/", response_model=List[CatalogSubject])
async def list_catalog(
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    return CatalogService(db).list_catalog()


@router.get("/{catalog_id}", response_model=CatalogEntryDetail)
async def get_catalog_entry(
    catalog_id: str,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
):
    return CatalogService(db).get_entry(catalog_id)


@router.post("/{catalog_id}/use", response_model=ProblemaResponse)
async def use_catalog_entry(
    catalog_id: str,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    return await CatalogService(db, inference, vector_store).use_entry(current_user.id, catalog_id)

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database.session import get_db
from app.infrastructure.database.models import Docente
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.infrastructure.inference import get_inference_engine
from app.infrastructure.vector_store import get_vector_store
from app.application.services.problem_service import ProblemService
from app.presentation.api.v1.deps import get_current_docente
from app.presentation.schemas.problem import ProblemaCreate, ProblemaResponse
from app.presentation.schemas.submission import CodigoFuenteCreate, CodigoFuenteResponse

router = APIRouter()


@router.post("/", response_model=ProblemaResponse, status_code=status.HTTP_201_CREATED)
async def create_problem(
    data: ProblemaCreate,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    service = ProblemService(db, inference, vector_store)
    return await service.create_problem(current_user.id, data)


@router.get("/", response_model=List[ProblemaResponse])
async def list_problems(
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    service = ProblemService(db, inference, vector_store)
    return await service.list_problems(current_user.id)


@router.get("/{problem_id}", response_model=ProblemaResponse)
async def get_problem(
    problem_id: int,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    service = ProblemService(db, inference, vector_store)
    problem = await service.get_problem(current_user.id, problem_id)
    return ProblemaResponse.model_validate(problem)


@router.post("/{problem_id}/references", response_model=CodigoFuenteResponse, status_code=status.HTTP_201_CREATED)
async def add_reference_code(
    problem_id: int,
    autor: str,
    contenido: str,
    lenguaje: str = "c",
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    service = ProblemService(db, inference, vector_store)
    return await service.add_reference_code(
        current_user.id, problem_id, autor, contenido, lenguaje
    )


@router.post("/{problem_id}/submissions", response_model=CodigoFuenteResponse, status_code=status.HTTP_201_CREATED)
async def add_submission(
    problem_id: int,
    data: CodigoFuenteCreate,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    data.problema_id = problem_id
    service = ProblemService(db, inference, vector_store)
    return await service.add_submission(current_user.id, data)


@router.get("/{problem_id}/submissions", response_model=List[CodigoFuenteResponse])
async def list_submissions(
    problem_id: int,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    service = ProblemService(db, inference, vector_store)
    return await service.list_submissions(current_user.id, problem_id)

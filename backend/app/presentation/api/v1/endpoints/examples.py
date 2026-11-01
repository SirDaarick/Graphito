from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.example_service import ExampleService
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.infrastructure.database.models import Docente
from app.infrastructure.database.session import get_db
from app.infrastructure.inference import get_inference_engine
from app.infrastructure.vector_store import get_vector_store
from app.presentation.api.v1.deps import get_current_docente
from app.presentation.schemas.examples import ExampleSummary

router = APIRouter()


@router.post("/ensure", response_model=ExampleSummary)
async def ensure_examples(
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    """Create the teacher's example group if it is missing (idempotent) and return the ids to open."""
    return await ExampleService(db, inference, vector_store).ensure_examples(current_user.id)

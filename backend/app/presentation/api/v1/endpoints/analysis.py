from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database.session import get_db
from app.infrastructure.database.models import Docente
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.infrastructure.inference import get_inference_engine
from app.infrastructure.vector_store import get_vector_store
from app.application.orchestrator.analysis_orchestrator import AnalysisOrchestrator
from app.presentation.api.v1.deps import get_current_docente
from app.presentation.schemas.analysis import AnalysisRunRequest, ReporteAnalisisResponse

router = APIRouter()


@router.post("/run", response_model=ReporteAnalisisResponse, status_code=status.HTTP_201_CREATED)
async def run_analysis(
    request: AnalysisRunRequest,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    orchestrator = AnalysisOrchestrator(db, inference, vector_store)
    return await orchestrator.execute_analysis(current_user.id, request)


@router.get("/reports/{report_id}", response_model=ReporteAnalisisResponse)
async def get_report(
    report_id: int,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    orchestrator = AnalysisOrchestrator(db, inference, vector_store)
    return await orchestrator.get_report(report_id)

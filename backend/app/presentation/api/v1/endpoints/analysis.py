from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database.session import get_db
from app.infrastructure.database.models import Docente, CodigoFuente, TipoCodigoEnum
from sqlalchemy import select
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.infrastructure.inference import get_inference_engine
from app.infrastructure.vector_store import get_vector_store
from app.application.orchestrator.analysis_orchestrator import AnalysisOrchestrator
from app.application.services.pdf_service import PdfReportService
from app.presentation.api.v1.deps import get_current_docente
from app.presentation.schemas.analysis import (
    AnalysisRunRequest,
    ReporteAnalisisResponse,
    ReportCodeComparisonResponse,
)

router = APIRouter()


@router.post("/run", response_model=ReporteAnalisisResponse, status_code=status.HTTP_201_CREATED)
async def run_analysis(
    request: AnalysisRunRequest,
    async_mode: bool = Query(False, description="Ejecutar inferencia en segundo plano"),
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    orchestrator = AnalysisOrchestrator(db, inference, vector_store)
    if async_mode:
        return await orchestrator.start_async_analysis(current_user.id, request)
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


@router.get("/reports/{report_id}/pdf")
async def download_report_pdf(
    report_id: int,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    """
    Genera y descarga en streaming el dictamen pericial institucional en formato PDF,
    incluyendo métricas bimodales, señales forenses, código fuente con numeración de líneas
    y anotaciones pedagógicas registradas por el docente.
    """
    orchestrator = AnalysisOrchestrator(db, inference, vector_store)
    report = await orchestrator.get_report_model(report_id)

    student_author = report.entrega.autor if report.entrega else None
    student_code = report.entrega.codigo_fuente if report.entrega else None
    problem_title = report.entrega.problema.titulo if (report.entrega and report.entrega.problema) else None
    language = report.entrega.lenguaje if report.entrega else None
    comments = list(report.comentarios) if hasattr(report, "comentarios") and report.comentarios else []

    pdf_buffer = PdfReportService.generate_pdf(
        report=report,
        student_author=student_author,
        problem_title=problem_title,
        language=language,
        student_code=student_code,
        comments=comments,
    )

    filename = f"reporte_integridad_{report_id}.pdf"
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/reports/{report_id}/code", response_model=ReportCodeComparisonResponse)
async def get_report_code(
    report_id: int,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    """
    Obtiene los códigos fuente necesarios para el cotejo visual lado a lado (Side-by-Side Diff):
    código evaluado del estudiante frente al código canónico de referencia del problema o entrega contrastada.
    """
    orchestrator = AnalysisOrchestrator(db, inference, vector_store)
    report = await orchestrator.get_report_model(report_id)

    student_author = report.entrega.autor if report.entrega else "Estudiante"
    student_code = report.entrega.contenido if report.entrega else ""
    language = report.entrega.lenguaje if report.entrega else "c"
    problem_title = (
        report.entrega.problema.titulo
        if (report.entrega and report.entrega.problema)
        else "Ejercicio"
    )

    reference_author = "Docente"
    reference_code = ""

    if report.referencia:
        reference_author = report.referencia.autor
        reference_code = report.referencia.contenido
    elif report.entrega and report.entrega.problema_id:
        # Buscar referencia canonica del problema
        ref_stmt = select(CodigoFuente).where(
            CodigoFuente.problema_id == report.entrega.problema_id,
            CodigoFuente.tipo == TipoCodigoEnum.REFERENCIA,
        )
        ref_res = await db.execute(ref_stmt)
        canonical_ref = ref_res.scalars().first()
        if canonical_ref:
            reference_author = canonical_ref.autor
            reference_code = canonical_ref.contenido

    return ReportCodeComparisonResponse(
        reporte_id=report.id,
        student_author=student_author,
        student_code=student_code,
        reference_author=reference_author,
        reference_code=reference_code,
        language=language,
        problem_title=problem_title,
    )

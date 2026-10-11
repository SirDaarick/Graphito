import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, status
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
from app.application.services.batch_analysis_service import BatchAnalysisService
from app.application.services.xai_service import XAIService
from app.application.services.scoring_service import ScoringService
from app.presentation.api.v1.deps import get_current_docente, get_scoring_service
from app.presentation.schemas.analysis import (
    AnalysisRunRequest,
    ReporteAnalisisResponse,
    ReportCodeComparisonResponse,
    IndicadorResponse,
)
from app.presentation.schemas.batch import (
    BatchUploadResponse,
    BatchStatusResponse,
    VerdictUpdateRequest,
)

router = APIRouter()


@router.post("/run", response_model=ReporteAnalisisResponse, status_code=status.HTTP_201_CREATED)
async def run_analysis(
    request: AnalysisRunRequest,
    async_mode: bool = Query(False, description="Ejecutar inferencia en segundo plano"),
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    scoring: ScoringService = Depends(get_scoring_service),
):
    orchestrator = AnalysisOrchestrator(db, scoring=scoring)
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
    student_code = report.entrega.contenido if report.entrega else None
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

    # Extraer indicadores de explicabilidad y métricas de complejidad de código (XAI)
    indicadores_resp = [
        IndicadorResponse(
            id=i.id,
            tipo_alerta=i.tipo_alerta,
            descripcion=i.descripcion,
            severidad=i.severidad,
            numero_linea=i.numero_linea,
            categoria=i.categoria,
        )
        for i in report.indicadores
    ]
    metricas = XAIService.compute_code_metrics(student_code)

    return ReportCodeComparisonResponse(
        reporte_id=report.id,
        student_author=student_author,
        student_code=student_code,
        reference_author=reference_author,
        reference_code=reference_code,
        language=language,
        problem_title=problem_title,
        indicadores=indicadores_resp,
        metricas_codigo=metricas,
    )


@router.post("/batch", response_model=BatchUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_batch_submissions(
    problema_id: int = Form(...),
    grupo_id: Optional[int] = Form(None),
    files: List[UploadFile] = File(...),
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    scoring: ScoringService = Depends(get_scoring_service),
):
    """
    Carga masiva de entregas de estudiantes (archivos múltiples o carpetas completas).
    Encola la inferencia bimodal en segundo plano evitando timeouts HTTP (Patrón 202 Accepted).
    """
    files_data = []
    for f in files:
        if not f.filename.lower().endswith((".c", ".cpp", ".cc", ".h")):
            continue
        raw_bytes = await f.read()
        # Same decoding as the evaluation data (`errors="replace"`), so Channel A sees the same text.
        content = raw_bytes.decode("utf-8", errors="replace")
        # Extraer nombre preliminar del archivo si no viene en metadatos
        clean_name = f.filename.rsplit(".", 1)[0]
        # Si tiene patrón boleta_nombre_apellido, aislar nombres
        tokens = [t for t in clean_name.replace("-", "_").split("_") if not t.isdigit()]
        author = " ".join(tokens) if tokens else clean_name

        files_data.append((f.filename, content, author))

    batch_service = BatchAnalysisService(db, scoring=scoring)
    batch_id = await batch_service.create_batch(
        docente_id=current_user.id,
        problema_id=problema_id,
        grupo_id=grupo_id,
        files_data=files_data,
    )

    # Lanzar worker en segundo plano (mismo ScoringService que el análisis individual)
    batch_service.dispatch_batch_worker(
        batch_id=batch_id,
        problema_id=problema_id,
        scoring=scoring,
    )

    return BatchUploadResponse(
        batch_id=batch_id,
        problema_id=problema_id,
        total_archivos=len(files_data),
        mensaje="Lote de entregas recibido y encolado para análisis asíncrono.",
    )


@router.get("/batch/{batch_id}/status", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: uuid.UUID,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    """
    Consulta en tiempo real el progreso de procesamiento del lote para actualización reactiva en la UI.
    """
    batch_service = BatchAnalysisService(db, inference, vector_store)
    return await batch_service.get_batch_status(current_user.id, batch_id)


@router.patch("/reports/{report_id}/verdict", response_model=ReporteAnalisisResponse)
async def update_report_verdict(
    report_id: int,
    request: VerdictUpdateRequest,
    current_user: Docente = Depends(get_current_docente),
    db: AsyncSession = Depends(get_db),
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
):
    """
    Persiste en base de datos la decisión humana final del docente (Human-in-the-Loop)
    para active learning y seguimiento de integridad académica institucional.
    """
    orchestrator = AnalysisOrchestrator(db, inference, vector_store)
    return await orchestrator.update_verdict(
        docente_id=current_user.id,
        report_id=report_id,
        verdict=request.decision_docente,
        notas=request.notas_docente,
    )


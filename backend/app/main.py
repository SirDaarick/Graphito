import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.domain.errors import NotReadyError
from app.infrastructure.database.session import engine, Base
import app.infrastructure.database.models  # Registra todas las entidades en Base.metadata
from app.infrastructure.inference import runtime as inference_runtime
from app.presentation.api.v1.api import api_router
from app.presentation.deps import gate_response, not_ready_body, readiness_snapshot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("graphito-backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando Graphito Backend...")
    # Crear tablas si no existen
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tablas de base de datos verificadas/creadas.")
    # Models and deploy artifacts load once, off the event loop. A failure starts the app
    # degraded (inference_ready=false, typed reason) instead of crashing or using a stub (D5).
    runtime = await asyncio.to_thread(inference_runtime.build_runtime, settings)
    inference_runtime.set_runtime(runtime)
    if not runtime.ready:
        logger.error("Inferencia NO lista (engine=%s, reason=%s): análisis devolverá 503.", runtime.engine_label, runtime.reason)
    yield
    logger.info("Cerrando conexiones del Backend...")
    close = getattr(runtime.engine, "close", None)
    if callable(close):
        close()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)


# Readiness gate: registered before CORS so CORS stays the outermost middleware.
@app.middleware("http")
async def inference_readiness_gate(request: Request, call_next):
    blocked = gate_response(request.method, request.url.path)
    if blocked is not None:
        return blocked
    return await call_next(request)


@app.exception_handler(NotReadyError)
async def not_ready_handler(request: Request, exc: NotReadyError):
    snapshot = dict(readiness_snapshot(), inference_error=exc.reason)
    return JSONResponse(status_code=503, content=not_ready_body(snapshot))


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Healthcheck
@app.get("/health", tags=["Health"])
async def health_check():
    readiness = readiness_snapshot()
    return {
        "status": "healthy" if readiness["inference_ready"] else "degraded",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "inference_mode": settings.INFERENCE_MODE,
        **readiness,
    }


# Routers
app.include_router(api_router, prefix=settings.API_V1_STR)

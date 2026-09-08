import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.infrastructure.database.session import engine, Base
from app.presentation.api.v1.api import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("graphito-backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando Graphito Backend...")
    # Crear tablas si no existen
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tablas de base de datos verificadas/creadas.")
    yield
    logger.info("Cerrando conexiones del Backend...")
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Healthcheck
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "inference_mode": settings.INFERENCE_MODE,
    }


# Routers
app.include_router(api_router, prefix=settings.API_V1_STR)

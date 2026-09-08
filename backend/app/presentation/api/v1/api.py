from fastapi import APIRouter
from app.presentation.api.v1.endpoints import auth, problems, analysis

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
api_router.include_router(problems.router, prefix="/problems", tags=["Problemas y Entregas"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["Análisis Bimodal e Integridad"])

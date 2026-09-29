from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db
from app.infrastructure.database.models import Docente
from app.presentation.schemas.auth import DocenteCreate, LoginRequest, TokenResponse, DocenteResponse
from app.application.services.auth_service import AuthService
from app.presentation.api.v1.deps import get_current_docente

router = APIRouter()


class GoogleLoginRequest(BaseModel):
    token: str = Field(..., description="ID Token / Credencial emitida por Google Identity Services")


@router.post("/register", response_model=DocenteResponse, status_code=status.HTTP_201_CREATED)
async def register_docente(
    data: DocenteCreate,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.register(data)


@router.post("/login", response_model=TokenResponse)
async def login_docente(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.login(data)


@router.post("/google", response_model=TokenResponse)
async def google_login(
    data: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.login_with_google(data.token)


@router.get("/me", response_model=DocenteResponse)
async def get_me(
    current_user: Docente = Depends(get_current_docente),
):
    return DocenteResponse.model_validate(current_user)
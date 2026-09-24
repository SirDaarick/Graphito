from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from google.oauth2 import id_token
from google.auth.transport import requests

from app.infrastructure.database.session import get_db
from app.infrastructure.database.models import Docente
from app.presentation.schemas.auth import DocenteCreate, LoginRequest, TokenResponse, DocenteResponse
from app.application.services.auth_service import AuthService
from app.presentation.api.v1.deps import get_current_docente

router = APIRouter()


class GoogleLoginRequest(BaseModel):
    token: str


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
    try:
        # Validar el token enviado con los servidores de Google
        id_info = id_token.verify_oauth2_token(data.token, requests.Request())
        email = id_info.get("email")
        nombre = id_info.get("name", email.split("@")[0] if email else "Docente")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El token de Google no contiene un correo válido.",
            )

        # Buscar si el docente existe en la BD
        result = await db.execute(select(Docente).where(Docente.email == email))
        docente = result.scalars().first()

        service = AuthService(db)

        # Si el docente no existe, se registra automáticamente
        if not docente:
            import secrets
            random_password = secrets.token_urlsafe(16)
            await service.register(
                DocenteCreate(email=email, password=random_password, nombre=nombre)
            )
            result = await db.execute(select(Docente).where(Docente.email == email))
            docente = result.scalars().first()

        # Generar token de acceso mediante AuthService o la función de seguridad del sistema
        if hasattr(service, "create_token"):
            return await service.create_token(docente)
        
        from app.core.security import create_access_token
        access_token = create_access_token(subject=str(docente.id))
        return {
            "access_token": access_token,
            "docente": docente
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Google inválido o expirado",
        )


@router.get("/me", response_model=DocenteResponse)
async def get_me(
    current_user: Docente = Depends(get_current_docente),
):
    return DocenteResponse.model_validate(current_user)
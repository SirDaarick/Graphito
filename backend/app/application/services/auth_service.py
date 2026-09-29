import secrets
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app.config import settings
from app.infrastructure.database.models import Docente
from app.core.security import get_password_hash, verify_password, create_access_token
from app.presentation.schemas.auth import DocenteCreate, LoginRequest, TokenResponse, DocenteResponse


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: DocenteCreate) -> DocenteResponse:
        result = await self.db.execute(select(Docente).where(Docente.email == data.email))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo electrónico ya está registrado.",
            )

        docente = Docente(
            email=data.email,
            hashed_password=get_password_hash(data.password),
            nombre=data.nombre,
        )
        self.db.add(docente)
        await self.db.commit()
        await self.db.refresh(docente)
        return DocenteResponse.model_validate(docente)

    async def login(self, data: LoginRequest) -> TokenResponse:
        result = await self.db.execute(select(Docente).where(Docente.email == data.email))
        docente = result.scalar_one_or_none()
        if not docente or not verify_password(data.password, docente.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas.",
            )

        token = create_access_token(subject=docente.id)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            docente=DocenteResponse.model_validate(docente),
        )

    async def get_current_user(self, user_id: int) -> Optional[Docente]:
        result = await self.db.execute(select(Docente).where(Docente.id == user_id))
        return result.scalar_one_or_none()

    async def login_with_google(self, token: str) -> TokenResponse:
        try:
            audience = settings.GOOGLE_CLIENT_ID if settings.GOOGLE_CLIENT_ID else None
            id_info = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                audience=audience,
            )

            issuer = id_info.get("iss")
            if issuer not in ["accounts.google.com", "https://accounts.google.com"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="El emisor del token de Google no es válido.",
                )

            email = id_info.get("email")
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El token de Google no contiene un correo electrónico válido.",
                )

            nombre = id_info.get("name") or email.split("@")[0]

            result = await self.db.execute(select(Docente).where(Docente.email == email))
            docente = result.scalar_one_or_none()

            if not docente:
                random_secret = secrets.token_urlsafe(32)
                docente = Docente(
                    email=email,
                    hashed_password=get_password_hash(random_secret),
                    nombre=nombre,
                )
                self.db.add(docente)
                await self.db.commit()
                await self.db.refresh(docente)

            access_token = create_access_token(subject=docente.id)
            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                docente=DocenteResponse.model_validate(docente),
            )
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token de Google inválido o expirado: {str(e)}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al autenticar con Google: {str(e)}",
            )

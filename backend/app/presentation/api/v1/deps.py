from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database.session import get_db
from app.infrastructure.database.models import Docente
from app.core.security import decode_access_token
from app.application.services.auth_service import AuthService
from app.infrastructure.inference import get_inference_engine
from app.infrastructure.vector_store import get_vector_store
from app.domain.ports.inference_port import InferencePort
from app.domain.ports.vector_store_port import VectorStorePort
from app.domain.errors import NotReadyError
from app.application.services.scoring_service import ScoringService
from app.infrastructure.inference import runtime as inference_runtime

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_scoring_service(
    inference: InferencePort = Depends(get_inference_engine),
    vector_store: VectorStorePort = Depends(get_vector_store),
) -> ScoringService:
    """The shared scoring service: the started engine, its frozen calibrations (artifacts in REAL,
    fixed defaults in STUB), the fingerprinted vector store and the Channel A Jaccard built once
    at startup with the runtime (its failure makes the runtime not ready)."""
    runtime = inference_runtime.current_runtime()
    if runtime.calibration is None:
        raise NotReadyError("calibration_unavailable", "no calibration loaded")
    if runtime.lexical is None:
        raise NotReadyError("lexical_unavailable", "no lexical similarity loaded")
    return ScoringService(inference, runtime.calibration, vector_store, runtime.lexical)


async def get_current_docente(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Docente:
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = int(payload["sub"])
    auth_service = AuthService(db)
    docente = await auth_service.get_current_user(user_id)
    if not docente:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Docente no encontrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return docente

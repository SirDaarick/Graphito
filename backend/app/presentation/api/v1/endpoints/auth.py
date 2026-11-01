from typing import Awaitable, Callable

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db
from app.infrastructure.database.models import Docente
from app.infrastructure.inference import get_inference_engine
from app.infrastructure.vector_store import get_vector_store
from app.presentation.schemas.auth import DocenteCreate, LoginRequest, TokenResponse, DocenteResponse
from app.application.services.auth_service import AuthService
from app.application.services.example_service import ExampleService
from app.presentation.api.v1.deps import get_current_docente

router = APIRouter()

# Every new account gets the example group (spec S1). Turned off by the test suite's default fixture.
SEED_EXAMPLES_ON_SIGNUP = True


def _example_seeder(request: Request, db: AsyncSession) -> Callable[[int], Awaitable[None]]:
    """Hook that seeds the example group for a new account.

    The engine and the vector store are resolved here, when the hook runs, and not as route
    dependencies: with the inference runtime not ready those dependencies would fail the request
    (503), and signing up or logging in must work regardless. Failures reach `AuthService`, which
    logs them and moves on. Dependency overrides are honoured so tests can swap the adapters.
    """
    overrides = request.app.dependency_overrides

    async def seed(docente_id: int) -> None:
        if not SEED_EXAMPLES_ON_SIGNUP:
            return
        inference = overrides.get(get_inference_engine, get_inference_engine)()
        vector_store = overrides.get(get_vector_store, get_vector_store)()
        await ExampleService(db, inference, vector_store).ensure_examples(docente_id)

    return seed


class GoogleLoginRequest(BaseModel):
    token: str = Field(..., description="ID Token / Credencial emitida por Google Identity Services")


@router.post("/register", response_model=DocenteResponse, status_code=status.HTTP_201_CREATED)
async def register_docente(
    data: DocenteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db, on_docente_created=_example_seeder(request, db))
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
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db, on_docente_created=_example_seeder(request, db))
    return await service.login_with_google(data.token)


@router.get("/me", response_model=DocenteResponse)
async def get_me(
    current_user: Docente = Depends(get_current_docente),
):
    return DocenteResponse.model_validate(current_user)
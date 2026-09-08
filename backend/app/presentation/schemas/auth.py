from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict


class DocenteCreate(BaseModel):
    email: EmailStr
    password: str
    nombre: str


class DocenteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nombre: str
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    docente: DocenteResponse

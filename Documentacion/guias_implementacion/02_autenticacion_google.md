# Guía de Implementación 02: Autenticación con Google (OAuth 2.0 / OIDC)

## 1. Fundamentos & Filosofía de Arquitectura
La autenticación no debe acoplarse rígidamente a una única fuente de identidad. En Clean Architecture, la autenticación es un **mecanismo de entrada (Infrastructure / Presentation)** que resuelve una entidad de dominio: el `Docente`.

Para admitir Google OAuth2 sin degradar la seguridad ni romper las cuentas existentes por contraseña:
1. Se utiliza el estándar **OpenID Connect (OIDC)** con verificación criptográfica del token en el Backend (evitar confiar ciegamente en datos enviados solo por el cliente).
2. Se implementa una **estrategia de conciliación de identidades (Account Linking)**: Si un docente ya existe con el email `profesor@institucion.edu` y entra con Google, su cuenta se vincula en lugar de duplicarse o colisionar.
3. El campo `hashed_password` pasa a ser opcional (`nullable=True`) para usuarios que se registran exclusivamente vía SSO.

---

## 2. Impacto en el Sistema
* **Base de Datos (PostgreSQL):**
  * Migración en tabla `docentes`:
    * `hashed_password`: Cambiar a `nullable=True`.
    * `google_id`: `String(255)`, `unique=True`, `nullable=True`, indexado.
    * `avatar_url`: `String(512)`, `nullable=True`.
* **Backend (FastAPI):**
  * Dependencia: `google-auth` (o `authlib`).
  * Endpoint nuevo: `POST /api/v1/auth/google`.
  * Servicio de autenticación: `GoogleAuthService` en `app/application/services/auth_service.py`.
* **Frontend (React):**
  * Dependencia: `@react-oauth/google`.
  * Integración del botón oficial de Google en `Login.tsx` y `Register.tsx`.

---

## 3. Especificación Técnica Detallada

### 3.1. Sentencia DDL en PostgreSQL
```sql
ALTER TABLE docentes ALTER COLUMN hashed_password DROP NOT NULL;
ALTER TABLE docentes ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE;
ALTER TABLE docentes ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512);
CREATE INDEX IF NOT EXISTS ix_docentes_google_id ON docentes(google_id);
```

### 3.2. Modelo de Datos (`backend/app/infrastructure/database/models.py`)
```python
class Docente(Base):
    __tablename__ = "docentes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)  # Ahora opcional para usuarios OAuth
    google_id = Column(String(255), unique=True, index=True, nullable=True)
    avatar_url = Column(String(512), nullable=True)
    nombre = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    problemas = relationship("Problema", back_populates="docente", cascade="all, delete-orphan")
```

### 3.3. Servicio de Verificación en Backend (`backend/app/application/services/google_auth.py`)
```python
from google.oauth2 import id_token
from google.auth.transport import requests
from fastapi import HTTPException, status
from app.config import settings

def verify_google_token(token: str) -> dict:
    try:
        id_info = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )
        if id_info["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Token issuer inválido")
            
        return {
            "google_id": id_info["sub"],
            "email": id_info["email"],
            "nombre": id_info.get("name", "Docente"),
            "avatar_url": id_info.get("picture"),
            "email_verified": id_info.get("email_verified", False)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token de Google inválido o expirado: {str(e)}"
        )
```

### 3.4. Endpoint de Autenticación (`backend/app/presentation/api/v1/endpoints/auth.py`)
```python
from pydantic import BaseModel

class GoogleLoginRequest(BaseModel):
    credential: str  # JWT de Google retornado por Google Identity Services

@router.post("/google", response_model=TokenResponse)
def login_with_google(
    payload: GoogleLoginRequest,
    db: Session = Depends(get_db)
):
    user_info = verify_google_token(payload.credential)
    
    if not user_info["email_verified"]:
        raise HTTPException(status_code=400, detail="El correo de Google no está verificado.")
        
    docente = db.query(Docente).filter(Docente.email == user_info["email"]).first()
    
    if docente:
        # Conciliación: enlazar google_id si aún no estaba vinculado
        if not docente.google_id:
            docente.google_id = user_info["google_id"]
        if user_info["avatar_url"]:
            docente.avatar_url = user_info["avatar_url"]
        db.commit()
    else:
        # Registro automático en primer inicio de sesión
        docente = Docente(
            email=user_info["email"],
            nombre=user_info["nombre"],
            google_id=user_info["google_id"],
            avatar_url=user_info["avatar_url"],
            hashed_password=None
        )
        db.add(docente)
        db.commit()
        db.refresh(docente)

    # Generar JWT interno de Graphito (misma sesión que login normal)
    access_token = create_access_token(data={"sub": str(docente.id)})
    return TokenResponse(access_token=access_token, token_type="bearer")
```

---

## 4. Riesgos y Anti-Patrones a Evitar
* ❌ **Falso SSO:** Enviar el correo desde el frontend sin validar el ID Token en el backend. Un atacante podría enviar cualquier email en el JSON.
* ⚠️ **Manejo de cuentas huérfanas:** Si un usuario entra con Google y después intenta hacer "Login con contraseña", la UI debe indicarle claramente *"Esta cuenta fue registrada con Google. Inicia sesión con Google o configura una contraseña"*.

---

## 5. Criterios de Aceptación y Pruebas
1. Un usuario nuevo puede registrarse con un solo clic con su cuenta de Google y se crea su perfil en `docentes`.
2. Un usuario ya existente con contraseña tradicional vincula su cuenta si su email de Google coincide.
3. Se emite un JWT firmado por Graphito con idénticos privilegios a los de sesión tradicional.

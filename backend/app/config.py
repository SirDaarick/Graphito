from typing import List, Union
from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Graphito Backend"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://graphito:graphitosecret@localhost:5432/graphito_db"

    # Vector Store (ChromaDB)
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_data"
    USE_CHROMA_SERVER: bool = False

    # Inference Engine (STUB | REAL)
    INFERENCE_MODE: str = "STUB"
    DEMO_MODE: bool = False

    # DEPRECATED legacy request defaults: only the legacy STUB decision path and the current API
    # schema still read them. The new decision takes thresholds from the calibration artifacts
    # (REAL) or the stub defaults (STUB) and ignores client thresholds (design D6, D9). Removed
    # together with the API change that makes `threshold_*` optional and ignored (WU9).
    THRESHOLD_SEM: float = 0.85
    THRESHOLD_AI: float = 0.20

    # Environment: "production" refuses development-only switches (design D7).
    APP_ENV: str = "development"

    # Deploy artifacts (models/deploy/, built by scripts/build_deploy_artifacts.py; design D6).
    # Relative paths resolve against the project root (`/` in the container, so /models/deploy/...).
    # Thresholds come only from the calibration files; the keys select which one is used.
    DEPLOY_MANIFEST: str = "models/deploy/manifest.json"
    CHANNEL_A_METHOD: str = "jaccard"
    CHANNEL_A_CALIBRATION: str = "models/deploy/channel_a/calibration.json"
    CHANNEL_A_THRESHOLD_KEY: str = "fpr_0.05"
    CHARCNN_CHECKPOINT: str = "models/deploy/channel_b/best.pth"
    CHARCNN_CALIBRATION: str = "models/deploy/channel_b/calibration.json"
    CHARCNN_THRESHOLD_KEY: str = "fpr_0.01"
    GCB_INPUT_VERSION: str = "v2"
    GCB_POOLING: str = "mean"
    # GraphCodeBERT is a non-deciding secondary signal; when enabled, a failed load blocks readiness.
    GCB_SECONDARY_ENABLED: bool = True
    INFERENCE_WORKERS: int = 1
    # Development only (with INFERENCE_MODE=REAL): score a channel without calibration, unflagged.
    ALLOW_UNCALIBRATED: bool = False

    # Security
    JWT_SECRET: str = "supersecretjwtkey_change_in_production_123456789"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    GOOGLE_CLIENT_ID: str = ""

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def _refuse_uncalibrated_in_production(self) -> "Settings":
        if self.ALLOW_UNCALIBRATED and self.APP_ENV.strip().lower() == "production":
            raise ValueError("ALLOW_UNCALIBRATED=true is refused when APP_ENV=production")
        if self.INFERENCE_WORKERS < 1:
            raise ValueError("INFERENCE_WORKERS must be >= 1")
        return self


settings = Settings()

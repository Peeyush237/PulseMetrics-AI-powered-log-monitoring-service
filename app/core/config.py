from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database — Render/Neon give postgresql://, asyncpg needs postgresql+asyncpg://
    database_url: str = "postgresql+asyncpg://pulsemetrics:pulsemetrics@localhost:5432/pulsemetrics"

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24h
    jwt_refresh_token_expire_days: int = 30

    # Embedding / Clustering
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    clustering_threshold: float = 0.85

    # App behaviour
    log_level: str = "INFO"
    default_retention_days: int = 30
    max_batch_size: int = 1000
    max_entry_size_bytes: int = 65536
    rate_limit_per_key: int = 5000

    # Email (optional — skip if empty)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@pulsemetrics.local"

    # CORS — add your Render URL here via env var, e.g. https://pulsemetrics.onrender.com
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )
    # Allow all origins when this is True (set via CORS_ALLOW_ALL=true in production if needed)
    cors_allow_all: bool = False


settings = Settings()

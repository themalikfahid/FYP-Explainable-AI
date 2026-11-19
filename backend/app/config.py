"""Environment-based configuration. Values come from environment variables or a
`.env` file in the project root (see .env.example). No secrets are hard-coded."""
from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
log = logging.getLogger("app.config")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

    APP_ENV: Literal["development", "test", "production"] = "development"
    SECRET_KEY: str = Field(default="", description="JWT signing key, >= 32 chars")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str = f"sqlite:///{(ROOT / 'data' / 'app.db').as_posix()}"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    MODELS_DIR: str = str(ROOT / "artifacts" / "models")
    FRONTEND_DIST: str = str(ROOT / "frontend" / "dist")

    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    PREDICT_RATE_LIMIT_PER_MINUTE: int = 30

    # email: disabled | file (writes .eml files to EMAIL_OUTBOX_DIR, for QA) | smtp
    EMAIL_MODE: Literal["disabled", "file", "smtp"] = "disabled"
    EMAIL_OUTBOX_DIR: str = str(ROOT / "artifacts" / "qa" / "email_outbox")
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM: str = ""
    SMTP_TIMEOUT_SECONDS: int = 10
    APP_PUBLIC_URL: str = "http://localhost:8000"

    @model_validator(mode="after")
    def _normalise_db_url(self):
        # hosted Postgres (Neon, Render, Heroku) gives postgres:// or postgresql:// URLs; SQLAlchemy needs a driver
        u = self.DATABASE_URL
        for old in ("postgres://", "postgresql://", "postgresql+psycopg://"):
            if u.startswith(old):
                object.__setattr__(self, "DATABASE_URL", "postgresql+psycopg2://" + u[len(old):])
                break
        return self

    @model_validator(mode="after")
    def _check_secret(self):
        if self.SECRET_KEY.startswith("change-me"):
            if self.APP_ENV == "production":
                raise ValueError("SECRET_KEY is still the .env.example placeholder")
            log.warning("SECRET_KEY is the .env.example placeholder; replace it before any real use.")
        if len(self.SECRET_KEY) < 32:
            if self.APP_ENV == "production":
                raise ValueError("SECRET_KEY must be set to at least 32 characters in production")
            # development/test: ephemeral random key (tokens become invalid on restart)
            object.__setattr__(self, "SECRET_KEY", secrets.token_urlsafe(48))
            log.warning("SECRET_KEY not set; using an ephemeral random key (development only).")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
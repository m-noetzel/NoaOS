"""Application configuration — environment-based with validation.

All config via environment variables with sensible defaults.
Secrets never in config files. Config validated at startup (fail fast).
Config is immutable after startup.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

_DEV_SECRET = "dev-secret-key-change-in-production"  # noqa: S105


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Environment(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    """Noa application settings.

    All values are loaded from environment variables.
    Validated at startup — invalid config raises immediately.
    """

    # Environment
    noa_env: Environment = Environment.DEVELOPMENT
    # iOS4: explicit `environment` field for client-facing environment selection
    # (iOS4 Environment.swift selects API base URL based on this — SPEC.md §29.4)
    environment: Environment = Environment.DEVELOPMENT

    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # Database (SPEC.md §10.1)
    database_url: str = (
        "postgresql+asyncpg://noa:noa@localhost:5432/noa"
    )

    # Security (SPEC.md §11.2)
    secret_key: str | None = _DEV_SECRET

    # Logging
    log_level: LogLevel = LogLevel.INFO

    # Token settings (SPEC.md §5.2)
    # AU1: Long-lived tokens for single-user personal system.
    access_token_expire_minutes: int = 10080  # 7 days
    refresh_token_expire_days: int = 90  # 90 days

    # API keys — injected from keychain via env vars (SPEC.md §11.1)
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_ai_api_key: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    notion_token: str | None = None
    tavily_api_key: str | None = None
    ollama_base_url: str | None = None

    # APNs Push Notifications (SPEC.md §29.5)
    apns_key_id: str | None = None
    apns_team_id: str | None = None
    apns_key_path: str | None = None
    apns_bundle_id: str | None = None

    # Voice / Whisper (SPEC.md §29.3)
    whisper_model: str = "whisper-1"
    max_audio_size_mb: int = 25
    # iOS8: dual-provider transcription
    transcription_provider: str = "openai"
    whisper_cpp_url: str = "http://host.docker.internal:8001"

    model_config = {
        "env_prefix": "",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: object) -> object:
        if isinstance(v, str):
            v_upper = v.upper()
            valid = {e.value for e in LogLevel}
            if v_upper not in valid:
                msg = (
                    f"Invalid log level: {v}. "
                    f"Must be one of: {', '.join(valid)}"
                )
                raise ValueError(msg)
            return v_upper
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if (
            self.noa_env == Environment.PRODUCTION
            and (self.secret_key is None or self.secret_key == _DEV_SECRET)
        ):
            msg = "SECRET_KEY must be set to a secure value in production"
            raise ValueError(msg)
        return self

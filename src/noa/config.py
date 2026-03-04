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
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

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

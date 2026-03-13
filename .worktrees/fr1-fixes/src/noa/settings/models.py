"""SQLAlchemy ORM model for user settings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from noa.db.models.base import Base


class UserSettings(Base):
    """Per-user settings and tool credentials.

    One row per user. Created on first settings update.
    API keys stored as plaintext for now — CM2 adds keychain override.
    """

    __tablename__ = "user_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_settings_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Defaults
    default_model: Mapped[str | None] = mapped_column(
        String(64), default="claude-sonnet-4-20250514",
    )
    default_provider: Mapped[str | None] = mapped_column(
        String(32), default="anthropic",
    )
    default_privacy_mode: Mapped[str | None] = mapped_column(
        String(16), default="standard",
    )

    # Budget limits (SPEC.md §24)
    budget_daily_usd: Mapped[float | None] = mapped_column(
        Numeric(10, 2), default=10.0,
    )
    budget_monthly_usd: Mapped[float | None] = mapped_column(
        Numeric(10, 2), default=200.0,
    )

    # Chat defaults
    system_prompt: Mapped[str | None] = mapped_column(String(4096))
    temperature: Mapped[float | None] = mapped_column(
        Numeric(3, 2), default=0.7,
    )
    max_tokens: Mapped[int | None] = mapped_column(default=4096)

    # Tool credentials (SPEC.md §11.1)
    anthropic_api_key: Mapped[str | None] = mapped_column(String(256))
    openai_api_key: Mapped[str | None] = mapped_column(String(256))
    google_client_id: Mapped[str | None] = mapped_column(String(256))
    google_client_secret: Mapped[str | None] = mapped_column(String(256))
    notion_token: Mapped[str | None] = mapped_column(String(256))
    tavily_api_key: Mapped[str | None] = mapped_column(String(256))
    google_refresh_token: Mapped[str | None] = mapped_column(String(512))
    ollama_base_url: Mapped[str | None] = mapped_column(
        String(512), default="http://private-worker:11434",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

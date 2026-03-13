"""Google OAuth2 credential storage — resolves M10.

Stores encrypted refresh tokens in DB so they survive restarts.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from noa.db.models.base import Base


class GoogleCredential(Base):
    __tablename__ = "google_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False,
    )
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

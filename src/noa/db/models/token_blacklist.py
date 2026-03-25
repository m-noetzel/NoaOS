"""Token blacklist model — SEC1: JWT revocation on logout.

SPEC.md SS5.4: Sessions and tokens must be revocable immediately.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from noa.db.models.base import Base


class TokenBlacklist(Base):
    """Stores revoked JWT token identifiers (jti claims).

    Entries are cleaned up when their expires_at timestamp passes —
    there is no need to store blacklist entries beyond the natural
    token lifetime.
    """

    __tablename__ = "token_blacklist"

    __table_args__ = (
        Index("ix_token_blacklist_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    jti: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

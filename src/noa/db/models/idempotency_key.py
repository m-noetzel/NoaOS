"""Persistent idempotency key store."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from noa.db.models.base import Base


class IdempotencyKey(Base):
    """Persistent store for tool-call idempotency keys.

    A key is stored after the first successful (or failed) execution.
    Subsequent calls with the same key return the stored response without
    re-executing the tool (§19.1 idempotency guarantee).
    """

    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        insert_default=uuid.uuid4,
    )
    key: Mapped[str] = mapped_column(
        String(256), unique=True, nullable=False, index=True
    )
    # JSON-serialized ToolResponse (result + error + latency_ms + provider)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        insert_default=lambda: datetime.now(UTC),
        nullable=False,
    )

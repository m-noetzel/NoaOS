"""ToolCallLog model — tool call telemetry persistence.

Stores per-invocation telemetry so it survives restarts.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from noa.db.models import Base


class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, insert_default=uuid.uuid4,
    )
    tool: Mapped[str] = mapped_column(String(128), nullable=False)
    function: Mapped[str] = mapped_column(String(128), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    cached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        insert_default=lambda: datetime.now(UTC),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    def __init__(self, **kwargs: Any) -> None:
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        if "timestamp" not in kwargs:
            kwargs["timestamp"] = datetime.now(UTC)
        super().__init__(**kwargs)

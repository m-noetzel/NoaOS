"""UsageStats model — SPEC.md cost tracking."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from noa.db.models.base import Base


class UsageStats(Base):
    __tablename__ = "usage_stats"
    __table_args__ = (
        Index("ix_usage_stats_user_id_timestamp", "user_id", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0"),
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"),
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column()
    task_id: Mapped[uuid.UUID | None] = mapped_column()

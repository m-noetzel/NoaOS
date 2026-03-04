"""AuditLog model with hash chain — SPEC.md §28.1, §28.2."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from noa.db.models import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    # Model info
    domain: Mapped[str] = mapped_column(String(16), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)

    # Token usage
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0"),
    )

    # Tool info (nullable — only if tool invoked)
    tool_name: Mapped[str | None] = mapped_column(String(128))
    tool_args: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    tool_result_summary: Mapped[str | None] = mapped_column(Text)
    side_effects: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # Privacy classification
    privacy_classification: Mapped[str] = mapped_column(String(16), nullable=False)
    classification_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
    )
    classification_reasoning: Mapped[str | None] = mapped_column(Text)

    # Hash chain (§28.2)
    previous_entry_hash: Mapped[str | None] = mapped_column(String(64))

    def hash_chain_data(self) -> str:
        """Serialize this entry for hash chain computation.

        Returns a deterministic JSON string of key fields.
        """
        data = {
            "id": str(self.id),
            "timestamp": (
                self.timestamp.isoformat() if self.timestamp else None
            ),
            "user_id": str(self.user_id),
            "trace_id": str(self.trace_id),
            "domain": self.domain,
            "model_provider": self.model_provider,
            "model_name": self.model_name,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": str(self.cost_usd),
            "tool_name": self.tool_name,
            "privacy_classification": self.privacy_classification,
            "previous_entry_hash": self.previous_entry_hash,
        }
        return json.dumps(data, sort_keys=True)

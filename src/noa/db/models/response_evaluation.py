"""ResponseEvaluation model — stores per-run evaluation scores.

Spec ref: SPEC.md — EV1 (Evaluation Node).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from noa.db.models.base import Base


class ResponseEvaluation(Base):
    """Stores evaluation scores for a single agent run.

    Verdict:
        pass    — overall >= 3.0
        reroute — overall >= 2.0 and < 3.0
        flag    — overall < 2.0
    """

    __tablename__ = "response_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    task_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    archetype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rubric_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="v1",
    )
    # {dimension_name: score_0_to_5}
    scores: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    overall: Mapped[float] = mapped_column(Float, nullable=False)
    verdict: Mapped[str] = mapped_column(
        String(32), nullable=False,
    )  # pass/reroute/flag
    reroute_target: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reroute_cycle: Mapped[int] = mapped_column(Integer, default=0)
    eval_model: Mapped[str] = mapped_column(String(128), nullable=False)
    eval_ms: Mapped[float] = mapped_column(Float, default=0.0)
    user_rating: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )  # NULL until FB1
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

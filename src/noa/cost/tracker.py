"""Token & cost tracking service — SPEC.md §24.

Records every LLM call with provider, model, tokens, and cost.
Provides aggregated usage queries for display endpoints.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func

from noa.db.models.usage import UsageStats

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class UsageSummary:
    """Aggregated usage data for display."""

    total_cost_usd: Decimal
    total_input_tokens: int
    total_output_tokens: int


class CostTracker:
    """Records token usage for every LLM call."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        user_id: uuid.UUID,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: Decimal,
        session_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
    ) -> UsageStats:
        """Record a single LLM call's token usage.

        Creates a UsageStats row and flushes to the session.
        """
        entry = UsageStats(
            id=uuid.uuid4(),
            user_id=user_id,
            provider=provider,
            model_name=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            session_id=session_id,
            run_id=run_id,
            task_id=task_id,
        )
        self._session.add(entry)
        self._session.flush()
        return entry


def get_usage(
    session: Session,
    *,
    user_id: uuid.UUID,
    period: str,
    session_id: uuid.UUID | None = None,
) -> UsageSummary:
    """Get aggregated usage for a given period.

    Args:
        session: SQLAlchemy session.
        user_id: User to query usage for.
        period: One of "daily", "monthly", "session".
        session_id: Required when period is "session".

    Returns:
        UsageSummary with totals.
    """
    query = session.query(
        func.coalesce(func.sum(UsageStats.cost_usd), Decimal("0")),
        func.coalesce(func.sum(UsageStats.input_tokens), 0),
        func.coalesce(func.sum(UsageStats.output_tokens), 0),
    ).filter(UsageStats.user_id == user_id)

    now = datetime.now(UTC)

    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(UsageStats.timestamp >= start)
    elif period == "monthly":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(UsageStats.timestamp >= start)
    elif period == "session":
        if session_id is None:
            msg = "session_id required for session period"
            raise ValueError(msg)
        query = query.filter(UsageStats.session_id == session_id)

    row = query.one()
    return UsageSummary(
        total_cost_usd=Decimal(str(row[0])) if row[0] else Decimal("0"),
        total_input_tokens=int(row[1]) if row[1] else 0,
        total_output_tokens=int(row[2]) if row[2] else 0,
    )

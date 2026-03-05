"""Budget limit enforcement — SPEC.md §24.

Monthly, daily, and per-task spending limits with warning thresholds.
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

# Warning threshold as fraction of limit (80%)
_WARN_THRESHOLD = Decimal("0.80")


@dataclass
class LimitCheckResult:
    """Result of a budget limit check."""

    allowed: bool
    warning: bool = False
    reason: str = ""


class CostLimiter:
    """Enforces monthly, daily, and per-task spending limits."""

    def __init__(
        self,
        *,
        monthly_limit_usd: Decimal,
        daily_limit_usd: Decimal,
        per_task_limit_usd: Decimal,
    ) -> None:
        self.monthly_limit_usd = monthly_limit_usd
        self.daily_limit_usd = daily_limit_usd
        self.per_task_limit_usd = per_task_limit_usd

    def check(
        self,
        session: Session,
        *,
        user_id: uuid.UUID,
        scope: str,
        task_id: uuid.UUID | None = None,
    ) -> LimitCheckResult:
        """Check if the given scope's spending is within limits.

        Args:
            session: SQLAlchemy session.
            user_id: User to check limits for.
            scope: One of "monthly", "daily", "task".
            task_id: Required when scope is "task".

        Returns:
            LimitCheckResult indicating whether the request is allowed.
        """
        if scope == "monthly":
            return self._check_monthly(session, user_id)
        if scope == "daily":
            return self._check_daily(session, user_id)
        if scope == "task":
            if task_id is None:
                msg = "task_id required for task scope"
                raise ValueError(msg)
            return self._check_task(session, user_id, task_id)
        msg = f"Unknown scope: {scope}"
        raise ValueError(msg)

    def _get_spend(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        since: datetime | None = None,
        task_id: uuid.UUID | None = None,
    ) -> Decimal:
        """Sum cost_usd for the given filters."""
        query = session.query(
            func.coalesce(func.sum(UsageStats.cost_usd), Decimal("0")),
        ).filter(UsageStats.user_id == user_id)

        if since is not None:
            query = query.filter(UsageStats.timestamp >= since)
        if task_id is not None:
            query = query.filter(UsageStats.task_id == task_id)

        result = query.scalar()
        return Decimal(str(result)) if result else Decimal("0")

    def _check_monthly(
        self, session: Session, user_id: uuid.UUID,
    ) -> LimitCheckResult:
        now = datetime.now(UTC)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        spend = self._get_spend(session, user_id, since=start)

        if spend >= self.monthly_limit_usd:
            return LimitCheckResult(
                allowed=False,
                reason=f"Monthly limit exceeded: ${spend} >= ${self.monthly_limit_usd}",
            )

        warning = spend >= self.monthly_limit_usd * _WARN_THRESHOLD
        return LimitCheckResult(allowed=True, warning=warning)

    def _check_daily(
        self, session: Session, user_id: uuid.UUID,
    ) -> LimitCheckResult:
        now = datetime.now(UTC)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        spend = self._get_spend(session, user_id, since=start)

        if spend >= self.daily_limit_usd:
            return LimitCheckResult(
                allowed=False,
                reason=f"Daily limit exceeded: ${spend} >= ${self.daily_limit_usd}",
            )

        warning = spend >= self.daily_limit_usd * _WARN_THRESHOLD
        return LimitCheckResult(allowed=True, warning=warning)

    def _check_task(
        self, session: Session, user_id: uuid.UUID, task_id: uuid.UUID,
    ) -> LimitCheckResult:
        spend = self._get_spend(session, user_id, task_id=task_id)

        if spend >= self.per_task_limit_usd:
            return LimitCheckResult(
                allowed=False,
                reason=f"Per-task limit exceeded: ${spend} >= "
                f"${self.per_task_limit_usd}",
            )

        warning = spend >= self.per_task_limit_usd * _WARN_THRESHOLD
        return LimitCheckResult(allowed=True, warning=warning)

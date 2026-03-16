"""Cost tracking endpoints — real DB queries for web client."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import AuthUser, require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cost", tags=["cost"])


@router.get("/pricing")
async def cost_pricing(
    user: Any = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Return the model pricing table."""
    from noa.cost.pricing import PRICING_TABLE

    entries = [
        {
            "provider": provider,
            "model": model,
            "input_price_per_m": float(pricing.input_per_million),
            "output_price_per_m": float(pricing.output_per_million),
        }
        for (provider, model), pricing in PRICING_TABLE.items()
    ]
    return success_envelope(data=entries, trace_id=trace_id_ctx.get(""))


def _get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    from noa.api.app_state import get_session_factory

    return get_session_factory()


def _extract_user_id(user: Any) -> uuid.UUID:
    """Extract user_id from AuthUser or legacy dict payload."""
    if isinstance(user, AuthUser):
        return user.user_id
    # Legacy dict support (e.g. patched require_auth in tests)
    raw = user.get("user_id", user.get("sub", ""))
    return uuid.UUID(raw) if isinstance(raw, str) else raw


@router.get("/summary")
async def cost_summary(
    request: Request,
    period: str = Query("monthly", pattern="^(daily|monthly)$"),
    privacy_mode: str | None = Query(default=None, pattern="^(private|external)$"),
    user: Any = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Return cost summary aggregated by period.

    When ``privacy_mode`` is specified, only costs from runs in that domain
    are included. When omitted, all domains are included (backwards compatible).
    """
    rid = trace_id_ctx.get("")
    factory = _get_session_factory()
    if factory is None:
        return success_envelope(data=[], trace_id=rid)

    uid = _extract_user_id(user)

    try:
        async with factory() as session:
            from sqlalchemy import func, select

            from noa.db.models.run import Run
            from noa.db.models.usage import UsageStats
            from noa.settings.repository import SettingsRepository

            # For summary, return both daily and monthly aggregates
            summaries = []
            from datetime import UTC, datetime

            now = datetime.now(UTC)
            # Determine period start timestamps (DB-agnostic using Python datetime)

            today_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
            month_start = datetime(now.year, now.month, 1, tzinfo=UTC)

            # Load user settings to get budget limits
            settings = await SettingsRepository(session).get_by_user_id(uid)
            budget_daily = (
                float(settings.budget_daily_usd)
                if settings and settings.budget_daily_usd is not None
                else None
            )
            budget_monthly = (
                float(settings.budget_monthly_usd)
                if settings and settings.budget_monthly_usd is not None
                else None
            )

            for p in (["daily", "monthly"] if period == "monthly" else ["daily"]):
                since = today_start if p == "daily" else month_start
                stmt = select(
                    func.coalesce(func.sum(UsageStats.cost_usd), 0)
                    .label("cost_usd"),
                    func.coalesce(func.sum(UsageStats.input_tokens), 0)
                    .label("tokens_in"),
                    func.coalesce(func.sum(UsageStats.output_tokens), 0)
                    .label("tokens_out"),
                ).where(
                    UsageStats.user_id == uid,
                    UsageStats.timestamp >= since,
                )
                if privacy_mode is not None:
                    # Join through runs to filter by domain
                    stmt = stmt.join(Run, UsageStats.run_id == Run.id).where(
                        Run.privacy_mode == privacy_mode,
                    )
                result = await session.execute(stmt)
                row = result.one()
                budget_limit = budget_daily if p == "daily" else budget_monthly
                summaries.append({
                    "period": p,
                    "tokens_in": int(row.tokens_in),
                    "tokens_out": int(row.tokens_out),
                    "cost_usd": float(row.cost_usd),
                    "budget_limit_usd": budget_limit,
                })

        return success_envelope(data=summaries, trace_id=rid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to query cost summary", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error") from exc


@router.get("/records")
async def cost_records(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    since: str | None = Query(default=None),
    privacy_mode: str | None = Query(default=None, pattern="^(private|external)$"),
    user: Any = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Return recent cost records.

    When ``since`` is specified (ISO 8601), only records after that timestamp
    are returned. When ``privacy_mode`` is specified, only records linked to
    runs in that domain are returned.
    """
    rid = trace_id_ctx.get("")
    factory = _get_session_factory()
    if factory is None:
        return success_envelope(data=[], trace_id=rid)

    uid = _extract_user_id(user)

    try:
        from datetime import datetime

        from sqlalchemy import select

        from noa.db.models.run import Run
        from noa.db.models.usage import UsageStats

        async with factory() as session:
            stmt = (
                select(UsageStats)
                .where(UsageStats.user_id == uid)
                .order_by(UsageStats.timestamp.desc())
                .limit(limit)
                .offset(offset)
            )
            if since is not None:
                since_dt = datetime.fromisoformat(since)
                stmt = stmt.where(UsageStats.timestamp >= since_dt)
            if privacy_mode is not None:
                # Join through runs to filter by domain.
                # Records without run_id are excluded when a filter is applied.
                stmt = stmt.join(Run, UsageStats.run_id == Run.id).where(
                    Run.privacy_mode == privacy_mode,
                )
            result = await session.execute(stmt)
            rows = result.scalars().all()

            records = [
                {
                    "run_id": str(r.run_id) if r.run_id else None,
                    "tokens_in": r.input_tokens,
                    "tokens_out": r.output_tokens,
                    "cost_usd": float(r.cost_usd),
                    "provider": r.provider,
                    "model": r.model_name,
                    "created_at": r.timestamp.isoformat(),
                }
                for r in rows
            ]

        return success_envelope(data=records, trace_id=rid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to query cost records", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error") from exc

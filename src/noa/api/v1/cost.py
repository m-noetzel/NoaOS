"""Cost tracking endpoints — real DB queries for web client."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cost", tags=["cost"])


def _get_session_factory() -> Any:
    from noa.api.app_state import get_session_factory

    return get_session_factory()


@router.get("/summary")
async def cost_summary(
    request: Request,
    period: str = Query("monthly", pattern="^(daily|monthly)$"),
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Return cost summary aggregated by period."""
    rid = trace_id_ctx.get("")
    factory = _get_session_factory()
    if factory is None:
        return success_envelope(data=[], trace_id=rid)

    user_id = user.get("user_id", user.get("sub", ""))

    try:
        async with factory() as session:
            from sqlalchemy import text

            uid = uuid.UUID(user_id)

            # For summary, return both daily and monthly aggregates
            summaries = []
            for p in (["daily", "monthly"] if period == "monthly" else ["daily"]):
                result = await session.execute(
                    text(
                        "SELECT COALESCE(SUM(cost_usd), 0), "
                        "COALESCE(SUM(input_tokens), 0), "
                        "COALESCE(SUM(output_tokens), 0) "
                        "FROM usage_stats WHERE user_id = :uid"
                        + (
                            " AND timestamp >= date_trunc('day', NOW())"
                            if p == "daily"
                            else " AND timestamp >= date_trunc('month', NOW())"
                        )
                    ),
                    {"uid": uid},
                )
                row = result.one()
                summaries.append({
                    "period": p,
                    "tokens_in": int(row[1]),
                    "tokens_out": int(row[2]),
                    "cost_usd": float(row[0]),
                })

        return success_envelope(data=summaries, trace_id=rid)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to query cost summary", exc_info=True)
        return success_envelope(data=[], trace_id=rid)


@router.get("/records")
async def cost_records(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Return recent cost records."""
    rid = trace_id_ctx.get("")
    factory = _get_session_factory()
    if factory is None:
        return success_envelope(data=[], trace_id=rid)

    user_id = user.get("user_id", user.get("sub", ""))

    try:
        from sqlalchemy import select

        from noa.db.models.usage import UsageStats

        uid = uuid.UUID(user_id)

        async with factory() as session:
            stmt = (
                select(UsageStats)
                .where(UsageStats.user_id == uid)
                .order_by(UsageStats.timestamp.desc())
                .limit(limit)
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
    except Exception:  # noqa: BLE001
        logger.warning("Failed to query cost records", exc_info=True)
        return success_envelope(data=[], trace_id=rid)

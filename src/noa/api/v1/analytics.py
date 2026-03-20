"""Analytics endpoints — EV2 (Self-Improvement Analytics).

Spec ref: SPEC.md — EV2.

GET /api/v1/analytics/eval-trends    — aggregate eval scores over time
GET /api/v1/analytics/worst-dimensions — worst-performing dimensions
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import error_envelope, success_envelope
from noa.auth.middleware import AuthUser, require_auth
from noa.db.models.response_evaluation import ResponseEvaluation
from noa.db.models.run import Run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

# Supported group_by keys and the ResponseEvaluation column/attribute they map to
_GROUP_BY_COLUMNS: dict[str, str] = {
    "dimension": "_dimension",  # virtual — expands from scores JSON
    "model": "eval_model",
    "task_type": "task_type",
    "archetype": "archetype",
}

# Divergence threshold: if |eval_overall_avg - user_rating_avg| > this, flag it
_DIVERGENCE_THRESHOLD = 1.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    from noa.api.app_state import get_session_factory

    return get_session_factory()


def _parse_period(period: str) -> datetime:
    """Return the start datetime for the requested period."""
    now = datetime.now(UTC)
    if period == "7d":
        return now - timedelta(days=7)
    if period == "30d":
        return now - timedelta(days=30)
    raise ValueError(f"Unknown period: {period}")


def _aggregate_by_dimension(
    evals: list[ResponseEvaluation],
) -> list[dict[str, Any]]:
    """Aggregate scores across all dimensions in the scores JSON column."""
    totals: dict[str, list[float]] = {}
    for ev in evals:
        if not ev.scores:
            continue
        for dim, score in ev.scores.items():
            totals.setdefault(dim, []).append(float(score))

    result = []
    for dim, scores in sorted(totals.items()):
        result.append(
            {
                "key": dim,
                "avg_score": round(sum(scores) / len(scores), 3),
                "count": len(scores),
            }
        )
    return result


def _aggregate_by_field(
    evals: list[ResponseEvaluation],
    field: str,
) -> list[dict[str, Any]]:
    """Aggregate overall scores grouped by a string field on the model."""
    totals: dict[str, list[float]] = {}
    for ev in evals:
        raw = getattr(ev, field, None)
        key = "unknown" if raw is None else str(raw)
        totals.setdefault(key, []).append(float(ev.overall))

    result = []
    for key, scores in sorted(totals.items()):
        result.append(
            {
                "key": key,
                "avg_score": round(sum(scores) / len(scores), 3),
                "count": len(scores),
            }
        )
    return result


def _compute_divergence_alerts(
    evals: list[ResponseEvaluation],
) -> list[dict[str, Any]]:
    """Detect divergence between eval overall score and user_rating.

    User ratings are 1 (thumbs up) or -1 (thumbs down).  We normalise them
    to a 1–5 scale (1→1.0, -1→5.0 inverted: positive=5, negative=1) so
    that the divergence is meaningful relative to the 0–5 eval score.

    Flag when |eval_avg - user_avg_normalised| > 1.5.
    """
    # Collect dimension scores paired with user_rating
    dim_eval: dict[str, list[float]] = {}
    dim_user: dict[str, list[float]] = {}

    for ev in evals:
        if ev.user_rating is None or not ev.scores:
            continue
        # Normalise user_rating: 1 → 5.0, -1 → 1.0
        user_score = 5.0 if ev.user_rating == 1 else 1.0
        for dim, score in ev.scores.items():
            dim_eval.setdefault(dim, []).append(float(score))
            dim_user.setdefault(dim, []).append(user_score)

    alerts = []
    for dim in dim_eval:
        if dim not in dim_user or not dim_user[dim]:
            continue
        eval_avg = sum(dim_eval[dim]) / len(dim_eval[dim])
        user_avg = sum(dim_user[dim]) / len(dim_user[dim])
        divergence = round(abs(eval_avg - user_avg), 3)
        if divergence > _DIVERGENCE_THRESHOLD:
            alerts.append(
                {
                    "dimension": dim,
                    "eval_avg": round(eval_avg, 3),
                    "user_avg": round(user_avg, 3),
                    "divergence": divergence,
                }
            )

    return sorted(alerts, key=lambda x: x["divergence"], reverse=True)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/eval-trends")
async def eval_trends(
    user: AuthUser = Depends(require_auth),  # noqa: B008
    period: str = Query("7d", pattern="^(7d|30d)$"),
    group_by: str = Query(
        "dimension",
        description="Aggregation dimension: dimension|model|task_type|archetype",
    ),
) -> dict[str, Any]:
    """Return aggregated evaluation score trends for the requested period.

    The ``group_by`` parameter controls how scores are bucketed:

    - ``dimension`` — average per rubric dimension (from the ``scores`` JSON)
    - ``model`` — average overall score per eval model
    - ``task_type`` — average overall score per task type
    - ``archetype`` — average overall score per archetype
    """
    tid = trace_id_ctx.get("")

    if group_by not in _GROUP_BY_COLUMNS:
        return error_envelope(
            code="INVALID_GROUP_BY",
            message=f"group_by must be one of: {', '.join(_GROUP_BY_COLUMNS)}",
            trace_id=tid,
        )

    try:
        since = _parse_period(period)
    except ValueError:
        return error_envelope(
            code="INVALID_PERIOD",
            message="period must be 7d or 30d",
            trace_id=tid,
        )

    sf = _get_session_factory()
    if sf is None:
        raise HTTPException(status_code=503, detail="Database not available")

    import uuid as _uuid

    from sqlalchemy import String, cast

    user_id = user.user_id

    async with sf() as session:
        # Fetch run IDs belonging to this user.
        # cast(Run.id, String) on SQLite returns hex without hyphens, but
        # ResponseEvaluation.run_id stores the canonical hyphenated UUID string.
        # Normalise to hyphenated form so the IN filter matches.
        run_id_result = await session.execute(
            select(cast(Run.id, String)).where(Run.user_id == user_id)
        )
        user_run_ids = [
            str(_uuid.UUID(row[0])) for row in run_id_result.all()
        ]

        if not user_run_ids:
            return success_envelope(
                data={
                    "period": period,
                    "group_by": group_by,
                    "data": [],
                    "overall_avg": 0.0,
                    "divergence_alerts": [],
                },
                trace_id=tid,
            )

        result = await session.execute(
            select(ResponseEvaluation).where(
                ResponseEvaluation.run_id.in_(user_run_ids),
                ResponseEvaluation.created_at >= since,
            )
        )
        evals = list(result.scalars().all())

    if not evals:
        return success_envelope(
            data={
                "period": period,
                "group_by": group_by,
                "data": [],
                "overall_avg": 0.0,
                "divergence_alerts": [],
            },
            trace_id=tid,
        )

    # Build grouped data
    if group_by == "dimension":
        data = _aggregate_by_dimension(evals)
    else:
        data = _aggregate_by_field(evals, _GROUP_BY_COLUMNS[group_by])

    overall_avg = round(sum(e.overall for e in evals) / len(evals), 3)
    divergence_alerts = _compute_divergence_alerts(evals)

    return success_envelope(
        data={
            "period": period,
            "group_by": group_by,
            "data": data,
            "overall_avg": overall_avg,
            "divergence_alerts": divergence_alerts,
        },
        trace_id=tid,
    )


@router.get("/worst-dimensions")
async def worst_dimensions(
    user: AuthUser = Depends(require_auth),  # noqa: B008
    period: str = Query("7d", pattern="^(7d|30d)$"),
    top_n: int = Query(3, ge=1, le=20),
) -> dict[str, Any]:
    """Return the worst-performing rubric dimensions for the period.

    Dimensions are ranked by ascending average score (lowest = worst).
    """
    tid = trace_id_ctx.get("")

    try:
        since = _parse_period(period)
    except ValueError:
        return error_envelope(
            code="INVALID_PERIOD",
            message="period must be 7d or 30d",
            trace_id=tid,
        )

    sf = _get_session_factory()
    if sf is None:
        raise HTTPException(status_code=503, detail="Database not available")

    import uuid as _uuid

    from sqlalchemy import String, cast

    user_id = user.user_id

    async with sf() as session:
        run_id_result = await session.execute(
            select(cast(Run.id, String)).where(Run.user_id == user_id)
        )
        # Normalise to hyphenated UUID strings (SQLite returns hex without hyphens)
        user_run_ids = [
            str(_uuid.UUID(row[0])) for row in run_id_result.all()
        ]

        if not user_run_ids:
            return success_envelope(
                data={"period": period, "worst": []},
                trace_id=tid,
            )

        result = await session.execute(
            select(ResponseEvaluation).where(
                ResponseEvaluation.run_id.in_(user_run_ids),
                ResponseEvaluation.created_at >= since,
            )
        )
        evals = list(result.scalars().all())

    # Aggregate by dimension
    dim_scores: dict[str, list[float]] = {}
    for ev in evals:
        if not ev.scores:
            continue
        for dim, score in ev.scores.items():
            dim_scores.setdefault(dim, []).append(float(score))

    if not dim_scores:
        return success_envelope(
            data={"period": period, "worst": []},
            trace_id=tid,
        )

    aggregated = [
        {
            "dimension": dim,
            "avg_score": round(sum(scores) / len(scores), 3),
            "count": len(scores),
        }
        for dim, scores in dim_scores.items()
    ]
    # Sort ascending (lowest score = worst)
    aggregated.sort(key=lambda x: float(x["avg_score"]))  # type: ignore[arg-type]
    worst = aggregated[:top_n]

    return success_envelope(
        data={"period": period, "worst": worst},
        trace_id=tid,
    )

"""User feedback ratings endpoints — FB1.

Spec ref: SPEC.md — FB1 (User Feedback Loop).

POST /api/v1/ratings     — submit a thumbs up/down rating for a run
GET  /api/v1/ratings/summary — aggregated quality score over a time window
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import error_envelope, success_envelope
from noa.auth.middleware import AuthUser, require_auth
from noa.db.models.response_evaluation import ResponseEvaluation
from noa.db.models.run import Run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ratings", tags=["ratings"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class RatingRequest(BaseModel):
    """Submit a user rating for a run."""

    run_id: str = Field(..., description="Run ID to rate")
    rating: int = Field(
        ...,
        description="1 for thumbs up, -1 for thumbs down",
        ge=-1,
        le=1,
    )

    @property
    def is_valid_rating(self) -> bool:
        """Rating must be 1 or -1 (not 0)."""
        return self.rating in (1, -1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    from noa.api.app_state import get_session_factory

    return get_session_factory()


def _extract_user_id(user: Any) -> uuid.UUID:
    """Extract user_id from AuthUser or legacy dict payload."""
    if isinstance(user, AuthUser):
        return user.user_id
    if isinstance(user, dict):
        uid = user.get("user_id") or user.get("sub")
        if uid:
            return uuid.UUID(str(uid))
    raise ValueError("Cannot extract user_id from auth payload")


def _parse_period(period: str) -> datetime:
    """Return the start datetime for the requested period."""
    now = datetime.now(UTC)
    if period == "7d":
        return now - timedelta(days=7)
    if period == "30d":
        return now - timedelta(days=30)
    raise ValueError(f"Unknown period: {period}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("")
async def submit_rating(
    body: RatingRequest,
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Submit a thumbs up/down rating for a completed run.

    Updates the ``user_rating`` column on the matching ``response_evaluations``
    row.  If no evaluation row exists (run was never evaluated), returns 404.
    """
    tid = trace_id_ctx.get("")

    if not body.is_valid_rating:
        raise HTTPException(
            status_code=422,
            detail="rating must be 1 (thumbs up) or -1 (thumbs down)",
        )

    sf = _get_session_factory()
    if sf is None:
        raise HTTPException(status_code=503, detail="Database not available")

    user_id = _extract_user_id(user)

    async with sf() as session:
        # Verify run exists and belongs to this user
        try:
            run_uuid = uuid.UUID(body.run_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="Invalid run_id format"
            ) from exc

        run_result = await session.execute(
            select(Run).where(Run.id == run_uuid, Run.user_id == user_id)
        )
        run = run_result.scalars().first()
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        # Upsert: find existing evaluation row or create a stub
        eval_result = await session.execute(
            select(ResponseEvaluation).where(
                ResponseEvaluation.run_id == body.run_id
            )
        )
        evaluation = eval_result.scalars().first()

        if evaluation is None:
            # Create a minimal stub row so the rating can be stored even
            # without an auto-evaluation score.
            evaluation = ResponseEvaluation(
                id=uuid.uuid4(),
                run_id=body.run_id,
                rubric_version="none",
                scores={},
                overall=0.0,
                verdict="unrated",
                eval_model="none",
                eval_ms=0.0,
            )
            session.add(evaluation)

        evaluation.user_rating = body.rating
        await session.commit()

    logger.info(
        "Rating submitted: run_id=%s rating=%s user_id=%s",
        body.run_id,
        body.rating,
        user_id,
    )

    return success_envelope(
        data={"run_id": body.run_id, "rating": body.rating},
        trace_id=tid,
    )


@router.get("/summary")
async def rating_summary(
    user: AuthUser = Depends(require_auth),  # noqa: B008
    period: str = Query("7d", pattern="^(7d|30d)$"),
) -> dict[str, Any]:
    """Return aggregated quality score for the requested period.

    Returns positive / negative / total counts and a score (positive / total).
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

    user_id = _extract_user_id(user)

    async with sf() as session:
        # First fetch the run IDs that belong to this user (as strings for the join)
        run_id_result = await session.execute(
            select(cast(Run.id, String)).where(Run.user_id == user_id)
        )
        user_run_ids = [row[0] for row in run_id_result.all()]

        if not user_run_ids:
            return success_envelope(
                data={
                    "positive": 0,
                    "negative": 0,
                    "total": 0,
                    "score": 0.0,
                    "period": period,
                },
                trace_id=tid,
            )

        # Count positive and negative ratings for this user's runs
        evals_result = await session.execute(
            select(ResponseEvaluation.user_rating).where(
                ResponseEvaluation.run_id.in_(user_run_ids),
                ResponseEvaluation.user_rating.isnot(None),
                ResponseEvaluation.created_at >= since,
            )
        )
        ratings = [row[0] for row in evals_result.all()]

        positive = sum(1 for r in ratings if r == 1)
        negative = sum(1 for r in ratings if r == -1)
        total = len(ratings)
        score = round(positive / total, 3) if total > 0 else 0.0

    return success_envelope(
        data={
            "positive": positive,
            "negative": negative,
            "total": total,
            "score": score,
            "period": period,
        },
        trace_id=tid,
    )

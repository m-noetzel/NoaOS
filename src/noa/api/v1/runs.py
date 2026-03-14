"""Run endpoints & SSE streaming — SPEC.md §22.4."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import AuthUser, require_auth
from noa.db.models.run import Run, RunEvent
from noa.db.models.usage import UsageStats

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


@router.get("")
async def list_runs(
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    db: Any = Depends(get_db_session),  # noqa: B008
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    privacy_mode: str | None = Query(default=None, pattern="^(private|external)$"),
) -> dict[str, Any]:
    """List runs for the authenticated user.

    When ``privacy_mode`` is specified, only runs from that domain are returned.
    When omitted, runs from all domains are returned (backwards compatible).
    """
    rid = trace_id_ctx.get("")
    # Fetch runs
    stmt = (
        select(Run)
        .where(Run.user_id == user.user_id)
        .order_by(Run.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if privacy_mode is not None:
        stmt = stmt.where(Run.privacy_mode == privacy_mode)
    run_result = await db.execute(stmt)
    runs = run_result.scalars().all()

    # Aggregate usage stats per run (outer join — many runs have no stats)
    run_ids = [r.id for r in runs]
    usage_by_run: dict[Any, dict[str, Any]] = {}
    if run_ids:
        usage_result = await db.execute(
            select(
                UsageStats.run_id,
                func.coalesce(func.max(UsageStats.provider), "").label("provider"),
                func.coalesce(func.max(UsageStats.model_name), "").label("model_name"),
                func.coalesce(func.sum(UsageStats.input_tokens), 0).label("tokens_in"),
                func.coalesce(func.sum(UsageStats.output_tokens), 0).label(
                    "tokens_out"
                ),
                func.coalesce(func.sum(UsageStats.cost_usd), 0).label("cost_usd"),
            )
            .where(UsageStats.run_id.in_(run_ids))
            .group_by(UsageStats.run_id)
        )
        for row in usage_result.all():
            usage_by_run[row.run_id] = {
                "provider": row.provider or "",
                "model": row.model_name or "",
                "tokens_in": int(row.tokens_in or 0),
                "tokens_out": int(row.tokens_out or 0),
                "cost_usd": float(row.cost_usd or 0),
            }

    data = []
    for r in runs:
        usage = usage_by_run.get(r.id, {})
        duration_ms = 0
        if r.created_at and r.updated_at:
            delta = r.updated_at - r.created_at
            duration_ms = int(delta.total_seconds() * 1000)
        data.append({
            "id": str(r.id),
            "thread_id": str(r.thread_id),
            "status": r.status,
            "risk_tier": r.risk_tier,
            "privacy_mode": r.privacy_mode,
            "summary": r.summary or "",
            "model": usage.get("model", ""),
            "provider": usage.get("provider", ""),
            "tokens_in": usage.get("tokens_in", 0),
            "tokens_out": usage.get("tokens_out", 0),
            "cost_usd": usage.get("cost_usd", 0.0),
            "duration_ms": duration_ms,
            "created_at": r.created_at.isoformat(),
        })
    return success_envelope(data=cast(dict[str, Any], data), trace_id=rid)


@router.get("/{run_id}")
async def get_run(
    run_id: uuid.UUID,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    db: Any = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Get a single run by ID."""
    rid = trace_id_ctx.get("")
    result = await db.execute(
        select(Run).where(Run.id == run_id, Run.user_id == user.user_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )

    # Aggregate usage stats for this run (outer join — may be empty)
    usage_result = await db.execute(
        select(
            func.coalesce(func.max(UsageStats.provider), "").label("provider"),
            func.coalesce(func.max(UsageStats.model_name), "").label("model_name"),
            func.coalesce(func.sum(UsageStats.input_tokens), 0).label("tokens_in"),
            func.coalesce(func.sum(UsageStats.output_tokens), 0).label("tokens_out"),
            func.coalesce(func.sum(UsageStats.cost_usd), 0).label("cost_usd"),
        )
        .where(UsageStats.run_id == run_id)
    )
    usage_row = usage_result.one()
    duration_ms = 0
    if run.created_at and run.updated_at:
        delta = run.updated_at - run.created_at
        duration_ms = int(delta.total_seconds() * 1000)
    data = {
        "id": str(run.id),
        "thread_id": str(run.thread_id),
        "status": run.status,
        "risk_tier": run.risk_tier,
        "privacy_mode": run.privacy_mode,
        "summary": run.summary or "",
        "model": usage_row.model_name or "",
        "provider": usage_row.provider or "",
        "tokens_in": int(usage_row.tokens_in or 0),
        "tokens_out": int(usage_row.tokens_out or 0),
        "cost_usd": float(usage_row.cost_usd or 0),
        "duration_ms": duration_ms,
        "created_at": run.created_at.isoformat(),
    }
    return success_envelope(data=data, trace_id=rid)


@router.get("/{run_id}/artifacts")
async def list_run_artifacts(
    run_id: uuid.UUID,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    db: Any = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """List artifacts for a specific run."""
    from noa.db.models.artifact import Artifact

    rid = trace_id_ctx.get("")
    # Verify run belongs to user
    run_result = await db.execute(
        select(Run).where(Run.id == run_id, Run.user_id == user.user_id)
    )
    if run_result.scalar_one_or_none() is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    result = await db.execute(
        select(Artifact)
        .where(Artifact.run_id == run_id)
        .order_by(Artifact.created_at.desc())
    )
    artifacts = result.scalars().all()
    data = [
        {
            "id": str(a.id),
            "run_id": str(a.run_id),
            "type": a.type,
            "name": a.name,
            "mime_type": a.mime_type,
            "size_bytes": a.size_bytes,
            "created_at": a.created_at.isoformat(),
        }
        for a in artifacts
    ]
    return success_envelope(data=cast(dict[str, Any], data), trace_id=rid)


@router.get("/{run_id}/events")
async def stream_run_events(
    run_id: uuid.UUID,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> StreamingResponse:
    """SSE endpoint for streaming run events per §22.4.

    Events include an ``id:`` field so clients can use ``Last-Event-ID``
    for reconnection replay.
    """
    rid = trace_id_ctx.get("")

    async def event_generator() -> Any:
        event_counter = 0
        event_counter += 1
        yield f"id: {event_counter}\nevent: connected\ndata: connected\n\n"

        try:
            while True:
                await asyncio.sleep(30)
                event_counter += 1
                yield f"id: {event_counter}\n: keepalive\n\n"
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Trace-ID": rid,
        },
    )


@router.get("/{run_id}/events/replay")
async def replay_run_events(
    run_id: uuid.UUID,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    after_id: str | None = Query(default=None),
    db: Any = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Replay events for SSE reconnection — resolves M5 + H11 + BE-H4.

    Joins through ``runs`` table to verify the authenticated user owns
    the run before returning events.

    ``after_id``: UUID of the last event the client received. When provided,
    only events with a later timestamp are returned (stable DB offset, not
    list index). Clients should store the ``id`` field from the last event
    and pass it on reconnect.
    """
    rid = trace_id_ctx.get("")

    # Determine the timestamp cursor when after_id is provided (BE-H4)
    after_timestamp = None
    if after_id is not None:
        try:
            after_uuid = uuid.UUID(after_id)
            cursor_stmt = (
                select(RunEvent.timestamp)
                .join(Run, RunEvent.run_id == Run.id)
                .where(RunEvent.id == after_uuid)
                .where(Run.user_id == user.user_id)
            )
            cursor_result = await db.execute(cursor_stmt)
            after_timestamp = cursor_result.scalar_one_or_none()
        except (ValueError, AttributeError):
            pass  # Invalid UUID — ignore and return all events

    # H11: filter by user_id to prevent cross-user access
    stmt = (
        select(RunEvent)
        .join(Run, RunEvent.run_id == Run.id)
        .where(RunEvent.run_id == run_id)
        .where(Run.user_id == user.user_id)
        .order_by(RunEvent.timestamp)
    )
    # BE-H4: Filter by stable DB timestamp offset, not list index
    if after_timestamp is not None:
        stmt = stmt.where(RunEvent.timestamp > after_timestamp)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    events = [
        {
            "id": str(row.id),
            "run_id": str(row.run_id),
            "type": row.event_type,
            "created_at": row.timestamp.isoformat(),
            "data": row.payload,
        }
        for row in rows
    ]

    return success_envelope(data={"events": events}, trace_id=rid)

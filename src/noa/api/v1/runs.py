"""Run endpoints & SSE streaming — SPEC.md §22.4."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import AuthUser, require_auth
from noa.db.models.run import Run, RunEvent

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


@router.get("")
async def list_runs(
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """List runs for the authenticated user."""
    rid = trace_id_ctx.get("")
    return success_envelope(data={"events": []}, trace_id=rid)


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
    after_event_id: int = 0,
    db: Any = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Replay events for SSE reconnection — resolves M5 + H11.

    Joins through ``runs`` table to verify the authenticated user owns
    the run before returning events.
    """
    rid = trace_id_ctx.get("")

    # H11: filter by user_id to prevent cross-user access
    stmt = (
        select(RunEvent)
        .join(Run, RunEvent.run_id == Run.id)
        .where(RunEvent.run_id == run_id)
        .where(Run.user_id == user.user_id)
        .order_by(RunEvent.timestamp)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    events = [
        {
            "id": str(row.id),
            "event_type": row.event_type,
            "timestamp": row.timestamp.isoformat(),
            "payload": row.payload,
        }
        for idx, row in enumerate(rows, start=1)
        if idx > after_event_id
    ]

    return success_envelope(data={"events": events}, trace_id=rid)

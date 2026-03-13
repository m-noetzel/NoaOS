"""Queue endpoints — real DB queries for web client."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import AuthUser, require_auth
from noa.db.models.task_queue import TaskQueue

router = APIRouter(prefix="/api/v1/queue", tags=["queue"])


@router.get("")
async def list_queue(
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """List queued and in-progress tasks."""
    rid = trace_id_ctx.get("")
    result = await session.execute(
        select(TaskQueue)
        .where(TaskQueue.status.in_(["queued", "processing"]))
        .order_by(TaskQueue.queued_at.asc())
        .limit(100)
    )
    tasks = result.scalars().all()

    # Map TaskQueue rows to QueueItem shape expected by frontend
    data = []
    for idx, t in enumerate(tasks):
        # Map DB status to frontend status
        fe_status = "active" if t.status == "processing" else "queued"
        # Extract run_id and privacy_mode from payload if available
        payload = t.payload or {}
        data.append({
            "id": str(t.id),
            "run_id": payload.get("run_id", str(t.request_id)),
            "status": fe_status,
            "privacy_mode": payload.get(
                "privacy_mode", "external",
            ),
            "position": idx,
            "estimated_wait": idx * 30,
            "created_at": t.queued_at.isoformat(),
        })

    return success_envelope(data=data, trace_id=rid)

"""Approval endpoints — SPEC.md §29.6."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth
from noa.db.models.approval import Approval

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


class ApprovalDecision(BaseModel):
    """Request body for approval decision."""

    decision: Literal["approved", "denied"]


@router.get("/pending")
async def list_pending_approvals(
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """List pending approvals for the authenticated user."""
    rid = trace_id_ctx.get("")
    return success_envelope(data=[], trace_id=rid)


@router.post("/{approval_id}/decide")
async def decide_approval(
    approval_id: uuid.UUID,
    body: ApprovalDecision,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Approve or deny a pending approval per §29.6.

    Persists the decision to the database and returns the full approval shape
    so ApprovalDetailViewModel can update badge color (risk_tier) and show
    the decision timestamp (decided_at).
    """
    rid = trace_id_ctx.get("")

    result = await session.execute(
        select(Approval).where(Approval.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval {approval_id} not found",
        )

    if approval.decision != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval already decided: {approval.decision}",
        )

    user_id = uuid.UUID(user["sub"])
    approval.decision = body.decision
    approval.decided_at = datetime.now(UTC)
    approval.decided_by_user_id = user_id
    await session.flush()

    return success_envelope(
        data={
            "approval_id": str(approval_id),
            "decision": approval.decision,
            "status": "decided",
            "risk_tier": approval.risk_tier,
            "decided_at": approval.decided_at.isoformat(),
        },
        trace_id=rid,
    )

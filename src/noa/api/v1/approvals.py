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
from noa.auth.middleware import AuthUser, require_auth
from noa.db.models.approval import Approval

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


class ApprovalDecision(BaseModel):
    """Request body for approval decision."""

    decision: Literal["approved", "denied"]


@router.get("/pending")
async def list_pending_approvals(
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """List pending approvals for the authenticated user."""
    rid = trace_id_ctx.get("")
    user_id = user.user_id
    result = await session.execute(
        select(Approval)
        .where(Approval.user_id == user_id, Approval.decision == "pending")
        .order_by(Approval.requested_at.desc())
    )
    approvals = result.scalars().all()
    data = []
    for a in approvals:
        # Parse tool_name and tool_args from preview_text
        preview = a.preview_text or ""
        tool_name = None
        tool_args = None
        if "\n" in preview:
            first_line, rest = preview.split("\n", 1)
            tool_name = first_line.strip()
            try:
                import json as _json
                tool_args = _json.loads(rest)
            except (ValueError, TypeError):
                pass
        elif preview:
            tool_name = preview.strip()

        data.append({
            "id": str(a.id),
            "run_id": str(a.run_id),
            "risk_tier": a.risk_tier,
            "preview_text": preview,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "domain": a.domain,
            "status": a.decision,  # Frontend expects "status" not "decision"
            "created_at": a.requested_at.isoformat(),  # Frontend expects "created_at"
        })
    return success_envelope(data=data, trace_id=rid)


@router.get("/history")
async def list_approval_history(
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """List decided approvals (approved/denied) for the authenticated user."""
    rid = trace_id_ctx.get("")
    user_id = user.user_id
    result = await session.execute(
        select(Approval)
        .where(Approval.user_id == user_id, Approval.decision != "pending")
        .order_by(Approval.decided_at.desc())
        .limit(50)
    )
    approvals = result.scalars().all()
    data = []
    for a in approvals:
        preview = a.preview_text or ""
        tool_name = None
        if "\n" in preview:
            tool_name = preview.split("\n", 1)[0].strip()
        elif preview:
            tool_name = preview.strip()

        data.append({
            "id": str(a.id),
            "run_id": str(a.run_id),
            "risk_tier": a.risk_tier,
            "preview_text": preview,
            "tool_name": tool_name,
            "domain": a.domain,
            "status": a.decision,
            "created_at": a.requested_at.isoformat(),
            "decided_at": a.decided_at.isoformat() if a.decided_at else None,
        })
    return success_envelope(data=data, trace_id=rid)


@router.post("/{approval_id}/decide")
async def decide_approval(
    approval_id: uuid.UUID,
    body: ApprovalDecision,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
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

    # IDOR check: only the approval owner may decide it
    if approval.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorised to decide this approval",
        )

    if approval.decision != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval already decided: {approval.decision}",
        )

    approval.decision = body.decision
    approval.decided_at = datetime.now(UTC)
    approval.decided_by_user_id = user.user_id
    await session.flush()
    await session.commit()

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

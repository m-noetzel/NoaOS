"""Approval endpoints — SPEC.md §29.6."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


class ApprovalDecision(BaseModel):
    """Request body for approval decision."""

    decision: str  # "approved" | "denied"


@router.get("/pending")
async def list_pending_approvals(
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """List pending approvals for the authenticated user."""
    rid = trace_id_ctx.get("")
    return success_envelope(data={"approvals": []}, trace_id=rid)


@router.post("/{approval_id}/decide")
async def decide_approval(
    approval_id: uuid.UUID,
    body: ApprovalDecision,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Approve or deny a pending approval per §29.6."""
    rid = trace_id_ctx.get("")
    return success_envelope(
        data={
            "approval_id": str(approval_id),
            "decision": body.decision,
            "status": "decided",
        },
        trace_id=rid,
    )

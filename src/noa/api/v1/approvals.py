"""Approval endpoints — SPEC.md §29.6.

OV2: decide_approval() now resumes the interrupted LangGraph graph instead
of executing the tool outside the graph via _execute_approved_tool().
"""

from __future__ import annotations

import asyncio
import json
import logging
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


def _handle_memory_approval(*, approval: Approval, decision: str) -> None:
    """Update MemoryStore when a memory auto-extract approval is decided.

    BE-H7: When a user approves a memory fact via the approvals flow,
    the fact must be marked 'approved' in the MemoryStore so it becomes
    available for recall.  When denied, the fact is removed.

    The fact_id is embedded in the approval's preview_text as JSON args,
    e.g.: ``memory\\n{"fact_id": "<uuid>", "fact": "...", ...}``
    """
    try:
        from noa.api.app_state import get_memory_store

        store = get_memory_store()
        if store is None:
            return

        # Parse tool_name and fact_id from preview_text
        preview = approval.preview_text or ""
        if "\n" not in preview:
            return
        first_line, rest = preview.split("\n", 1)
        tool_name = first_line.strip().lower()
        if tool_name != "memory":
            return

        try:
            args = json.loads(rest)
        except (ValueError, TypeError):
            return

        fact_id = args.get("fact_id")
        if not fact_id:
            return

        user_id = str(approval.user_id)
        if decision == "approved":
            updated = store.update_status(fact_id, "approved", user_id=user_id)
            if updated:
                logger.info(
                    "Memory fact %s approved for user %s", fact_id, user_id
                )
            else:
                logger.warning(
                    "Memory fact %s not found in store (user=%s)", fact_id, user_id
                )
        elif decision == "denied":
            deleted = store.delete(fact_id, user_id=user_id)
            if deleted:
                logger.info(
                    "Memory fact %s denied and removed for user %s", fact_id, user_id
                )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to update MemoryStore on approval decision", exc_info=True
        )


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

    # BE-H7: When a memory auto-extract approval is approved, persist the
    # fact to MemoryStore so it becomes available for recall.
    _handle_memory_approval(approval=approval, decision=body.decision)

    # OV2: Resume the graph via runner.resume() (fire-and-forget).
    # The runner continues the graph from interrupt() in tool_node.
    # Both approved and denied paths go through resume() — for denial,
    # tool_node inserts a denial message, then the graph completes normally.
    run_id_str = str(approval.run_id)
    decision_payload: dict[str, Any] = {"decision": body.decision}

    asyncio.ensure_future(
        _resume_graph(
            run_id=run_id_str,
            decision=decision_payload,
            user_id=str(user.user_id),
        )
    )

    data: dict[str, Any] = {
        "approval_id": str(approval_id),
        "decision": approval.decision,
        "status": "decided",
        "risk_tier": approval.risk_tier,
        "decided_at": approval.decided_at.isoformat(),
    }

    return success_envelope(data=data, trace_id=rid)


async def _resume_graph(
    run_id: str,
    decision: dict[str, Any],
    user_id: str,  # noqa: ARG001 — kept for call-site symmetry; graph has its own context
) -> None:
    """Resume the interrupted LangGraph graph with the user's approval decision.

    OV2: Replaces _execute_approved_tool().  The runner.resume() method
    continues the graph from the interrupt() point in tool_node, which
    re-dispatches the tool with approved=True (or inserts a denial message)
    and then continues to responder and evaluator normally.

    Runs as a fire-and-forget background task (asyncio.ensure_future) so
    decide_approval can return immediately.
    """
    try:
        from noa.api.app_state import get_runner, get_session_factory
        from noa.runs.service import RunService

        runner = get_runner()
        if runner is None:
            logger.warning(
                "No runner available to resume graph for run_id=%s", run_id
            )
            return

        session_factory = get_session_factory()
        if session_factory is None:
            logger.warning(
                "No session factory available to resume graph for run_id=%s", run_id
            )
            return

        async with session_factory() as db_session:
            run_service = RunService(session=db_session)
            async for _event in runner.resume(
                run_id=run_id,
                decision=decision,
                run_service=run_service,
            ):
                # Events persisted inside resume() via run_service.
                # The original SSE connection is gone; drain the generator.
                pass

    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to resume graph for run_id=%s",
            run_id,
            exc_info=True,
        )

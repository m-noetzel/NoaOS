"""Approval endpoints — SPEC.md §29.6."""

from __future__ import annotations

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

    # Execute the approved tool and complete the run
    tool_result = None
    if body.decision == "approved":
        tool_result = await _execute_approved_tool(approval, str(user.user_id))

    data: dict[str, Any] = {
        "approval_id": str(approval_id),
        "decision": approval.decision,
        "status": "decided",
        "risk_tier": approval.risk_tier,
        "decided_at": approval.decided_at.isoformat(),
    }
    if tool_result is not None:
        data["tool_result"] = tool_result

    return success_envelope(data=data, trace_id=rid)


async def _execute_approved_tool(
    approval: Approval, user_id: str
) -> dict[str, Any] | None:
    """Execute a tool after its approval is granted, then complete the run.

    Parses tool/function/args from the approval's preview_text,
    dispatches via ToolGateway with approved=True, and updates the
    run status from awaiting_approval → completed.
    """
    try:
        from noa.api.app_state import get_gateway, get_session_factory
        from noa.tools.gateway import ToolRequest

        gateway = get_gateway()
        if gateway is None:
            logger.warning("No ToolGateway available to execute approved tool")
            return None

        # Parse tool_name and args from preview_text
        # Format: "tool.function\n{args_json}" or "tool_name\n{args_json}"
        preview = approval.preview_text or ""
        if "\n" not in preview:
            logger.warning("Cannot parse tool from approval preview_text: %s", preview)
            return None

        first_line, rest = preview.split("\n", 1)
        tool_function = first_line.strip()

        try:
            tool_args = json.loads(rest)
        except (ValueError, TypeError):
            tool_args = {}

        # Parse "tool.function" or just "function"
        if "." in tool_function:
            tool_name, func_name = tool_function.split(".", 1)
        else:
            tool_name = tool_function
            func_name = tool_function

        # Dispatch with approved=True to bypass the approval gate
        request = ToolRequest(
            tool=tool_name,
            function=func_name,
            args=tool_args,
            approved=True,
            user_id=uuid.UUID(user_id),
            privacy_mode=approval.domain or "external",
        )

        response = await gateway.dispatch(request, approvals_enabled=False)

        # Resume run — set back to "running" so the next message continues
        # the same run (a Run = full task lifecycle, not a single action).
        try:
            session_factory = get_session_factory()
            if session_factory:
                async with session_factory() as db_session:
                    from noa.db.models.run import Run

                    result = await db_session.execute(
                        select(Run).where(Run.id == approval.run_id)
                    )
                    run = result.scalar_one_or_none()
                    if run and run.status == "awaiting_approval":
                        run.status = "running"
                        run.updated_at = datetime.now(UTC)
                        await db_session.commit()
                        logger.info(
                            "Run %s resumed after approval %s",
                            approval.run_id,
                            approval.id,
                        )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to update run status after approval", exc_info=True
            )

        if response.error:
            logger.warning(
                "Tool execution after approval failed: %s", response.error
            )
            return {"error": response.error}

        return response.result

    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to execute approved tool for approval %s",
            approval.id,
            exc_info=True,
        )
        return None

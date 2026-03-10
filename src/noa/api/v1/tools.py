"""Tool enable/disable API endpoints — MR5 capability management.

POST   /api/v1/tools/{name}/enable  — grant capability to caller
DELETE /api/v1/tools/{name}         — revoke capability for caller
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth
from noa.tools.capabilities import TOOL_CAPABILITIES, DbCapabilityChecker

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


@router.post("/{name}/enable")
async def enable_tool(
    name: str,
    payload: Any = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Grant the calling user the capability for the named tool."""
    if name not in TOOL_CAPABILITIES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown tool: {name}",
        )

    rid = trace_id_ctx.get("")
    user_id = (
        payload.user_id if hasattr(payload, "user_id") else uuid.UUID(payload["sub"])
    )
    checker = DbCapabilityChecker(session)
    await checker.grant(user_id=user_id, tool_name=name, granted_by=user_id)

    return success_envelope(data={
        "tool": name,
        "capability": TOOL_CAPABILITIES[name],
        "status": "granted",
    }, trace_id=rid)


@router.delete("/{name}")
async def disable_tool(
    name: str,
    payload: Any = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Revoke the calling user's capability for the named tool."""
    rid = trace_id_ctx.get("")
    user_id = (
        payload.user_id if hasattr(payload, "user_id") else uuid.UUID(payload["sub"])
    )
    checker = DbCapabilityChecker(session)
    count = await checker.revoke(user_id=user_id, tool_name=name)

    return success_envelope(data={
        "tool": name,
        "revoked": count,
        "status": "revoked",
    }, trace_id=rid)

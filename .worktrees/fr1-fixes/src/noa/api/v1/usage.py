"""Usage endpoints — web client usage/cost tracking."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import AuthUser, require_auth

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])


@router.get("")
async def get_usage(
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Get usage data with daily and monthly breakdown."""
    rid = trace_id_ctx.get("")
    # Stub: return mock usage data
    return success_envelope(
        data={
            "daily": {
                "cost_usd": 0.0,
                "requests": 0,
            },
            "monthly": {
                "cost_usd": 0.0,
                "requests": 0,
            },
        },
        trace_id=rid,
    )

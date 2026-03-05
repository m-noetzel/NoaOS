"""Settings endpoints — web client user settings."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import require_auth

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class UpdateSettingsRequest(BaseModel):
    """Request body for updating user settings."""

    default_model: str | None = None
    default_privacy_mode: str | None = None
    budget_daily_usd: float | None = None
    budget_monthly_usd: float | None = None


@router.get("")
async def get_settings(
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Get user settings."""
    rid = trace_id_ctx.get("")
    # Stub: return default settings
    return success_envelope(
        data={
            "default_model": "claude-sonnet-4-20250514",
            "default_privacy_mode": "standard",
            "budget_daily_usd": 10.0,
            "budget_monthly_usd": 200.0,
        },
        trace_id=rid,
    )


@router.put("")
async def update_settings(
    body: UpdateSettingsRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Update user settings."""
    rid = trace_id_ctx.get("")
    return success_envelope(data={"status": "saved"}, trace_id=rid)

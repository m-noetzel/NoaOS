"""Settings endpoints — user preferences and tool credentials."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import AuthUser, require_auth
from noa.settings.repository import SettingsRepository
from noa.settings.service import SettingsService

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class UpdateSettingsRequest(BaseModel):
    """Request body for updating user settings."""

    default_model: str | None = None
    default_provider: str | None = None
    default_privacy_mode: str | None = None
    budget_daily_usd: float | None = None
    budget_monthly_usd: float | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    notion_token: str | None = None
    tavily_api_key: str | None = None
    ollama_base_url: str | None = None


@router.get("")
async def get_settings(
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Get user settings with masked API keys."""
    rid = trace_id_ctx.get("")
    service = SettingsService(SettingsRepository(session))
    user_id = user.user_id
    data = await service.get_settings(user_id)
    return success_envelope(data=data, trace_id=rid)


@router.put("")
async def update_settings(
    body: UpdateSettingsRequest,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Update user settings. Partial updates supported."""
    rid = trace_id_ctx.get("")
    service = SettingsService(SettingsRepository(session))
    user_id = user.user_id
    updates = body.model_dump(exclude_unset=True)
    data = await service.update_settings(user_id, updates)
    await session.commit()
    return success_envelope(data=data, trace_id=rid)


@router.patch("")
async def patch_settings(
    body: UpdateSettingsRequest,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Partially update user settings. Only provided fields are changed."""
    rid = trace_id_ctx.get("")
    service = SettingsService(SettingsRepository(session))
    user_id = user.user_id
    # exclude_unset ensures only explicitly provided fields are applied
    updates = body.model_dump(exclude_unset=True)
    data = await service.update_settings(user_id, updates)
    await session.commit()
    return success_envelope(data=data, trace_id=rid)

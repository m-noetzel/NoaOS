"""Settings endpoints — user preferences and tool credentials."""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

# Credential fields that require reloading the LLM provider router when changed.
_LLM_CREDENTIAL_FIELDS = frozenset({
    "anthropic_api_key",
    "openai_api_key",
    "ollama_base_url",
})


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


def _reload_llm_pipeline_if_needed(
    updates: dict[str, Any],
    full_settings: dict[str, Any],
) -> None:
    """Reload the LLM ProviderRouter when credential fields change.

    BE-H1: After credentials are persisted to DB, the in-memory ProviderRouter
    must be updated so the new keys take effect without a restart.

    Only reloads if one of the LLM credential fields was included in *updates*.

    Uses *full_settings* (the complete post-update settings row) rather than
    just *updates* so that a partial update (e.g. only openai_api_key) does not
    silently drop credentials that were already stored for other providers.
    """
    if not _LLM_CREDENTIAL_FIELDS.intersection(updates):
        return

    try:
        import os

        from noa.api.app_state import set_provider_router
        from noa.external_worker.llm.router import ProviderRouter

        # Build a minimal settings-like object from the *full* settings dict so
        # that a partial update (e.g. only openai_api_key changed) preserves all
        # other provider credentials that were already stored in the DB.
        # Env-var values act as final fallback for any key not in DB.

        class _DynSettings:
            """Minimal settings adapter for ProviderRouter.from_settings()."""

            anthropic_api_key: str | None = full_settings.get(
                "anthropic_api_key",
                os.environ.get("ANTHROPIC_API_KEY"),
            )
            openai_api_key: str | None = full_settings.get(
                "openai_api_key",
                os.environ.get("OPENAI_API_KEY"),
            )
            google_ai_api_key: str | None = os.environ.get("GOOGLE_AI_API_KEY")
            ollama_base_url: str | None = full_settings.get(
                "ollama_base_url",
                os.environ.get("OLLAMA_BASE_URL", "http://private-worker:11434"),
            )
            default_provider: str = (
                full_settings.get("default_provider", "openai") or "openai"
            )

        new_router = ProviderRouter.from_settings(_DynSettings())
        set_provider_router(new_router)

        # Also update the agent router used inside the orchestrator graph
        try:
            from noa.orchestrator.nodes.agent import (
                set_router as set_agent_router,
            )
            set_agent_router(new_router)
        except Exception:  # noqa: BLE001
            logger.debug("Agent router not available for reload", exc_info=True)

        logger.info(
            "ProviderRouter reloaded after credential update: providers=%s",
            new_router.available_providers,
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to reload ProviderRouter after credential update",
            exc_info=True,
        )


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
    # BE-H1: Reload ProviderRouter if LLM credential fields changed.
    # Pass full settings (data) so partial updates don't drop other credentials.
    _reload_llm_pipeline_if_needed(updates, full_settings=data)
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
    # BE-H1: Reload ProviderRouter if LLM credential fields changed.
    # Pass full settings (data) so partial updates don't drop other credentials.
    _reload_llm_pipeline_if_needed(updates, full_settings=data)
    return success_envelope(data=data, trace_id=rid)

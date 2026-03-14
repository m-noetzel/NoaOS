"""Settings endpoints — user preferences and tool credentials."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from noa.api.deps import get_db_session
from noa.api.middleware import trace_id_ctx
from noa.api.schemas.common import success_envelope
from noa.auth.middleware import AuthUser, require_auth
from noa.settings.repository import SettingsRepository
from noa.settings.service import SettingsService

# UX-H3: Path to the default system prompt file in the repo
_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "prompts"
_DEFAULT_SYSTEM_PROMPT_FILE = _PROMPTS_DIR / "system_prompt.txt"

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
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    notion_token: str | None = None
    tavily_api_key: str | None = None
    ollama_base_url: str | None = None
    # UX-M2: Governance — human-in-the-loop approvals toggle
    approvals_enabled: bool | None = None
    # UX-M4: Agent execution limits
    max_tool_calls: int | None = None
    max_retries: int | None = None
    timeout_seconds: int | None = None


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


# Providers available per domain (BE-H11)
_ALL_PROVIDERS = ["anthropic", "openai", "google_ai", "ollama"]
_PRIVATE_PROVIDERS = ["ollama"]
_EXTERNAL_PROVIDERS = _ALL_PROVIDERS


@router.get("/providers")
async def list_providers(
    privacy_mode: Literal["private", "external"] = Query(default="external"),  # noqa: B008
    user: AuthUser = Depends(require_auth),  # noqa: B008
) -> dict[str, Any]:
    """Return the list of providers available in the requested domain.

    BE-H11: In private mode only 'ollama' (local) is returned.
    In external mode all configured providers are returned.
    """
    rid = trace_id_ctx.get("")
    provider_meta: dict[str, dict[str, str]] = {
        "anthropic": {"domain": "external", "description": "Anthropic Claude"},
        "openai": {"domain": "external", "description": "OpenAI GPT"},
        "google_ai": {"domain": "external", "description": "Google Gemini"},
        "ollama": {"domain": "private", "description": "Local Ollama (on-device)"},
    }
    names = _PRIVATE_PROVIDERS if privacy_mode == "private" else _ALL_PROVIDERS
    providers = [
        {"name": name, **provider_meta[name]}
        for name in names
        if name in provider_meta
    ]
    return success_envelope(data=providers, trace_id=rid)


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


# ---------------------------------------------------------------------------
# UX-H3: System prompt file endpoints
# ---------------------------------------------------------------------------


class SystemPromptBody(BaseModel):
    """Request body for updating the system prompt."""

    content: str


def _load_default_system_prompt() -> str:
    """Load the default system prompt from the prompts/ directory."""
    try:
        return _DEFAULT_SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


@router.get("/system-prompt")
async def get_system_prompt(
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Get the current system prompt.

    Returns the user's saved system_prompt from settings if set,
    otherwise falls back to the default from prompts/system_prompt.txt.
    """
    rid = trace_id_ctx.get("")
    service = SettingsService(SettingsRepository(session))
    data = await service.get_settings(user.user_id)
    # User's stored system prompt takes precedence; file is the default
    user_prompt = data.get("system_prompt")
    content = user_prompt or _load_default_system_prompt()
    return success_envelope(
        data={"content": content, "is_default": not user_prompt},
        trace_id=rid,
    )


@router.put("/system-prompt")
async def update_system_prompt(
    body: SystemPromptBody,
    request: Request,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Save a custom system prompt for the user.

    Stores the prompt in user settings so it persists across sessions.
    To restore the default, PUT an empty string.
    """
    rid = trace_id_ctx.get("")
    if len(body.content) > 10_000:
        raise HTTPException(
            status_code=422,
            detail="System prompt exceeds 10,000 character limit",
        )
    service = SettingsService(SettingsRepository(session))
    content = body.content.strip() or None  # empty string -> reset to default
    data = await service.update_settings(user.user_id, {"system_prompt": content})
    await session.commit()
    # Return what was saved (or default if reset)
    saved_content = data.get("system_prompt") or _load_default_system_prompt()
    return success_envelope(
        data={"content": saved_content, "is_default": not data.get("system_prompt")},
        trace_id=rid,
    )


def load_default_system_prompt() -> str:
    """Public helper: load default system prompt from prompts/ directory.

    Used by the orchestrator to seed the system prompt when no user
    override is present.
    """
    return _load_default_system_prompt()

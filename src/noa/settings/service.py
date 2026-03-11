"""Settings service — business logic with API key masking."""

from __future__ import annotations

import os
import uuid
from typing import Any

from noa.settings.repository import SettingsRepository

# Fields that contain secrets and must be masked on read
_SECRET_FIELDS = frozenset({
    "anthropic_api_key",
    "openai_api_key",
    "google_client_secret",
    "notion_token",
    "tavily_api_key",
})

# All credential/config fields accepted on update
_ALL_FIELDS = frozenset({
    "default_model",
    "default_provider",
    "default_privacy_mode",
    "budget_daily_usd",
    "budget_monthly_usd",
    "anthropic_api_key",
    "openai_api_key",
    "google_client_id",
    "google_client_secret",
    "notion_token",
    "tavily_api_key",
    "ollama_base_url",
})

_DEFAULTS: dict[str, Any] = {
    "default_model": "claude-sonnet-4-20250514",
    "default_provider": "anthropic",
    "default_privacy_mode": "external",
    "budget_daily_usd": 10.0,
    "budget_monthly_usd": 200.0,
    "anthropic_api_key": None,
    "openai_api_key": None,
    "google_client_id": None,
    "google_client_secret": None,
    "notion_token": None,
    "tavily_api_key": None,
    "ollama_base_url": "http://private-worker:11434",
}


# Map from settings field name → env var name (for keychain override)
_FIELD_TO_ENV: dict[str, str] = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "openai_api_key": "OPENAI_API_KEY",
    "google_client_id": "GOOGLE_CLIENT_ID",
    "google_client_secret": "GOOGLE_CLIENT_SECRET",
    "notion_token": "NOTION_TOKEN",
    "tavily_api_key": "TAVILY_API_KEY",
    "ollama_base_url": "OLLAMA_BASE_URL",
}


class SettingsService:
    """Settings business logic with masking for secret fields."""

    def __init__(self, repo: SettingsRepository) -> None:
        self._repo = repo

    @staticmethod
    def get_effective_key(
        field_name: str, *, db_value: str | None = None,
    ) -> str | None:
        """Return env var value if set, else fall back to DB value.

        Env vars from keychain bootstrap take priority over DB-stored
        keys per SPEC.md §11.2.
        """
        env_name = _FIELD_TO_ENV.get(field_name, field_name.upper())
        env_value = os.environ.get(env_name, "")
        if env_value:
            return env_value
        return db_value

    @staticmethod
    def mask_key(key: str | None) -> str | None:
        """Mask an API key, showing only the last 4 characters.

        Returns None for None or empty strings.
        """
        if not key:
            return None
        if len(key) <= 4:
            return "****"
        return f"****{key[-4:]}"

    async def get_settings(self, user_id: uuid.UUID) -> dict[str, Any]:
        """Get settings for a user, with API keys masked."""
        row = await self._repo.get_by_user_id(user_id)
        if row is None:
            # Return defaults with masked env-var keys
            result = dict(_DEFAULTS)
            for field in _SECRET_FIELDS:
                env_val = self.get_effective_key(field, db_value=None)
                result[field] = self.mask_key(env_val)
            return result

        result: dict[str, Any] = {}
        for field in _ALL_FIELDS:
            db_value = getattr(row, field, None)
            if field in _SECRET_FIELDS:
                effective = self.get_effective_key(field, db_value=db_value)
                result[field] = self.mask_key(effective)
            else:
                # Decimal → float for JSON serialization
                val = db_value
                if hasattr(val, "as_integer_ratio"):
                    val = float(val)
                result[field] = val
        return result

    async def update_settings(
        self, user_id: uuid.UUID, updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update settings. Only provided fields are changed.

        Empty strings for secret fields are treated as None (clear).
        Returns the updated settings (masked).
        """
        # Filter to allowed fields only, normalize empty strings
        filtered: dict[str, Any] = {}
        for key, value in updates.items():
            if key not in _ALL_FIELDS:
                continue
            if key in _SECRET_FIELDS and value == "":
                value = None
            filtered[key] = value

        await self._repo.upsert(user_id, filtered)
        return await self.get_settings(user_id)

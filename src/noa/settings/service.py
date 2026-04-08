"""Settings service — business logic with API key masking."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from noa.settings.repository import SettingsRepository

# Single source of truth for the system prompt (file on disk).
# Read/written by both the API and the runner. No DB storage.
_SYSTEM_PROMPT_FILE = (
    Path(__file__).parent.parent.parent.parent
    / "prompts"
    / "system_prompt.txt"
)

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
    "temperature",
    "max_tokens",
    "anthropic_api_key",
    "openai_api_key",
    "google_client_id",
    "google_client_secret",
    "notion_token",
    "tavily_api_key",
    "ollama_base_url",
    # UX-M2, UX-M4: governance & agent limits
    "approvals_enabled",
    "max_tool_calls",
    "max_retries",
    "timeout_seconds",
    # PC1: custom privacy classifier keywords
    "private_keywords",
    # OV4 / UX-EV1: evaluator configuration
    "eval_config",
})

# Fields stored as JSON blobs (TEXT column, decode on read)
_JSON_FIELDS = frozenset({"node_models", "private_keywords", "eval_config"})

_DEFAULTS: dict[str, Any] = {
    "default_model": "claude-sonnet-4-20250514",
    "default_provider": "anthropic",
    "default_privacy_mode": "external",
    "budget_daily_usd": 10.0,
    "budget_monthly_usd": 200.0,
    "temperature": 0.7,
    "max_tokens": 4096,
    "anthropic_api_key": None,
    "openai_api_key": None,
    "google_client_id": None,
    "google_client_secret": None,
    "notion_token": None,
    "tavily_api_key": None,
    "ollama_base_url": "http://private-worker:11434",
    # UX-M2, UX-M4: governance & agent limits
    "approvals_enabled": True,
    "max_tool_calls": 10,
    "max_retries": 3,
    "timeout_seconds": 120,
    # MC1: Per-node model configuration (None = use ModelConfig defaults)
    "node_models": None,
    # PC1: User-configurable private keywords (None = use built-in defaults only)
    "private_keywords": None,
    # OV4 / UX-EV1: evaluator config (None = use hardcoded defaults)
    "eval_config": None,
}


def read_system_prompt() -> str:
    """Read the system prompt from the file on disk.

    This is the single source of truth for the system prompt.
    The same file is read by the settings API and the orchestrator runner.
    """
    try:
        return _SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_system_prompt(content: str) -> None:
    """Write the system prompt to the file on disk.

    Called when the user edits the prompt in the UI. The file is the
    canonical store — there is no DB column for system_prompt.
    """
    _SYSTEM_PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SYSTEM_PROMPT_FILE.write_text(content.strip() + "\n", encoding="utf-8")


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
        """Get settings for a user, with API keys masked.

        system_prompt is read from the file (prompts/system_prompt.txt),
        not the DB. Single source of truth — file, UI, and runner all
        see the same value.
        """
        row = await self._repo.get_by_user_id(user_id)
        if row is None:
            # Return defaults with masked env-var keys
            defaults_result: dict[str, Any] = dict(_DEFAULTS)
            for field in _SECRET_FIELDS:
                env_val = self.get_effective_key(field, db_value=None)
                defaults_result[field] = self.mask_key(env_val)
            defaults_result["system_prompt"] = read_system_prompt()
            return defaults_result

        row_result: dict[str, Any] = {}
        for field in _ALL_FIELDS:
            db_value = getattr(row, field, None)
            if field in _SECRET_FIELDS:
                effective = self.get_effective_key(field, db_value=db_value)
                row_result[field] = self.mask_key(effective)
            else:
                # Decimal → float for JSON serialization
                val: Any = db_value
                if hasattr(val, "as_integer_ratio"):
                    val = float(val)
                row_result[field] = val
        # Always from file, never DB
        row_result["system_prompt"] = read_system_prompt()

        # MC1: node_models stored as JSON TEXT — decode and include
        raw_node_models = getattr(row, "node_models", None)
        if raw_node_models:
            try:
                row_result["node_models"] = json.loads(raw_node_models)
            except (json.JSONDecodeError, TypeError):
                row_result["node_models"] = None
        else:
            row_result["node_models"] = None

        # PC1: private_keywords stored as JSON TEXT — decode and include
        raw_private_keywords = getattr(row, "private_keywords", None)
        if raw_private_keywords:
            try:
                row_result["private_keywords"] = json.loads(raw_private_keywords)
            except (json.JSONDecodeError, TypeError):
                row_result["private_keywords"] = None
        else:
            row_result["private_keywords"] = None

        # OV4 / UX-EV1: eval_config stored as JSON TEXT — decode and include
        raw_eval_config = getattr(row, "eval_config", None)
        if raw_eval_config:
            try:
                row_result["eval_config"] = json.loads(raw_eval_config)
            except (json.JSONDecodeError, TypeError):
                row_result["eval_config"] = None
        else:
            row_result["eval_config"] = None

        return row_result

    async def get_scope_overrides(
        self, user_id: uuid.UUID,
    ) -> dict[str, list[str]]:
        """Return persisted scope overrides for a user.

        Returns an empty dict when no overrides have been set (caller should
        fall back to registry defaults).
        """
        row = await self._repo.get_by_user_id(user_id)
        if row is None or row.scope_overrides is None:
            return {}
        try:
            parsed: dict[str, list[str]] = json.loads(row.scope_overrides)
            return parsed
        except (json.JSONDecodeError, TypeError):
            return {}

    async def set_scope_override(
        self,
        user_id: uuid.UUID,
        scope_name: str,
        tools: list[str],
    ) -> dict[str, list[str]]:
        """Persist a single scope override for a user.

        Merges with any existing overrides (other scopes are untouched).
        Returns the full updated overrides dict.
        """
        current = await self.get_scope_overrides(user_id)
        current[scope_name] = tools
        encoded = json.dumps(current)
        await self._repo.upsert(user_id, {"scope_overrides": encoded})
        return current

    async def update_settings(
        self, user_id: uuid.UUID, updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update settings. Only provided fields are changed.

        system_prompt writes to the file on disk (single source of truth).
        Empty strings for secret fields are treated as None (clear).
        Returns the updated settings (masked).
        """
        # Handle system_prompt separately — goes to file, not DB
        if "system_prompt" in updates:
            prompt_val = updates["system_prompt"] or ""
            if len(prompt_val) > 10_000:
                msg = "System prompt exceeds 10,000 character limit"
                raise ValueError(msg)
            write_system_prompt(prompt_val)

        # Filter to DB-backed fields only, normalize empty strings
        filtered: dict[str, Any] = {}
        for key, value in updates.items():
            if key not in _ALL_FIELDS:
                continue
            if key in _SECRET_FIELDS and value == "":
                value = None
            filtered[key] = value

        # MC1: handle node_models separately (JSON-encoded TEXT column).
        # Strip None values so only explicitly-set models are stored.
        if "node_models" in updates:
            nm_value = updates["node_models"]
            if nm_value is None:
                filtered["node_models"] = None
            elif isinstance(nm_value, dict):
                # Remove None values — only store explicitly configured models
                cleaned = {k: v for k, v in nm_value.items() if v is not None}
                filtered["node_models"] = json.dumps(cleaned) if cleaned else None
            # ignore non-dict values

        # PC1: handle private_keywords (JSON-encoded TEXT column).
        # Stores a list of user-defined keyword strings.
        if "private_keywords" in updates:
            kw_value = updates["private_keywords"]
            if kw_value is None:
                filtered["private_keywords"] = None
            elif isinstance(kw_value, list):
                # Store non-empty strings only
                cleaned_kw = [str(k) for k in kw_value if k]
                filtered["private_keywords"] = (
                    json.dumps(cleaned_kw) if cleaned_kw else None
                )
            # ignore non-list values

        # OV4 / UX-EV1: handle eval_config (JSON-encoded TEXT column).
        # Stores evaluator threshold settings as a JSON object.
        if "eval_config" in updates:
            ec_value = updates["eval_config"]
            if ec_value is None:
                filtered["eval_config"] = None
            elif isinstance(ec_value, dict):
                # Only store recognised keys with valid types
                cleaned_ec: dict[str, Any] = {}
                if ec_value.get("pass_threshold") is not None:
                    cleaned_ec["pass_threshold"] = float(ec_value["pass_threshold"])
                if ec_value.get("reroute_threshold") is not None:
                    cleaned_ec["reroute_threshold"] = float(
                        ec_value["reroute_threshold"]
                    )
                if ec_value.get("max_cycles") is not None:
                    cleaned_ec["max_cycles"] = int(ec_value["max_cycles"])
                filtered["eval_config"] = json.dumps(cleaned_ec) if cleaned_ec else None
            # ignore non-dict values

        if filtered:
            await self._repo.upsert(user_id, filtered)
        return await self.get_settings(user_id)

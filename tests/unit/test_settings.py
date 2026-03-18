"""Tests for Phase CM1: Settings Persistence & Tool Credentials.

Covers: user_settings DB model, repository CRUD, service layer with
API key masking, and settings API endpoint wiring.

Spec refs: SPEC.md §11.1, §24
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.cm1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user_id() -> uuid.UUID:
    return uuid.uuid4()


def _settings_dict(**overrides) -> dict:
    """Default settings field values."""
    defaults = {
        "default_model": "claude-sonnet-4-20250514",
        "default_provider": "anthropic",
        "default_privacy_mode": "standard",
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
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# ORM Model
# ---------------------------------------------------------------------------

class TestUserSettingsModel:
    """Tests for the SQLAlchemy ORM model."""

    def test_model_has_required_columns(self):
        from noa.settings.models import UserSettings

        # Verify all expected columns exist on the model
        expected = {
            "id", "user_id", "default_model", "default_provider",
            "default_privacy_mode", "budget_daily_usd", "budget_monthly_usd",
            "anthropic_api_key", "openai_api_key", "google_client_id",
            "google_client_secret", "notion_token", "tavily_api_key",
            "ollama_base_url", "created_at", "updated_at",
        }
        mapper = UserSettings.__table__
        actual = {c.name for c in mapper.columns}
        assert expected.issubset(actual), f"Missing columns: {expected - actual}"

    def test_model_tablename(self):
        from noa.settings.models import UserSettings

        assert UserSettings.__tablename__ == "user_settings"

    def test_user_id_is_unique(self):
        from noa.settings.models import UserSettings

        col = UserSettings.__table__.c.user_id
        assert col.unique or any(
            uc.columns.contains_column(col)
            for uc in UserSettings.__table__.constraints
            if hasattr(uc, "columns")
        ), "user_id must have a unique constraint"


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class TestSettingsRepository:
    """Tests for settings repository CRUD."""

    @pytest.mark.asyncio
    async def test_upsert_creates_new_settings(self):
        from noa.settings.repository import SettingsRepository

        user_id = _make_user_id()
        mock_session = AsyncMock()
        # Simulate no existing row
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SettingsRepository(mock_session)
        await repo.upsert(user_id, _settings_dict())

        # Should have called execute (select + add/merge)
        assert (
            mock_session.execute.called
            or mock_session.merge.called
            or mock_session.add.called
        )

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_settings(self):
        from noa.settings.models import UserSettings
        from noa.settings.repository import SettingsRepository

        user_id = _make_user_id()
        existing = MagicMock(spec=UserSettings)
        existing.user_id = user_id

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = mock_result

        repo = SettingsRepository(mock_session)
        await repo.upsert(user_id, {"default_model": "gpt-4o"})

        # The existing object's attribute should be updated
        assert existing.default_model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_get_returns_none_for_unknown_user(self):
        from noa.settings.repository import SettingsRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SettingsRepository(mock_session)
        result = await repo.get_by_user_id(_make_user_id())
        assert result is None


# ---------------------------------------------------------------------------
# Service — masking logic
# ---------------------------------------------------------------------------

class TestSettingsService:
    """Tests for settings service with API key masking."""

    def test_mask_key_returns_last_4_chars(self):
        from noa.settings.service import SettingsService

        masked = SettingsService.mask_key("sk-ant-api03-abcdefghijklmnop")
        assert masked.endswith("mnop")
        assert "sk-ant" not in masked  # original prefix hidden
        assert len(masked) < len("sk-ant-api03-abcdefghijklmnop")

    def test_mask_key_short_key_still_safe(self):
        from noa.settings.service import SettingsService

        masked = SettingsService.mask_key("abc")
        # Short keys should be fully masked or handled safely
        assert masked is not None
        assert "abc" not in masked or len(masked) <= 4

    def test_mask_key_none_returns_none(self):
        from noa.settings.service import SettingsService

        assert SettingsService.mask_key(None) is None

    def test_mask_key_empty_returns_none(self):
        from noa.settings.service import SettingsService

        assert SettingsService.mask_key("") is None

    @pytest.mark.asyncio
    async def test_get_settings_returns_defaults_when_no_row(self):
        from noa.settings.service import SettingsService

        mock_repo = AsyncMock()
        mock_repo.get_by_user_id.return_value = None

        service = SettingsService(mock_repo)
        result = await service.get_settings(_make_user_id())

        assert result["default_model"] is not None
        assert result["default_privacy_mode"] == "external"
        # API key fields should be None in defaults
        assert result["anthropic_api_key"] is None

    @pytest.mark.asyncio
    async def test_get_settings_masks_api_keys(self):
        from noa.settings.models import UserSettings
        from noa.settings.service import SettingsService

        row = MagicMock(spec=UserSettings)
        row.default_model = "claude-sonnet-4-20250514"
        row.default_provider = "anthropic"
        row.default_privacy_mode = "standard"
        row.budget_daily_usd = 10.0
        row.budget_monthly_usd = 200.0
        row.anthropic_api_key = "sk-ant-api03-realkey1234abcd"
        row.openai_api_key = "sk-openai-key5678efgh"
        row.google_client_id = "123456.apps.googleusercontent.com"
        row.google_client_secret = "GOCSPX-secretvalue"  # noqa: S105
        row.notion_token = "ntn_realtoken9999"  # noqa: S105
        row.tavily_api_key = "tvly-realkey7777"
        row.ollama_base_url = "http://private-worker:11434"

        mock_repo = AsyncMock()
        mock_repo.get_by_user_id.return_value = row

        service = SettingsService(mock_repo)
        result = await service.get_settings(_make_user_id())

        # Full keys must NOT appear
        assert result["anthropic_api_key"] != "sk-ant-api03-realkey1234abcd"
        assert result["openai_api_key"] != "sk-openai-key5678efgh"
        # But they should be masked (not None)
        assert result["anthropic_api_key"] is not None
        assert result["anthropic_api_key"].endswith("abcd")

    @pytest.mark.asyncio
    async def test_update_settings_persists(self):
        from noa.settings.service import SettingsService

        mock_repo = AsyncMock()
        service = SettingsService(mock_repo)

        user_id = _make_user_id()
        await service.update_settings(user_id, {"default_model": "gpt-4o"})

        mock_repo.upsert.assert_called_once()
        call_args = mock_repo.upsert.call_args
        assert call_args[0][0] == user_id
        assert call_args[0][1]["default_model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_update_settings_null_key_clears(self):
        from noa.settings.service import SettingsService

        mock_repo = AsyncMock()
        service = SettingsService(mock_repo)

        await service.update_settings(
            _make_user_id(),
            {"anthropic_api_key": None},
        )

        call_args = mock_repo.upsert.call_args
        assert call_args[0][1]["anthropic_api_key"] is None

    @pytest.mark.asyncio
    async def test_update_settings_empty_string_treated_as_null(self):
        from noa.settings.service import SettingsService

        mock_repo = AsyncMock()
        service = SettingsService(mock_repo)

        await service.update_settings(
            _make_user_id(),
            {"anthropic_api_key": ""},
        )

        call_args = mock_repo.upsert.call_args
        assert call_args[0][1]["anthropic_api_key"] is None

    @pytest.mark.asyncio
    async def test_update_partial_preserves_other_fields(self):
        """Partial update should only set provided fields."""
        from noa.settings.service import SettingsService

        mock_repo = AsyncMock()
        service = SettingsService(mock_repo)

        # Only update default_model — other fields should not be in the upsert dict
        await service.update_settings(
            _make_user_id(),
            {"default_model": "gpt-4o"},
        )

        call_args = mock_repo.upsert.call_args
        update_dict = call_args[0][1]
        assert "default_model" in update_dict
        # Should NOT forcibly set keys not provided
        assert "anthropic_api_key" not in update_dict


# ---------------------------------------------------------------------------
# API endpoint integration
# ---------------------------------------------------------------------------

class TestSettingsAPI:
    """Tests for settings API endpoint schema and structure."""

    def test_update_request_accepts_credential_fields(self):
        """The UpdateSettingsRequest must accept tool credential fields.

        Wave 23: anthropic_api_key and openai_api_key were removed from
        UpdateSettingsRequest (credentials moved to env-var injection).
        Remaining credential fields: google OAuth, notion_token, tavily_api_key,
        ollama_base_url.
        """
        from noa.api.v1.settings import UpdateSettingsRequest

        req = UpdateSettingsRequest(
            google_client_id="client-id",
            google_client_secret="client-secret",  # noqa: S106
            notion_token="ntn_test",  # noqa: S106
            tavily_api_key="tvly-test",
            ollama_base_url="http://localhost:11434",
            default_provider="anthropic",
        )
        assert req.google_client_id == "client-id"
        assert req.default_provider == "anthropic"

    def test_update_request_all_fields_optional(self):
        """All fields must be optional for partial updates."""
        from noa.api.v1.settings import UpdateSettingsRequest

        req = UpdateSettingsRequest()
        assert req.default_model is None
        assert req.google_client_id is None
        assert req.default_provider is None

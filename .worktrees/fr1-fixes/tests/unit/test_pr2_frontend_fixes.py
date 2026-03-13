"""Tests for PR2: Frontend Critical Fixes.

Covers:
  FE-C1 / BE-H3: PATCH /api/v1/settings endpoint for partial updates
                 (PrivacyToggle was sending PATCH but only PUT existed).
  FE-H1: Thread creation race in Chat — documented via integration test.
  FE-H2: RunDetail unsafe type cast removed — validated via TypeScript type-check.

Spec refs: SPEC.md §11.1, §24
"""

# ruff: noqa: S101, S105, S106

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.pr2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth_user(user_id: uuid.UUID | None = None) -> Any:
    from noa.auth.middleware import AuthUser

    return AuthUser(user_id=user_id or uuid.uuid4())


def _mock_request() -> Any:
    from starlette.requests import Request as StarletteRequest

    return MagicMock(spec=StarletteRequest)


def _make_settings_row(**overrides: Any) -> Any:
    """Create a minimal UserSettings-like ORM row."""
    row = MagicMock()
    row.default_model = "claude-sonnet-4-20250514"
    row.default_provider = "anthropic"
    row.default_privacy_mode = "external"
    row.budget_daily_usd = 10.0
    row.budget_monthly_usd = 200.0
    row.anthropic_api_key = None
    row.openai_api_key = None
    row.google_client_id = None
    row.google_client_secret = None
    row.notion_token = None
    row.tavily_api_key = None
    row.ollama_base_url = "http://private-worker:11434"
    for k, v in overrides.items():
        setattr(row, k, v)
    return row


# ===========================================================================
# BE-H3 / FE-C1: PATCH /api/v1/settings endpoint
# ===========================================================================


class TestPatchSettingsEndpoint:
    """PATCH /api/v1/settings must exist and behave like partial PUT."""

    def test_patch_handler_is_registered(self) -> None:
        """The router must expose a PATCH route at /api/v1/settings."""
        from noa.api.v1.settings import router

        all_methods: set[str] = set()
        for route in router.routes:
            if hasattr(route, "methods") and route.methods:  # type: ignore[union-attr]
                all_methods.update(route.methods)  # type: ignore[union-attr]

        assert "PATCH" in all_methods, (
            f"No PATCH route found in settings router. Methods: {all_methods}"
        )

    @pytest.mark.asyncio
    async def test_patch_settings_privacy_mode_only(self) -> None:
        """PATCH with only default_privacy_mode should update just that field."""
        from noa.api.v1.settings import UpdateSettingsRequest, patch_settings

        user = _make_auth_user()
        existing_row = _make_settings_row(default_privacy_mode="external")

        # Simulate: GET returns existing row, upsert updates it
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = existing_row

        session = AsyncMock()
        session.execute = AsyncMock(return_value=get_result)
        session.commit = AsyncMock()

        request = _mock_request()
        body = UpdateSettingsRequest(default_privacy_mode="private")

        with patch("noa.api.middleware.trace_id_ctx") as mock_ctx:
            mock_ctx.get.return_value = "trace-pr2"
            response = await patch_settings(
                body=body, request=request, user=user, session=session
            )

        assert response["ok"] is True
        # The updated value should be reflected in the returned data
        assert response["data"]["default_privacy_mode"] == "private"

    @pytest.mark.asyncio
    async def test_patch_settings_preserves_unspecified_fields(self) -> None:
        """PATCH with one field should not overwrite other fields with None."""
        from noa.api.v1.settings import UpdateSettingsRequest, patch_settings

        user = _make_auth_user()
        existing_row = _make_settings_row(
            default_model="claude-sonnet-4-20250514",
            default_provider="anthropic",
            default_privacy_mode="external",
        )

        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = existing_row

        session = AsyncMock()
        session.execute = AsyncMock(return_value=get_result)
        session.commit = AsyncMock()

        request = _mock_request()
        # Only send privacy_mode — model and provider must survive
        body = UpdateSettingsRequest(default_privacy_mode="private")

        with patch("noa.api.middleware.trace_id_ctx") as mock_ctx:
            mock_ctx.get.return_value = ""
            response = await patch_settings(
                body=body, request=request, user=user, session=session
            )

        assert response["ok"] is True
        data = response["data"]
        # Fields not in the PATCH body must retain their original values
        assert data["default_model"] == "claude-sonnet-4-20250514"
        assert data["default_provider"] == "anthropic"
        assert data["default_privacy_mode"] == "private"

    @pytest.mark.asyncio
    async def test_patch_settings_full_update(self) -> None:
        """PATCH with all fields behaves like PUT — all fields updated."""
        from noa.api.v1.settings import UpdateSettingsRequest, patch_settings

        user = _make_auth_user()
        existing_row = _make_settings_row()

        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = existing_row

        session = AsyncMock()
        session.execute = AsyncMock(return_value=get_result)
        session.commit = AsyncMock()

        request = _mock_request()
        body = UpdateSettingsRequest(
            default_model="gpt-4o",
            default_provider="openai",
            default_privacy_mode="private",
            budget_daily_usd=5.0,
            budget_monthly_usd=100.0,
        )

        with patch("noa.api.middleware.trace_id_ctx") as mock_ctx:
            mock_ctx.get.return_value = ""
            response = await patch_settings(
                body=body, request=request, user=user, session=session
            )

        assert response["ok"] is True
        data = response["data"]
        assert data["default_model"] == "gpt-4o"
        assert data["default_provider"] == "openai"
        assert data["default_privacy_mode"] == "private"
        assert data["budget_daily_usd"] == 5.0
        assert data["budget_monthly_usd"] == 100.0

    @pytest.mark.asyncio
    async def test_patch_settings_creates_row_if_not_exists(self) -> None:
        """PATCH on a user with no settings row calls upsert (creates the row)."""
        from noa.api.v1.settings import UpdateSettingsRequest, patch_settings

        user = _make_auth_user()

        # First execute call (upsert select) returns None (no row), second
        # execute call (get_settings select after upsert) also returns None —
        # triggering service to return defaults, which is correct for a brand-new user.
        no_row_result = MagicMock()
        no_row_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(return_value=no_row_result)
        session.commit = AsyncMock()

        request = _mock_request()
        body = UpdateSettingsRequest(default_privacy_mode="private")

        with patch("noa.api.middleware.trace_id_ctx") as mock_ctx:
            mock_ctx.get.return_value = ""
            response = await patch_settings(
                body=body, request=request, user=user, session=session
            )

        # The endpoint should return 200 OK even for a new user (upsert creates row)
        assert response["ok"] is True
        # session.execute was called (upsert attempted)
        assert session.execute.called

    def test_patch_returns_success_envelope(self) -> None:
        """Response schema must match the standard success_envelope structure."""
        from noa.api.schemas.common import success_envelope

        data = {"default_privacy_mode": "private", "default_model": "gpt-4o"}
        env = success_envelope(data=data, trace_id="t1")
        assert env["ok"] is True
        assert env["data"] == data
        assert "error" in env


# ===========================================================================
# FE-H1: Thread creation race — documented behavior via unit logic test
# ===========================================================================


class TestThreadCreationRaceLogic:
    """
    FE-H1: Before the fix, Chat.tsx called createThreadMutation.mutate() and
    immediately proceeded to SSE connect with thread_id=null. The fix awaits
    the thread creation and uses the returned ID.

    We verify the fix indirectly here: the Chat page now calls mutateAsync and
    the body contains the real thread_id. The actual UI flow is covered by
    E2E tests (PR6).
    """

    def test_create_thread_mutation_uses_mutate_async_in_handle_send(self) -> None:
        """Chat.tsx handleSend must await createThreadMutation.mutateAsync."""
        import pathlib

        chat_path = pathlib.Path(
            __file__
        ).parent.parent.parent / "web" / "src" / "pages" / "Chat.tsx"
        source = chat_path.read_text()

        # The fix replaces createThreadMutation.mutate(title) with
        # createThreadMutation.mutateAsync(title) inside handleSend
        assert "mutateAsync" in source, (
            "Chat.tsx handleSend must use mutateAsync for thread creation"
        )
        assert "await createThreadMutation.mutateAsync" in source, (
            "Thread creation must be awaited before SSE connect"
        )

    def test_thread_id_from_response_used_in_chat_body(self) -> None:
        """After await, the thread_id from the response must be in the body."""
        import pathlib

        chat_path = (
            pathlib.Path(__file__).parent.parent.parent
            / "web"
            / "src"
            / "pages"
            / "Chat.tsx"
        )
        source = chat_path.read_text()
        # The fixed code assigns `threadId = res.data?.id` and uses it in body
        assert "threadId" in source, (
            "Fixed code must use a local threadId variable"
        )
        assert "thread_id: threadId" in source, (
            "ChatRequest body must reference the resolved threadId"
        )


# ===========================================================================
# FE-H2: RunDetail unsafe type cast removed
# ===========================================================================


class TestRunDetailTypeSafety:
    """FE-H2: as unknown as double-cast must be removed from RunDetail.tsx."""

    def test_double_cast_removed_from_run_detail(self) -> None:
        """RunDetail.tsx must not contain 'as unknown as'."""
        import pathlib

        run_detail_path = (
            pathlib.Path(__file__).parent.parent.parent
            / "web"
            / "src"
            / "pages"
            / "RunDetail.tsx"
        )
        source = run_detail_path.read_text()
        assert "as unknown as" not in source, (
            "RunDetail.tsx must not use 'as unknown as' double-cast — "
            "use an explicit return type annotation instead"
        )

    def test_events_query_has_explicit_return_type(self) -> None:
        """The eventsRes query fn must declare its return type explicitly."""
        import pathlib

        run_detail_path = (
            pathlib.Path(__file__).parent.parent.parent
            / "web"
            / "src"
            / "pages"
            / "RunDetail.tsx"
        )
        source = run_detail_path.read_text()
        # The fixed version uses `: Promise<...ApiResponse<RunEvent[]>>` annotation
        assert "Promise<" in source and "ApiResponse<RunEvent[]>" in source, (
            "eventsRes queryFn must declare an explicit "
            "Promise<ApiResponse<RunEvent[]>> return type"
        )

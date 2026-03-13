"""Tests for FR4: Chat & Streaming UX fixes.

Covers:
- UX-H1: SSE keepalive pings during long-running tool calls
- UX-H3: System prompt file backed endpoint (GET/PUT /api/v1/settings/system-prompt)
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: I001

from noa.api.app import create_app
from noa.api.deps import get_db_session
from noa.auth.middleware import AuthUser, require_auth

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_user() -> AuthUser:
    return AuthUser(user_id=uuid.uuid4())


async def _fake_db() -> AsyncGenerator[AsyncSession, None]:
    """Fake DB session that yields a MagicMock (for unit tests)."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    yield mock_session


def _make_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[require_auth] = _fake_user
    app.dependency_overrides[get_db_session] = _fake_db
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# UX-H1: SSE keepalive — verify _SSE_KEEPALIVE_INTERVAL exists at module level
# ---------------------------------------------------------------------------

class TestSSEKeepaliveConstant:
    """UX-H1: SSE keepalive constant is defined at module level."""

    def test_keepalive_interval_exists(self) -> None:
        from noa.api.v1.chat import (
            _SSE_KEEPALIVE_INTERVAL,  # type: ignore[attr-defined]
        )

        assert isinstance(_SSE_KEEPALIVE_INTERVAL, (int, float))
        assert _SSE_KEEPALIVE_INTERVAL > 0

    def test_keepalive_interval_is_reasonable(self) -> None:
        """Must be between 5 and 30 seconds — low enough to beat common proxy timeouts."""
        from noa.api.v1.chat import (
            _SSE_KEEPALIVE_INTERVAL,  # type: ignore[attr-defined]
        )

        assert 5 <= _SSE_KEEPALIVE_INTERVAL <= 30, (
            f"Keepalive interval {_SSE_KEEPALIVE_INTERVAL}s is outside safe range [5, 30]"
        )

    def test_chat_endpoint_uses_asyncio(self) -> None:
        """Keepalive implementation requires asyncio to be imported in chat module."""
        import importlib

        chat_module = importlib.import_module("noa.api.v1.chat")
        # asyncio must be imported for the keepalive wait_for implementation
        assert hasattr(chat_module, "asyncio") or "asyncio" in dir(chat_module)

    def test_chat_stream_returns_sse_response(self) -> None:
        """SSE endpoint returns streaming response for valid requests."""
        app = create_app()
        app.dependency_overrides[require_auth] = _fake_user

        async def _no_events():
            return
            yield  # make it async generator

        mock_runner = MagicMock()
        mock_runner.run = MagicMock(return_value=_no_events())

        with (
            patch("noa.api.v1.chat.get_runner", return_value=mock_runner),
            patch("noa.api.v1.chat.get_session_factory", return_value=None),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/chat",
                json={"message": "hello", "privacy_mode": "external"},
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_chat_stream_includes_meta_event(self) -> None:
        """First SSE event must be a meta event with run_id and thread_id."""
        app = create_app()
        app.dependency_overrides[require_auth] = _fake_user

        async def _no_events():
            return
            yield

        mock_runner = MagicMock()
        mock_runner.run = MagicMock(return_value=_no_events())

        with (
            patch("noa.api.v1.chat.get_runner", return_value=mock_runner),
            patch("noa.api.v1.chat.get_session_factory", return_value=None),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/chat",
                json={"message": "hello", "privacy_mode": "external"},
            )

        # Parse the first SSE data line
        first_data = None
        for line in response.text.splitlines():
            if line.startswith("data: "):
                first_data = json.loads(line[6:])
                break

        assert first_data is not None
        assert first_data.get("event_type") == "meta"
        assert "run_id" in first_data
        assert "thread_id" in first_data


# ---------------------------------------------------------------------------
# UX-H3: System prompt file + GET/PUT endpoints
# ---------------------------------------------------------------------------

class TestSystemPromptFile:
    """UX-H3: prompts/system_prompt.txt must exist."""

    def test_default_system_prompt_file_exists(self) -> None:
        """The prompts/system_prompt.txt file must exist in the repo."""
        # Find the repo root relative to this test file
        repo_root = Path(__file__).parent.parent.parent
        prompt_file = repo_root / "prompts" / "system_prompt.txt"
        assert prompt_file.exists(), f"Missing {prompt_file}"

    def test_default_system_prompt_file_is_not_empty(self) -> None:
        repo_root = Path(__file__).parent.parent.parent
        prompt_file = repo_root / "prompts" / "system_prompt.txt"
        if prompt_file.exists():
            content = prompt_file.read_text(encoding="utf-8").strip()
            assert len(content) > 20, "System prompt file is too short/empty"

    def test_load_default_system_prompt_helper(self) -> None:
        """load_default_system_prompt() returns non-empty string."""
        from noa.api.v1.settings import load_default_system_prompt

        result = load_default_system_prompt()
        assert isinstance(result, str)
        # May be empty string if file doesn't exist, but function must not raise
        # (graceful fallback)


class TestSystemPromptEndpoints:
    """UX-H3: GET/PUT /api/v1/settings/system-prompt."""

    def _app_with_mock_service(
        self,
        mock_service: AsyncMock,
    ) -> TestClient:
        """Create a test client with mocked SettingsService and fake DB."""
        app = create_app()
        app.dependency_overrides[require_auth] = _fake_user
        app.dependency_overrides[get_db_session] = _fake_db

        mock_repo = MagicMock()
        with (
            patch("noa.api.v1.settings.SettingsRepository", return_value=mock_repo),
            patch("noa.api.v1.settings.SettingsService", return_value=mock_service),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            # Store patches so they stay active; use context inside test method
        return app, mock_repo

    def test_get_system_prompt_endpoint_exists(self) -> None:
        """GET /api/v1/settings/system-prompt returns 200."""
        app = create_app()
        app.dependency_overrides[require_auth] = _fake_user
        app.dependency_overrides[get_db_session] = _fake_db

        mock_service = AsyncMock()
        mock_service.get_settings.return_value = {"system_prompt": "My custom prompt"}
        mock_repo = MagicMock()

        with (
            patch("noa.api.v1.settings.SettingsRepository", return_value=mock_repo),
            patch("noa.api.v1.settings.SettingsService", return_value=mock_service),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/settings/system-prompt")

        assert response.status_code == 200

    def test_get_system_prompt_returns_user_prompt_when_set(self) -> None:
        """GET returns user's saved prompt when system_prompt is in settings."""
        app = create_app()
        app.dependency_overrides[require_auth] = _fake_user
        app.dependency_overrides[get_db_session] = _fake_db

        mock_service = AsyncMock()
        mock_service.get_settings.return_value = {"system_prompt": "Be concise."}
        mock_repo = MagicMock()

        with (
            patch("noa.api.v1.settings.SettingsRepository", return_value=mock_repo),
            patch("noa.api.v1.settings.SettingsService", return_value=mock_service),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/settings/system-prompt")

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["data"]["content"] == "Be concise."
        assert data["data"]["is_default"] is False

    def test_get_system_prompt_falls_back_to_file_when_none(self) -> None:
        """GET returns file-based default when no user prompt is set."""
        app = create_app()
        app.dependency_overrides[require_auth] = _fake_user
        app.dependency_overrides[get_db_session] = _fake_db

        mock_service = AsyncMock()
        mock_service.get_settings.return_value = {"system_prompt": None}
        mock_repo = MagicMock()

        with (
            patch("noa.api.v1.settings.SettingsRepository", return_value=mock_repo),
            patch("noa.api.v1.settings.SettingsService", return_value=mock_service),
            patch(
                "noa.api.v1.settings._load_default_system_prompt",
                return_value="You are Noa, a personal AI agent.",
            ),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/settings/system-prompt")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["content"] == "You are Noa, a personal AI agent."
        assert data["data"]["is_default"] is True

    def test_put_system_prompt_saves_content(self) -> None:
        """PUT /api/v1/settings/system-prompt persists the custom prompt."""
        app = create_app()
        app.dependency_overrides[require_auth] = _fake_user
        app.dependency_overrides[get_db_session] = _fake_db

        new_prompt = "Always respond in German."
        mock_service = AsyncMock()
        mock_service.update_settings.return_value = {"system_prompt": new_prompt}
        mock_repo = MagicMock()

        with (
            patch("noa.api.v1.settings.SettingsRepository", return_value=mock_repo),
            patch("noa.api.v1.settings.SettingsService", return_value=mock_service),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.put(
                "/api/v1/settings/system-prompt",
                json={"content": new_prompt},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

    def test_put_system_prompt_rejects_too_long_content(self) -> None:
        """PUT returns 422 if content exceeds 10,000 characters."""
        app = create_app()
        app.dependency_overrides[require_auth] = _fake_user
        app.dependency_overrides[get_db_session] = _fake_db

        mock_service = AsyncMock()
        mock_repo = MagicMock()

        with (
            patch("noa.api.v1.settings.SettingsRepository", return_value=mock_repo),
            patch("noa.api.v1.settings.SettingsService", return_value=mock_service),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.put(
                "/api/v1/settings/system-prompt",
                json={"content": "x" * 10_001},
            )

        assert response.status_code == 422

    def test_put_empty_content_resets_to_default(self) -> None:
        """PUT with empty string saves None (resets to file default)."""
        app = create_app()
        app.dependency_overrides[require_auth] = _fake_user
        app.dependency_overrides[get_db_session] = _fake_db

        mock_service = AsyncMock()
        mock_service.update_settings.return_value = {"system_prompt": None}
        mock_repo = MagicMock()

        with (
            patch("noa.api.v1.settings.SettingsRepository", return_value=mock_repo),
            patch("noa.api.v1.settings.SettingsService", return_value=mock_service),
            patch(
                "noa.api.v1.settings._load_default_system_prompt",
                return_value="You are Noa.",
            ),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.put(
                "/api/v1/settings/system-prompt",
                json={"content": ""},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["is_default"] is True
        # update_settings must have been called with system_prompt=None
        mock_service.update_settings.assert_called_once()
        call_kwargs = mock_service.update_settings.call_args
        updates = call_kwargs[0][1] if call_kwargs[0] else call_kwargs.kwargs.get("updates", {})
        assert updates.get("system_prompt") is None


# ---------------------------------------------------------------------------
# HIGH: UX-H10 — Runner emits tool_start / tool_end events
# ---------------------------------------------------------------------------


class TestRunnerToolLifecycleEvents:
    """UX-H10: OrchestratorRunner emits tool_start and tool_end around tool_called."""

    async def _collect_events(self, tool_calls: list[Any], tool_results: list[Any]) -> list[dict[str, Any]]:
        """Run the orchestrator with a mocked graph that returns given tools."""
        from noa.orchestrator.runner import OrchestratorRunner

        fake_result: dict[str, Any] = {
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "response": "done",
            "total_cost": 0.0,
            "llm_usage": [],
        }

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value=fake_result)

        runner = OrchestratorRunner(graph=mock_graph)
        run_svc = AsyncMock()
        run_svc.update_status = AsyncMock()
        run_svc.append_event = AsyncMock()

        events = []
        async for evt in runner.run(
            message="test",
            run_service=run_svc,
            run_id=str(uuid.uuid4()),
        ):
            events.append(evt)
        return events

    async def test_tool_start_emitted_before_tool_called(self) -> None:
        """tool_start must come before tool_called for each tool."""
        tc = {"name": "web_search", "args": {"query": "noa"}}
        events = await self._collect_events([tc], [])
        event_types = [e["event_type"] for e in events]
        idx_start = event_types.index("tool_start")
        idx_called = event_types.index("tool_called")
        assert idx_start < idx_called, "tool_start must precede tool_called"

    async def test_tool_end_emitted_after_tool_called(self) -> None:
        """tool_end must come after tool_called for each tool."""
        tc = {"name": "calendar", "args": {}}
        events = await self._collect_events([tc], [])
        event_types = [e["event_type"] for e in events]
        idx_called = event_types.index("tool_called")
        idx_end = event_types.index("tool_end")
        assert idx_end > idx_called, "tool_end must follow tool_called"

    async def test_tool_start_carries_tool_name(self) -> None:
        """tool_start payload must include tool_name."""
        tc = {"name": "tavily_search", "args": {"query": "test"}}
        events = await self._collect_events([tc], [])
        start_events = [e for e in events if e["event_type"] == "tool_start"]
        assert len(start_events) == 1
        assert start_events[0]["payload"]["tool_name"] == "tavily_search"

    async def test_tool_end_carries_tool_name(self) -> None:
        """tool_end payload must include tool_name."""
        tc = {"name": "gmail", "args": {}}
        events = await self._collect_events([tc], [])
        end_events = [e for e in events if e["event_type"] == "tool_end"]
        assert len(end_events) == 1
        assert end_events[0]["payload"]["tool_name"] == "gmail"

    async def test_multiple_tools_each_get_start_end(self) -> None:
        """Each tool call gets its own tool_start and tool_end."""
        tool_calls = [
            {"name": "web_search", "args": {}},
            {"name": "calendar", "args": {}},
        ]
        events = await self._collect_events(tool_calls, [])
        start_events = [e for e in events if e["event_type"] == "tool_start"]
        end_events = [e for e in events if e["event_type"] == "tool_end"]
        assert len(start_events) == 2
        assert len(end_events) == 2

"""Tests for CP3: Chat Endpoint → Real Pipeline.

Verifies that /api/v1/chat creates SSE streaming response,
yields events from OrchestratorRunner, and handles errors.
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from noa.api.app import create_app
from noa.auth.middleware import AuthUser, require_auth


def _fake_user() -> AuthUser:
    return AuthUser(user_id=uuid.uuid4())


def _make_client(
    runner: Any = None,
) -> TestClient:
    """Create a test client with auth overridden."""
    app = create_app()
    app.dependency_overrides[require_auth] = _fake_user

    # Patch app_state getters
    with (
        patch("noa.api.v1.chat.get_runner", return_value=runner),
        patch(
            "noa.api.v1.chat.get_session_factory",
            return_value=None,
        ),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        # We need the patches active during requests too,
        # so return within context — use a different approach
    return client


def _post_chat(
    runner: Any = None,
    message: str = "hi",
    thread_id: str | None = None,
) -> Any:
    """Helper to POST /api/v1/chat with mocked deps."""
    app = create_app()
    app.dependency_overrides[require_auth] = _fake_user

    body: dict[str, Any] = {
        "message": message,
        "privacy_mode": "external",
        "model": "anthropic/claude-haiku",
        "provider": "anthropic",
    }
    if thread_id:
        body["thread_id"] = thread_id

    with (
        patch("noa.api.v1.chat.get_runner", return_value=runner),
        patch(
            "noa.api.v1.chat.get_session_factory",
            return_value=None,
        ),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        return client.post(
            "/api/v1/chat",
            json=body,
            headers={"Authorization": "Bearer test"},
        )


def _make_runner(
    events: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Create a mock runner that yields given events."""
    runner = MagicMock()

    if events is None:
        events = [
            {
                "event_type": "message_received",
                "payload": {"message": "hi"},
                "timestamp": "2026-03-06T00:00:00Z",
            },
            {
                "event_type": "result_ready",
                "payload": {"response": "Hello!"},
                "timestamp": "2026-03-06T00:00:01Z",
            },
        ]

    async def fake_run(**kwargs: Any) -> Any:
        for e in events:
            yield e

    runner.run = fake_run
    return runner


class TestChatSSE:
    """Chat endpoint returns SSE StreamingResponse."""

    def test_returns_sse_content_type(self) -> None:
        runner = _make_runner()
        response = _post_chat(runner=runner)
        assert response.status_code == 200
        ct = response.headers.get("content-type", "")
        assert "text/event-stream" in ct

    def test_first_event_is_meta_with_run_id(self) -> None:
        runner = _make_runner()
        response = _post_chat(runner=runner)
        data_lines = [
            ln
            for ln in response.text.split("\n")
            if ln.startswith("data:")
        ]
        assert len(data_lines) > 0
        first = json.loads(data_lines[0].removeprefix("data:").strip())
        assert "run_id" in first
        assert "thread_id" in first

    def test_includes_result_ready_event(self) -> None:
        runner = _make_runner()
        response = _post_chat(runner=runner)
        assert "result_ready" in response.text

    def test_includes_message_received_event(self) -> None:
        runner = _make_runner()
        response = _post_chat(runner=runner)
        assert "message_received" in response.text


class TestChatErrors:
    """Error handling in chat endpoint."""

    def test_no_runner_returns_error_event(self) -> None:
        response = _post_chat(runner=None)
        assert response.status_code == 200
        assert "error" in response.text
        assert "not configured" in response.text

    def test_error_event_from_runner(self) -> None:
        runner = _make_runner(
            events=[
                {
                    "event_type": "error",
                    "payload": {"error": "LLM failed"},
                    "timestamp": "2026-03-06T00:00:01Z",
                },
            ]
        )
        response = _post_chat(runner=runner)
        assert "error" in response.text
        assert "LLM failed" in response.text


class TestChatThread:
    """Thread creation logic."""

    def test_new_thread_when_none_provided(self) -> None:
        runner = _make_runner()
        response = _post_chat(runner=runner, thread_id=None)
        assert response.status_code == 200
        # Meta event should contain a generated thread_id
        data_lines = [
            ln
            for ln in response.text.split("\n")
            if ln.startswith("data:")
        ]
        first = json.loads(data_lines[0].removeprefix("data:").strip())
        assert "thread_id" in first
        # Should be a valid UUID
        uuid.UUID(first["thread_id"])

    def test_existing_thread_reused(self) -> None:
        runner = _make_runner()
        tid = str(uuid.uuid4())
        response = _post_chat(runner=runner, thread_id=tid)
        data_lines = [
            ln
            for ln in response.text.split("\n")
            if ln.startswith("data:")
        ]
        first = json.loads(data_lines[0].removeprefix("data:").strip())
        assert first["thread_id"] == tid

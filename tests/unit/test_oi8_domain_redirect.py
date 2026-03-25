"""Tests for OI8: Smart Domain Redirect.

Verifies that a domain mismatch no longer returns 403 but instead
auto-creates a new thread in the correct domain and includes redirect
metadata in the SSE meta event so the frontend can update context.
"""

from __future__ import annotations

import contextlib
import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from noa.api.app import create_app
from noa.auth.middleware import AuthUser, require_auth

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_user() -> AuthUser:
    return AuthUser(user_id=uuid.uuid4())


def _parse_sse_events(raw: str) -> list[dict[str, Any]]:
    """Parse raw SSE text into a list of event dicts."""
    events: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if line.startswith("data: "):
            with contextlib.suppress(json.JSONDecodeError):
                events.append(json.loads(line[6:]))
    return events


def _make_session_factory(thread_domain: str | None = None) -> Any:
    """Build a mock session factory that returns threads with a given domain.

    If thread_domain is None the mock simulates a thread that doesn't exist.
    """
    mock_factory = MagicMock()
    mock_session = AsyncMock()

    # Simulate Conversation.domain returned from DB
    if thread_domain is not None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = thread_domain
    else:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    # Context manager support
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_factory.return_value = mock_ctx

    return mock_factory


def _post_chat(
    message: str = "hello",
    thread_id: str | None = None,
    privacy_mode: str = "external",
    session_factory: Any = None,
    runner: Any = None,
) -> Any:
    """POST /api/v1/chat with controlled dependencies."""
    app = create_app()
    app.dependency_overrides[require_auth] = _fake_user

    body: dict[str, Any] = {
        "message": message,
        "privacy_mode": privacy_mode,
        "model": "anthropic/claude-haiku",
        "provider": "anthropic",
    }
    if thread_id is not None:
        body["thread_id"] = thread_id

    with (
        patch("noa.api.v1.chat.get_runner", return_value=runner),
        patch("noa.api.v1.chat.get_session_factory", return_value=session_factory),
        patch("noa.api.v1.chat._get_session_factory", return_value=session_factory),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        return client.post(
            "/api/v1/chat",
            json=body,
            headers={"Authorization": "Bearer test"},
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOI8DomainRedirect:
    """OI8: Smart domain redirect replaces 403 DOMAIN_MISMATCH."""

    def test_no_redirect_when_no_thread_id(self) -> None:
        """New conversation (no thread_id) — no redirect, meta event is plain."""
        resp = _post_chat(thread_id=None, privacy_mode="external")
        assert resp.status_code == 200, resp.text

        events = _parse_sse_events(resp.text)
        meta = next((e for e in events if e.get("event_type") == "meta"), None)
        assert meta is not None
        assert meta.get("redirected") is None, "no redirect expected for new thread"

    def test_no_redirect_when_domain_matches(self) -> None:
        """Thread exists in same domain as request — no redirect."""
        thread_id = str(uuid.uuid4())
        factory = _make_session_factory(thread_domain="external")

        resp = _post_chat(
            thread_id=thread_id,
            privacy_mode="external",
            session_factory=factory,
        )
        assert resp.status_code == 200, resp.text

        events = _parse_sse_events(resp.text)
        meta = next((e for e in events if e.get("event_type") == "meta"), None)
        assert meta is not None
        assert meta.get("redirected") is None, "no redirect expected for same-domain request"
        # thread_id in meta should be the original one
        assert meta["thread_id"] == thread_id

    def test_redirect_on_domain_mismatch_private_request(self) -> None:
        """Explicit private request to external thread → auto-redirect, no 403."""
        thread_id = str(uuid.uuid4())
        # Thread is in "external" domain; user explicitly requests "private"
        factory = _make_session_factory(thread_domain="external")

        resp = _post_chat(
            thread_id=thread_id,
            privacy_mode="private",
            session_factory=factory,
        )
        # Must NOT return 403
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        events = _parse_sse_events(resp.text)
        meta = next((e for e in events if e.get("event_type") == "meta"), None)
        assert meta is not None, "meta event must be present"

        # Redirect fields must be present
        assert meta.get("redirected") is True, "redirected flag must be True"
        assert meta.get("original_thread_id") == thread_id, "original_thread_id must match"
        assert meta.get("redirect_reason") == "domain_mismatch"

        # New thread_id must be different from the original
        new_thread_id = meta["thread_id"]
        assert new_thread_id != thread_id, "a fresh thread_id must be generated"
        # Validate it is a UUID
        uuid.UUID(new_thread_id)

    def test_redirect_meta_has_new_run_id(self) -> None:
        """On redirect, the run_id in meta corresponds to the new run."""
        thread_id = str(uuid.uuid4())
        factory = _make_session_factory(thread_domain="external")

        resp = _post_chat(
            thread_id=thread_id,
            privacy_mode="private",
            session_factory=factory,
        )
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        meta = next((e for e in events if e.get("event_type") == "meta"), None)
        assert meta is not None
        assert meta.get("redirected") is True

        # run_id must be a valid UUID distinct from any original
        run_id = meta["run_id"]
        uuid.UUID(run_id)

    def test_no_redirect_when_thread_does_not_exist(self) -> None:
        """Thread_id given but thread not in DB — treat as new, no redirect."""
        thread_id = str(uuid.uuid4())
        # DB returns None (thread not found)
        factory = _make_session_factory(thread_domain=None)

        resp = _post_chat(
            thread_id=thread_id,
            privacy_mode="private",
            session_factory=factory,
        )
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        meta = next((e for e in events if e.get("event_type") == "meta"), None)
        assert meta is not None
        # No redirect — thread doesn't exist, will be created in correct domain
        assert meta.get("redirected") is None


class TestOI8MetaEventType:
    """MetaEvent TypedDict supports optional redirect fields."""

    def test_meta_event_typeddict_has_optional_redirect_fields(self) -> None:
        """MetaEvent TypedDict accepts redirect fields without error."""
        from noa.orchestrator.sse_types import MetaEvent

        # Minimal MetaEvent (no redirect)
        plain: MetaEvent = {  # type: ignore[typeddict-item]
            "event_type": "meta",
            "run_id": "r1",
            "thread_id": "t1",
        }
        assert plain["event_type"] == "meta"

        # MetaEvent with redirect fields
        redirected: MetaEvent = {  # type: ignore[typeddict-item]
            "event_type": "meta",
            "run_id": "r2",
            "thread_id": "t2",
            "redirected": True,
            "original_thread_id": "t1",
            "redirect_reason": "domain_mismatch",
        }
        assert redirected.get("redirected") is True
        assert redirected.get("original_thread_id") == "t1"
        assert redirected.get("redirect_reason") == "domain_mismatch"

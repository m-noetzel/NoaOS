"""Tests for DI2 — DB-backed chat idempotency (RV-M1).

Verifies that _check_chat_idempotency() and _register_chat_idempotency()
use the idempotency_keys DB table instead of the removed in-memory dict.
Also tests the chat endpoint returns 409 on duplicate Idempotency-Key.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noa.api.v1.chat import (
    _CHAT_IDEM_PREFIX,
    _check_chat_idempotency,
    _register_chat_idempotency,
)

# ---------------------------------------------------------------------------
# Unit tests for _check_chat_idempotency
# ---------------------------------------------------------------------------


class TestCheckChatIdempotency:
    @pytest.mark.asyncio
    async def test_returns_false_when_no_factory(self) -> None:
        """Without session factory, idempotency check always passes (False = not a dup)."""
        with patch("noa.api.v1.chat._get_session_factory", return_value=None):
            result = await _check_chat_idempotency("some-key")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_key_exists_in_db(self) -> None:
        """When DB has the key, returns True (duplicate)."""
        factory = _make_factory_with_key_found(True)
        with patch("noa.api.v1.chat._get_session_factory", return_value=factory):
            result = await _check_chat_idempotency("dup-key")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_key_not_in_db(self) -> None:
        """When DB does not have the key, returns False (not a dup)."""
        factory = _make_factory_with_key_found(False)
        with patch("noa.api.v1.chat._get_session_factory", return_value=factory):
            result = await _check_chat_idempotency("new-key")
        assert result is False

    @pytest.mark.asyncio
    async def test_uses_chat_prefix(self) -> None:
        """Key stored in DB must be prefixed with _CHAT_IDEM_PREFIX."""
        captured_key: list[str] = []

        mock_factory = MagicMock()
        mock_session = AsyncMock()

        async def capture_execute(stmt: Any) -> Any:
            # Capture the WHERE clause key value
            compiled = stmt.compile(compile_kwargs={"literal_binds": True})
            captured_key.append(str(compiled))
            mock_res = MagicMock()
            mock_res.scalar_one_or_none.return_value = None
            return mock_res

        mock_session.execute = capture_execute
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_ctx

        with patch("noa.api.v1.chat._get_session_factory", return_value=mock_factory):
            await _check_chat_idempotency("mykey")

        # The full key must start with the prefix
        assert len(captured_key) == 1
        assert _CHAT_IDEM_PREFIX in captured_key[0]
        assert "mykey" in captured_key[0]

    @pytest.mark.asyncio
    async def test_returns_false_on_db_error(self) -> None:
        """DB errors degrade gracefully — allow the request through."""
        factory = _make_factory_that_raises()
        with patch("noa.api.v1.chat._get_session_factory", return_value=factory):
            result = await _check_chat_idempotency("error-key")
        assert result is False


class TestRegisterChatIdempotency:
    @pytest.mark.asyncio
    async def test_noop_when_no_factory(self) -> None:
        """Without session factory, register is a no-op (no exception)."""
        with patch("noa.api.v1.chat._get_session_factory", return_value=None):
            await _register_chat_idempotency("some-key")  # must not raise

    @pytest.mark.asyncio
    async def test_calls_session_execute_and_commit(self) -> None:
        """With a factory, register calls execute() and commit()."""
        mock_factory = MagicMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock())
        mock_session.commit = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_ctx

        with patch("noa.api.v1.chat._get_session_factory", return_value=mock_factory):
            await _register_chat_idempotency("new-key")

        assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_noop_on_db_error(self) -> None:
        """DB errors during register are swallowed — never raise to caller."""
        factory = _make_factory_that_raises()
        with patch("noa.api.v1.chat._get_session_factory", return_value=factory):
            await _register_chat_idempotency("fail-key")  # must not raise


class TestChatEndpointIdempotency:
    """Integration-style: chat endpoint returns 409 for duplicate key."""

    def _make_app(self) -> Any:
        from noa.api.app import create_app
        from noa.auth.middleware import AuthUser, require_auth

        app = create_app()
        app.dependency_overrides[require_auth] = lambda: AuthUser(user_id=uuid.uuid4())
        return app

    def test_409_on_duplicate_idempotency_key(self) -> None:
        """When the DB has the key, endpoint returns 409."""
        from fastapi.testclient import TestClient

        app = self._make_app()
        idem_key = str(uuid.uuid4())

        # Simulate: first check returns True (already processed)
        with (
            patch("noa.api.v1.chat._check_chat_idempotency", return_value=True),
            patch("noa.api.v1.chat.get_runner", return_value=None),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/api/v1/chat",
                json={"message": "hello", "privacy_mode": "external"},
                headers={
                    "Authorization": "Bearer test",
                    "Idempotency-Key": idem_key,
                },
            )

        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "DUPLICATE_REQUEST"

    def test_200_on_first_request_with_idem_key(self) -> None:
        """When the DB does NOT have the key, request proceeds normally."""
        from fastapi.testclient import TestClient

        app = self._make_app()
        idem_key = str(uuid.uuid4())

        with (
            patch("noa.api.v1.chat._check_chat_idempotency", return_value=False),
            patch("noa.api.v1.chat._register_chat_idempotency", return_value=None),
            patch("noa.api.v1.chat.get_runner", return_value=None),
            patch("noa.api.v1.chat._get_session_factory", return_value=None),
            patch("noa.api.v1.chat.get_health_checker", return_value=None),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/api/v1/chat",
                json={"message": "hello", "privacy_mode": "external"},
                headers={
                    "Authorization": "Bearer test",
                    "Idempotency-Key": idem_key,
                },
            )

        # Should stream (200), not be rejected
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_factory_with_key_found(found: bool) -> Any:
    mock_factory = MagicMock()
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = uuid.uuid4() if found else None
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_factory.return_value = mock_ctx
    return mock_factory


def _make_factory_that_raises() -> Any:
    mock_factory = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=RuntimeError("DB unavailable"))

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_factory.return_value = mock_ctx
    return mock_factory

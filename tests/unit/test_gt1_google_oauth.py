"""Tests for GT1: Google OAuth Token Exchange + Storage.

Covers: exchange_code(), refresh_access_token(), GoogleAuthError,
google_refresh_token column on UserSettings, auth URL with combined scopes,
and SPEC §11.2 (secrets never logged) / §11.3 (refresh token rotation).

Spec refs: SPEC.md §11.2, §11.3, §12.1, §12.2
"""
# ruff: noqa: S105, S106, S107

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.gt1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(**overrides):
    """Create a GoogleAuthClient with test defaults."""
    from noa.tools.google_auth import GoogleAuthClient

    defaults = {
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "redirect_uri": "http://localhost:8000/auth/google/callback",
    }
    defaults.update(overrides)
    return GoogleAuthClient(**defaults)


def _mock_httpx_success(
    *, access_token: str = "access-tok-123", refresh_token: str = "refresh-tok-456"
):
    """Build a mock httpx module returning a successful token response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": 3600,
        "token_type": "Bearer",
    }
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.post.return_value = mock_resp
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    return mock_http, mock_resp


def _mock_httpx_error(status_code: int = 400, body: str = "Bad Request"):
    """Build a mock httpx module returning an error response."""
    import httpx as real_httpx

    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = body
    mock_resp.json.return_value = {"error": "invalid_grant"}
    mock_resp.raise_for_status.side_effect = real_httpx.HTTPStatusError(
        str(status_code), request=MagicMock(), response=mock_resp
    )

    mock_http = AsyncMock()
    mock_http.post.return_value = mock_resp
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    return mock_http, mock_resp


# ---------------------------------------------------------------------------
# 1. exchange_code sends correct POST params
# ---------------------------------------------------------------------------


class TestExchangeCode:
    """Tests for GoogleAuthClient.exchange_code()."""

    @pytest.mark.asyncio
    async def test_exchange_code_sends_correct_params(self):
        """exchange_code must POST to token endpoint with correct params.

        SPEC.md §12.1 — OAuth2 code exchange sends client_id, client_secret,
        code, redirect_uri, grant_type=authorization_code.
        """
        client = _make_client()
        mock_http, _ = _mock_httpx_success()

        with patch("noa.tools.google_auth.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.exchange_code("auth-code-xyz")

            mock_http.post.assert_called_once()
            call_args = mock_http.post.call_args

            # Check the URL contains the token endpoint
            url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
            assert "oauth2.googleapis.com/token" in url

            # Check POST body params
            body = call_args[1].get("data", call_args[1].get("json", {}))
            assert body["client_id"] == "test-client-id"
            assert body["client_secret"] == "test-client-secret"
            assert body["code"] == "auth-code-xyz"
            assert body["redirect_uri"] == "http://localhost:8000/auth/google/callback"
            assert body["grant_type"] == "authorization_code"

    # -----------------------------------------------------------------------
    # 2. exchange_code returns tokens
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_exchange_code_returns_tokens(self):
        """exchange_code must return access_token and refresh_token.

        SPEC.md §12.1 — OAuth2 code exchange returns tokens.
        """
        client = _make_client()
        mock_http, _ = _mock_httpx_success(
            access_token="at-new", refresh_token="rt-new"
        )

        with patch("noa.tools.google_auth.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            result = await client.exchange_code("code-abc")

        assert result["access_token"] == "at-new"
        assert result["refresh_token"] == "rt-new"

    # -----------------------------------------------------------------------
    # 3. exchange_code raises GoogleAuthError on error response
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_exchange_code_raises_on_400(self):
        """exchange_code must raise GoogleAuthError on 400 response.

        SPEC.md §12.1 — Error handling for OAuth2 exchange.
        """
        from noa.tools.google_auth import GoogleAuthError

        client = _make_client()
        mock_http, _ = _mock_httpx_error(status_code=400)

        with patch("noa.tools.google_auth.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            with pytest.raises(GoogleAuthError):
                await client.exchange_code("bad-code")

    @pytest.mark.asyncio
    async def test_exchange_code_raises_on_401(self):
        """exchange_code must raise GoogleAuthError on 401 response.

        SPEC.md §12.1 — Error handling for OAuth2 exchange.
        """
        from noa.tools.google_auth import GoogleAuthError

        client = _make_client()
        mock_http, _ = _mock_httpx_error(status_code=401)

        with patch("noa.tools.google_auth.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            with pytest.raises(GoogleAuthError):
                await client.exchange_code("bad-code")


# ---------------------------------------------------------------------------
# 4-6. refresh_access_token
# ---------------------------------------------------------------------------


class TestRefreshAccessToken:
    """Tests for GoogleAuthClient.refresh_access_token()."""

    @pytest.mark.asyncio
    async def test_refresh_sends_correct_params(self):
        """refresh_access_token must POST with grant_type=refresh_token.

        SPEC.md §11.3 — Refresh tokens rotate on use.
        """
        client = _make_client()
        # Pre-set tokens so refresh has something to work with
        client.set_tokens(access_token="old-at", refresh_token="old-rt")

        mock_http, _ = _mock_httpx_success(
            access_token="new-at", refresh_token="new-rt"
        )

        with patch("noa.tools.google_auth.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.refresh_access_token()

            mock_http.post.assert_called_once()
            call_args = mock_http.post.call_args
            body = call_args[1].get("data", call_args[1].get("json", {}))
            assert body["grant_type"] == "refresh_token"
            assert body["refresh_token"] == "old-rt"
            assert body["client_id"] == "test-client-id"
            assert body["client_secret"] == "test-client-secret"

    @pytest.mark.asyncio
    async def test_refresh_updates_access_token_in_place(self):
        """refresh_access_token must update access_token on the client.

        SPEC.md §11.3 — Token refresh updates stored credentials.
        """
        client = _make_client()
        client.set_tokens(access_token="old-at", refresh_token="old-rt")

        mock_http, _ = _mock_httpx_success(
            access_token="refreshed-at", refresh_token="rotated-rt"
        )

        with patch("noa.tools.google_auth.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.refresh_access_token()

        assert client.access_token == "refreshed-at"

    @pytest.mark.asyncio
    async def test_refresh_raises_on_invalid_token(self):
        """refresh_access_token must raise on expired/invalid refresh token.

        SPEC.md §11.3 — Refresh failures are surfaced as errors.
        """
        from noa.tools.google_auth import GoogleAuthError

        client = _make_client()
        client.set_tokens(access_token="old-at", refresh_token="expired-rt")

        mock_http, _ = _mock_httpx_error(
            status_code=400, body="Token has been revoked"
        )

        with patch("noa.tools.google_auth.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            with pytest.raises(GoogleAuthError):
                await client.refresh_access_token()


# ---------------------------------------------------------------------------
# 7. Auth URL with combined calendar + gmail scopes
# ---------------------------------------------------------------------------


class TestAuthUrlCombinedScopes:
    """Tests for auth URL generation with combined scopes."""

    def test_auth_url_includes_calendar_and_gmail_scopes(self):
        """get_auth_url with combined scopes must include both sets.

        SPEC.md §12.1, §12.2 — Calendar + Gmail scopes in one flow.
        """
        from noa.tools.google_auth import CALENDAR_SCOPES, GMAIL_SCOPES

        client = _make_client()
        combined = CALENDAR_SCOPES + GMAIL_SCOPES
        url = client.get_auth_url(scopes=combined)

        from urllib.parse import unquote

        decoded = unquote(url)
        for scope in CALENDAR_SCOPES:
            assert scope in decoded

        for scope in GMAIL_SCOPES:
            assert scope in decoded

    def test_auth_url_requests_offline_access(self):
        """Auth URL must include access_type=offline for refresh tokens.

        SPEC.md §11.3 — Refresh token support.
        """
        client = _make_client()
        url = client.get_auth_url(scopes=["openid"])

        assert "access_type=offline" in url

    def test_auth_url_forces_consent_prompt(self):
        """Auth URL must include prompt=consent to get refresh token.

        SPEC.md §11.3 — Must force consent to receive refresh token.
        """
        client = _make_client()
        url = client.get_auth_url(scopes=["openid"])

        assert "prompt=consent" in url


# ---------------------------------------------------------------------------
# 8-9. Callback endpoint behavior (tested via GoogleAuthClient directly)
# ---------------------------------------------------------------------------


class TestCallbackFlow:
    """Tests for the OAuth callback code exchange flow."""

    @pytest.mark.asyncio
    async def test_callback_exchanges_code_and_stores_tokens(self):
        """Callback flow: exchange code, then client is_authenticated.

        SPEC.md §12.1 — OAuth2 callback exchanges code and stores tokens.
        """
        client = _make_client()
        mock_http, _ = _mock_httpx_success()

        with patch("noa.tools.google_auth.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            result = await client.exchange_code("callback-code-xxx")

        # After exchange, tokens should be stored on the client
        assert client.is_authenticated is True
        assert client.access_token == "access-tok-123"
        assert result["access_token"] == "access-tok-123"

    @pytest.mark.asyncio
    async def test_exchange_code_requires_code_parameter(self):
        """exchange_code must require a non-empty code string.

        Validates that empty/None code is rejected.
        """
        from noa.tools.google_auth import GoogleAuthError

        client = _make_client()

        with pytest.raises((GoogleAuthError, ValueError)):
            await client.exchange_code("")

        with pytest.raises((GoogleAuthError, ValueError, TypeError)):
            await client.exchange_code(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 10. google_refresh_token column on UserSettings
# ---------------------------------------------------------------------------


class TestUserSettingsRefreshToken:
    """Tests for google_refresh_token column on UserSettings model."""

    def test_google_refresh_token_column_exists(self):
        """UserSettings must have google_refresh_token column.

        SPEC.md §11.3 — Refresh tokens persisted in user settings.
        """
        from noa.settings.models import UserSettings

        # Check that the column is defined on the model
        columns = {c.name for c in UserSettings.__table__.columns}
        assert "google_refresh_token" in columns, (
            "UserSettings is missing google_refresh_token column; "
            f"found columns: {sorted(columns)}"
        )

    def test_google_refresh_token_column_is_string(self):
        """google_refresh_token column must be a string type.

        SPEC.md §11.3 — Refresh token stored as encrypted/plain string.
        """
        from sqlalchemy import String

        from noa.settings.models import UserSettings

        col = UserSettings.__table__.columns["google_refresh_token"]
        assert isinstance(col.type, String)


# ---------------------------------------------------------------------------
# 11. is_authenticated after exchange
# ---------------------------------------------------------------------------


class TestIsAuthenticatedAfterExchange:
    """Tests for is_authenticated property after token exchange."""

    def test_not_authenticated_initially(self):
        """Client must not be authenticated before exchange.

        SPEC.md §12.1 — No tokens until OAuth2 flow completes.
        """
        client = _make_client()
        assert client.is_authenticated is False

    @pytest.mark.asyncio
    async def test_authenticated_after_exchange(self):
        """Client must be authenticated after successful exchange.

        SPEC.md §12.1 — is_authenticated reflects token state.
        """
        client = _make_client()
        mock_http, _ = _mock_httpx_success()

        with patch("noa.tools.google_auth.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.exchange_code("some-code")

        assert client.is_authenticated is True

    @pytest.mark.asyncio
    async def test_not_authenticated_after_failed_exchange(self):
        """Client must remain unauthenticated after failed exchange.

        SPEC.md §12.1 — Failed exchange does not set tokens.
        """
        from noa.tools.google_auth import GoogleAuthError

        client = _make_client()
        mock_http, _ = _mock_httpx_error(status_code=400)

        with patch("noa.tools.google_auth.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            with pytest.raises(GoogleAuthError):
                await client.exchange_code("bad-code")

        assert client.is_authenticated is False


# ---------------------------------------------------------------------------
# 12. Exchange does not log token values (SPEC §11.2)
# ---------------------------------------------------------------------------


class TestNoTokenLogging:
    """Tests ensuring token values are never logged per SPEC §11.2."""

    @pytest.mark.asyncio
    async def test_exchange_does_not_log_tokens(self, caplog):
        """Token values must never appear in logs.

        SPEC.md §11.2 — Secrets never logged.
        """
        access_tok = "super-secret-access-token-12345"
        refresh_tok = "super-secret-refresh-token-67890"

        client = _make_client()
        mock_http, _ = _mock_httpx_success(
            access_token=access_tok, refresh_token=refresh_tok
        )

        with patch("noa.tools.google_auth.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            with caplog.at_level(logging.DEBUG, logger="noa.tools.google_auth"):
                await client.exchange_code("code-for-logging-test")

        log_output = caplog.text
        assert access_tok not in log_output, (
            f"Access token leaked in logs: {log_output}"
        )
        assert refresh_tok not in log_output, (
            f"Refresh token leaked in logs: {log_output}"
        )

    @pytest.mark.asyncio
    async def test_refresh_does_not_log_tokens(self, caplog):
        """Refresh token values must never appear in logs.

        SPEC.md §11.2 — Secrets never logged.
        """
        client = _make_client()
        client.set_tokens(
            access_token="old-secret-at", refresh_token="old-secret-rt"
        )

        new_at = "new-secret-access-token-xyz"
        new_rt = "new-secret-refresh-token-abc"
        mock_http, _ = _mock_httpx_success(
            access_token=new_at, refresh_token=new_rt
        )

        with patch("noa.tools.google_auth.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            with caplog.at_level(logging.DEBUG, logger="noa.tools.google_auth"):
                await client.refresh_access_token()

        log_output = caplog.text
        assert new_at not in log_output
        assert new_rt not in log_output
        assert "old-secret-at" not in log_output
        assert "old-secret-rt" not in log_output

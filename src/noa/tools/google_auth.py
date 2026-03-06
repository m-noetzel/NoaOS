"""Shared Google OAuth2 client for Calendar, Gmail tools.

Spec refs: SPEC.md §12.1 (Calendar OAuth2), §12.2 (Gmail OAuth2),
           §11.2 (secrets never logged), §11.3 (refresh token rotation)

This module provides the OAuth2 flow and token management for all
Google API integrations: authorization URL generation, code exchange,
and token refresh.
"""

from __future__ import annotations

import logging
from urllib.parse import quote, urlencode

import httpx
from httpx import HTTPStatusError

logger = logging.getLogger(__name__)

# Required scopes per §12.1
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

# Required scopes per §12.2
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105


class GoogleAuthError(Exception):
    """Raised when Google OAuth2 operations fail."""


class GoogleAuthClient:
    """Google OAuth2 client for managing credentials and token refresh.

    Args:
        client_id: Google OAuth2 client ID.
        client_secret: Google OAuth2 client secret.
        redirect_uri: OAuth2 callback URL.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        self.client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._access_token: str | None = None
        self._refresh_token: str | None = None

    def get_auth_url(self, scopes: list[str]) -> str:
        """Generate the Google OAuth2 authorization URL.

        Args:
            scopes: OAuth2 scopes to request.

        Returns:
            Authorization URL string.
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{_GOOGLE_AUTH_URL}?{urlencode(params, quote_via=quote)}"

    @property
    def is_authenticated(self) -> bool:
        """Whether we have a valid access token."""
        return self._access_token is not None

    def set_tokens(
        self, *, access_token: str, refresh_token: str
    ) -> None:
        """Store tokens after OAuth2 code exchange."""
        self._access_token = access_token
        self._refresh_token = refresh_token

    @property
    def access_token(self) -> str | None:
        """Current access token."""
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Current refresh token."""
        return self._refresh_token

    async def exchange_code(self, code: str) -> dict[str, str]:
        """Exchange an authorization code for access + refresh tokens.

        Args:
            code: The authorization code from the OAuth2 callback.

        Returns:
            Dict with access_token and refresh_token.

        Raises:
            GoogleAuthError: On HTTP error or empty code.
            ValueError: If code is None.
        """
        if code is None:
            raise ValueError("code must not be None")
        if not code:
            raise GoogleAuthError("Authorization code must not be empty")

        data = {
            "client_id": self.client_id,
            "client_secret": self._client_secret,
            "code": code,
            "redirect_uri": self._redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(_GOOGLE_TOKEN_URL, data=data)
                resp.raise_for_status()
        except HTTPStatusError as exc:
            raise GoogleAuthError(
                f"Token exchange failed: {exc.response.status_code}"
            ) from exc

        body = resp.json()
        at = body["access_token"]
        rt = body["refresh_token"]

        self._access_token = at
        self._refresh_token = rt

        logger.info("Google OAuth2 code exchange succeeded")
        return {"access_token": at, "refresh_token": rt}

    async def refresh_access_token(self) -> None:
        """Refresh the access token using the stored refresh token.

        Raises:
            GoogleAuthError: On HTTP error or missing refresh token.
        """
        if not self._refresh_token:
            raise GoogleAuthError("No refresh token available")

        data = {
            "client_id": self.client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(_GOOGLE_TOKEN_URL, data=data)
                resp.raise_for_status()
        except HTTPStatusError as exc:
            raise GoogleAuthError(
                f"Token refresh failed: {exc.response.status_code}"
            ) from exc

        body = resp.json()
        self._access_token = body["access_token"]

        # Rotate refresh token if a new one is provided (§11.3)
        if "refresh_token" in body:
            self._refresh_token = body["refresh_token"]

        logger.info("Google OAuth2 token refresh succeeded")

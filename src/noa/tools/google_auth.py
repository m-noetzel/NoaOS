"""Shared Google OAuth2 client for Calendar, Gmail tools.

Spec refs: SPEC.md §12.1 (Calendar OAuth2), §12.2 (Gmail OAuth2)

This module provides the OAuth2 flow and token management for all
Google API integrations. Actual HTTP token exchange is deferred to
production wiring — this module handles credential storage, scope
management, and auth URL generation.
"""

from __future__ import annotations

from urllib.parse import quote, urlencode

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

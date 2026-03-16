"""Shared Google OAuth2 client for Calendar, Gmail tools.

Spec refs: SPEC.md §12.1 (Calendar OAuth2), §12.2 (Gmail OAuth2),
           §11.2 (secrets never logged), §11.3 (refresh token rotation)

This module provides the OAuth2 flow and token management for all
Google API integrations: authorization URL generation, code exchange,
and token refresh.
"""

from __future__ import annotations

import logging
from typing import Any
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
        on_token_change: Any | None = None,
    ) -> None:
        self.client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._on_token_change = on_token_change

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
        """Store tokens after OAuth2 code exchange.

        Calls the on_token_change callback if configured.  Phase QC8 / M10.
        """
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._notify_token_change()

    def _notify_token_change(self) -> None:
        """Invoke the on_token_change callback if configured.

        The callback must be synchronous. If an async callable is passed,
        a warning is logged and the coroutine is properly closed to avoid
        resource leaks.

        Catches and logs callback errors so they never break the client.
        Phase QC8 / M10.
        """
        if self._on_token_change is None:
            return
        try:
            import inspect

            result = self._on_token_change(
                access_token=self._access_token,
                refresh_token=self._refresh_token,
            )
            if inspect.isawaitable(result):
                logger.warning(
                    "on_token_change callback returned a coroutine — "
                    "callback must be synchronous; closing coroutine"
                )
                result.close()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            logger.warning(
                "on_token_change callback failed", exc_info=True,
            )

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
        at = body.get("access_token")
        rt = body.get("refresh_token")
        if not at or not rt:
            raise GoogleAuthError(
                "Token exchange response missing access_token or refresh_token"
            )

        self._access_token = at
        self._refresh_token = rt

        self._notify_token_change()
        logger.info("Google OAuth2 code exchange succeeded")
        return {"access_token": at, "refresh_token": rt}

    async def clear_tokens(self) -> None:
        """Clear stored tokens (called on disconnect)."""
        self._access_token = None
        self._refresh_token = None
        logger.info("Google OAuth2 tokens cleared")

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

        self._notify_token_change()
        logger.info("Google OAuth2 token refresh succeeded")


async def load_tokens_from_db(
    session: object,
    user_id: object,
    auth_client: GoogleAuthClient,
) -> bool:
    """Load encrypted Google tokens from DB and call set_tokens() on the client.

    Args:
        session: AsyncSession to query with.
        user_id: UUID of the user to load tokens for.
        auth_client: GoogleAuthClient to configure with loaded tokens.

    Returns:
        True if tokens were loaded, False if no row exists.
    """
    from sqlalchemy import select

    from noa.db.models.google_credential import GoogleCredential
    from noa.tools._token_crypto import decrypt_token

    stmt = select(GoogleCredential).where(
        GoogleCredential.user_id == user_id
    )
    result = await session.execute(stmt)  # type: ignore[attr-defined]
    cred = result.scalar_one_or_none()

    if cred is None:
        logger.debug("No Google credentials in DB for user %s", user_id)
        return False

    try:
        access_token = (
            decrypt_token(cred.access_token_enc) if cred.access_token_enc else ""
        )
        refresh_token = decrypt_token(cred.refresh_token_enc)
    except (ValueError, Exception):  # noqa: BLE001
        # cryptography.fernet.InvalidToken (subclass of Exception) is raised
        # when decryption fails (wrong key or corrupted ciphertext). We can't
        # import it here without adding cryptography as a hard dependency at
        # module level, so we catch broadly with a comment explaining why.
        logger.warning("Failed to decrypt Google tokens for user %s", user_id)
        return False

    auth_client.set_tokens(access_token=access_token, refresh_token=refresh_token)
    logger.info("Google tokens loaded from DB for user %s", user_id)
    return True

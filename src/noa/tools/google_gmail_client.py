"""Gmail API v1 HTTP client.

Spec refs: SPEC.md §12.2 (Gmail functions), §8.2 (external egress)

Real httpx-based async client using OAuth2 bearer tokens. Auto-refreshes
on 401 and retries once.
"""

from __future__ import annotations

import base64
import logging
import uuid
from email.mime.text import MIMEText
from typing import Any

import httpx
from httpx import HTTPStatusError

from noa.tools.gmail import GmailAPIError
from noa.tools.google_auth import GoogleAuthError, load_tokens_from_db

logger = logging.getLogger(__name__)

_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"

# BE-AP3: Friendly reconnect error returned when token refresh fails with
# GoogleAuthError (e.g. invalid_grant).  Returned instead of raising so
# the tool call surface stays safe (no raw exception text to the LLM).
_GOOGLE_RECONNECT_ERROR: dict[str, str] = {
    "error": (
        "Google account needs to be reconnected. "
        "Please go to Settings → Google and reconnect your account."
    )
}


class GmailClient:
    """Async client for Gmail API v1.

    Args:
        auth_client: GoogleAuthClient with valid tokens.
        user_id: Optional UUID of the authenticated user. Used to reload
            tokens from DB before each request (BE-AP3 token refresh).
        session_factory: Optional callable that returns an async DB session
            context manager.  Required when user_id is provided.
    """

    def __init__(
        self,
        *,
        auth_client: Any,
        user_id: uuid.UUID | None = None,
        session_factory: Any | None = None,
    ) -> None:
        self._auth = auth_client
        self._auth_client = auth_client
        self._user_id = user_id
        self._session_factory = session_factory

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._auth.access_token}"}

    async def _ensure_fresh_token(self) -> None:
        """Reload tokens from DB if session_factory and user_id are available.

        BE-AP3: Best-effort — never raises.  Silently skips when no
        session_factory or user_id is configured.
        """
        if self._session_factory is None or self._user_id is None:
            return
        try:
            async with self._session_factory() as session:
                await load_tokens_from_db(session, self._user_id, self._auth_client)
        except Exception:  # noqa: BLE001
            logger.debug(
                "GmailClient._ensure_fresh_token: DB reload failed — skipping"
            )

    async def _safe_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make request with token refresh and friendly error on auth failure.

        BE-AP3: Calls _ensure_fresh_token() first to load the latest token
        from the DB, then makes the HTTP request.  On 401, retries once after
        calling refresh_access_token().  If the refresh raises GoogleAuthError
        (e.g. invalid_grant), returns _GOOGLE_RECONNECT_ERROR instead of
        raising so the LLM sees a user-friendly message.
        """
        await self._ensure_fresh_token()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await getattr(client, method)(
                url, headers=self._headers(), **kwargs,
            )
            if resp.status_code == 401:
                try:
                    await self._auth_client.refresh_access_token()
                except GoogleAuthError:
                    logger.warning(
                        "GmailClient: token refresh failed — returning reconnect error"
                    )
                    return dict(_GOOGLE_RECONNECT_ERROR)
                resp = await getattr(client, method)(
                    url, headers=self._headers(), **kwargs,
                )
            try:
                resp.raise_for_status()
            except HTTPStatusError as exc:
                raise GmailAPIError(
                    f"Gmail API error: {exc.response.status_code}"
                ) from exc
            result: dict[str, Any] = resp.json()
            return result

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make request, retry once on 401 after token refresh.

        Delegates to _safe_request for consistent error handling.
        """
        return await self._safe_request(method, url, **kwargs)

    async def search_emails(
        self, *, query: str, max_results: int = 20
    ) -> list[dict[str, Any]]:
        """Search emails matching a query string."""
        url = f"{_BASE_URL}/messages"
        params = {"q": query, "maxResults": max_results}
        data = await self._request_with_retry("get", url, params=params)
        msgs: list[dict[str, Any]] = data.get("messages", [])
        return msgs

    async def read_email(self, *, email_id: str) -> dict[str, Any]:
        """Read full email content by message ID."""
        url = f"{_BASE_URL}/messages/{email_id}"
        params = {"format": "full"}
        return await self._request_with_retry("get", url, params=params)

    async def send_email(
        self, *, to: str, subject: str, body: str
    ) -> dict[str, Any]:
        """Send an email."""
        url = f"{_BASE_URL}/messages/send"
        raw = _encode_message(to=to, subject=subject, body=body)
        return await self._request_with_retry(
            "post", url, json={"raw": raw}
        )

    async def draft_email(
        self, *, to: str, subject: str, body: str
    ) -> dict[str, Any]:
        """Create an email draft."""
        url = f"{_BASE_URL}/drafts"
        raw = _encode_message(to=to, subject=subject, body=body)
        return await self._request_with_retry(
            "post", url, json={"message": {"raw": raw}}
        )


def _encode_message(*, to: str, subject: str, body: str) -> str:
    """Encode an email as base64url for Gmail API."""
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    raw_bytes = msg.as_bytes()
    return base64.urlsafe_b64encode(raw_bytes).decode("ascii")

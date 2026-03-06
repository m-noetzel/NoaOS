"""Gmail API v1 HTTP client.

Spec refs: SPEC.md §12.2 (Gmail functions), §8.2 (external egress)

Real httpx-based async client using OAuth2 bearer tokens. Auto-refreshes
on 401 and retries once.
"""

from __future__ import annotations

import base64
import logging
from email.mime.text import MIMEText
from typing import Any

import httpx
from httpx import HTTPStatusError

from noa.tools.gmail import GmailAPIError

logger = logging.getLogger(__name__)

_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailClient:
    """Async client for Gmail API v1.

    Args:
        auth_client: GoogleAuthClient with valid tokens.
    """

    def __init__(self, *, auth_client: Any) -> None:
        self._auth = auth_client

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._auth.access_token}"}

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make request, retry once on 401 after token refresh."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await getattr(client, method)(
                url, headers=self._headers(), **kwargs,
            )
            if resp.status_code == 401:
                await self._auth.refresh_access_token()
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

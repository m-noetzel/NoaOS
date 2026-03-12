"""Gmail tool — search, read, send, draft emails.

Spec refs: SPEC.md §12.2, §16.3

Requires Google OAuth2 authentication with gmail.readonly, gmail.send,
and gmail.compose scopes. All operations go through the external domain.
"""

from __future__ import annotations

import logging
import re
from typing import Any, cast

logger = logging.getLogger(__name__)

# RFC 5322 simplified: local@domain, no commas/newlines/spaces
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$"
)


def _validate_email_recipient(to: str) -> None:
    """Validate a single email recipient address (H6).

    Rejects empty, malformed, multi-recipient injection, and header injection.
    """
    if not to or not to.strip():
        raise ValueError("Invalid email recipient: address is empty")
    if "," in to or ";" in to:
        raise ValueError("Invalid email recipient: multiple recipients not allowed")
    if "\n" in to or "\r" in to:
        raise ValueError("Invalid email recipient: newline injection detected")
    if not _EMAIL_RE.match(to.strip()):
        raise ValueError(f"Invalid email recipient: {to!r}")


class GmailAPIError(Exception):
    """Raised when the Gmail API returns an error."""


class GmailTool:
    """Gmail tool per SPEC.md §12.2.

    Attributes:
        domain: "external" — requires Gmail API access.
        risk_tiers: Per-action risk tiers.
    """

    name: str = "gmail"
    domain: str = "external"
    risk_tiers: dict[str, str] = {
        "search_emails": "low",
        "read_email": "low",
        "send_email": "medium",
        "draft_email": "low",
    }

    def __init__(self, *, api_client: Any) -> None:
        """Initialize with a Gmail API client.

        Args:
            api_client: Async client for Gmail API calls.
        """
        self._client = api_client

    async def execute(
        self, *, function: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatch to the appropriate method by function name."""
        method = getattr(self, function, None)
        if method is None:
            raise ValueError(f"Unknown function: {function}")
        return cast(dict[str, Any], await method(**args))

    async def search_emails(
        self,
        *,
        query: str,
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """Search email summaries.

        Args:
            query: Search query string.
            max_results: Maximum number of results.

        Returns:
            List of email summary dicts.
        """
        return cast(list[dict[str, Any]], await self._client.search_emails(
            query=query,
            max_results=max_results,
        ))

    async def read_email(
        self,
        *,
        email_id: str,
    ) -> dict[str, Any]:
        """Read full email content.

        Args:
            email_id: ID of the email to read.

        Returns:
            Full email dict with from, to, subject, body, date.
        """
        return cast(dict[str, Any], await self._client.read_email(email_id=email_id))

    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        body: str,
    ) -> dict[str, Any]:
        """Send an email (Medium risk).

        Args:
            to: Recipient email address.
            subject: Email subject.
            body: Email body text.

        Returns:
            Send confirmation dict with id and status.
        """
        _validate_email_recipient(to)
        result: dict[str, Any] = cast(dict[str, Any], await self._client.send_email(
            to=to,
            subject=subject,
            body=body,
        ))

        # Log confirmation before reporting success per §16.3
        logger.info(
            "send_confirmation: email_id=%s to=%s subject=%s",
            result.get("id", "unknown"),
            to,
            subject,
        )

        return result

    async def draft_email(
        self,
        *,
        to: str,
        subject: str,
        body: str,
    ) -> dict[str, Any]:
        """Create an email draft (Low risk).

        Args:
            to: Recipient email address.
            subject: Email subject.
            body: Email body text.

        Returns:
            Draft dict with id and status.
        """
        _validate_email_recipient(to)
        return cast(dict[str, Any], await self._client.draft_email(
            to=to,
            subject=subject,
            body=body,
        ))

"""Tests for Phase TI3: Gmail Tool.

Covers: search_emails, read_email, send_email, draft_email, risk tiers,
send confirmation logging, error handling.

Spec refs: SPEC.md §12.2, §16.3
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.ti3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_email_summary(
    *,
    email_id: str = "msg-123",
    subject: str = "Meeting notes",
    sender: str = "alice@example.com",
    snippet: str = "Here are the notes from...",
) -> dict[str, Any]:
    return {
        "id": email_id,
        "subject": subject,
        "from": sender,
        "snippet": snippet,
        "date": "2026-03-05T10:00:00Z",
    }


def _make_full_email(
    *,
    email_id: str = "msg-123",
    subject: str = "Meeting notes",
    body: str = "Full body content here.",
) -> dict[str, Any]:
    return {
        "id": email_id,
        "subject": subject,
        "from": "alice@example.com",
        "to": ["bob@example.com"],
        "body": body,
        "date": "2026-03-05T10:00:00Z",
    }


# ---------------------------------------------------------------------------
# GmailTool metadata
# ---------------------------------------------------------------------------


class TestGmailToolMetadata:
    """Tests for GmailTool class attributes per §12.2."""

    def test_domain_is_external(self):
        """Gmail tool must be in external domain.

        SPEC.md §12.2 — Privacy: external.
        """
        from noa.tools.gmail import GmailTool

        assert GmailTool.domain == "external"

    def test_search_risk_tier_is_low(self):
        """search_emails risk tier must be Low.

        SPEC.md §12.2 — Risk tier: Low (search).
        """
        from noa.tools.gmail import GmailTool

        assert GmailTool.risk_tiers["search_emails"] == "low"

    def test_read_risk_tier_is_low(self):
        """read_email risk tier must be Low.

        SPEC.md §12.2 — Risk tier: Low (read).
        """
        from noa.tools.gmail import GmailTool

        assert GmailTool.risk_tiers["read_email"] == "low"

    def test_send_risk_tier_is_medium(self):
        """send_email risk tier must be Medium.

        SPEC.md §12.2 — Risk tier: Medium (send).
        """
        from noa.tools.gmail import GmailTool

        assert GmailTool.risk_tiers["send_email"] == "medium"

    def test_draft_risk_tier_is_low(self):
        """draft_email risk tier must be Low.

        SPEC.md §12.2 — Risk tier: Low (draft).
        """
        from noa.tools.gmail import GmailTool

        assert GmailTool.risk_tiers["draft_email"] == "low"


# ---------------------------------------------------------------------------
# search_emails
# ---------------------------------------------------------------------------


class TestSearchEmails:
    """Tests for search_emails() per §12.2."""

    @pytest.mark.asyncio
    async def test_search_returns_summaries(self):
        """search_emails must return email summaries.

        SPEC.md §12.2 — search_emails returns list of email summaries.
        """
        from noa.tools.gmail import GmailTool

        mock_client = AsyncMock()
        mock_client.search_emails.return_value = [
            _make_email_summary(),
            _make_email_summary(email_id="msg-456", subject="Agenda"),
        ]
        tool = GmailTool(api_client=mock_client)

        result = await tool.search_emails(query="meeting")

        assert len(result) == 2
        assert result[0]["subject"] == "Meeting notes"

    @pytest.mark.asyncio
    async def test_search_respects_max_results(self):
        """search_emails must pass max_results to the API.

        SPEC.md §12.2 — search_emails(query, max_results?).
        """
        from noa.tools.gmail import GmailTool

        mock_client = AsyncMock()
        mock_client.search_emails.return_value = []
        tool = GmailTool(api_client=mock_client)

        await tool.search_emails(query="test", max_results=10)

        mock_client.search_emails.assert_called_once_with(
            query="test", max_results=10,
        )


# ---------------------------------------------------------------------------
# read_email
# ---------------------------------------------------------------------------


class TestReadEmail:
    """Tests for read_email() per §12.2."""

    @pytest.mark.asyncio
    async def test_read_returns_full_content(self):
        """read_email must return full email content.

        SPEC.md §12.2 — read_email returns full email content.
        """
        from noa.tools.gmail import GmailTool

        mock_client = AsyncMock()
        mock_client.read_email.return_value = _make_full_email()
        tool = GmailTool(api_client=mock_client)

        result = await tool.read_email(email_id="msg-123")

        assert result["body"] == "Full body content here."
        assert result["subject"] == "Meeting notes"

    @pytest.mark.asyncio
    async def test_read_includes_required_fields(self):
        """read_email must include from, to, subject, body, date.

        SPEC.md §12.2 — Full email content.
        """
        from noa.tools.gmail import GmailTool

        mock_client = AsyncMock()
        mock_client.read_email.return_value = _make_full_email()
        tool = GmailTool(api_client=mock_client)

        result = await tool.read_email(email_id="msg-123")

        for key in ("from", "to", "subject", "body", "date"):
            assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# send_email
# ---------------------------------------------------------------------------


class TestSendEmail:
    """Tests for send_email() per §12.2, §16.3."""

    @pytest.mark.asyncio
    async def test_send_returns_confirmation(self):
        """send_email must return sent confirmation.

        SPEC.md §12.2 — send_email returns sent confirmation.
        """
        from noa.tools.gmail import GmailTool

        mock_client = AsyncMock()
        mock_client.send_email.return_value = {
            "id": "sent-123",
            "status": "sent",
        }
        tool = GmailTool(api_client=mock_client)

        result = await tool.send_email(
            to="bob@example.com",
            subject="Hello",
            body="Hi Bob!",
        )

        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_send_logs_confirmation(self, caplog):
        """send_email must log confirmation before reporting success.

        SPEC.md §16.3 — Email send confirmations logged before
        reporting success.
        """
        import logging

        from noa.tools.gmail import GmailTool

        mock_client = AsyncMock()
        mock_client.send_email.return_value = {
            "id": "sent-123",
            "status": "sent",
        }
        tool = GmailTool(api_client=mock_client)

        with caplog.at_level(logging.INFO):
            await tool.send_email(
                to="bob@example.com",
                subject="Hello",
                body="Hi Bob!",
            )

        assert any(
            "send_confirmation" in record.message
            for record in caplog.records
        )


# ---------------------------------------------------------------------------
# draft_email
# ---------------------------------------------------------------------------


class TestDraftEmail:
    """Tests for draft_email() per §12.2."""

    @pytest.mark.asyncio
    async def test_draft_returns_draft_id(self):
        """draft_email must return the draft ID.

        SPEC.md §12.2 — draft_email returns draft ID.
        """
        from noa.tools.gmail import GmailTool

        mock_client = AsyncMock()
        mock_client.draft_email.return_value = {
            "id": "draft-123",
            "status": "created",
        }
        tool = GmailTool(api_client=mock_client)

        result = await tool.draft_email(
            to="bob@example.com",
            subject="Draft Hello",
            body="Draft body",
        )

        assert result["id"] == "draft-123"


# ---------------------------------------------------------------------------
# OAuth2 scopes
# ---------------------------------------------------------------------------


class TestGmailScopes:
    """Tests for Gmail OAuth2 scopes per §12.2."""

    def test_gmail_scopes_defined(self):
        """Gmail scopes must include readonly, send, compose.

        SPEC.md §12.2 — Scopes: gmail.readonly, gmail.send, gmail.compose.
        """
        from noa.tools.google_auth import GMAIL_SCOPES

        assert "https://www.googleapis.com/auth/gmail.readonly" in GMAIL_SCOPES
        assert "https://www.googleapis.com/auth/gmail.send" in GMAIL_SCOPES
        assert "https://www.googleapis.com/auth/gmail.compose" in GMAIL_SCOPES


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling per §12.2."""

    @pytest.mark.asyncio
    async def test_api_failure_handled_gracefully(self):
        """API failures must be handled gracefully.

        SPEC.md §12.2 — Error handling: API failures handled gracefully.
        """
        from noa.tools.gmail import GmailAPIError, GmailTool

        mock_client = AsyncMock()
        mock_client.search_emails.side_effect = GmailAPIError(
            "Gmail API returned 503"
        )
        tool = GmailTool(api_client=mock_client)

        with pytest.raises(GmailAPIError, match="503"):
            await tool.search_emails(query="test")

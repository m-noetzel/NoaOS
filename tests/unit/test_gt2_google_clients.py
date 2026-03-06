"""Tests for GT2: Google Calendar + Gmail HTTP Clients.

Covers: GoogleCalendarClient, GmailClient with real httpx calls,
auto-refresh on 401, and tool registration in gateway.

Spec refs: SPEC.md §12.1, §12.2, §8.2
"""
# ruff: noqa: S105, S106, S107

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.gt2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_auth_client(access_token: str = "test-access-tok"):
    """Create a mock GoogleAuthClient with a token."""
    auth = MagicMock()
    auth.access_token = access_token
    auth.refresh_access_token = AsyncMock()
    return auth


def _mock_response(*, status_code: int = 200, json_data: dict | list | None = None):
    """Build a mock httpx response."""
    import httpx as real_httpx

    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = real_httpx.HTTPStatusError(
            str(status_code), request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status = MagicMock()
    return resp


def _mock_httpx_client(*responses):
    """Build a mock async httpx client returning given responses in order."""
    mock_client = AsyncMock()
    mock_client.request = AsyncMock(side_effect=list(responses))
    mock_client.get = AsyncMock(side_effect=list(responses))
    mock_client.post = AsyncMock(side_effect=list(responses))
    mock_client.patch = AsyncMock(side_effect=list(responses))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ===========================================================================
# GoogleCalendarClient tests
# ===========================================================================


class TestGoogleCalendarClientListEvents:
    """Tests for GoogleCalendarClient.list_events()."""

    @pytest.mark.asyncio
    async def test_list_events_sends_get_to_events_endpoint(self):
        """list_events must GET /calendars/primary/events."""
        from noa.tools.google_calendar_client import GoogleCalendarClient

        auth = _mock_auth_client()
        client = GoogleCalendarClient(auth_client=auth)

        events_data = {"items": [{"id": "e1", "summary": "Test"}]}
        mock_http = _mock_httpx_client(_mock_response(json_data=events_data))

        with patch("noa.tools.google_calendar_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.list_events(
                start_date="2026-03-01T00:00:00Z",
                end_date="2026-03-07T00:00:00Z",
            )

        # Verify GET was called
        mock_http.get.assert_called_once()
        call_url = mock_http.get.call_args[0][0]
        assert "/calendars/primary/events" in call_url

    @pytest.mark.asyncio
    async def test_list_events_passes_time_params(self):
        """list_events must pass timeMin and timeMax as query params."""
        from noa.tools.google_calendar_client import GoogleCalendarClient

        auth = _mock_auth_client()
        client = GoogleCalendarClient(auth_client=auth)

        mock_http = _mock_httpx_client(
            _mock_response(json_data={"items": []})
        )

        with patch("noa.tools.google_calendar_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.list_events(
                start_date="2026-03-01T00:00:00Z",
                end_date="2026-03-07T00:00:00Z",
            )

        call_kwargs = mock_http.get.call_args[1]
        params = call_kwargs.get("params", {})
        assert params["timeMin"] == "2026-03-01T00:00:00Z"
        assert params["timeMax"] == "2026-03-07T00:00:00Z"


class TestGoogleCalendarClientCreateEvent:
    """Tests for GoogleCalendarClient.create_event()."""

    @pytest.mark.asyncio
    async def test_create_event_sends_post(self):
        """create_event must POST to /calendars/primary/events."""
        from noa.tools.google_calendar_client import GoogleCalendarClient

        auth = _mock_auth_client()
        client = GoogleCalendarClient(auth_client=auth)

        mock_http = _mock_httpx_client(
            _mock_response(json_data={"id": "new-event-1"})
        )

        with patch("noa.tools.google_calendar_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            result = await client.create_event(
                title="Meeting",
                start="2026-03-10T10:00:00Z",
                end="2026-03-10T11:00:00Z",
                description="Standup",
                attendees=["a@b.com"],
            )

        mock_http.post.assert_called_once()
        assert result["id"] == "new-event-1"


class TestGoogleCalendarClientUpdateEvent:
    """Tests for GoogleCalendarClient.update_event()."""

    @pytest.mark.asyncio
    async def test_update_event_sends_patch(self):
        """update_event must PATCH /calendars/primary/events/{id}."""
        from noa.tools.google_calendar_client import GoogleCalendarClient

        auth = _mock_auth_client()
        client = GoogleCalendarClient(auth_client=auth)

        mock_http = _mock_httpx_client(
            _mock_response(json_data={"id": "e1", "summary": "Updated"})
        )

        with patch("noa.tools.google_calendar_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.update_event(
                event_id="e1", title="Updated"
            )

        mock_http.patch.assert_called_once()
        call_url = mock_http.patch.call_args[0][0]
        assert "/events/e1" in call_url


class TestGoogleCalendarClientAuth:
    """Tests for Calendar client auth header and retry."""

    @pytest.mark.asyncio
    async def test_sets_bearer_header(self):
        """Calendar client must set Authorization: Bearer header."""
        from noa.tools.google_calendar_client import GoogleCalendarClient

        auth = _mock_auth_client(access_token="my-token")
        client = GoogleCalendarClient(auth_client=auth)

        mock_http = _mock_httpx_client(
            _mock_response(json_data={"items": []})
        )

        with patch("noa.tools.google_calendar_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.list_events(
                start_date="2026-03-01T00:00:00Z",
                end_date="2026-03-07T00:00:00Z",
            )

        call_kwargs = mock_http.get.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer my-token"

    @pytest.mark.asyncio
    async def test_retries_on_401_after_refresh(self):
        """Calendar client must refresh token and retry on 401."""
        from noa.tools.google_calendar_client import GoogleCalendarClient

        auth = _mock_auth_client(access_token="expired-tok")
        # After refresh, update the token
        auth.refresh_access_token.side_effect = lambda: setattr(
            auth, "access_token", "new-tok"
        )

        client = GoogleCalendarClient(auth_client=auth)

        resp_401 = _mock_response(status_code=401, json_data={})
        resp_200 = _mock_response(json_data={"items": []})

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=[resp_401, resp_200])
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)

        with patch("noa.tools.google_calendar_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.list_events(
                start_date="2026-03-01T00:00:00Z",
                end_date="2026-03-07T00:00:00Z",
            )

        auth.refresh_access_token.assert_called_once()
        assert mock_http.get.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_on_4xx_5xx(self):
        """Calendar client must raise CalendarAPIError on HTTP errors."""
        from noa.tools.calendar import CalendarAPIError
        from noa.tools.google_calendar_client import GoogleCalendarClient

        auth = _mock_auth_client()
        client = GoogleCalendarClient(auth_client=auth)

        mock_http = _mock_httpx_client(
            _mock_response(status_code=500, json_data={"error": "server"})
        )

        with patch("noa.tools.google_calendar_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            with pytest.raises(CalendarAPIError):
                await client.list_events(
                    start_date="2026-03-01T00:00:00Z",
                    end_date="2026-03-07T00:00:00Z",
                )


# ===========================================================================
# GmailClient tests
# ===========================================================================


class TestGmailClientSearch:
    """Tests for GmailClient.search_emails()."""

    @pytest.mark.asyncio
    async def test_search_sends_get_to_messages(self):
        """search_emails must GET /gmail/v1/users/me/messages."""
        from noa.tools.google_gmail_client import GmailClient

        auth = _mock_auth_client()
        client = GmailClient(auth_client=auth)

        # search returns message IDs, then we fetch each one
        mock_http = _mock_httpx_client(
            _mock_response(
                json_data={"messages": [{"id": "m1"}], "resultSizeEstimate": 1},
            )
        )

        with patch("noa.tools.google_gmail_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.search_emails(query="from:test@x.com")

        mock_http.get.assert_called_once()
        call_url = mock_http.get.call_args[0][0]
        assert "/messages" in call_url


class TestGmailClientRead:
    """Tests for GmailClient.read_email()."""

    @pytest.mark.asyncio
    async def test_read_sends_get_to_message_id(self):
        """read_email must GET /messages/{id} with format=full."""
        from noa.tools.google_gmail_client import GmailClient

        auth = _mock_auth_client()
        client = GmailClient(auth_client=auth)

        email_data = {
            "id": "msg-1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "a@b.com"},
                    {"name": "Subject", "value": "Test"},
                ],
                "body": {"data": "SGVsbG8="},
            },
        }
        mock_http = _mock_httpx_client(
            _mock_response(json_data=email_data)
        )

        with patch("noa.tools.google_gmail_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.read_email(email_id="msg-1")

        call_url = mock_http.get.call_args[0][0]
        assert "/messages/msg-1" in call_url
        call_kwargs = mock_http.get.call_args[1]
        params = call_kwargs.get("params", {})
        assert params.get("format") == "full"


class TestGmailClientSend:
    """Tests for GmailClient.send_email()."""

    @pytest.mark.asyncio
    async def test_send_posts_to_messages_send(self):
        """send_email must POST to /messages/send."""
        from noa.tools.google_gmail_client import GmailClient

        auth = _mock_auth_client()
        client = GmailClient(auth_client=auth)

        mock_http = _mock_httpx_client(
            _mock_response(json_data={"id": "sent-1", "labelIds": ["SENT"]})
        )

        with patch("noa.tools.google_gmail_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.send_email(
                to="x@y.com", subject="Hi", body="Hello"
            )

        mock_http.post.assert_called_once()
        call_url = mock_http.post.call_args[0][0]
        assert "/messages/send" in call_url


class TestGmailClientDraft:
    """Tests for GmailClient.draft_email()."""

    @pytest.mark.asyncio
    async def test_draft_posts_to_drafts(self):
        """draft_email must POST to /drafts."""
        from noa.tools.google_gmail_client import GmailClient

        auth = _mock_auth_client()
        client = GmailClient(auth_client=auth)

        mock_http = _mock_httpx_client(
            _mock_response(json_data={"id": "draft-1"})
        )

        with patch("noa.tools.google_gmail_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            await client.draft_email(
                to="x@y.com", subject="Hi", body="Hello"
            )

        mock_http.post.assert_called_once()
        call_url = mock_http.post.call_args[0][0]
        assert "/drafts" in call_url


class TestGmailClientErrors:
    """Tests for Gmail client error handling."""

    @pytest.mark.asyncio
    async def test_raises_gmail_api_error(self):
        """Gmail client must raise GmailAPIError on HTTP errors."""
        from noa.tools.gmail import GmailAPIError
        from noa.tools.google_gmail_client import GmailClient

        auth = _mock_auth_client()
        client = GmailClient(auth_client=auth)

        mock_http = _mock_httpx_client(
            _mock_response(status_code=403, json_data={"error": "forbidden"})
        )

        with patch("noa.tools.google_gmail_client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_http

            with pytest.raises(GmailAPIError):
                await client.search_emails(query="test")


# ===========================================================================
# Registration tests
# ===========================================================================


class TestRegistration:
    """Tests for tool registration functions."""

    def test_register_calendar_when_credentials_set(self):
        """_register_calendar registers calendar tool when creds exist."""
        from noa.tools.gateway import ToolGateway
        from noa.tools.registration import register_tools

        gateway = ToolGateway()

        with patch.dict("os.environ", {
            "GOOGLE_CLIENT_ID": "cid",
            "GOOGLE_CLIENT_SECRET": "csec",
            "GOOGLE_REFRESH_TOKEN": "rt",
        }):
            register_tools(gateway)

        assert "calendar" in gateway._adapters

    def test_register_gmail_when_credentials_set(self):
        """_register_gmail registers gmail tool when creds exist."""
        from noa.tools.gateway import ToolGateway
        from noa.tools.registration import register_tools

        gateway = ToolGateway()

        with patch.dict("os.environ", {
            "GOOGLE_CLIENT_ID": "cid",
            "GOOGLE_CLIENT_SECRET": "csec",
            "GOOGLE_REFRESH_TOKEN": "rt",
        }):
            register_tools(gateway)

        assert "gmail" in gateway._adapters

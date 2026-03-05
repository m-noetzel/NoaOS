"""Tests for Phase TI2: Google Calendar Tool.

Covers: list_events, create_event, update_event, OAuth2, risk tiers,
validation (no past events, no unreasonable durations), error handling.

Spec refs: SPEC.md §12.1, §16.3
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.ti2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 5, 12, 0, 0, tzinfo=UTC)


def _future(hours: int = 1) -> datetime:
    return _NOW + timedelta(hours=hours)


def _past(hours: int = 1) -> datetime:
    return _NOW - timedelta(hours=hours)


def _make_event(
    *,
    event_id: str = "evt-123",
    title: str = "Team standup",
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, Any]:
    start = start or _future(1)
    end = end or _future(2)
    return {
        "id": event_id,
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "attendees": [],
        "description": "",
    }


# ---------------------------------------------------------------------------
# CalendarTool metadata
# ---------------------------------------------------------------------------


class TestCalendarToolMetadata:
    """Tests for CalendarTool class attributes per §12.1."""

    def test_domain_is_external(self):
        """Calendar tool must be in external domain.

        SPEC.md §12.1 — Privacy: external.
        """
        from noa.tools.calendar import CalendarTool

        assert CalendarTool.domain == "external"

    def test_list_risk_tier_is_low(self):
        """list_events risk tier must be Low.

        SPEC.md §12.1 — Risk tier: Low (list).
        """
        from noa.tools.calendar import CalendarTool

        assert CalendarTool.risk_tiers["list_events"] == "low"

    def test_create_risk_tier_is_medium(self):
        """create_event risk tier must be Medium.

        SPEC.md §12.1 — Risk tier: Medium (create).
        """
        from noa.tools.calendar import CalendarTool

        assert CalendarTool.risk_tiers["create_event"] == "medium"

    def test_update_risk_tier_is_medium(self):
        """update_event risk tier must be Medium.

        SPEC.md §12.1 — Risk tier: Medium (update).
        """
        from noa.tools.calendar import CalendarTool

        assert CalendarTool.risk_tiers["update_event"] == "medium"


# ---------------------------------------------------------------------------
# list_events
# ---------------------------------------------------------------------------


class TestListEvents:
    """Tests for list_events() per §12.1."""

    @pytest.mark.asyncio
    async def test_list_events_returns_events(self):
        """list_events must return events within date range.

        SPEC.md §12.1 — list_events(start_date, end_date).
        """
        from noa.tools.calendar import CalendarTool

        mock_client = AsyncMock()
        mock_client.list_events.return_value = [
            _make_event(),
            _make_event(event_id="evt-456", title="Lunch"),
        ]
        tool = CalendarTool(api_client=mock_client)

        result = await tool.list_events(
            start_date=_NOW.date().isoformat(),
            end_date=_future(24).date().isoformat(),
        )

        assert len(result) == 2
        assert result[0]["title"] == "Team standup"

    @pytest.mark.asyncio
    async def test_list_events_includes_required_fields(self):
        """list_events results must include title, time, attendees.

        SPEC.md §12.1 — list of events with title, time, attendees.
        """
        from noa.tools.calendar import CalendarTool

        mock_client = AsyncMock()
        mock_client.list_events.return_value = [_make_event()]
        tool = CalendarTool(api_client=mock_client)

        result = await tool.list_events(
            start_date=_NOW.date().isoformat(),
            end_date=_future(24).date().isoformat(),
        )

        event = result[0]
        assert "title" in event
        assert "start" in event
        assert "end" in event
        assert "attendees" in event


# ---------------------------------------------------------------------------
# create_event
# ---------------------------------------------------------------------------


class TestCreateEvent:
    """Tests for create_event() per §12.1, §16.3."""

    @pytest.mark.asyncio
    async def test_create_event_returns_event_id(self):
        """create_event must return the created event ID.

        SPEC.md §12.1 — create_event returns created event ID.
        """
        from noa.tools.calendar import CalendarTool

        mock_client = AsyncMock()
        mock_client.create_event.return_value = {"id": "evt-new"}
        tool = CalendarTool(api_client=mock_client)

        result = await tool.create_event(
            title="New meeting",
            start=_future(1).isoformat(),
            end=_future(2).isoformat(),
            now=_NOW,
        )

        assert result["id"] == "evt-new"

    @pytest.mark.asyncio
    async def test_create_event_rejects_past_start(self):
        """create_event must reject events in the past.

        SPEC.md §16.3 — No events in the past.
        """
        from noa.tools.calendar import CalendarTool, CalendarValidationError

        mock_client = AsyncMock()
        tool = CalendarTool(api_client=mock_client)

        with pytest.raises(CalendarValidationError, match="past"):
            await tool.create_event(
                title="Past meeting",
                start=_past(1).isoformat(),
                end=_past(0).isoformat(),
                now=_NOW,
            )

        mock_client.create_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_event_rejects_unreasonable_duration(self):
        """create_event must reject unreasonable durations (>24h).

        SPEC.md §16.3 — No unreasonable durations.
        """
        from noa.tools.calendar import CalendarTool, CalendarValidationError

        mock_client = AsyncMock()
        tool = CalendarTool(api_client=mock_client)

        with pytest.raises(CalendarValidationError, match="duration"):
            await tool.create_event(
                title="Week-long event",
                start=_future(1).isoformat(),
                end=_future(26).isoformat(),
                now=_NOW,
            )

    @pytest.mark.asyncio
    async def test_create_event_with_optional_fields(self):
        """create_event must accept description and attendees.

        SPEC.md §12.1 — create_event(title, start, end, description?,
        attendees?).
        """
        from noa.tools.calendar import CalendarTool

        mock_client = AsyncMock()
        mock_client.create_event.return_value = {"id": "evt-new"}
        tool = CalendarTool(api_client=mock_client)

        await tool.create_event(
            title="Meeting",
            start=_future(1).isoformat(),
            end=_future(2).isoformat(),
            description="Discuss roadmap",
            attendees=["alice@example.com"],
            now=_NOW,
        )

        call_kwargs = mock_client.create_event.call_args[1]
        assert call_kwargs["description"] == "Discuss roadmap"
        assert "alice@example.com" in call_kwargs["attendees"]

    @pytest.mark.asyncio
    async def test_create_event_rejects_end_before_start(self):
        """create_event must reject end time before start time.

        SPEC.md §16.3 — Calendar events are validated.
        """
        from noa.tools.calendar import CalendarTool, CalendarValidationError

        mock_client = AsyncMock()
        tool = CalendarTool(api_client=mock_client)

        with pytest.raises(CalendarValidationError):
            await tool.create_event(
                title="Invalid",
                start=_future(2).isoformat(),
                end=_future(1).isoformat(),
                now=_NOW,
            )


# ---------------------------------------------------------------------------
# update_event
# ---------------------------------------------------------------------------


class TestUpdateEvent:
    """Tests for update_event() per §12.1."""

    @pytest.mark.asyncio
    async def test_update_event_modifies_fields(self):
        """update_event must modify event fields.

        SPEC.md §12.1 — update_event(event_id, changes).
        """
        from noa.tools.calendar import CalendarTool

        mock_client = AsyncMock()
        mock_client.update_event.return_value = {
            "id": "evt-123",
            "title": "Updated standup",
        }
        tool = CalendarTool(api_client=mock_client)

        result = await tool.update_event(
            event_id="evt-123",
            changes={"title": "Updated standup"},
        )

        assert result["title"] == "Updated standup"
        mock_client.update_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_event_validates_new_times(self):
        """update_event must validate new start/end times if provided.

        SPEC.md §16.3 — Calendar events are validated.
        """
        from noa.tools.calendar import CalendarTool, CalendarValidationError

        mock_client = AsyncMock()
        tool = CalendarTool(api_client=mock_client)

        with pytest.raises(CalendarValidationError, match="duration"):
            await tool.update_event(
                event_id="evt-123",
                changes={
                    "start": _future(1).isoformat(),
                    "end": _future(26).isoformat(),
                },
                now=_NOW,
            )


# ---------------------------------------------------------------------------
# OAuth2
# ---------------------------------------------------------------------------


class TestOAuth2:
    """Tests for Google OAuth2 integration per §12.1."""

    def test_required_scopes(self):
        """OAuth2 must request calendar.readonly and calendar.events.

        SPEC.md §12.1 — Scopes: calendar.readonly, calendar.events.
        """
        from noa.tools.google_auth import CALENDAR_SCOPES

        assert "https://www.googleapis.com/auth/calendar.readonly" in CALENDAR_SCOPES
        assert "https://www.googleapis.com/auth/calendar.events" in CALENDAR_SCOPES

    def test_google_auth_client_stores_credentials(self):
        """GoogleAuthClient must store and refresh credentials.

        SPEC.md §12.1 — Google OAuth2 integration.
        """
        from noa.tools.google_auth import GoogleAuthClient

        client = GoogleAuthClient(
            client_id="test-id",
            client_secret="test-secret",  # noqa: S106
            redirect_uri="http://localhost/callback",
        )

        assert client.client_id == "test-id"

    def test_auth_url_generation(self):
        """GoogleAuthClient must generate an authorization URL.

        SPEC.md §12.1 — Google OAuth2 flow.
        """
        from noa.tools.google_auth import GoogleAuthClient

        client = GoogleAuthClient(
            client_id="test-id",
            client_secret="test-secret",  # noqa: S106
            redirect_uri="http://localhost/callback",
        )

        url = client.get_auth_url(scopes=["calendar.readonly"])
        assert "test-id" in url
        assert "calendar.readonly" in url


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling per §12.1."""

    @pytest.mark.asyncio
    async def test_api_failure_handled_gracefully(self):
        """API failures must be handled gracefully.

        SPEC.md §12.1 — Error handling: API failures handled gracefully.
        """
        from noa.tools.calendar import CalendarAPIError, CalendarTool

        mock_client = AsyncMock()
        mock_client.list_events.side_effect = CalendarAPIError(
            "Google API returned 500"
        )
        tool = CalendarTool(api_client=mock_client)

        with pytest.raises(CalendarAPIError, match="500"):
            await tool.list_events(
                start_date="2026-03-05",
                end_date="2026-03-06",
            )

"""Google Calendar tool — list, create, update events.

Spec refs: SPEC.md §12.1, §16.3

Requires Google OAuth2 authentication with calendar.readonly and
calendar.events scopes. All calendar operations go through the
external domain.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

# Maximum event duration (24 hours) per §16.3
MAX_EVENT_DURATION_HOURS = 24


class CalendarValidationError(Exception):
    """Raised when calendar event validation fails per §16.3."""


class CalendarAPIError(Exception):
    """Raised when the Google Calendar API returns an error."""


class CalendarTool:
    """Google Calendar tool per SPEC.md §12.1.

    Attributes:
        domain: "external" — requires Google API access.
        risk_tiers: Per-action risk tiers.
    """

    name: str = "calendar"
    domain: str = "external"
    risk_tiers: dict[str, str] = {
        "list_events": "low",
        "create_event": "medium",
        "update_event": "medium",
    }

    def __init__(self, *, api_client: Any) -> None:
        """Initialize with a Google Calendar API client.

        Args:
            api_client: Async client for Google Calendar API calls.
        """
        self._client = api_client

    async def execute(
        self, *, function: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatch to the appropriate method by function name."""
        method = getattr(self, function, None)
        if method is None:
            raise ValueError(f"Unknown function: {function}")
        return await method(**args)

    async def list_events(
        self,
        *,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """List events within a date range.

        Args:
            start_date: Start date (ISO format).
            end_date: End date (ISO format).

        Returns:
            List of event dicts with title, start, end, attendees.
        """
        return await self._client.list_events(
            start_date=start_date,
            end_date=end_date,
        )

    async def create_event(
        self,
        *,
        title: str,
        start: str,
        end: str,
        description: str | None = None,
        attendees: list[str] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Create a calendar event.

        Args:
            title: Event title.
            start: Start time (ISO format).
            end: End time (ISO format).
            description: Optional event description.
            attendees: Optional list of attendee emails.
            now: Current time (injectable for testing).

        Returns:
            Dict with created event ID.

        Raises:
            CalendarValidationError: If validation fails per §16.3.
        """
        _validate_event_times(start, end, now=now)

        return await self._client.create_event(
            title=title,
            start=start,
            end=end,
            description=description or "",
            attendees=attendees or [],
        )

    async def update_event(
        self,
        *,
        event_id: str,
        changes: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Update a calendar event.

        Args:
            event_id: ID of the event to update.
            changes: Dict of fields to update.
            now: Current time (injectable for testing).

        Returns:
            Dict with updated event data.

        Raises:
            CalendarValidationError: If new times are invalid per §16.3.
        """
        # Validate new times if both start and end are being changed
        if "start" in changes and "end" in changes:
            _validate_event_times(
                changes["start"], changes["end"], now=now
            )

        return await self._client.update_event(
            event_id=event_id,
            **changes,
        )


def _validate_event_times(
    start: str,
    end: str,
    *,
    now: datetime | None = None,
) -> None:
    """Validate event start/end times per §16.3.

    Raises:
        CalendarValidationError: If validation fails.
    """
    now = now or datetime.now(UTC)
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)

    # Ensure timezone awareness
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=UTC)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=UTC)

    # No events in the past
    if start_dt < now:
        raise CalendarValidationError(
            "Cannot create events in the past"
        )

    # End must be after start
    if end_dt <= start_dt:
        raise CalendarValidationError(
            "Event end time must be after start time"
        )

    # No unreasonable durations
    duration = end_dt - start_dt
    max_duration = timedelta(hours=MAX_EVENT_DURATION_HOURS)
    if duration > max_duration:
        raise CalendarValidationError(
            f"Event duration exceeds maximum of "
            f"{MAX_EVENT_DURATION_HOURS} hours"
        )

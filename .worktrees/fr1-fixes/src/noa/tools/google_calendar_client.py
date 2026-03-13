"""Google Calendar API v3 HTTP client.

Spec refs: SPEC.md §12.1 (Calendar functions), §8.2 (external egress)

Real httpx-based async client using OAuth2 bearer tokens from
GoogleAuthClient. Auto-refreshes on 401 and retries once.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from httpx import HTTPStatusError

from noa.tools.calendar import CalendarAPIError

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarClient:
    """Async client for Google Calendar API v3.

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
                raise CalendarAPIError(
                    f"Calendar API error: {exc.response.status_code}"
                ) from exc
            result: dict[str, Any] = resp.json()
            return result

    async def list_events(
        self, *, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """List events in primary calendar within a date range."""
        url = f"{_BASE_URL}/calendars/primary/events"
        params = {
            "timeMin": start_date,
            "timeMax": end_date,
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        data = await self._request_with_retry("get", url, params=params)
        items: list[dict[str, Any]] = data.get("items", [])
        return items

    async def create_event(
        self,
        *,
        title: str,
        start: str,
        end: str,
        description: str = "",
        attendees: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new event on the primary calendar."""
        url = f"{_BASE_URL}/calendars/primary/events"
        body: dict[str, Any] = {
            "summary": title,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }
        if description:
            body["description"] = description
        if attendees:
            body["attendees"] = [{"email": e} for e in attendees]

        return await self._request_with_retry("post", url, json=body)

    async def update_event(
        self,
        *,
        event_id: str,
        **changes: Any,
    ) -> dict[str, Any]:
        """Update an existing event."""
        url = f"{_BASE_URL}/calendars/primary/events/{event_id}"
        body: dict[str, Any] = {}
        if "title" in changes:
            body["summary"] = changes["title"]
        if "start" in changes:
            body["start"] = {"dateTime": changes["start"]}
        if "end" in changes:
            body["end"] = {"dateTime": changes["end"]}
        if "description" in changes:
            body["description"] = changes["description"]

        return await self._request_with_retry("patch", url, json=body)

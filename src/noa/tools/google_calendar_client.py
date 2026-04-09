"""Google Calendar API v3 HTTP client.

Spec refs: SPEC.md §12.1 (Calendar functions), §8.2 (external egress)

Real httpx-based async client using OAuth2 bearer tokens from
GoogleAuthClient. Auto-refreshes on 401 and retries once.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Any

import httpx
from httpx import HTTPStatusError

from noa.tools.calendar import CalendarAPIError
from noa.tools.google_auth import GoogleAuthError, load_tokens_from_db

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.googleapis.com/calendar/v3"

# BE-AP3: Friendly reconnect error returned when token refresh fails with
# GoogleAuthError (e.g. invalid_grant).
_GOOGLE_RECONNECT_ERROR: dict[str, str] = {
    "error": (
        "Google account needs to be reconnected. "
        "Please go to Settings → Google and reconnect your account."
    )
}

# Regex: has timezone offset (+HH:MM / -HH:MM) or trailing Z
_TZ_AWARE_RE = re.compile(r"(?:Z|[+-]\d{2}:\d{2})$")


def _make_datetime_entry(dt_str: str) -> dict[str, str]:
    """Build a Google Calendar datetime entry.

    If the datetime string is naive (no offset/Z suffix), attach the
    system's local UTC offset so the event lands at the intended local
    time rather than being misinterpreted as UTC.
    """
    if not _TZ_AWARE_RE.search(dt_str):
        # Treat naive string as local time, attach the system offset.
        # datetime.fromisoformat + astimezone() preserves wall-clock
        # time and appends the local UTC offset (e.g. +01:00).
        aware = datetime.fromisoformat(dt_str).astimezone()
        return {"dateTime": aware.isoformat()}
    return {"dateTime": dt_str}


class GoogleCalendarClient:
    """Async client for Google Calendar API v3.

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
                "GoogleCalendarClient._ensure_fresh_token: DB reload failed — skipping"
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
                        "GoogleCalendarClient: token refresh failed"
                        " — returning reconnect error"
                    )
                    return dict(_GOOGLE_RECONNECT_ERROR)
                resp = await getattr(client, method)(
                    url, headers=self._headers(), **kwargs,
                )
            try:
                resp.raise_for_status()
            except HTTPStatusError as exc:
                detail = exc.response.text[:300] if exc.response.text else ""
                raise CalendarAPIError(
                    f"Calendar API error {exc.response.status_code}: {detail}"
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
            "start": _make_datetime_entry(start),
            "end": _make_datetime_entry(end),
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
            body["start"] = _make_datetime_entry(changes["start"])
        if "end" in changes:
            body["end"] = _make_datetime_entry(changes["end"])
        if "description" in changes:
            body["description"] = changes["description"]

        return await self._request_with_retry("patch", url, json=body)

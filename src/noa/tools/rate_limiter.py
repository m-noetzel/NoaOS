"""Per-tool rate limiting per SPEC.md §19.3.

Rate limits (per hour):
- send_email: 10
- create_event: 20
- create_page: 20
- web_search: 30
"""

from __future__ import annotations

import time

# Default rate limits per §19.3 (calls per hour)
_DEFAULT_LIMITS: dict[str, int] = {
    "send_email": 10,
    "create_event": 20,
    "create_page": 20,
    "web_search": 30,
}

_WINDOW_SECONDS = 3600  # 1 hour


class RateLimiter:
    """Sliding-window rate limiter per tool action.

    Actions not in the limits dict are unlimited.
    """

    def __init__(
        self,
        limits: dict[str, int] | None = None,
        window_seconds: float = _WINDOW_SECONDS,
    ) -> None:
        self._limits = limits if limits is not None else _DEFAULT_LIMITS
        self._window = window_seconds
        self._windows: dict[str, dict[str, float | int]] = {}

    def check(self, action: str) -> bool:
        """Check if an action is allowed under its rate limit.

        Returns True if allowed (and increments counter), False if blocked.
        Unlimited actions always return True.
        """
        limit = self._limits.get(action)
        if limit is None:
            return True

        now = time.monotonic()
        window = self._windows.get(action)

        if window is None or now - window["start"] > self._window:
            # Start a new window
            self._windows[action] = {"start": now, "count": 1}
            return True

        if window["count"] >= limit:
            return False

        window["count"] = int(window["count"]) + 1
        return True

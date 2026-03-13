"""Per-tool rate limiting per SPEC.md §19.3.

Rate limits (per hour):
- send_email: 10
- create_event: 20
- create_page: 20
- web_search: 30
"""

from __future__ import annotations

import time
from collections import deque

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

    Tracks individual call timestamps and evicts those outside the window,
    giving smooth rate limiting without fixed-window boundary bursts.

    Actions not in the limits dict are unlimited.
    """

    def __init__(
        self,
        limits: dict[str, int] | None = None,
        window_seconds: float = _WINDOW_SECONDS,
    ) -> None:
        self._limits = limits if limits is not None else _DEFAULT_LIMITS
        self._window = window_seconds
        self._timestamps: dict[str, deque[float]] = {}

    def check(self, action: str, *, user_id: str | None = None) -> bool:
        """Check if an action is allowed under its rate limit.

        Returns True if allowed (and records the call), False if blocked.
        Unlimited actions always return True.

        Rate limits are keyed by ``(user_id, action)`` so that one user
        hitting a limit does not block other users.  Phase QC8 / H8.

        Args:
            action: The action name to rate-limit.
            user_id: Optional user identifier for per-user isolation.
                     If None, a shared/global bucket is used.
        """
        limit = self._limits.get(action)
        if limit is None:
            return True

        # Per-user isolation: key by (user_id, action)
        bucket_key = f"{user_id or '__global__'}:{action}"

        now = time.monotonic()
        ts = self._timestamps.get(bucket_key)

        if ts is None:
            ts = deque()
            self._timestamps[bucket_key] = ts

        # Evict timestamps outside the sliding window
        cutoff = now - self._window
        while ts and ts[0] <= cutoff:
            ts.popleft()

        if len(ts) >= limit:
            return False

        ts.append(now)
        return True

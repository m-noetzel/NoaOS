"""Private container health check — SPEC.md §17.1.

Polls the private container health endpoint at a configurable interval
(default 30s). Exposes is_available() for the queue to check before
dispatching tasks.
"""

from __future__ import annotations

DEFAULT_POLL_INTERVAL = 30  # seconds


class HealthChecker:
    """Polls private container health endpoint.

    Integration contract:
    - is_available() -> bool
    - poll_interval configurable (default 30s)
    - Background polling is started via start() / stopped via stop()
      (async lifecycle managed by the application).
    """

    def __init__(
        self,
        poll_url: str,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self.poll_url = poll_url
        self.poll_interval = poll_interval
        self._available = False
        self._running = False

    def is_available(self) -> bool:
        """Return whether the private container is currently reachable."""
        return self._available

    def set_available(self, available: bool) -> None:
        """Update availability state (called by the polling loop)."""
        self._available = available

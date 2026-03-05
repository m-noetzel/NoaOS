"""Private container health check — SPEC.md §17.1.

Polls the private container health endpoint at a configurable interval
(default 30s). Exposes is_available() for the queue to check before
dispatching tasks.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from typing import Any

import httpx

DEFAULT_POLL_INTERVAL = 30  # seconds


class HealthChecker:
    """Polls private container health endpoint.

    Integration contract:
    - is_available() -> bool
    - poll_interval configurable (default 30s)
    - Background polling via start() / stop() (async lifecycle)
    """

    def __init__(
        self,
        poll_url: str,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        http_client: Any | None = None,
        on_change: Callable[[bool], None] | None = None,
    ) -> None:
        self.poll_url = poll_url
        self.poll_interval = poll_interval
        self._available = False
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._http_client = http_client
        self._on_change = on_change

    def is_available(self) -> bool:
        """Return whether the private container is currently reachable."""
        return self._available

    def set_available(self, available: bool) -> None:
        """Update availability state (called by the polling loop)."""
        old = self._available
        self._available = available
        if self._on_change and old != available:
            self._on_change(available)

    async def _poll_once(self) -> bool:
        """Perform a single health check. Returns True if healthy."""
        try:
            client = self._http_client or httpx.AsyncClient()
            try:
                resp = await client.get(self.poll_url, timeout=5.0)
                return resp.status_code == 200  # noqa: PLR2004
            finally:
                if not self._http_client:
                    await client.aclose()
        except (httpx.HTTPError, OSError):
            return False

    async def _loop(self) -> None:
        """Background polling loop."""
        while self._running:
            healthy = await self._poll_once()
            self.set_available(healthy)
            await asyncio.sleep(self.poll_interval)

    async def start(self) -> None:
        """Start background health polling."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Stop background health polling."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

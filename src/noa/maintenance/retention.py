"""Retention maintenance scheduler — SPEC.md §28.7.

Runs periodic purge of expired audit log entries via a background
asyncio task.  Designed to be started/stopped from the app lifespan.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


class RetentionScheduler:
    """Periodically purges audit entries older than the retention window.

    Parameters
    ----------
    audit_service:
        An object with a ``purge_expired_async(retention_days=...)`` coroutine.
    retention_days:
        Number of days to retain audit entries (default 90, per §28.7).
    interval_hours:
        Hours between purge runs (default 24).
    approval_service:
        Optional service with ``expire_stale()`` for cleaning up stale
        pending approvals (M6).
    """

    def __init__(
        self,
        audit_service: Any,
        retention_days: int = 90,
        interval_hours: int = 24,
        *,
        approval_service: Any = None,
    ) -> None:
        self._audit_service = audit_service
        self._retention_days = retention_days
        self._interval_hours = interval_hours
        self._approval_service = approval_service
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the background purge loop."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "RetentionScheduler started: retention=%dd interval=%dh",
            self._retention_days,
            self._interval_hours,
        )

    async def stop(self) -> None:
        """Cancel the background purge loop."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
            logger.info("RetentionScheduler stopped")

    async def _run_once(self) -> None:
        """Execute a single purge cycle (audit + approval expiry)."""
        try:
            await self._purge_audit()
        except Exception:  # noqa: BLE001
            logger.exception("Retention purge failed")

        if self._approval_service is not None:
            try:
                self._approval_service.expire_stale()
                logger.info("Approval expiry complete")
            except Exception:  # noqa: BLE001
                logger.exception("Approval expiry failed")

    async def _purge_audit(self) -> None:
        """Run the appropriate purge method on audit_service."""
        purge_async = getattr(self._audit_service, "purge_expired_async", None)
        if purge_async is not None and asyncio.iscoroutinefunction(purge_async):
            count = await purge_async(retention_days=self._retention_days)
        else:
            count = self._audit_service.purge_expired(
                retention_days=self._retention_days,
            )
        logger.info("Retention purge complete: %d entries removed", count)

    async def run_once(self) -> None:
        """Execute a single purge cycle (backward-compatible public API)."""
        try:
            await self._purge_audit()
        except Exception:  # noqa: BLE001
            logger.exception("Retention purge failed")

        if self._approval_service is not None:
            try:
                self._approval_service.expire_stale()
                logger.info("Approval expiry complete")
            except Exception:  # noqa: BLE001
                logger.exception("Approval expiry failed")

    async def _loop(self) -> None:
        """Internal loop — run purge, sleep, repeat."""
        sleep_seconds = max(self._interval_hours * 3600, 0.01)
        while True:
            await self._run_once()
            await asyncio.sleep(sleep_seconds)

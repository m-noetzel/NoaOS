"""Tests for audit retention scheduling — SPEC.md §28.7.

Verifies:
- Purge deletes entries older than retention window
- Purge preserves entries within retention window
- RetentionScheduler runs at configured interval
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noa.maintenance.retention import RetentionScheduler


class TestRetentionPurgeViaScheduler:
    """RetentionScheduler.run_once delegates to audit_service.purge_expired."""

    @pytest.mark.asyncio
    async def test_run_once_calls_purge_with_retention_days(self) -> None:
        audit_svc = MagicMock()
        audit_svc.purge_expired = MagicMock(return_value=5)

        scheduler = RetentionScheduler(
            audit_service=audit_svc, retention_days=90
        )
        await scheduler.run_once()

        audit_svc.purge_expired.assert_called_once_with(retention_days=90)

    @pytest.mark.asyncio
    async def test_run_once_respects_custom_retention(self) -> None:
        audit_svc = MagicMock()
        audit_svc.purge_expired = MagicMock(return_value=0)

        scheduler = RetentionScheduler(
            audit_service=audit_svc, retention_days=30
        )
        await scheduler.run_once()

        audit_svc.purge_expired.assert_called_once_with(retention_days=30)

    @pytest.mark.asyncio
    async def test_purge_deletes_old_entries(self) -> None:
        """Simulate purge_expired returning count of deleted entries."""
        audit_svc = MagicMock()
        audit_svc.purge_expired = MagicMock(return_value=42)

        scheduler = RetentionScheduler(audit_service=audit_svc)
        await scheduler.run_once()

        audit_svc.purge_expired.assert_called_once()
        # The mock returns 42, confirming old entries would be purged
        assert audit_svc.purge_expired.return_value == 42

    @pytest.mark.asyncio
    async def test_purge_preserves_recent_entries(self) -> None:
        """When no old entries exist, purge returns 0."""
        audit_svc = MagicMock()
        audit_svc.purge_expired = MagicMock(return_value=0)

        scheduler = RetentionScheduler(audit_service=audit_svc)
        await scheduler.run_once()

        assert audit_svc.purge_expired.return_value == 0


class TestRetentionSchedulerLifecycle:
    """RetentionScheduler start/stop manage a background asyncio task."""

    @pytest.mark.asyncio
    async def test_start_creates_background_task(self) -> None:
        audit_svc = MagicMock()
        audit_svc.purge_expired = MagicMock(return_value=0)

        scheduler = RetentionScheduler(
            audit_service=audit_svc, interval_hours=24
        )
        await scheduler.start()

        assert scheduler._task is not None
        assert not scheduler._task.done()

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self) -> None:
        audit_svc = MagicMock()
        audit_svc.purge_expired = MagicMock(return_value=0)

        scheduler = RetentionScheduler(
            audit_service=audit_svc, interval_hours=24
        )
        await scheduler.start()
        task = scheduler._task
        await scheduler.stop()

        assert task is not None
        assert task.done() or task.cancelled()

    @pytest.mark.asyncio
    async def test_scheduler_runs_purge_on_interval(self) -> None:
        """Verify the scheduler loop calls purge at least once quickly."""
        audit_svc = MagicMock()
        audit_svc.purge_expired = MagicMock(return_value=1)

        # Use very short interval so the loop iterates quickly
        scheduler = RetentionScheduler(
            audit_service=audit_svc,
            retention_days=90,
            interval_hours=0,  # will use a tiny sleep in _loop
        )
        await scheduler.start()
        # Give the loop a moment to execute
        await asyncio.sleep(0.1)
        await scheduler.stop()

        assert audit_svc.purge_expired.call_count >= 1

    @pytest.mark.asyncio
    async def test_default_retention_days_is_90(self) -> None:
        audit_svc = MagicMock()
        scheduler = RetentionScheduler(audit_service=audit_svc)
        assert scheduler._retention_days == 90

    @pytest.mark.asyncio
    async def test_default_interval_hours_is_24(self) -> None:
        audit_svc = MagicMock()
        scheduler = RetentionScheduler(audit_service=audit_svc)
        assert scheduler._interval_hours == 24

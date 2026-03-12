"""Tests for database & data integrity fixes — Phase QC5.

Spec refs: SPEC.md §9.4 (Contract Violations), §28.7 (Data Retention),
           §23.2 (Approval expiry)
Phase plan: PHASE_DETAILS.md Phase QC5

Findings addressed:
  H2  — Performance indexes on high-query tables
  M3  — Retention scheduler purge_expired must work async
  M6  — expire_stale wired into periodic background task
  M9  — ContractViolationTracker.violation_count must filter 24h window
  M12 — Service layer standardized on async (RunService accepts AsyncSession)

These tests define the behavioral contract for database integrity fixes.
They are written BEFORE implementation and must fail initially.
"""

import asyncio
import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.qc5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _make_audit_kwargs(**overrides):
    """Keyword arguments for creating an AuditLog row."""
    defaults = {
        "user_id": _uuid(),
        "session_id": _uuid(),
        "device_id": _uuid(),
        "trace_id": _uuid(),
        "domain": "external",
        "model_provider": "anthropic",
        "model_name": "claude-3",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0,
        "privacy_classification": "none",
        "classification_confidence": 0.95,
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# H2 — Performance indexes on high-query tables
# ===========================================================================

class TestPerformanceIndexes:
    """H2: Critical query paths must have database indexes."""

    def test_audit_log_timestamp_index_exists(self):
        """SPEC.md §28.7: Audit log queries by timestamp for retention purge.

        An index on audit_log(timestamp) is required for efficient purge.
        """
        from noa.db.models.audit import AuditLog

        table = AuditLog.__table__
        index_columns = {
            frozenset(col.name for col in idx.columns)
            for idx in table.indexes
        }
        assert frozenset({"timestamp"}) in index_columns, (
            "Missing index on audit_log(timestamp)"
        )

    def test_audit_log_user_id_index_exists(self):
        """SPEC.md §28.1: Audit queries filter by user_id for per-user views."""
        from noa.db.models.audit import AuditLog

        table = AuditLog.__table__
        index_columns = {
            frozenset(col.name for col in idx.columns)
            for idx in table.indexes
        }
        assert frozenset({"user_id"}) in index_columns, (
            "Missing index on audit_log(user_id)"
        )

    def test_audit_log_trace_id_index_exists(self):
        """SPEC.md §28.2: Trace correlation requires fast trace_id lookup."""
        from noa.db.models.audit import AuditLog

        table = AuditLog.__table__
        index_columns = {
            frozenset(col.name for col in idx.columns)
            for idx in table.indexes
        }
        assert frozenset({"trace_id"}) in index_columns, (
            "Missing index on audit_log(trace_id)"
        )

    def test_messages_thread_id_index_exists(self):
        """SPEC.md §10.1: Loading a conversation fetches messages by thread_id."""
        from noa.db.models.conversation import Message

        table = Message.__table__
        index_columns = {
            frozenset(col.name for col in idx.columns)
            for idx in table.indexes
        }
        assert frozenset({"thread_id"}) in index_columns, (
            "Missing index on messages(thread_id)"
        )

    def test_run_events_run_id_index_exists(self):
        """SPEC.md §22.2: Run event stream queries by run_id."""
        from noa.db.models.run import RunEvent

        table = RunEvent.__table__
        index_columns = {
            frozenset(col.name for col in idx.columns)
            for idx in table.indexes
        }
        assert frozenset({"run_id"}) in index_columns, (
            "Missing index on run_events(run_id)"
        )

    def test_usage_stats_user_id_timestamp_index_exists(self):
        """SPEC.md §14: Cost dashboard queries usage_stats by (user_id, timestamp)."""
        from noa.db.models.usage import UsageStats

        table = UsageStats.__table__
        index_columns = {
            frozenset(col.name for col in idx.columns)
            for idx in table.indexes
        }
        assert frozenset({"user_id", "timestamp"}) in index_columns, (
            "Missing composite index on usage_stats(user_id, timestamp)"
        )

    def test_task_queue_status_queued_at_index_exists(self):
        """SPEC.md §17.2: Task dequeue scans by (status, queued_at)."""
        from noa.db.models.task_queue import TaskQueue

        table = TaskQueue.__table__
        index_columns = {
            frozenset(col.name for col in idx.columns)
            for idx in table.indexes
        }
        assert frozenset({"status", "queued_at"}) in index_columns, (
            "Missing composite index on task_queue(status, queued_at)"
        )


# ===========================================================================
# M3 — Retention scheduler must actually purge (not skip)
# ===========================================================================

class TestRetentionPurge:
    """M3: purge_expired must work asynchronously with the async engine."""

    @pytest.mark.asyncio
    async def test_audit_service_has_async_purge(self):
        """PLAN QC5/M3: AuditService must expose an async purge method.

        The current sync purge_expired cannot run inside the async event
        loop used by the retention scheduler. An async variant is required.
        """
        from noa.audit.service import AuditService

        svc = AuditService()
        assert hasattr(svc, "purge_expired_async"), (
            "AuditService must have purge_expired_async for async retention"
        )
        assert asyncio.iscoroutinefunction(svc.purge_expired_async), (
            "purge_expired_async must be a coroutine function"
        )

    @pytest.mark.asyncio
    async def test_retention_scheduler_calls_async_purge(self):
        """PLAN QC5/M3: RetentionScheduler._run_once must await async purge.

        The scheduler runs inside an asyncio task, so it needs to call the
        async purge method rather than the sync one that always skips.
        """
        from noa.maintenance.retention import RetentionScheduler

        mock_service = MagicMock()
        mock_service.purge_expired_async = AsyncMock(return_value=5)

        scheduler = RetentionScheduler(mock_service, retention_days=90)
        # _run_once should exist and be async
        assert hasattr(scheduler, "_run_once"), (
            "RetentionScheduler must have _run_once method"
        )
        await scheduler._run_once()
        mock_service.purge_expired_async.assert_called_once_with(
            retention_days=90,
        )

    @pytest.mark.asyncio
    async def test_purge_expired_async_deletes_old_entries(self):
        """SPEC.md §28.7: Audit logs older than retention window are deleted.

        Integration test: real AuditService with an in-memory DB verifying
        that old records are actually removed.
        """
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from noa.audit.service import AuditService
        from noa.db.models.audit import AuditLog
        from noa.db.models.base import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        user_id = _uuid()
        old_ts = datetime.now(UTC) - timedelta(days=100)
        recent_ts = datetime.now(UTC) - timedelta(days=10)

        with Session(engine) as session:
            old_entry = AuditLog(
                timestamp=old_ts,
                **_make_audit_kwargs(user_id=user_id),
            )
            recent_entry = AuditLog(
                timestamp=recent_ts,
                **_make_audit_kwargs(user_id=user_id),
            )
            session.add_all([old_entry, recent_entry])
            session.commit()

            svc = AuditService(session=session)
            # The async purge should remove the 100-day-old entry but keep
            # the 10-day-old one (retention=90 days).
            count = await svc.purge_expired_async(retention_days=90)
            assert count == 1, f"Expected 1 purged entry, got {count}"

            remaining = session.query(AuditLog).count()
            assert remaining == 1, "Only recent entry should remain"


# ===========================================================================
# M6 — expire_stale wired into periodic background task
# ===========================================================================

class TestApprovalExpiry:
    """M6: Stale pending approvals must be cleaned up periodically."""

    @pytest.mark.asyncio
    async def test_expire_stale_wired_into_scheduler(self):
        """PLAN QC5/M6: App startup must schedule periodic expire_stale calls.

        The approval service's expire_stale() must be invoked by a
        background task, not left unwired.
        """
        # After QC5, the app lifespan should register a periodic task for
        # approval expiry. We verify the RetentionScheduler (or a dedicated
        # scheduler) accepts an approval_service parameter.
        from noa.maintenance.retention import RetentionScheduler

        mock_audit = MagicMock()
        mock_audit.purge_expired_async = AsyncMock(return_value=0)
        mock_approval = MagicMock()
        mock_approval.expire_stale = MagicMock(return_value=[])

        # RetentionScheduler should accept approval_service kwarg
        scheduler = RetentionScheduler(
            mock_audit,
            approval_service=mock_approval,
        )
        assert scheduler._approval_service is not None, (
            "RetentionScheduler must store the approval_service"
        )

    @pytest.mark.asyncio
    async def test_scheduler_run_once_expires_stale_approvals(self):
        """PLAN QC5/M6: Each scheduler tick must call expire_stale.

        When _run_once executes, it should expire stale approvals in
        addition to purging old audit entries.
        """
        from noa.maintenance.retention import RetentionScheduler

        mock_audit = MagicMock()
        mock_audit.purge_expired_async = AsyncMock(return_value=0)
        mock_approval = MagicMock()
        mock_approval.expire_stale = MagicMock(return_value=[])

        scheduler = RetentionScheduler(
            mock_audit,
            approval_service=mock_approval,
        )
        await scheduler._run_once()
        mock_approval.expire_stale.assert_called_once()


# ===========================================================================
# M9 — ContractViolationTracker must filter by 24h window
# ===========================================================================

class TestContractViolationWindow:
    """M9: violation_count must only count violations within 24 hours."""

    def test_old_violations_excluded_from_count(self):
        """SPEC.md §9.4: 3 contract violations in 24 hours triggers alert.

        Violations older than 24 hours must not count toward the threshold.
        """
        from noa.private_worker.rpc import ContractViolationTracker

        tracker = ContractViolationTracker()

        # Record a violation and backdate it to 25 hours ago
        tracker.record_violation("size_exceeded", "payload too large")
        # Manually adjust the timestamp to simulate aging
        tracker._violations[0]["timestamp"] = (
            time.monotonic() - (25 * 60 * 60)
        )

        # This old violation should NOT count
        assert tracker.violation_count == 0, (
            "Violations older than 24h must be excluded from count"
        )

    def test_recent_violations_counted(self):
        """SPEC.md §9.4: Recent violations (within 24h) count toward threshold."""
        from noa.private_worker.rpc import ContractViolationTracker

        tracker = ContractViolationTracker()
        tracker.record_violation("size_exceeded", "too large")
        tracker.record_violation("unexpected_fields", "extra keys")

        assert tracker.violation_count == 2

    def test_mixed_old_and_new_violations(self):
        """SPEC.md §9.4: Only recent violations count; old ones are ignored.

        With 1 old + 2 recent violations, count should be 2 (below threshold).
        """
        from noa.private_worker.rpc import ContractViolationTracker

        tracker = ContractViolationTracker()

        # Old violation (25h ago)
        tracker.record_violation("size_exceeded", "old violation")
        tracker._violations[0]["timestamp"] = (
            time.monotonic() - (25 * 60 * 60)
        )

        # Two recent violations
        tracker.record_violation("size_exceeded", "recent 1")
        tracker.record_violation("unexpected_fields", "recent 2")

        assert tracker.violation_count == 2, (
            "Only recent violations should be counted"
        )
        assert not tracker.should_alert, (
            "2 recent violations should not trigger alert (threshold=3)"
        )

    def test_alert_triggers_at_3_recent_violations(self):
        """SPEC.md §9.4: 3 violations in 24h triggers alert + pause."""
        from noa.private_worker.rpc import ContractViolationTracker

        tracker = ContractViolationTracker()

        # One old violation that should be excluded
        tracker.record_violation("old", "should not count")
        tracker._violations[0]["timestamp"] = (
            time.monotonic() - (25 * 60 * 60)
        )

        # Three recent violations
        tracker.record_violation("size", "v1")
        tracker.record_violation("size", "v2")
        tracker.record_violation("size", "v3")

        assert tracker.violation_count == 3
        assert tracker.should_alert, (
            "3 recent violations must trigger alert"
        )
        assert tracker.should_pause_worker, (
            "3 recent violations must trigger worker pause"
        )


# ===========================================================================
# M12 — RunService must accept AsyncSession
# ===========================================================================

class TestRunServiceAsync:
    """M12: RunService must be standardized on async."""

    def test_run_service_accepts_async_session(self):
        """PLAN QC5/M12: RunService constructor must accept AsyncSession.

        The orchestrator runs in an async context and needs an async-compatible
        RunService.
        """
        from noa.runs.service import RunService

        mock_session = AsyncMock()
        svc = RunService(session=mock_session)
        assert svc._session is mock_session

    async def test_create_run_works_with_any_session(self):
        """PLAN QC5/M12: create_run must work with async session.

        RunService is now fully async (BE-H2). The session must be async-compatible.
        """
        from unittest.mock import AsyncMock, MagicMock

        from noa.runs.service import RunService

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        svc = RunService(session=mock_session)
        import uuid
        run = await svc.create_run(
            user_id=uuid.uuid4(), thread_id=uuid.uuid4(),
        )
        assert run is not None
        mock_session.add.assert_called_once()

    async def test_append_event_works_with_any_session(self):
        """PLAN QC5/M12: append_event must work with async session."""
        from unittest.mock import AsyncMock, MagicMock

        from noa.runs.service import RunService

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        svc = RunService(session=mock_session)
        import uuid
        event = await svc.append_event(
            run_id=uuid.uuid4(),
            event_type="message_received",
            payload={"text": "hi"},
        )
        assert event is not None
        mock_session.add.assert_called_once()

    def test_audit_service_has_async_purge_variant(self):
        """PLAN QC5/M12: AuditService must provide purge_expired_async.

        The async variant is used by RetentionScheduler in the event loop.
        The sync purge_expired is kept for backward compatibility.
        """
        from noa.audit.service import AuditService

        svc = AuditService()
        assert hasattr(svc, "purge_expired_async"), (
            "AuditService must have purge_expired_async"
        )
        assert asyncio.iscoroutinefunction(svc.purge_expired_async), (
            "purge_expired_async must be an async coroutine"
        )

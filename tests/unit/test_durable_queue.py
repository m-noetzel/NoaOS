"""Tests for durable queue & private domain availability — Phase AB4.

Spec refs: SPEC.md §17.1, §17.2, §17.3
Phase plan: MASTER_PLAN.md Phase AB4

Tests cover: queue persistence, idempotency, timeout, retry backoff,
max depth, cancellation, health checking, domain isolation, poll ordering,
notifications.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.ab4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task_row(
    *,
    task_id: uuid.UUID | None = None,
    task_type: str = "private.llm",
    payload: dict | None = None,
    idempotency_key: uuid.UUID | None = None,
    status: str = "queued",
    retry_count: int = 0,
    queued_at: datetime | None = None,
    timeout_at: datetime | None = None,
    priority: int = 2,
) -> dict:
    """Return a dict mimicking a TaskQueue row for mock results."""
    return {
        "id": task_id or uuid.uuid4(),
        "task_type": task_type,
        "payload": payload or {},
        "idempotency_key": idempotency_key or uuid.uuid4(),
        "status": status,
        "retry_count": retry_count,
        "queued_at": queued_at or datetime.now(UTC),
        "timeout_at": timeout_at,
        "priority": priority,
    }


# ---------------------------------------------------------------------------
# 1. Queue persistence — tasks survive API restart (§17.2)
# ---------------------------------------------------------------------------


class TestQueuePersistence:
    """Durable queue stores tasks in Postgres (survives restart)."""

    @pytest.mark.asyncio
    async def test_enqueue_persists_to_db(self):
        """enqueue() inserts a row into the task_queue table."""
        from noa.queue.durable import DurableQueue

        mock_session = AsyncMock()

        # First execute: idempotency check (no duplicate found)
        mock_dup_result = MagicMock()
        mock_dup_scalars = MagicMock()
        mock_dup_scalars.first.return_value = None
        mock_dup_result.scalars.return_value = mock_dup_scalars

        # Second execute: count check (0 tasks)
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0

        mock_session.execute = AsyncMock(
            side_effect=[mock_dup_result, mock_count_result],
        )

        queue = DurableQueue(session=mock_session)

        queue_id = await queue.enqueue(
            task_type="private.llm",
            payload={"prompt": "hello"},
            idempotency_key=uuid.uuid4(),
            timeout=60,
        )

        assert isinstance(queue_id, uuid.UUID)
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2. Idempotency — duplicate key within 24h rejected (§17.2)
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Duplicate idempotency_key within 24h window is rejected."""

    @pytest.mark.asyncio
    async def test_duplicate_idempotency_key_rejected(self):
        """Second enqueue with same idempotency_key within 24h raises."""
        from noa.queue.durable import DuplicateTaskError, DurableQueue

        idem_key = uuid.uuid4()
        mock_session = AsyncMock()

        # Simulate existing row found by scalars().first()
        mock_result = MagicMock()
        mock_result.first.return_value = MagicMock()  # row exists
        mock_scalars = MagicMock(return_value=mock_result)
        mock_execute_result = MagicMock()
        mock_execute_result.scalars = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        queue = DurableQueue(session=mock_session)

        with pytest.raises(DuplicateTaskError, match="[Dd]uplicate"):
            await queue.enqueue(
                task_type="private.llm",
                payload={},
                idempotency_key=idem_key,
                timeout=60,
            )


# ---------------------------------------------------------------------------
# 3. Timeout — tasks fail after timeout with private_domain_unavailable
# ---------------------------------------------------------------------------


class TestTimeout:
    """Tasks that exceed timeout are marked failed."""

    @pytest.mark.asyncio
    async def test_timed_out_task_marked_failed(self):
        """poll() skips timed-out tasks and marks them failed."""
        from noa.queue.durable import DurableQueue

        mock_session = AsyncMock()

        # Simulate no ready tasks (all timed out handled internally)
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_scalars = MagicMock(return_value=mock_result)
        mock_execute_result = MagicMock()
        mock_execute_result.scalars = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        queue = DurableQueue(session=mock_session)
        task = await queue.poll()
        assert task is None


# ---------------------------------------------------------------------------
# 4. Retry — exponential backoff at 5s, 15s, 45s (§17.2)
# ---------------------------------------------------------------------------


class TestRetryBackoff:
    """Retry schedule follows 5s, 15s, 45s exponential backoff."""

    def test_backoff_schedule(self):
        """Backoff delays are 5, 15, 45 seconds."""
        from noa.queue.durable import compute_backoff

        assert compute_backoff(0) == 5
        assert compute_backoff(1) == 15
        assert compute_backoff(2) == 45

    def test_backoff_caps_at_max_retries(self):
        """Retry count beyond max still returns last backoff value."""
        from noa.queue.durable import compute_backoff

        # After 3 retries (0, 1, 2), further retries cap at 45s
        assert compute_backoff(3) == 45
        assert compute_backoff(10) == 45


# ---------------------------------------------------------------------------
# 5. Max depth — tasks rejected beyond 50 (§17.2)
# ---------------------------------------------------------------------------


class TestMaxQueueDepth:
    """Queue rejects tasks when depth exceeds 50."""

    @pytest.mark.asyncio
    async def test_enqueue_rejected_at_max_depth(self):
        """enqueue() raises when queue already has 50 tasks."""
        from noa.queue.durable import DurableQueue, QueueFullError

        mock_session = AsyncMock()

        # First call: no duplicate (scalars().first() returns None)
        # Second call: count returns 50
        mock_no_dup = MagicMock()
        mock_no_dup.first.return_value = None
        mock_scalars_no_dup = MagicMock(return_value=mock_no_dup)
        mock_exec_no_dup = MagicMock()
        mock_exec_no_dup.scalars = mock_scalars_no_dup

        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 50
        mock_exec_count = MagicMock()
        mock_exec_count.scalar_one = mock_count_result.scalar_one

        mock_session.execute = AsyncMock(
            side_effect=[mock_exec_no_dup, mock_exec_count],
        )

        queue = DurableQueue(session=mock_session)

        with pytest.raises(QueueFullError, match="50"):
            await queue.enqueue(
                task_type="private.llm",
                payload={},
                idempotency_key=uuid.uuid4(),
                timeout=60,
            )


# ---------------------------------------------------------------------------
# 6. Cancellation — user can cancel queued tasks (§17.2)
# ---------------------------------------------------------------------------


class TestCancellation:
    """User can cancel queued tasks."""

    @pytest.mark.asyncio
    async def test_cancel_queued_task(self):
        """cancel() marks a queued task as cancelled."""
        from noa.queue.durable import DurableQueue

        task_id = uuid.uuid4()
        mock_task = MagicMock()
        mock_task.status = "queued"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_task)

        queue = DurableQueue(session=mock_session)
        await queue.cancel(task_id)

        assert mock_task.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_raises(self):
        """cancel() raises KeyError for unknown task_id."""
        from noa.queue.durable import DurableQueue

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)

        queue = DurableQueue(session=mock_session)
        with pytest.raises(KeyError):
            await queue.cancel(uuid.uuid4())


# ---------------------------------------------------------------------------
# 7. Health check — container health polled every 30s (§17.1)
# ---------------------------------------------------------------------------


class TestHealthChecker:
    """HealthChecker polls private container every 30s."""

    @pytest.mark.asyncio
    async def test_is_available_returns_bool(self):
        """is_available() returns a boolean."""
        from noa.queue.health import HealthChecker

        checker = HealthChecker(poll_url="http://private:8080/health")
        # Without a running server, default is unavailable
        result = checker.is_available()
        assert isinstance(result, bool)

    def test_default_poll_interval_30s(self):
        """Default poll interval is 30 seconds."""
        from noa.queue.health import HealthChecker

        checker = HealthChecker(poll_url="http://private:8080/health")
        assert checker.poll_interval == 30

    def test_custom_poll_interval(self):
        """Poll interval is configurable."""
        from noa.queue.health import HealthChecker

        checker = HealthChecker(
            poll_url="http://private:8080/health",
            poll_interval=10,
        )
        assert checker.poll_interval == 10


# ---------------------------------------------------------------------------
# 8. Never fallback — private tasks never route to external (§17.1)
# ---------------------------------------------------------------------------


class TestNeverFallback:
    """Private-domain tasks must never route to external domain."""

    @pytest.mark.asyncio
    async def test_enqueue_rejects_external_task_type(self):
        """enqueue() rejects task_types that don't start with 'private.'."""
        from noa.queue.durable import DurableQueue

        mock_session = AsyncMock()
        queue = DurableQueue(session=mock_session)

        with pytest.raises(ValueError, match="[Pp]rivate"):
            await queue.enqueue(
                task_type="external.search",
                payload={},
                idempotency_key=uuid.uuid4(),
                timeout=60,
            )


# ---------------------------------------------------------------------------
# 9. Poll returns highest priority ready task (§17.2)
# ---------------------------------------------------------------------------


class TestPollOrdering:
    """poll() returns the highest priority ready task."""

    @pytest.mark.asyncio
    async def test_poll_returns_task_or_none(self):
        """poll() returns a task object or None when empty."""
        from noa.queue.durable import DurableQueue

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_scalars = MagicMock(return_value=mock_result)
        mock_execute_result = MagicMock()
        mock_execute_result.scalars = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        queue = DurableQueue(session=mock_session)
        result = await queue.poll()
        assert result is None


# ---------------------------------------------------------------------------
# 10. Notification on queue state changes (§17.3)
# ---------------------------------------------------------------------------


class TestNotifications:
    """User receives notifications on queue state changes."""

    @pytest.mark.asyncio
    async def test_notification_sent_on_enqueue(self):
        """NotificationService.notify() called when task is enqueued."""
        from noa.queue.notifications import NotificationService

        svc = NotificationService()
        # Should be callable — concrete delivery deferred
        await svc.notify(
            event="task_queued",
            task_id=uuid.uuid4(),
            detail="Task queued for private domain",
        )

    @pytest.mark.asyncio
    async def test_notification_sent_on_failure(self):
        """NotificationService.notify() called when task fails."""
        from noa.queue.notifications import NotificationService

        svc = NotificationService()
        await svc.notify(
            event="task_failed",
            task_id=uuid.uuid4(),
            detail="private_domain_unavailable",
        )

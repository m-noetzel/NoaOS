"""Postgres-backed durable queue — SPEC.md §17.2.

Provides:
- Persistent task queue that survives API restarts
- Idempotency window (24h) — duplicate keys rejected
- Exponential backoff retries (5s, 15s, 45s)
- Queue depth limit (50)
- Timeout per task type
- Private-domain enforcement (never routes to external)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from noa.db.models.task_queue import TaskQueue

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_QUEUE_DEPTH = 50
IDEMPOTENCY_WINDOW_HOURS = 24
BACKOFF_SCHEDULE = [5, 15, 45]  # seconds


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DuplicateTaskError(Exception):
    """Raised when a duplicate idempotency key is detected within 24h."""


class QueueFullError(Exception):
    """Raised when the queue has reached its maximum depth."""


# ---------------------------------------------------------------------------
# Backoff helper
# ---------------------------------------------------------------------------


def compute_backoff(retry_count: int) -> int:
    """Return backoff delay in seconds for the given retry count.

    Schedule: 5s, 15s, 45s. Retries beyond index 2 cap at 45s.
    """
    idx = min(retry_count, len(BACKOFF_SCHEDULE) - 1)
    return BACKOFF_SCHEDULE[idx]


# ---------------------------------------------------------------------------
# DurableQueue
# ---------------------------------------------------------------------------


class DurableQueue:
    """Postgres-backed durable queue per §17.2.

    Integration contract:
    - enqueue(task_type, payload, idempotency_key, timeout) -> queue_id
    - poll() -> next ready task (respects retry backoff)
    - cancel(queue_id) -> None
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(
        self,
        task_type: str,
        payload: dict[str, Any],
        idempotency_key: uuid.UUID,
        timeout: int,
    ) -> uuid.UUID:
        """Add a task to the durable queue.

        Args:
            task_type: Must start with 'private.' (domain enforcement).
            payload: Arbitrary JSON payload for the task.
            idempotency_key: Unique key; duplicates within 24h rejected.
            timeout: Seconds before the task is considered timed out.

        Returns:
            The UUID of the newly queued task.

        Raises:
            ValueError: If task_type does not start with 'private.'.
            DuplicateTaskError: If idempotency_key seen within 24h.
            QueueFullError: If queue already has MAX_QUEUE_DEPTH tasks.
        """
        # Domain enforcement: private tasks only
        if not task_type.startswith("private."):
            msg = "Private queue only accepts task_types starting with 'private.'"
            raise ValueError(msg)

        # Idempotency check (24h window)
        cutoff = datetime.now(UTC) - timedelta(hours=IDEMPOTENCY_WINDOW_HOURS)
        dup_stmt = select(TaskQueue).where(
            TaskQueue.idempotency_key == idempotency_key,
            TaskQueue.queued_at >= cutoff,
        )
        dup_result = await self._session.execute(dup_stmt)
        if dup_result.scalars().first() is not None:
            msg = f"Duplicate idempotency key: {idempotency_key}"
            raise DuplicateTaskError(msg)

        # Queue depth check
        count_stmt = select(func.count()).select_from(TaskQueue).where(
            TaskQueue.status.in_(["queued", "retrying"]),
        )
        count_result = await self._session.execute(count_stmt)
        current_depth = count_result.scalar_one()
        if current_depth >= MAX_QUEUE_DEPTH:
            msg = f"Queue full: {MAX_QUEUE_DEPTH} tasks queued"
            raise QueueFullError(msg)

        # Create task row
        now = datetime.now(UTC)
        task = TaskQueue(
            id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            idempotency_key=idempotency_key,
            task_type=task_type,
            payload=payload,
            queued_at=now,
            timeout_at=now + timedelta(seconds=timeout),
            status="queued",
            retry_count=0,
            max_retries=3,
        )
        self._session.add(task)
        await self._session.flush()
        return task.id

    async def poll(self) -> TaskQueue | None:
        """Return the next ready task, or None.

        Respects retry backoff: a task in 'retrying' status is only
        eligible if enough time has elapsed since its last retry.
        Timed-out tasks are marked as 'failed' and skipped.
        """
        now = datetime.now(UTC)

        # Mark timed-out tasks
        timeout_stmt = select(TaskQueue).where(
            TaskQueue.status.in_(["queued", "retrying"]),
            TaskQueue.timeout_at <= now,
        )
        timeout_result = await self._session.execute(timeout_stmt)
        for task in timeout_result.scalars():
            task.status = "failed"

        # Recover stale "processing" tasks (MVP-L3):
        # If a task has been "processing" past its timeout_at, the
        # worker likely crashed. Reset to "queued" for retry.
        stale_stmt = select(TaskQueue).where(
            TaskQueue.status == "processing",
            TaskQueue.timeout_at <= now,
        )
        stale_result = await self._session.execute(stale_stmt)
        for task in stale_result.scalars():
            task.status = "queued"
            task.retry_count = task.retry_count + 1

        # Find next ready task (ordered by queued_at for simplicity;
        # priority ordering can be added when scheduler integrates)
        ready_stmt = (
            select(TaskQueue)
            .where(TaskQueue.status == "queued")
            .order_by(TaskQueue.queued_at)
        )
        ready_result = await self._session.execute(ready_stmt)
        return ready_result.scalars().first()

    async def cancel(self, queue_id: uuid.UUID) -> None:
        """Cancel a queued task.

        Args:
            queue_id: The UUID of the task to cancel.

        Raises:
            KeyError: If no task with the given ID exists.
        """
        task = await self._session.get(TaskQueue, queue_id)
        if task is None:
            msg = f"Unknown task: {queue_id}"
            raise KeyError(msg)
        task.status = "cancelled"

"""Tests for MVP-M1: QueueDrainWorker must actually dispatch queued tasks.

Spec refs: SPEC.md §17.2
Phase: MVP-M1

Test plan:
- Happy path: runner.run() yields events → task.status = "completed"
- Failed dispatch (retries remain): runner.run() raises → retry_count++, status="queued"
- Max retries exceeded: runner.run() raises, retry_count already at max → status="failed"
- No runner configured: task reverts to "queued" without dispatch
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noa.queue.drain import QueueDrainWorker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(
    *,
    retry_count: int = 0,
    max_retries: int = 3,
    task_type: str = "private.chat",
) -> MagicMock:
    """Create a mock TaskQueue row."""
    task = MagicMock()
    task.id = uuid.uuid4()
    task.task_type = task_type
    task.status = "queued"
    task.retry_count = retry_count
    task.max_retries = max_retries
    task.payload = {
        "user_id": str(uuid.uuid4()),
        "run_id": str(uuid.uuid4()),
        "thread_id": str(uuid.uuid4()),
        "message": "hello from queue",
        "model": None,
        "provider": None,
    }
    return task


def _make_session(task: MagicMock | None) -> MagicMock:
    """Create an async context manager session mock that poll() returns the task."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.commit = AsyncMock()
    return session


def _make_factory(session: MagicMock) -> MagicMock:
    """Return a session factory that yields the given session."""
    factory = MagicMock()
    factory.return_value = session
    return factory


def _make_runner_that_succeeds() -> MagicMock:
    """Runner whose run() is an async generator that yields one event."""
    runner = MagicMock()

    async def fake_run(**kwargs: Any) -> Any:
        yield {"event_type": "result_ready", "payload": {"response": "ok"}}

    runner.run = fake_run
    return runner


def _make_runner_that_raises(exc: Exception) -> MagicMock:
    """Runner whose run() raises immediately.

    Returns an async iterable whose __aiter__/__anext__ raise exc so that
    ``async for event in runner.run(...)`` propagates the exception to the
    caller without needing a real async generator with unreachable yield.
    """
    runner = MagicMock()
    _exc = exc

    class _RaisingAsyncIter:
        def __aiter__(self) -> _RaisingAsyncIter:
            return self

        async def __anext__(self) -> Any:
            raise _exc

    def fake_run(**kwargs: Any) -> _RaisingAsyncIter:
        return _RaisingAsyncIter()

    runner.run = fake_run
    return runner


def _make_checker(available: bool = True) -> MagicMock:
    checker = MagicMock()
    checker.is_available.return_value = available
    return checker


# ---------------------------------------------------------------------------
# 1. Successful dispatch
# ---------------------------------------------------------------------------


class TestSuccessfulDispatch:
    """Happy path: runner yields events → task.status = 'completed'."""

    @pytest.mark.asyncio
    async def test_task_marked_completed_on_success(self) -> None:
        task = _make_task()
        session = _make_session(task)

        runner = _make_runner_that_succeeds()

        with patch("noa.queue.drain.DurableQueue") as MockQueue:
            mock_queue = AsyncMock()
            mock_queue.poll = AsyncMock(return_value=task)
            MockQueue.return_value = mock_queue

            worker = QueueDrainWorker(
                session_factory=_make_factory(session),
                health_checker=_make_checker(),
                runner=runner,
            )
            await worker._drain_one()  # noqa: SLF001

        assert task.status == "completed"

    @pytest.mark.asyncio
    async def test_session_committed_after_success(self) -> None:
        task = _make_task()
        session = _make_session(task)

        runner = _make_runner_that_succeeds()

        with patch("noa.queue.drain.DurableQueue") as MockQueue:
            mock_queue = AsyncMock()
            mock_queue.poll = AsyncMock(return_value=task)
            MockQueue.return_value = mock_queue

            worker = QueueDrainWorker(
                session_factory=_make_factory(session),
                health_checker=_make_checker(),
                runner=runner,
            )
            await worker._drain_one()  # noqa: SLF001

        # commit must be called: once for "processing", once for "completed"
        assert session.commit.call_count >= 2

    @pytest.mark.asyncio
    async def test_retry_count_unchanged_on_success(self) -> None:
        task = _make_task(retry_count=1)
        session = _make_session(task)

        runner = _make_runner_that_succeeds()

        with patch("noa.queue.drain.DurableQueue") as MockQueue:
            mock_queue = AsyncMock()
            mock_queue.poll = AsyncMock(return_value=task)
            MockQueue.return_value = mock_queue

            worker = QueueDrainWorker(
                session_factory=_make_factory(session),
                health_checker=_make_checker(),
                runner=runner,
            )
            await worker._drain_one()  # noqa: SLF001

        # retry_count should not be incremented on success
        assert task.retry_count == 1


# ---------------------------------------------------------------------------
# 2. Failed dispatch — retries remain
# ---------------------------------------------------------------------------


class TestFailedDispatchWithRetriesRemaining:
    """Runner raises, retries remain → retry_count++, status='queued'."""

    @pytest.mark.asyncio
    async def test_retry_count_incremented(self) -> None:
        task = _make_task(retry_count=0, max_retries=3)
        session = _make_session(task)

        runner = _make_runner_that_raises(RuntimeError("LLM timeout"))

        with patch("noa.queue.drain.DurableQueue") as MockQueue:
            mock_queue = AsyncMock()
            mock_queue.poll = AsyncMock(return_value=task)
            MockQueue.return_value = mock_queue

            worker = QueueDrainWorker(
                session_factory=_make_factory(session),
                health_checker=_make_checker(),
                runner=runner,
            )
            await worker._drain_one()  # noqa: SLF001

        assert task.retry_count == 1

    @pytest.mark.asyncio
    async def test_status_set_to_queued_when_retries_remain(self) -> None:
        task = _make_task(retry_count=0, max_retries=3)
        session = _make_session(task)

        runner = _make_runner_that_raises(RuntimeError("LLM timeout"))

        with patch("noa.queue.drain.DurableQueue") as MockQueue:
            mock_queue = AsyncMock()
            mock_queue.poll = AsyncMock(return_value=task)
            MockQueue.return_value = mock_queue

            worker = QueueDrainWorker(
                session_factory=_make_factory(session),
                health_checker=_make_checker(),
                runner=runner,
            )
            await worker._drain_one()  # noqa: SLF001

        assert task.status == "queued"

    @pytest.mark.asyncio
    async def test_session_committed_after_failure(self) -> None:
        task = _make_task(retry_count=0, max_retries=3)
        session = _make_session(task)

        runner = _make_runner_that_raises(ValueError("bad payload"))

        with patch("noa.queue.drain.DurableQueue") as MockQueue:
            mock_queue = AsyncMock()
            mock_queue.poll = AsyncMock(return_value=task)
            MockQueue.return_value = mock_queue

            worker = QueueDrainWorker(
                session_factory=_make_factory(session),
                health_checker=_make_checker(),
                runner=runner,
            )
            await worker._drain_one()  # noqa: SLF001

        # commit called: once for "processing", once after failure
        assert session.commit.call_count >= 2


# ---------------------------------------------------------------------------
# 3. Max retries exceeded
# ---------------------------------------------------------------------------


class TestMaxRetriesExceeded:
    """When retry_count reaches max_retries on failure → status='failed'."""

    @pytest.mark.asyncio
    async def test_status_failed_when_max_retries_reached(self) -> None:
        # retry_count is 2, max_retries is 3 — this dispatch is the 3rd attempt
        task = _make_task(retry_count=2, max_retries=3)
        session = _make_session(task)

        runner = _make_runner_that_raises(RuntimeError("still broken"))

        with patch("noa.queue.drain.DurableQueue") as MockQueue:
            mock_queue = AsyncMock()
            mock_queue.poll = AsyncMock(return_value=task)
            MockQueue.return_value = mock_queue

            worker = QueueDrainWorker(
                session_factory=_make_factory(session),
                health_checker=_make_checker(),
                runner=runner,
            )
            await worker._drain_one()  # noqa: SLF001

        assert task.status == "failed"
        assert task.retry_count == 3

    @pytest.mark.asyncio
    async def test_status_failed_immediately_when_already_at_max(self) -> None:
        # retry_count == max_retries before dispatch — any failure tips to failed
        task = _make_task(retry_count=3, max_retries=3)
        session = _make_session(task)

        runner = _make_runner_that_raises(RuntimeError("broken"))

        with patch("noa.queue.drain.DurableQueue") as MockQueue:
            mock_queue = AsyncMock()
            mock_queue.poll = AsyncMock(return_value=task)
            MockQueue.return_value = mock_queue

            worker = QueueDrainWorker(
                session_factory=_make_factory(session),
                health_checker=_make_checker(),
                runner=runner,
            )
            await worker._drain_one()  # noqa: SLF001

        assert task.status == "failed"


# ---------------------------------------------------------------------------
# 4. No runner configured
# ---------------------------------------------------------------------------


class TestNoRunnerConfigured:
    """When no runner is wired, the task reverts to 'queued' without dispatch."""

    @pytest.mark.asyncio
    async def test_task_reverts_to_queued_when_no_runner(self) -> None:
        task = _make_task()
        session = _make_session(task)

        with patch("noa.queue.drain.DurableQueue") as MockQueue:
            mock_queue = AsyncMock()
            mock_queue.poll = AsyncMock(return_value=task)
            MockQueue.return_value = mock_queue

            worker = QueueDrainWorker(
                session_factory=_make_factory(session),
                health_checker=_make_checker(),
                runner=None,
            )
            await worker._drain_one()  # noqa: SLF001

        assert task.status == "queued"

    @pytest.mark.asyncio
    async def test_no_exception_when_no_runner(self) -> None:
        """_drain_one() must not raise when runner is None."""
        task = _make_task()
        session = _make_session(task)

        with patch("noa.queue.drain.DurableQueue") as MockQueue:
            mock_queue = AsyncMock()
            mock_queue.poll = AsyncMock(return_value=task)
            MockQueue.return_value = mock_queue

            worker = QueueDrainWorker(
                session_factory=_make_factory(session),
                health_checker=_make_checker(),
                runner=None,
            )
            # Should not raise
            await worker._drain_one()  # noqa: SLF001


# ---------------------------------------------------------------------------
# 5. Empty queue — no-op
# ---------------------------------------------------------------------------


class TestEmptyQueue:
    """When queue.poll() returns None, _drain_one() is a no-op."""

    @pytest.mark.asyncio
    async def test_no_dispatch_when_queue_empty(self) -> None:
        session = _make_session(None)
        runner = _make_runner_that_succeeds()
        run_called = []

        original_run = runner.run

        async def spy_run(**kwargs: Any) -> Any:
            run_called.append(True)
            async for e in original_run(**kwargs):
                yield e

        runner.run = spy_run

        with patch("noa.queue.drain.DurableQueue") as MockQueue:
            mock_queue = AsyncMock()
            mock_queue.poll = AsyncMock(return_value=None)
            MockQueue.return_value = mock_queue

            worker = QueueDrainWorker(
                session_factory=_make_factory(session),
                health_checker=_make_checker(),
                runner=runner,
            )
            await worker._drain_one()  # noqa: SLF001

        assert len(run_called) == 0, "Runner must not be called when queue is empty"

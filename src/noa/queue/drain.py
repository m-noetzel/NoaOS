"""Queue drain worker — dispatches queued private tasks when domain recovers.

SPEC.md §17.2: Background worker that polls the task queue and re-dispatches
tasks once the private domain is available again.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from noa.queue.durable import DurableQueue

if TYPE_CHECKING:
    from noa.orchestrator.runner import OrchestratorRunner
    from noa.queue.health import HealthChecker

logger = logging.getLogger(__name__)

_DRAIN_POLL_INTERVAL = 10  # seconds


class _NoOpRunService:
    """Minimal RunService stub for drain worker dispatch."""

    async def create_run(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def update_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def append_event(self, *args: Any, **kwargs: Any) -> None:
        pass


class QueueDrainWorker:
    """Polls the durable queue and dispatches tasks when private domain is available.

    Lifecycle: start() → background loop → stop().
    """

    def __init__(
        self,
        session_factory: Any,
        health_checker: HealthChecker,
        runner: OrchestratorRunner | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._checker = health_checker
        self._runner: OrchestratorRunner | None = runner
        self._task: asyncio.Task[None] | None = None
        self._stop = False

    async def start(self) -> None:
        """Start the background drain loop."""
        self._stop = False
        self._task = asyncio.create_task(self._loop())
        logger.info("QueueDrainWorker started")

    async def stop(self) -> None:
        """Stop the background drain loop gracefully."""
        self._stop = True
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("QueueDrainWorker stopped")

    async def _loop(self) -> None:
        """Main drain loop — poll queue every 10s when private domain is up."""
        while not self._stop:
            try:
                if self._checker.is_available():
                    await self._drain_one()
            except Exception:  # noqa: BLE001
                logger.exception("QueueDrainWorker: unexpected error in drain loop")
            await asyncio.sleep(_DRAIN_POLL_INTERVAL)

    async def _drain_one(self) -> None:
        """Poll the queue for one ready task and dispatch it via the runner."""
        try:
            async with self._session_factory() as session:
                queue = DurableQueue(session)
                task = await queue.poll()
                if task is None:
                    return

                logger.info(
                    "QueueDrainWorker: draining task %s (type=%s)",
                    task.id,
                    task.task_type,
                )

                # Mark as processing with a dispatch timeout.
                # If we crash before completing, poll() will recover
                # the task after timeout_at (MVP-L3).
                dispatch_timeout = (
                    task.payload or {}
                ).get("timeout_seconds", 120)
                task.status = "processing"
                task.timeout_at = (
                    datetime.now(UTC)
                    + timedelta(seconds=dispatch_timeout)
                )
                await session.commit()

                if self._runner is None:
                    logger.warning(
                        "QueueDrainWorker: no runner — cannot dispatch %s",
                        task.id,
                    )
                    task.status = "queued"
                    await session.commit()
                    return

                await self._dispatch_task(session, task)
        except Exception:  # noqa: BLE001
            logger.exception(
                "QueueDrainWorker: error draining task from queue"
            )

    async def _dispatch_task(self, session: Any, task: Any) -> None:
        """Invoke the runner for a task and update its status on completion.

        On success: task.status = "completed".
        On failure: increment retry_count; if retries remain, status = "queued";
                    otherwise status = "failed".
        """
        payload = task.payload or {}
        run_id = payload.get("run_id") or str(task.id)
        user_id = payload.get("user_id")
        message = payload.get("message", "")
        model = payload.get("model")
        provider = payload.get("provider")

        run_service = _NoOpRunService()
        runner = self._runner
        if runner is None:
            return

        try:
            async for _event in runner.run(
                message=message,
                run_service=run_service,
                run_id=run_id,
                privacy_mode="private",
                model=model,
                provider=provider,
                user_id=user_id,
                trace_id=str(task.id),
            ):
                pass  # consume all events; SSE not streamed for queued tasks

            task.status = "completed"
            logger.info(
                "QueueDrainWorker: task %s dispatched successfully",
                task.id,
            )
        except Exception as exc:  # noqa: BLE001
            task.retry_count = (task.retry_count or 0) + 1
            if task.retry_count >= task.max_retries:
                task.status = "failed"
                logger.error(
                    "QueueDrainWorker: task %s failed after %d retries: %s",
                    task.id,
                    task.retry_count,
                    exc,
                )
            else:
                task.status = "queued"
                logger.warning(
                    "QueueDrainWorker: task %s failed (retry %d/%d): %s",
                    task.id,
                    task.retry_count,
                    task.max_retries,
                    exc,
                )

        await session.commit()

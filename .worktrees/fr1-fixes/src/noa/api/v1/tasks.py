"""Task queue endpoints — SPEC.md §23.4.

Provides REST endpoints for task queue management:
- GET /tasks — list all tasks
- POST /tasks — enqueue a task
- GET /tasks/next — dequeue highest-priority unblocked task
- POST /tasks/{task_id}/cancel — cancel a task
- POST /tasks/{task_id}/retry — retry a cancelled/failed task
- GET /tasks/{task_id}/status — get task status
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from noa.auth.middleware import AuthUser, require_auth
from noa.scheduler.queue import Priority, TaskScheduler

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

# Module-level scheduler instance (will be replaced by DI in production)
_scheduler = TaskScheduler()


def get_scheduler() -> TaskScheduler:
    """Dependency injection for scheduler."""
    return _scheduler


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class EnqueueRequest(BaseModel):
    """Request body for task enqueue."""

    task_id: str = Field(..., min_length=1, max_length=256)
    priority: str = Field(default="normal")
    dependencies: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnqueueResponse(BaseModel):
    """Response for task enqueue."""

    task_id: str
    queue_position: int


class TaskStatusResponse(BaseModel):
    """Response for task status."""

    task_id: str
    status: str


class NextTaskResponse(BaseModel):
    """Response for next task."""

    task_id: str | None
    priority: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_tasks(
    user: AuthUser = Depends(require_auth),  # noqa: B008
    scheduler: TaskScheduler = Depends(get_scheduler),  # noqa: B008
) -> dict[str, Any]:
    """List all tasks in the queue per §23.4."""
    tasks = []
    for task_id, entry in scheduler._tasks.items():
        tasks.append({
            "task_id": task_id,
            "status": entry.status,
            "priority": entry.priority.name.lower(),
            "metadata": entry.metadata,
        })
    from noa.api.middleware import trace_id_ctx
    from noa.api.schemas.common import success_envelope

    rid = trace_id_ctx.get("")
    return success_envelope(data={"tasks": tasks}, trace_id=rid)


@router.post("", response_model=EnqueueResponse)
async def enqueue_task(
    body: EnqueueRequest,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    scheduler: TaskScheduler = Depends(get_scheduler),  # noqa: B008
) -> EnqueueResponse:
    """Enqueue a new task per §23.4."""
    try:
        priority = Priority[body.priority.upper()]
    except KeyError:
        raise HTTPException(  # noqa: B904
            status_code=400,
            detail=f"Invalid priority: {body.priority}. "
            f"Valid: critical, high, normal, background",
        )

    try:
        position = scheduler.enqueue(
            body.task_id,
            priority=priority,
            dependencies=body.dependencies,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return EnqueueResponse(task_id=body.task_id, queue_position=position)


@router.get("/next", response_model=NextTaskResponse)
async def get_next_task(
    user: AuthUser = Depends(require_auth),  # noqa: B008
    scheduler: TaskScheduler = Depends(get_scheduler),  # noqa: B008
) -> NextTaskResponse:
    """Get the next highest-priority unblocked task per §23.4."""
    task = scheduler.next()
    if task is None:
        return NextTaskResponse(task_id=None)
    return NextTaskResponse(task_id=task.task_id, priority=task.priority.name.lower())


@router.post("/{task_id}/cancel", response_model=TaskStatusResponse)
async def cancel_task(
    task_id: str,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    scheduler: TaskScheduler = Depends(get_scheduler),  # noqa: B008
) -> TaskStatusResponse:
    """Cancel a task and cascade-cancel dependents per §23.4."""
    try:
        scheduler.cancel(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")  # noqa: B904
    return TaskStatusResponse(task_id=task_id, status="cancelled")


@router.post("/{task_id}/retry", response_model=TaskStatusResponse)
async def retry_task(
    task_id: str,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    scheduler: TaskScheduler = Depends(get_scheduler),  # noqa: B008
) -> TaskStatusResponse:
    """Retry a cancelled/failed task per §23.4."""
    try:
        scheduler.retry(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")  # noqa: B904
    return TaskStatusResponse(task_id=task_id, status="queued")


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    user: AuthUser = Depends(require_auth),  # noqa: B008
    scheduler: TaskScheduler = Depends(get_scheduler),  # noqa: B008
) -> TaskStatusResponse:
    """Get task status per §23.4."""
    try:
        status = scheduler.status(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")  # noqa: B904
    return TaskStatusResponse(task_id=task_id, status=status)

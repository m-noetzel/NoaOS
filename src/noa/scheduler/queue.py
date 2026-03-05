"""Priority queue with deterministic ordering — SPEC.md §23.1.

Provides a pure in-memory task scheduler with:
- Priority-based ordering (critical > high > normal > background)
- FIFO within same priority tier
- Dependency-aware dequeuing
- Cancel/retry/complete lifecycle operations
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


class Priority(enum.IntEnum):
    """Task priority tiers per §23.1.

    Lower numeric value = higher priority (dequeued first).
    """

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    BACKGROUND = 3


@dataclass
class ScheduledTask:
    """A task entry in the scheduler queue."""

    task_id: str
    priority: Priority
    queued_at: datetime
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "queued"
    sequence: int = 0  # monotonic counter for FIFO within tier


# Maximum allowed dependency chain depth per §23.3.
MAX_CHAIN_DEPTH = 5


class TaskScheduler:
    """In-memory priority task scheduler per §23.1, §23.3.

    Tasks are ordered by (priority, sequence) where sequence is a
    monotonic counter ensuring FIFO within the same priority tier.
    LLM-generated metadata has no effect on ordering.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}
        self._counter: int = 0

    def enqueue(
        self,
        task_id: str,
        *,
        priority: Priority,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Add a task to the queue.

        Args:
            task_id: Unique task identifier.
            priority: Priority tier for ordering.
            dependencies: List of task_ids that must complete first.
            metadata: Arbitrary metadata (ignored for ordering).

        Returns:
            Queue position (0-indexed count of queued tasks ahead).

        Raises:
            ValueError: On circular dependency or chain depth > MAX_CHAIN_DEPTH.
        """
        deps = dependencies or []

        # Self-dependency check
        if task_id in deps:
            msg = f"Circular dependency: {task_id} depends on itself"
            raise ValueError(msg)

        # Circular dependency detection
        if deps:
            self._check_circular(task_id, deps)

        # Chain depth check
        if deps:
            self._check_chain_depth(deps)

        task = ScheduledTask(
            task_id=task_id,
            priority=priority,
            queued_at=datetime.now(UTC),
            dependencies=list(deps),
            metadata=metadata or {},
            sequence=self._counter,
        )
        self._counter += 1
        self._tasks[task_id] = task

        # Calculate position: count queued tasks with higher or equal priority
        # that would be dequeued before this one
        position = sum(
            1
            for t in self._tasks.values()
            if t.status == "queued"
            and t.task_id != task_id
            and (t.priority, t.sequence) < (priority, task.sequence)
        )
        return position

    def next(self) -> ScheduledTask | None:
        """Return the highest-priority unblocked task, or None.

        Ordering: priority (lower = higher), then sequence (FIFO).
        A task is blocked if any of its dependencies are not completed.
        """
        candidates = [
            t
            for t in self._tasks.values()
            if t.status == "queued" and not self._is_blocked(t)
        ]
        if not candidates:
            return None

        # Sort by (priority, sequence) — deterministic ordering
        candidates.sort(key=lambda t: (t.priority, t.sequence))
        winner = candidates[0]
        winner.status = "running"
        return winner

    def complete(self, task_id: str) -> None:
        """Mark a task as completed, unblocking dependents."""
        task = self._tasks.get(task_id)
        if task is None:
            msg = f"Unknown task: {task_id}"
            raise KeyError(msg)
        task.status = "completed"

    def cancel(self, task_id: str) -> None:
        """Cancel a task and cascade-cancel its dependents."""
        task = self._tasks.get(task_id)
        if task is None:
            msg = f"Unknown task: {task_id}"
            raise KeyError(msg)
        task.status = "cancelled"

        # Cascade: cancel all tasks that depend on this one
        self._cascade_cancel(task_id)

    def retry(self, task_id: str) -> None:
        """Re-enqueue a cancelled or failed task."""
        task = self._tasks.get(task_id)
        if task is None:
            msg = f"Unknown task: {task_id}"
            raise KeyError(msg)
        task.status = "queued"
        task.queued_at = datetime.now(UTC)
        task.sequence = self._counter
        self._counter += 1

    def status(self, task_id: str) -> str:
        """Return the status of a task."""
        task = self._tasks.get(task_id)
        if task is None:
            msg = f"Unknown task: {task_id}"
            raise KeyError(msg)
        return task.status

    # ----- internal helpers -----

    def _is_blocked(self, task: ScheduledTask) -> bool:
        """Check if a task has unresolved dependencies."""
        for dep_id in task.dependencies:
            dep = self._tasks.get(dep_id)
            if dep is None or dep.status != "completed":
                return True
        return False

    def _cascade_cancel(self, task_id: str) -> None:
        """Recursively cancel all tasks depending on task_id."""
        for t in list(self._tasks.values()):
            if task_id in t.dependencies and t.status in ("queued", "running"):
                t.status = "cancelled"
                self._cascade_cancel(t.task_id)

    def _check_circular(self, new_id: str, deps: list[str]) -> None:
        """Detect circular dependencies.

        Builds the dependency graph including the proposed new task,
        then checks for cycles using DFS. The graph maps each task to
        the set of tasks it depends on (i.e., must complete before it).
        A cycle means: new_id depends on dep, and dep (transitively)
        depends on new_id.
        """
        # Build adjacency: task_id → set of task_ids it depends on
        graph: dict[str, list[str]] = {}
        for t in self._tasks.values():
            graph[t.task_id] = list(t.dependencies)
        # Add proposed task
        graph[new_id] = list(deps)

        # DFS cycle detection from new_id
        visited: set[str] = set()
        in_stack: set[str] = set()

        def has_cycle(node: str) -> bool:
            if node in in_stack:
                return True
            if node in visited:
                return False
            visited.add(node)
            in_stack.add(node)
            for dep in graph.get(node, []):
                if has_cycle(dep):
                    return True
            in_stack.discard(node)
            return False

        if has_cycle(new_id):
            msg = f"Circular dependency detected involving {new_id}"
            raise ValueError(msg)

    def _check_chain_depth(self, deps: list[str]) -> None:
        """Ensure no dependency chain exceeds MAX_CHAIN_DEPTH."""
        for dep_id in deps:
            depth = self._get_chain_depth(dep_id)
            if depth >= MAX_CHAIN_DEPTH:
                msg = (
                    f"Dependency chain depth {depth + 1} exceeds "
                    f"maximum of {MAX_CHAIN_DEPTH}"
                )
                raise ValueError(msg)

    def _get_chain_depth(self, task_id: str) -> int:
        """Calculate the depth of a dependency chain from task_id."""
        task = self._tasks.get(task_id)
        if task is None or not task.dependencies:
            return 1
        return 1 + max(
            self._get_chain_depth(dep) for dep in task.dependencies
        )

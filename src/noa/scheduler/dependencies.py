"""Dependency resolution & validation — SPEC.md §23.3.

Provides utilities for validating dependency graphs:
- Circular dependency detection
- Chain depth enforcement
- Dependency type classification (explicit, sequential, independent)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class DependencyType(enum.Enum):
    """Dependency relationship types per §23.3."""

    EXPLICIT = "explicit"  # Declared dependency between tasks
    SEQUENTIAL = "sequential"  # Must execute after predecessor
    INDEPENDENT = "independent"  # May execute concurrently


@dataclass(frozen=True)
class DependencyEdge:
    """A directed edge in the dependency graph."""

    from_task: str  # This task...
    to_task: str  # ...depends on this task
    dep_type: DependencyType = DependencyType.EXPLICIT


def detect_cycle(
    edges: list[DependencyEdge],
    new_edge: DependencyEdge,
) -> bool:
    """Check if adding new_edge would create a cycle.

    Args:
        edges: Existing dependency edges.
        new_edge: Proposed edge to add.

    Returns:
        True if adding new_edge creates a cycle.
    """
    # Build adjacency list: task → tasks it depends on
    adj: dict[str, list[str]] = {}
    for edge in [*edges, new_edge]:
        adj.setdefault(edge.from_task, []).append(edge.to_task)

    # DFS from new_edge.to_task; if we reach new_edge.from_task, cycle
    visited: set[str] = set()

    def dfs(node: str) -> bool:
        if node == new_edge.from_task:
            return True
        if node in visited:
            return False
        visited.add(node)
        return any(dfs(dep) for dep in adj.get(node, []))

    return dfs(new_edge.to_task)


def chain_depth(
    edges: list[DependencyEdge],
    task_id: str,
) -> int:
    """Calculate the depth of the dependency chain ending at task_id.

    Args:
        edges: All dependency edges.
        task_id: Task to measure chain depth for.

    Returns:
        Chain depth (1 = no dependencies).
    """
    # Build reverse adjacency: task → tasks it depends on
    deps: dict[str, list[str]] = {}
    for edge in edges:
        deps.setdefault(edge.from_task, []).append(edge.to_task)

    def depth(tid: str, seen: set[str] | None = None) -> int:
        if seen is None:
            seen = set()
        if tid in seen:
            return 0  # cycle guard
        seen.add(tid)
        dep_list = deps.get(tid, [])
        if not dep_list:
            return 1
        return 1 + max(depth(d, seen) for d in dep_list)

    return depth(task_id)

"""Tool registry for external domain capabilities.

Spec refs: SPEC.md Section 6.2
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class ToolRegistry:
    """Registry for external-domain tool handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        """Register a tool handler under *name*."""
        self._handlers[name] = handler

    def has(self, name: str) -> bool:
        """Return ``True`` if a tool with *name* is registered."""
        return name in self._handlers

    def list_tools(self) -> list[str]:
        """Return a list of registered tool names."""
        return list(self._handlers)

    def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        """Dispatch a tool call to its handler.

        Raises:
            KeyError: If *name* is not registered.
        """
        if name not in self._handlers:
            msg = f"Tool not found: {name}"
            raise KeyError(msg)
        return self._handlers[name](args)

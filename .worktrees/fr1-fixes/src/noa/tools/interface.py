"""ToolInterface Protocol and ToolRegistry per SPEC.md §2.1, §12.

The ToolInterface is a runtime-checkable Protocol that all tools must
implement. The ToolRegistry is a static dict that the orchestrator
dispatches through.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ToolInterface(Protocol):
    """Protocol that all Noa tools must implement.

    Attributes:
        name: Tool identifier string.
        domain: "private" or "external".
        risk_tiers: Dict mapping function names to risk levels.
    """

    name: str
    domain: str
    risk_tiers: dict[str, str]

    async def execute(
        self, *, function: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a tool function.

        Args:
            function: The function name to execute.
            args: Keyword arguments for the function.

        Returns:
            Result dict.
        """
        ...


class ToolRegistry:
    """Static tool registry per §2.1.

    Tools are registered at startup from config. No runtime registration.
    """

    def __init__(self, tools: dict[str, ToolInterface]) -> None:
        self._tools = tools

    def get(self, name: str) -> ToolInterface:
        """Get a tool by name. Raises KeyError if not found."""
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    @property
    def allowlist(self) -> frozenset[str]:
        """Static allowlist of registered tool names."""
        return frozenset(self._tools.keys())

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    async def dispatch(
        self,
        *,
        name: str,
        function: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch a tool call through the registry.

        Args:
            name: Tool name.
            function: Function to call on the tool.
            args: Arguments for the function.

        Returns:
            Result dict from the tool.

        Raises:
            KeyError: If tool is not registered.
        """
        tool = self.get(name)
        return await tool.execute(function=function, args=args)

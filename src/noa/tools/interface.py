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



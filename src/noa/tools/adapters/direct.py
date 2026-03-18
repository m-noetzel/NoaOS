"""DirectApiAdapter — wraps a ToolInterface for the ToolGateway.

Converts ToolRequest → tool.execute() → ToolResponse.
Used for tools that make direct HTTP API calls (Tavily, Google, etc.).
"""

from __future__ import annotations

import time
from typing import Any

from noa.tools.gateway import ToolRequest, ToolResponse


class DirectApiAdapter:
    """Adapter that delegates to a ToolInterface implementation."""

    def __init__(self, *, tool: Any) -> None:
        self._tool = tool

    async def execute(self, request: ToolRequest) -> ToolResponse:
        t0 = time.monotonic()
        try:
            # Inject user_id into args for tools that need user-scoped storage
            args = dict(request.args)
            is_memory = (
                hasattr(self._tool, 'name')
                and self._tool.name == "memory"
            )
            if request.user_id is not None and is_memory:
                args.setdefault("user_id", str(request.user_id))
            result = await self._tool.execute(
                function=request.function,
                args=args,
            )
            latency = (time.monotonic() - t0) * 1000
            return ToolResponse(
                result=result,
                provider="direct",
                latency_ms=latency,
            )
        except Exception as exc:  # noqa: BLE001
            latency = (time.monotonic() - t0) * 1000
            return ToolResponse(
                error=str(exc),
                provider="direct",
                latency_ms=latency,
            )

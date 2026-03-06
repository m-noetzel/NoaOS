"""ToolGateway — transport-agnostic tool dispatch with governance + telemetry.

Spec refs: SPEC.md §19.1 (idempotency), §19.2 (dry-run previews),
           §19.3 (rate limits), §2.1 (static allowlist enforcement).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class ToolRequest:
    """Transport-agnostic tool invocation request."""

    tool: str
    function: str
    args: dict[str, Any]
    idempotency_key: str | None = None
    privacy_mode: str = "external"


@dataclass
class ToolResponse:
    """Standardised tool invocation response."""

    result: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: float = 0.0
    provider: str = ""
    cached: bool = False


@runtime_checkable
class ToolAdapter(Protocol):
    """Protocol that all tool adapters must implement."""

    async def execute(self, request: ToolRequest) -> ToolResponse: ...


# ---------------------------------------------------------------------------
# Internal rate-limit tracker (per tool, in-memory)
# ---------------------------------------------------------------------------

@dataclass
class _RateLimit:
    max_calls: int
    window_seconds: float
    calls: list[float] = field(default_factory=list)

    def check(self) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self.calls = [t for t in self.calls if t > cutoff]
        if len(self.calls) >= self.max_calls:
            return False
        self.calls.append(now)
        return True


# ---------------------------------------------------------------------------
# ToolGateway
# ---------------------------------------------------------------------------


class ToolGateway:
    """Central tool dispatch hub.

    Resolves tool name -> adapter, enforces governance (idempotency,
    rate limits, dry-run), records telemetry.

    When *session_factory* is provided, telemetry is persisted to the
    ``tool_call_logs`` table.  Falls back to an in-memory list otherwise.
    """

    def __init__(self, *, session_factory: Any | None = None) -> None:
        self._adapters: dict[str, ToolAdapter] = {}
        self._idempotency_cache: dict[str, ToolResponse] = {}
        self._rate_limits: dict[str, _RateLimit] = {}
        self.telemetry: list[dict[str, Any]] = []
        self._session_factory = session_factory

    # -- registration -------------------------------------------------------

    def register(self, tool_name: str, adapter: ToolAdapter) -> None:
        self._adapters[tool_name] = adapter

    @property
    def allowlist(self) -> frozenset[str]:
        return frozenset(self._adapters.keys())

    def list_tools(self) -> list[str]:
        return list(self._adapters.keys())

    # -- governance config --------------------------------------------------

    def set_rate_limit(
        self, tool_name: str, *, max_calls: int, window_seconds: float
    ) -> None:
        self._rate_limits[tool_name] = _RateLimit(
            max_calls=max_calls, window_seconds=window_seconds
        )

    # -- dispatch -----------------------------------------------------------

    async def dispatch(
        self, request: ToolRequest, *, dry_run: bool = False
    ) -> ToolResponse:
        tool = request.tool

        # 1. Allowlist check
        if tool not in self._adapters:
            resp = ToolResponse(error=f"Tool not registered: {tool}")
            await self._record_telemetry(request, resp, "error")
            return resp

        # 2. Dry-run preview (§19.2)
        if dry_run:
            preview = {
                "action": request.function,
                "tool": tool,
                "args": request.args,
                "preview": True,
            }
            resp = ToolResponse(result=preview, provider="dry_run")
            await self._record_telemetry(request, resp, "dry_run")
            return resp

        # 3. Idempotency check (§19.1)
        if request.idempotency_key:
            cached = self._idempotency_cache.get(request.idempotency_key)
            if cached is not None:
                resp = ToolResponse(
                    result=cached.result,
                    error=cached.error,
                    latency_ms=cached.latency_ms,
                    provider=cached.provider,
                    cached=True,
                )
                await self._record_telemetry(request, resp, "cached")
                return resp

        # 4. Rate limit check (§19.3)
        rl = self._rate_limits.get(tool)
        if rl and not rl.check():
            resp = ToolResponse(error=f"Rate limit exceeded for {tool}")
            await self._record_telemetry(request, resp, "rate_limited")
            return resp

        # 5. Execute via adapter
        t0 = time.monotonic()
        try:
            resp = await self._adapters[tool].execute(request)
        except Exception as exc:  # noqa: BLE001
            resp = ToolResponse(error=str(exc))
        resp.latency_ms = (time.monotonic() - t0) * 1000

        # 6. Cache if idempotency key
        if request.idempotency_key:
            self._idempotency_cache[request.idempotency_key] = resp

        status = "error" if resp.error else "ok"
        await self._record_telemetry(request, resp, status)
        return resp

    # -- telemetry ----------------------------------------------------------

    async def _record_telemetry(
        self, request: ToolRequest, response: ToolResponse, status: str
    ) -> None:
        entry = {
            "tool": request.tool,
            "function": request.function,
            "latency_ms": response.latency_ms,
            "status": status,
            "cached": response.cached,
        }
        self.telemetry.append(entry)

        # Persist to DB if session_factory is available
        if self._session_factory is not None:
            await self._persist_telemetry(entry)

    async def _persist_telemetry(self, entry: dict[str, Any]) -> None:
        """Write a telemetry entry to the database."""
        try:
            from noa.db.models.tool_call_log import ToolCallLog

            factory = self._session_factory
            if factory is None:
                return

            log = ToolCallLog(
                tool=entry["tool"],
                function=entry["function"],
                latency_ms=entry["latency_ms"],
                status=entry["status"],
                cached=entry["cached"],
            )
            async with factory() as session:
                session.add(log)
                await session.commit()
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to persist tool telemetry to DB", exc_info=True,
            )

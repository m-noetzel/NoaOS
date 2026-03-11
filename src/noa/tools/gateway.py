"""ToolGateway — transport-agnostic tool dispatch with governance + telemetry.

Spec refs: SPEC.md §19.1 (idempotency), §19.2 (dry-run previews),
           §19.3 (rate limits), §2.1 (static allowlist enforcement).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# Type alias for the audit callback:
#   async def callback(request, response, *, status: str) -> None
AuditCallback = Callable[["ToolRequest", "ToolResponse", str], Awaitable[None]]

@dataclass
class ToolRequest:
    """Transport-agnostic tool invocation request."""

    tool: str
    function: str
    args: dict[str, Any]
    idempotency_key: str | None = None
    privacy_mode: str = "external"
    user_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    trace_id: uuid.UUID | None = None
    step_up_verified: bool = False


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

    def __init__(
        self,
        *,
        audit_callback: AuditCallback | None = None,
        session_factory: Any | None = None,
    ) -> None:
        self._adapters: dict[str, ToolAdapter] = {}
        self._idempotency_cache: dict[str, ToolResponse] = {}
        self._rate_limits: dict[str, _RateLimit] = {}
        self._per_user_rate_calls: dict[str, list[float]] = {}
        self.telemetry: list[dict[str, Any]] = []
        self._audit_callback = audit_callback
        self._session_factory = session_factory
        self.capability_checker: Any | None = None
        self.policy_engine: Any | None = None

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
            await self._fire_audit(request, resp, "error")
            return resp

        # 1a. Domain isolation check (§4.1, §8.3)
        adapter = self._adapters[tool]
        adapter_domain = getattr(adapter, "domain", None)
        if adapter_domain is not None and request.privacy_mode:
            if adapter_domain == "private" and request.privacy_mode == "external":
                raise PermissionError(
                    f"Private-domain tool '{tool}' cannot be dispatched "
                    f"for external-domain request"
                )
            if adapter_domain == "external" and request.privacy_mode == "private":
                raise PermissionError(
                    f"External-domain tool '{tool}' cannot be dispatched "
                    f"for private-domain request"
                )

        # 1b. Capability check (MR5)
        if (
            self.capability_checker is not None
            and request.user_id is not None
        ):
            has_cap = await self.capability_checker.has_capability(
                request.user_id, tool,
            )
            if not has_cap:
                resp = ToolResponse(
                    error=f"Capability denied for tool: {tool}",
                )
                await self._record_telemetry(request, resp, "capability_denied")
                return resp

        # 1c. Step-up auth check (M7 / §21)
        if self.policy_engine is not None:
            risk_tier = self.policy_engine.classify(request.function, request.args)
            needs_step_up = self.policy_engine.requires_step_up_auth(risk_tier)
            if needs_step_up and not request.step_up_verified:
                resp = ToolResponse(
                    error="Step_up authentication required for high-risk action",
                )
                await self._record_telemetry(request, resp, "step_up_required")
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
            await self._fire_audit(request, resp, "dry_run")
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
                await self._fire_audit(request, resp, "cached")
                return resp

        # 4. Rate limit check (§19.3) — per-user isolation (H8)
        rl = self._rate_limits.get(tool)
        if rl:
            user_key = f"{request.user_id or '__global__'}:{tool}"
            now = time.monotonic()
            calls = self._per_user_rate_calls.get(user_key)
            if calls is None:
                calls = []
                self._per_user_rate_calls[user_key] = calls
            cutoff = now - rl.window_seconds
            calls[:] = [t for t in calls if t > cutoff]
            if len(calls) >= rl.max_calls:
                resp = ToolResponse(error=f"Rate limit exceeded for {tool}")
                await self._record_telemetry(request, resp, "rate_limited")
                await self._fire_audit(request, resp, "rate_limited")
                return resp
            calls.append(now)

        # 5. Execute via adapter
        t0 = time.monotonic()
        try:
            resp = await self._adapters[tool].execute(request)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Adapter exception for tool=%s", tool, exc_info=True)
            resp = ToolResponse(error=str(exc))
        resp.latency_ms = (time.monotonic() - t0) * 1000

        # 6. Cache if idempotency key
        if request.idempotency_key:
            self._idempotency_cache[request.idempotency_key] = resp

        status = "error" if resp.error else "ok"
        await self._record_telemetry(request, resp, status)
        await self._fire_audit(request, resp, status)
        return resp

    # -- audit callback -----------------------------------------------------

    async def _fire_audit(
        self, request: ToolRequest, response: ToolResponse, status: str
    ) -> None:
        """Invoke audit callback if configured and user context present."""
        if self._audit_callback is None or request.user_id is None:
            return
        try:
            await self._audit_callback(request, response, status)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Audit callback failed for tool=%s status=%s",
                request.tool,
                status,
                exc_info=True,
            )

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

"""GovernanceWrapper — idempotency, rate limiting, dry-run previews.

Spec refs: SPEC.md §19.1, §19.2, §19.3, §25.4
"""

from __future__ import annotations

from typing import Any

from noa.tools.idempotency import IdempotencyStore
from noa.tools.interface import ToolInterface
from noa.tools.rate_limiter import RateLimiter

# Actions that require confirmation preview per §19.2
_PREVIEW_ACTIONS = frozenset({
    "send_email",
    "create_event",
    "update_event",
    "create_page",
    "update_page",
})


class RateLimitError(Exception):
    """Raised when a tool action exceeds its rate limit per §19.3."""


def generate_preview(
    *,
    tool_name: str,
    function: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Generate a dry-run preview for a tool action per §19.2.

    Returns:
        Preview dict with action, summary, and requires_confirmation.
    """
    requires_confirmation = function in _PREVIEW_ACTIONS

    # Build a human-readable summary
    parts: list[str] = [f"{tool_name}.{function}"]
    for key, value in args.items():
        parts.append(f"  {key}: {value}")
    summary = "\n".join(parts)

    return {
        "action": function,
        "summary": summary,
        "requires_confirmation": requires_confirmation,
    }


class GovernanceWrapper:
    """Wraps a ToolInterface with idempotency, rate limiting, and previews.

    Args:
        tool: The underlying tool implementing ToolInterface.
        idempotency_store: Optional shared IdempotencyStore.
        rate_limiter: Optional shared RateLimiter.
    """

    def __init__(
        self,
        *,
        tool: ToolInterface,
        idempotency_store: IdempotencyStore | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._tool = tool
        self._idempotency = idempotency_store or IdempotencyStore()
        self._rate_limiter = rate_limiter or RateLimiter()

    @property
    def name(self) -> str:
        return self._tool.name

    @property
    def domain(self) -> str:
        return self._tool.domain

    @property
    def risk_tiers(self) -> dict[str, str]:
        return self._tool.risk_tiers

    async def execute(
        self,
        *,
        function: str,
        args: dict[str, Any],
        idempotency_key: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute with governance checks.

        1. Check idempotency key (return cached if duplicate).
        2. Check rate limit (raise RateLimitError if exceeded).
        3. Execute the underlying tool.
        4. Cache result if idempotency key provided.
        """
        # 1. Idempotency check
        if idempotency_key is not None:
            cached = self._idempotency.get(idempotency_key)
            if cached is not None:
                return cached

        # 2. Rate limit check (per-user isolation — H8)
        if not self._rate_limiter.check(function, user_id=user_id):
            raise RateLimitError(
                f"Rate limit exceeded for {function}"
            )

        # 3. Execute
        result = await self._tool.execute(function=function, args=args)

        # 4. Cache result
        if idempotency_key is not None:
            self._idempotency.set(idempotency_key, result)

        return result

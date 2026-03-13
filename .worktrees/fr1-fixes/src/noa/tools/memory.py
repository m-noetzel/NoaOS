"""Memory tool — remember/recall facts via private worker RPC.

Spec refs: SPEC.md §12.5, §13.2, §13.3, §19.1

All memory operations go through the private domain RPC contract.
Facts never leave the private domain except as truncated, redacted
RPC responses.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any, cast

from noa.constants import MAX_N_RESULTS

# Type alias for the RPC client callable.
RPCClient = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class MemoryTool:
    """Memory tool providing remember() and recall() via private worker RPC.

    Attributes:
        domain: Always "private" per §12.5.
        risk_tier: Always "low" per §12.5.
    """

    name: str = "memory"
    domain: str = "private"
    risk_tiers: dict[str, str] = {
        "remember": "low",
        "recall": "low",
        "auto_extract": "low",
    }

    def __init__(
        self,
        *,
        rpc_client: RPCClient,
        auto_extraction_enabled: bool = False,
    ) -> None:
        self._rpc = rpc_client
        self.auto_extraction_enabled = auto_extraction_enabled

    async def execute(
        self, *, function: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatch to the appropriate method by function name."""
        method = getattr(self, function, None)
        if method is None:
            raise ValueError(f"Unknown function: {function}")
        return cast(dict[str, Any], await method(**args))

    async def remember(
        self,
        *,
        fact: str,
        category: str,
        source_thread_id: str,
    ) -> dict[str, Any]:
        """Store a fact with embedding for later retrieval.

        Args:
            fact: The fact text to store.
            category: Category tag (preference, habit, etc.).
            source_thread_id: ID of the thread where fact originated.

        Returns:
            RPC response dict with status.
        """
        request = {
            "idempotency_key": str(uuid.uuid4()),
            "task_type": "remember",
            "payload": {
                "fact": fact,
                "category": category,
                "source_thread_id": source_thread_id,
                "auto_extracted": False,
            },
        }
        return await self._rpc(request)

    async def recall(
        self,
        *,
        query: str,
        n_results: int = 5,
    ) -> dict[str, Any]:
        """Semantic search over stored facts.

        Args:
            query: Search query text.
            n_results: Max number of results (capped at 20 per §9.1).

        Returns:
            RPC response dict with facts array.
        """
        # Cap at MAX_N_RESULTS per §9.1
        n_results = min(n_results, MAX_N_RESULTS)

        request = {
            "idempotency_key": str(uuid.uuid4()),
            "task_type": "recall",
            "payload": {
                "query": query,
                "n_results": n_results,
            },
        }
        response = await self._rpc(request)

        # Return the result portion with facts
        return {
            "status": response.get("status", "success"),
            "facts": response.get("result", {}).get("facts", []),
        }

    async def auto_extract(
        self,
        *,
        fact: str,
        category: str,
        source_thread_id: str,
    ) -> dict[str, Any]:
        """Auto-extract a fact (pending status, requires user approval).

        Only callable when auto_extraction_enabled is True.

        Args:
            fact: The fact text to store.
            category: Category tag.
            source_thread_id: ID of the source thread.

        Returns:
            RPC response dict.
        """
        request = {
            "idempotency_key": str(uuid.uuid4()),
            "task_type": "remember",
            "payload": {
                "fact": fact,
                "category": category,
                "source_thread_id": source_thread_id,
                "auto_extracted": True,
            },
        }
        return await self._rpc(request)

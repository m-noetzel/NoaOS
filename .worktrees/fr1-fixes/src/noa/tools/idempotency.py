"""Idempotency key store for tool deduplication per SPEC.md §19.1, §25.4.

Stores results keyed by idempotency key with TTL-based expiry.
"""

from __future__ import annotations

import time
from typing import Any

# Default TTL: 24 hours per §25.4
_DEFAULT_TTL_SECONDS = 24 * 60 * 60


class IdempotencyStore:
    """In-memory idempotency key store with TTL expiry.

    Args:
        ttl_seconds: Time-to-live for cached results (default 24h).
    """

    def __init__(self, ttl_seconds: float = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        """Get cached result for a key, or None if expired/missing."""
        entry = self._entries.get(key)
        if entry is None:
            return None

        if time.monotonic() > entry["expires_at"]:
            del self._entries[key]
            return None

        result: dict[str, Any] = entry["result"]
        return result

    def set(self, key: str, result: dict[str, Any]) -> None:
        """Cache a result for a key. Does not overwrite existing entries."""
        if key in self._entries:
            return  # Already cached, don't overwrite

        self._entries[key] = {
            "result": result,
            "expires_at": time.monotonic() + self._ttl,
        }

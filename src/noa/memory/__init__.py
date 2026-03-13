"""Shared memory layer — re-exports MemoryStore for use across domains.

Both private and external workers share the same MemoryStore implementation.
Importing from this shared package (noa.memory) avoids cross-domain imports
between noa.private_worker and noa.external_worker (ARCH L3).

Usage:
    from noa.memory import MemoryStore
"""

from __future__ import annotations

from noa.private_worker.memory_store import VALID_CATEGORIES, MemoryStore

__all__ = ["MemoryStore", "VALID_CATEGORIES"]

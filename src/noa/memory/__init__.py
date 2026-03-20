"""Shared memory layer — re-exports MemoryStore and VectorMemoryStore.

Both private and external workers share the same MemoryStore implementation.
Importing from this shared package (noa.memory) avoids cross-domain imports
between noa.private_worker and noa.external_worker (ARCH L3).

VM1: VectorMemoryStore adds pgvector-backed cosine similarity recall.

Usage:
    from noa.memory import MemoryStore, VectorMemoryStore
"""

from __future__ import annotations

from noa.memory.vector_store import VectorMemoryStore
from noa.private_worker.memory_store import VALID_CATEGORIES, MemoryStore

__all__ = ["MemoryStore", "VectorMemoryStore", "VALID_CATEGORIES"]

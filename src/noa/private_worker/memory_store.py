"""Private-side fact storage with embedding-based semantic retrieval.

Spec refs: SPEC.md §13.2, §19.1

In-memory implementation for Phase 1. Facts are stored with vector
embeddings for cosine similarity search. Persistence will be added
when the private domain gets a real database.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Any

# Valid fact categories per §13.2
VALID_CATEGORIES = frozenset({
    "preference",
    "habit",
    "project_context",
    "personal_info",
})


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        # Pad shorter vector with zeros for dimension mismatch
        max_len = max(len(a), len(b))
        a = a + [0.0] * (max_len - len(a))
        b = b + [0.0] * (max_len - len(b))

    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


class MemoryStore:
    """In-memory fact store with vector similarity search.

    Phase 1 implementation using a Python dict. Will be replaced with
    a proper vector DB (pgvector or similar) in later phases.
    """

    def __init__(self) -> None:
        self._facts: dict[str, dict[str, Any]] = {}

    def store(
        self,
        *,
        fact: str,
        category: str,
        embedding: list[float],
        source_thread_id: str,
        auto_extracted: bool = False,
    ) -> str | None:
        """Store a fact with its embedding.

        Args:
            fact: The fact text.
            category: Category tag per §13.2.
            embedding: Vector embedding for semantic search.
            source_thread_id: Thread where fact originated.
            auto_extracted: Whether fact was auto-extracted.

        Returns:
            The fact ID if stored, None if duplicate detected per §19.1.
        """
        # Deduplication per §19.1 — exact text match
        for existing in self._facts.values():
            if existing["fact"] == fact:
                return None

        fact_id = str(uuid.uuid4())
        status = "pending" if auto_extracted else "approved"

        self._facts[fact_id] = {
            "id": fact_id,
            "fact": fact,
            "category": category,
            "embedding": embedding,
            "created_at": datetime.now(UTC).isoformat(),
            "source_thread_id": source_thread_id,
            "status": status,
            "auto_extracted": auto_extracted,
        }

        return fact_id

    def get_by_id(self, fact_id: str) -> dict[str, Any] | None:
        """Retrieve a fact by ID."""
        return self._facts.get(fact_id)

    def recall(
        self,
        *,
        query_embedding: list[float],
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Semantic search over approved facts using cosine similarity.

        Only returns facts with status='approved' per §13.2.

        Args:
            query_embedding: Query vector for similarity search.
            n_results: Maximum number of results to return.

        Returns:
            List of matching facts sorted by similarity (descending).
        """
        scored: list[tuple[float, dict[str, Any]]] = []

        for fact in self._facts.values():
            # Only return approved facts per §13.2
            if fact["status"] != "approved":
                continue

            similarity = _cosine_similarity(
                query_embedding, fact["embedding"],
            )
            scored.append((similarity, fact))

        # Sort by similarity descending
        scored.sort(key=lambda x: x[0], reverse=True)

        return [fact for _, fact in scored[:n_results]]

    def delete(self, fact_id: str) -> bool:
        """Delete a fact by ID. Returns True if deleted.

        SPEC.md §13.2 — Purge: immediate removal.
        """
        if fact_id in self._facts:
            del self._facts[fact_id]
            return True
        return False

    def update_status(self, fact_id: str, status: str) -> bool:
        """Update a fact's status (approve/reject).

        Args:
            fact_id: The fact ID.
            status: New status ('approved', 'rejected', 'pending').

        Returns:
            True if updated, False if fact not found.
        """
        if fact_id in self._facts:
            self._facts[fact_id]["status"] = status
            return True
        return False

    def list_all(self) -> list[dict[str, Any]]:
        """Return all facts (for Memory Audit UI)."""
        return list(self._facts.values())

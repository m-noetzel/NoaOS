"""Private-side fact storage with embedding-based semantic retrieval.

Spec refs: SPEC.md §13.2, §19.1

Facts are stored with vector embeddings for cosine similarity search.
When ``data_dir`` is provided, each fact is persisted as a JSON file
so that data survives container restarts (backed by the ``/data``
Docker volume).
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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

    def __init__(self, data_dir: Path | None = None) -> None:
        self._facts: dict[str, dict[str, Any]] = {}
        self._data_dir = data_dir
        if self._data_dir is not None:
            self._load_from_disk()

    def store(
        self,
        *,
        fact: str,
        category: str,
        embedding: list[float],
        source_thread_id: str,
        auto_extracted: bool = False,
        user_id: str | None = None,
    ) -> str | None:
        """Store a fact with its embedding.

        Args:
            fact: The fact text.
            category: Category tag per §13.2.
            embedding: Vector embedding for semantic search.
            source_thread_id: Thread where fact originated.
            auto_extracted: Whether fact was auto-extracted.
            user_id: Owner of the fact — required for scoped read access (BE-M5,
                     L12). When provided, list_all/get_by_id/delete/update_status
                     will filter to only show this user's facts.

        Returns:
            The fact ID if stored, None if duplicate detected per §19.1.
        """
        # Deduplication per §19.1 — exact text match (scoped to user when provided)
        for existing in self._facts.values():
            if existing["fact"] == fact and (
                user_id is None or existing.get("user_id") == user_id
            ):
                return None

        fact_id = str(uuid.uuid4())
        status = "pending" if auto_extracted else "approved"

        fact_data: dict[str, Any] = {
            "id": fact_id,
            "fact": fact,
            "category": category,
            "embedding": embedding,
            "created_at": datetime.now(UTC).isoformat(),
            "source_thread_id": source_thread_id,
            "status": status,
            "auto_extracted": auto_extracted,
        }
        # BE-M5 / L12: always store user_id when available so read-path filters work
        if user_id is not None:
            fact_data["user_id"] = user_id
        self._facts[fact_id] = fact_data
        self._persist(fact_id)

        return fact_id

    def get_by_id(
        self, fact_id: str, *, user_id: str | None = None
    ) -> dict[str, Any] | None:
        """Retrieve a fact by ID, optionally scoped to user_id."""
        fact = self._facts.get(fact_id)
        if fact is None:
            return None
        if user_id is not None and fact.get("user_id") != user_id:
            return None
        return fact

    def recall(
        self,
        *,
        query_embedding: list[float],
        n_results: int = 5,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search over approved facts using cosine similarity.

        Only returns facts with status='approved' per §13.2.

        Args:
            query_embedding: Query vector for similarity search.
            n_results: Maximum number of results to return.
            user_id: Optional user scope filter.

        Returns:
            List of matching facts sorted by similarity (descending).
        """
        scored: list[tuple[float, dict[str, Any]]] = []

        for fact in self._facts.values():
            # Only return approved facts per §13.2
            if fact["status"] != "approved":
                continue
            # Filter by user_id when provided
            if user_id is not None and fact.get("user_id") != user_id:
                continue

            similarity = _cosine_similarity(
                query_embedding, fact["embedding"],
            )
            scored.append((similarity, fact))

        # Sort by similarity descending
        scored.sort(key=lambda x: x[0], reverse=True)

        return [fact for _, fact in scored[:n_results]]

    def delete(self, fact_id: str, *, user_id: str | None = None) -> bool:
        """Delete a fact by ID. Returns True if deleted.

        SPEC.md §13.2 — Purge: immediate removal.
        When user_id is provided, only deletes if the fact belongs to that user.
        """
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        if user_id is not None and fact.get("user_id") != user_id:
            return False
        del self._facts[fact_id]
        self._remove_file(fact_id)
        return True

    def update_status(
        self, fact_id: str, status: str, *, user_id: str | None = None
    ) -> bool:
        """Update a fact's status (approve/reject).

        Args:
            fact_id: The fact ID.
            status: New status ('approved', 'rejected', 'pending').
            user_id: When provided, only updates if the fact belongs to this user.

        Returns:
            True if updated, False if fact not found or user mismatch.
        """
        fact = self._facts.get(fact_id)
        if fact is None:
            return False
        if user_id is not None and fact.get("user_id") != user_id:
            return False
        self._facts[fact_id]["status"] = status
        self._persist(fact_id)
        return True

    def list_all(self, *, user_id: str | None = None) -> list[dict[str, Any]]:
        """Return all facts (for Memory Audit UI).

        When user_id is provided, only returns facts belonging to that user.
        """
        facts = self._facts.values()
        if user_id is not None:
            return [f for f in facts if f.get("user_id") == user_id]
        return list(facts)

    def persist(self, fact_id: str) -> None:
        """Public method to persist a fact to disk."""
        self._persist(fact_id)

    # ------------------------------------------------------------------
    # Disk persistence helpers
    # ------------------------------------------------------------------

    def _persist(self, fact_id: str) -> None:
        """Write a single fact to ``{data_dir}/{fact_id}.json``."""
        if self._data_dir is None:
            return
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            path = self._data_dir / f"{fact_id}.json"
            path.write_text(json.dumps(self._facts[fact_id]))
        except OSError:
            logger.warning("Cannot persist fact %s to %s", fact_id, self._data_dir)

    def _remove_file(self, fact_id: str) -> None:
        """Remove the JSON file for *fact_id* if it exists."""
        if self._data_dir is None:
            return
        try:
            path = self._data_dir / f"{fact_id}.json"
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Cannot remove fact file %s", fact_id)

    def _load_from_disk(self) -> None:
        """Load all ``*.json`` files from *data_dir* into memory."""
        if self._data_dir is None or not self._data_dir.exists():
            return
        for path in self._data_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                fact_id = data["id"]
                self._facts[fact_id] = data
            except (json.JSONDecodeError, KeyError, TypeError):
                logger.warning("Skipping invalid fact file: %s", path)
                continue

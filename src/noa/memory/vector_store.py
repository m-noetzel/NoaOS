"""VectorMemoryStore — pgvector-backed memory with cosine similarity recall.

Spec refs: SPEC.md §13.2, §19.1

This is an additive layer on top of the existing file-based MemoryStore.
When a DB session factory and Ollama client are available, facts are
persisted to memory_facts with real nomic-embed-text embeddings and
retrieved via pgvector cosine similarity.

Trust tiers (status field):
  - 'ephemeral'  — not persisted to DB (handled in-process only)
  - 'pending'    — stored, awaiting user approval (excluded from recall)
  - 'approved'   — trusted, included in vector search
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text

from noa.db.models.memory_fact import MemoryFact

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    from noa.llm.providers.ollama import OllamaClient

logger = logging.getLogger(__name__)

# Status constants
STATUS_APPROVED = "approved"
STATUS_PENDING = "pending"
STATUS_EPHEMERAL = "ephemeral"

# Cosine distance operator in pgvector: <=> gives cosine distance (0 = identical)
# Similarity = 1 - distance
_COSINE_DIST_OP = "<=>"


class VectorMemoryStore:
    """pgvector-backed memory store for semantic fact retrieval.

    Requires:
      - A session factory (async SQLAlchemy)
      - An OllamaClient for generating embeddings

    Falls back gracefully when either is unavailable:
      - No Ollama → stores without embedding (keyword search only)
      - No DB → logs warning, returns empty results
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncGenerator[AsyncSession, None]],
        ollama_client: OllamaClient,
        *,
        embed_model: str = "nomic-embed-text",
        default_domain: str = "private",
    ) -> None:
        self._session_factory = session_factory
        self._ollama = ollama_client
        self._embed_model = embed_model
        self._default_domain = default_domain

    async def _get_embedding(self, text: str) -> list[float] | None:
        """Get embedding for text, returning None on failure."""
        from noa.llm.exceptions import ProviderError  # noqa: PLC0415

        try:
            return await self._ollama.embed(text, model=self._embed_model)
        except ProviderError as exc:
            logger.warning("vm1_embed_failed: %s", exc)
            return None

    async def store_fact(
        self,
        *,
        fact: str,
        user_id: str,
        category: str = "preference",
        source_thread_id: str = "",
        auto_extracted: bool = False,
        domain: str | None = None,
    ) -> str | None:
        """Store a fact with embedding in the DB.

        Args:
            fact: The fact text to store.
            user_id: Owner of the fact.
            category: Category tag per §13.2.
            source_thread_id: Thread where fact originated.
            auto_extracted: If True, status is 'pending' (requires approval).
            domain: Domain ('private' or 'external'). Defaults to default_domain.

        Returns:
            Fact UUID as string if stored, None if duplicate detected per §19.1.
        """
        domain = domain or self._default_domain

        # Generate embedding (None if Ollama unavailable — still store the fact)
        embedding = await self._get_embedding(fact)

        status = STATUS_PENDING if auto_extracted else STATUS_APPROVED

        try:
            async with self._get_session() as session:
                # Deduplication per §19.1 — exact text match scoped to user
                existing = await session.execute(
                    select(MemoryFact).where(
                        MemoryFact.user_id == user_id,
                        MemoryFact.content == fact,
                        MemoryFact.domain == domain,
                    )
                )
                if existing.scalars().first() is not None:
                    logger.debug("vm1_store_duplicate: user=%s", user_id)
                    return None

                memory_fact = MemoryFact(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    domain=domain,
                    content=fact,
                    category=category,
                    source_thread_id=source_thread_id or None,
                    status=status,
                    auto_extracted=auto_extracted,
                    embedding=embedding,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                session.add(memory_fact)
                await session.commit()
                logger.debug(
                    "vm1_fact_stored: id=%s user=%s status=%s embed=%s",
                    memory_fact.id,
                    user_id,
                    status,
                    "yes" if embedding else "no",
                )
                return str(memory_fact.id)

        except Exception as exc:  # noqa: BLE001
            logger.error("vm1_store_error: user=%s error=%s", user_id, exc)
            return None

    async def recall_similar(
        self,
        *,
        query: str,
        user_id: str,
        domain: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Cosine similarity search over approved facts.

        When query embedding is available, uses pgvector ORDER BY <=> (cosine
        distance). Falls back to keyword (ILIKE) search when embedding unavailable.

        Only returns facts with status='approved' per §13.2.

        Args:
            query: The search query text.
            user_id: Owner of the facts.
            domain: Domain filter. Defaults to default_domain.
            limit: Maximum number of results.

        Returns:
            List of dicts with fact data, sorted by relevance descending.
        """
        domain = domain or self._default_domain
        query_embedding = await self._get_embedding(query)

        try:
            async with self._get_session() as session:
                if query_embedding is not None:
                    return await self._vector_search(
                        session=session,
                        user_id=user_id,
                        domain=domain,
                        query_embedding=query_embedding,
                        limit=limit,
                    )
                else:
                    return await self._keyword_search(
                        session=session,
                        user_id=user_id,
                        domain=domain,
                        query=query,
                        limit=limit,
                    )
        except Exception as exc:  # noqa: BLE001
            logger.error("vm1_recall_error: user=%s error=%s", user_id, exc)
            return []

    async def _vector_search(
        self,
        *,
        session: AsyncSession,
        user_id: str,
        domain: str,
        query_embedding: list[float],
        limit: int,
    ) -> list[dict[str, Any]]:
        """Execute pgvector cosine similarity search."""
        # Use raw SQL for the vector operator — SQLAlchemy ORM doesn't support <=>
        # natively without explicit type registration.
        sql = text(
            """
            SELECT
                id,
                content,
                category,
                source_thread_id,
                status,
                auto_extracted,
                created_at,
                1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
            FROM memory_facts
            WHERE
                user_id = :user_id
                AND domain = :domain
                AND status = :status
                AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:query_vec AS vector)
            LIMIT :limit
            """
        )
        result = await session.execute(
            sql,
            {
                "query_vec": str(query_embedding),
                "user_id": user_id,
                "domain": domain,
                "status": STATUS_APPROVED,
                "limit": limit,
            },
        )
        rows = result.mappings().all()
        return [dict(row) for row in rows]

    async def _keyword_search(
        self,
        *,
        session: AsyncSession,
        user_id: str,
        domain: str,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fallback keyword search when embedding unavailable."""
        stmt = (
            select(MemoryFact)
            .where(
                MemoryFact.user_id == user_id,
                MemoryFact.domain == domain,
                MemoryFact.status == STATUS_APPROVED,
                MemoryFact.content.ilike(f"%{query}%"),
            )
            .limit(limit)
        )
        result = await session.execute(stmt)
        facts = result.scalars().all()
        return [
            {
                "id": str(f.id),
                "content": f.content,
                "category": f.category,
                "source_thread_id": f.source_thread_id,
                "status": f.status,
                "auto_extracted": f.auto_extracted,
                "created_at": f.created_at,
                "similarity": None,
            }
            for f in facts
        ]

    async def update_fact_status(
        self, fact_id: str, status: str, *, user_id: str
    ) -> bool:
        """Update fact status (approve/reject pending facts).

        Args:
            fact_id: UUID of the fact.
            status: New status ('approved', 'pending', 'rejected').
            user_id: Must match fact's owner.

        Returns:
            True if updated, False if not found or user mismatch.
        """
        try:
            async with self._get_session() as session:
                fact = await session.get(MemoryFact, uuid.UUID(fact_id))
                if fact is None or fact.user_id != user_id:
                    return False
                fact.status = status
                fact.updated_at = datetime.now(UTC)
                await session.commit()
                return True
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "vm1_update_status_error: fact_id=%s error=%s", fact_id, exc
            )
            return False

    async def list_facts(
        self,
        *,
        user_id: str,
        domain: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List facts for a user (Memory Audit UI).

        Args:
            user_id: Owner filter.
            domain: Optional domain filter.
            status: Optional status filter.

        Returns:
            List of fact dicts (no embedding payload).
        """
        domain = domain or self._default_domain

        try:
            async with self._get_session() as session:
                conditions = [MemoryFact.user_id == user_id]
                if domain:
                    conditions.append(MemoryFact.domain == domain)
                if status:
                    conditions.append(MemoryFact.status == status)

                stmt = (
                    select(MemoryFact)
                    .where(*conditions)
                    .order_by(MemoryFact.created_at.desc())
                )
                result = await session.execute(stmt)
                facts = result.scalars().all()
                return [
                    {
                        "id": str(f.id),
                        "content": f.content,
                        "category": f.category,
                        "source_thread_id": f.source_thread_id,
                        "status": f.status,
                        "auto_extracted": f.auto_extracted,
                        "domain": f.domain,
                        "created_at": f.created_at,
                    }
                    for f in facts
                ]
        except Exception as exc:  # noqa: BLE001
            logger.error("vm1_list_error: user=%s error=%s", user_id, exc)
            return []

    async def delete_fact(self, fact_id: str, *, user_id: str) -> bool:
        """Delete a fact by ID, scoped to user.

        Returns True if deleted, False if not found or user mismatch.
        """
        try:
            async with self._get_session() as session:
                fact = await session.get(MemoryFact, uuid.UUID(fact_id))
                if fact is None or fact.user_id != user_id:
                    return False
                await session.delete(fact)
                await session.commit()
                return True
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "vm1_delete_error: fact_id=%s error=%s", fact_id, exc
            )
            return False

    def _get_session(self) -> Any:
        """Return an async session context manager."""
        return self._session_factory()

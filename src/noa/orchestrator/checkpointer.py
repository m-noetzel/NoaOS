"""Async PostgreSQL checkpointer for LangGraph — SPEC.md S10.1.

Resolves A4: replaces NoOpCheckpointer with real DB-backed persistence.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


class PostgresCheckpointer:
    """Postgres-backed checkpointer for LangGraph run state.

    Saves and loads run state to the ``checkpoints`` table using
    upsert semantics (one checkpoint per run_id).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, *, run_id: str, state: dict[str, Any]) -> None:
        """Save or update a checkpoint for the given run."""
        from noa.db.models.checkpoint import Checkpoint

        async with self._session_factory() as session:
            stmt = select(Checkpoint).where(Checkpoint.run_id == run_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is not None:
                existing.state = state
            else:
                cp = Checkpoint(run_id=run_id, state=state)
                session.add(cp)

            await session.commit()
            logger.debug("Checkpoint saved for run_id=%s", run_id)

    async def load(self, *, run_id: str) -> dict[str, Any] | None:
        """Load a checkpoint for the given run, or None if not found."""
        from noa.db.models.checkpoint import Checkpoint

        async with self._session_factory() as session:
            stmt = select(Checkpoint).where(Checkpoint.run_id == run_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                return None
            return existing.state


class NoOpCheckpointer:
    """Fallback checkpointer when no DB is available.

    Used only when the database session factory is not configured
    (e.g., in minimal test environments).
    """

    def __init__(self) -> None:
        logger.warning(
            "NoOpCheckpointer in use — state will not persist across restarts."
        )

    async def save(self, *, run_id: str, state: dict[str, Any]) -> None:
        """No-op save — state is discarded."""

    async def load(self, *, run_id: str) -> dict[str, Any] | None:
        """No-op load — always returns None."""
        return None

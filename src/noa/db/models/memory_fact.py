"""MemoryFact ORM model — persistent vector memory storage.

Spec refs: SPEC.md §13.2, §19.1

Stores user facts with pgvector embeddings for cosine similarity recall.
Trust tiers (status):
  - 'ephemeral'  — not persisted to DB (handled in MemoryStore in-memory only)
  - 'pending'    — stored, awaiting user approval
  - 'approved'   — trusted, included in vector search
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from noa.db.models.base import Base

try:
    from pgvector.sqlalchemy import Vector  # noqa: F401

    _PGVECTOR_AVAILABLE = True
    _Vector = Vector
except ImportError:
    _PGVECTOR_AVAILABLE = False
    _Vector = None

# nomic-embed-text produces 768-dimensional vectors
_EMBEDDING_DIM = 768


def _embedding_column() -> Any:
    """Return a Vector(768) column if pgvector is available, else Text (fallback)."""
    if _PGVECTOR_AVAILABLE and _Vector is not None:
        return mapped_column(_Vector(_EMBEDDING_DIM), nullable=True)
    # Fallback: store as text (no vector search, keyword search only)
    return mapped_column(Text, nullable=True)


class MemoryFact(Base):
    """Persisted memory fact with optional vector embedding."""

    __tablename__ = "memory_facts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(
        String(32), nullable=False, default="private"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_thread_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="approved", index=True
    )
    auto_extracted: Mapped[bool] = mapped_column(nullable=False, default=False)
    # Vector embedding — nullable so facts can be stored before embedding is computed
    embedding: Mapped[Any] = _embedding_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<MemoryFact id={self.id!s:.8} user={self.user_id!r} "
            f"status={self.status!r} category={self.category!r}>"
        )

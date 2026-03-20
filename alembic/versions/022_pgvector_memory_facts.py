"""Add memory_facts table with pgvector embedding column.

VM1: Private Vector Memory — pgvector + Ollama nomic-embed-text embeddings.

Spec refs: SPEC.md §13.2, §19.1

Creates the memory_facts table with:
  - id (UUID primary key)
  - user_id (indexed for scoped access)
  - domain (private/external)
  - content (fact text)
  - category, source_thread_id, status, auto_extracted
  - embedding (vector(768) — nomic-embed-text dimension)
  - created_at, updated_at

Trust tiers (status):
  - 'ephemeral': in-memory only, not persisted
  - 'pending': stored, awaiting user approval
  - 'approved': trusted, returned by vector search

Revision ID: 022
Revises: 021
Create Date: 2026-03-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: str = "021"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Enable pgvector extension (safe to run multiple times)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "memory_facts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(256), nullable=False),
        sa.Column("domain", sa.String(32), nullable=False, server_default="private"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("source_thread_id", sa.String(256), nullable=True),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="approved"
        ),
        sa.Column(
            "auto_extracted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        # Vector column — 768-dim for nomic-embed-text
        # Uses TEXT fallback type for environments without pgvector (e.g. SQLite tests)
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memory_facts_user_id", "memory_facts", ["user_id"], unique=False
    )
    op.create_index(
        "ix_memory_facts_status", "memory_facts", ["status"], unique=False
    )

    # Alter the embedding column to use pgvector type when extension is available.
    # This is safe because we just created the table (empty) and the extension
    # was just enabled. On SQLite (test env), this block will be skipped via
    # the connection dialect check.
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE memory_facts "
            "ALTER COLUMN embedding TYPE vector(768) "
            "USING NULL"
        )
        # Create HNSW index for fast approximate nearest-neighbor search
        op.execute(
            "CREATE INDEX ix_memory_facts_embedding_hnsw "
            "ON memory_facts USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    op.drop_table("memory_facts")
    # Note: we do NOT drop the vector extension here because other objects
    # might rely on it in future phases.

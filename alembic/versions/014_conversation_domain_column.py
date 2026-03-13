"""Add domain column to conversations table.

Revision ID: 014
Revises: 013
Create Date: 2026-03-13

BE-C3: Domain-scoped threads — each conversation belongs to either
the private or external domain so threads don't leak across domains.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "domain",
            sa.String(16),
            nullable=False,
            server_default="external",
        ),
    )
    op.create_index(
        "ix_conversations_user_domain",
        "conversations",
        ["user_id", "domain"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_user_domain", table_name="conversations")
    op.drop_column("conversations", "domain")

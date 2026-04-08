"""Add run_id column to messages table.

Links each message to the orchestrator run that produced it so the
frontend RatingButtons component can surface per-run ratings.

Revision ID: 029
Revises: 028
Create Date: 2026-04-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "029"
down_revision: str = "028"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("run_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "run_id")

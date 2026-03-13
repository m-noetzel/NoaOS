"""Alter usage_stats.run_id FK to add ON DELETE SET NULL.

Without this, deleting a thread (which cascades to runs) would attempt to
cascade-delete usage_stats rows tied to those runs, causing a FK violation
and a 500 on DELETE /threads/{id}.

Revision ID: 012
Revises: 011
Create Date: 2026-03-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str = "011"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # SQLite does not support ALTER COLUMN for FK constraints, so we use
    # batch mode (which rebuilds the table) for portability.
    with op.batch_alter_table("usage_stats") as batch_op:
        batch_op.drop_constraint("usage_stats_run_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "usage_stats_run_id_fkey",
            "runs",
            ["run_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("usage_stats") as batch_op:
        batch_op.drop_constraint("usage_stats_run_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "usage_stats_run_id_fkey",
            "runs",
            ["run_id"],
            ["id"],
        )

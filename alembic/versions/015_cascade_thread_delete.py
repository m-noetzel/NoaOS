"""Ensure usage_stats.run_id FK has ON DELETE SET NULL (Postgres-safe).

Migration 012 added this via SQLite batch mode, but on Postgres the FK
constraint name may differ. This migration explicitly drops any existing
FK on run_id then recreates it with ON DELETE SET NULL, preventing
DuplicateObject errors if the constraint already exists.

Addresses W21-H1: DELETE /threads/{id} must succeed even when runs and
usage_stats rows exist for the thread.

Revision ID: 015
Revises: 014
Create Date: 2026-03-13
"""

from __future__ import annotations

from alembic import op

revision: str = "015"
down_revision: str = "014"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Drop the existing FK constraint (created by migration 012) before
    # recreating it. Without this, Postgres raises DuplicateObject.
    # recreate="always" handles SQLite (full table rebuild); on Postgres,
    # batch_alter_table issues ALTER TABLE DROP/ADD CONSTRAINT directly.
    with op.batch_alter_table("usage_stats", recreate="always") as batch_op:
        batch_op.drop_constraint("usage_stats_run_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "usage_stats_run_id_fkey",
            "runs",
            ["run_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("usage_stats", recreate="always") as batch_op:
        batch_op.drop_constraint("usage_stats_run_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "usage_stats_run_id_fkey",
            "runs",
            ["run_id"],
            ["id"],
        )

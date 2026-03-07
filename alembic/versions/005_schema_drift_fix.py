"""Fix schema drift: add missing columns to approvals and usage_stats.

Revision ID: 005
Revises: 004
Create Date: 2026-03-07

Adds:
- approvals.domain (String(16), NOT NULL, default 'private')
- usage_stats.task_id (Uuid, nullable)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "approvals",
        sa.Column("domain", sa.String(16), nullable=False, server_default="private"),
    )
    op.add_column(
        "usage_stats",
        sa.Column("task_id", sa.Uuid(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("usage_stats", "task_id")
    op.drop_column("approvals", "domain")

"""Add function_name column to tool_capabilities for per-function grants.

Revision ID: 009
Revises: 008
Create Date: 2026-03-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str = "008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "tool_capabilities",
        sa.Column("function_name", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tool_capabilities", "function_name")

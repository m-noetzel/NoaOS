"""Add tool_capabilities table for per-tool capability grants.

Revision ID: 004
Revises: 003
Create Date: 2026-03-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: str = "003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "tool_capabilities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("capability", sa.String(64), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "granted_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_tool_capabilities_user_tool",
        "tool_capabilities",
        ["user_id", "tool_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_tool_capabilities_user_tool", table_name="tool_capabilities")
    op.drop_table("tool_capabilities")

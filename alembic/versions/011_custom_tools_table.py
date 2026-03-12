"""Add custom_tools table for user-registered custom tool definitions.

TM5 added the CustomTool ORM model but no migration was created at the time
(schema drift detected by QE4 integration tests).

Revision ID: 011
Revises: 010
Create Date: 2026-03-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: str = "010"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "custom_tools",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("auth_type", sa.String(32), nullable=False, server_default="none"),
        sa.Column("domain", sa.String(32), nullable=False, server_default="external"),
        sa.Column("functions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("custom_tools")

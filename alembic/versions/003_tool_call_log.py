"""Add tool_call_logs table for tool telemetry persistence.

Revision ID: 003
Revises: 002
Create Date: 2026-03-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "tool_call_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tool", sa.String(128), nullable=False),
        sa.Column("function", sa.String(128), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("cached", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("user_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_tool_call_logs_tool", "tool_call_logs", ["tool"]
    )
    op.create_index(
        "ix_tool_call_logs_timestamp", "tool_call_logs", ["timestamp"]
    )


def downgrade() -> None:
    op.drop_index("ix_tool_call_logs_timestamp", table_name="tool_call_logs")
    op.drop_index("ix_tool_call_logs_tool", table_name="tool_call_logs")
    op.drop_table("tool_call_logs")

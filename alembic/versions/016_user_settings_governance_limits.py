"""Add governance and agent limit fields to user_settings.

UX-M2: approvals_enabled — toggle human-in-the-loop approvals.
UX-M4: max_tool_calls, max_retries, timeout_seconds — agent execution limits.

Revision ID: 016
Revises: 015
Create Date: 2026-03-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: str = "015"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_settings", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "approvals_enabled",
                sa.Boolean(),
                nullable=True,
                server_default="1",
            ),
        )
        batch_op.add_column(
            sa.Column(
                "max_tool_calls",
                sa.Integer(),
                nullable=True,
                server_default="10",
            ),
        )
        batch_op.add_column(
            sa.Column(
                "max_retries",
                sa.Integer(),
                nullable=True,
                server_default="3",
            ),
        )
        batch_op.add_column(
            sa.Column(
                "timeout_seconds",
                sa.Integer(),
                nullable=True,
                server_default="120",
            ),
        )


def downgrade() -> None:
    with op.batch_alter_table("user_settings", recreate="always") as batch_op:
        batch_op.drop_column("timeout_seconds")
        batch_op.drop_column("max_retries")
        batch_op.drop_column("max_tool_calls")
        batch_op.drop_column("approvals_enabled")

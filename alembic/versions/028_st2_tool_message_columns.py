"""Add tool_calls, tool_call_id, tool_name columns to messages.

ST2: Chat History & Tool Persistence (CHAT-H1).
Stores tool call context so multi-turn conversations retain tool history.

Revision ID: 028
Revises: 027
Create Date: 2026-03-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "028"
down_revision: str = "027"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("tool_calls", sa.JSON(), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("tool_call_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("tool_name", sa.String(255), nullable=True),
    )
    # Also relax the NOT NULL constraint on content so tool-only assistant
    # messages (where content is None) can be persisted.
    op.alter_column("messages", "content", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("messages", "content", existing_type=sa.Text(), nullable=False)
    op.drop_column("messages", "tool_name")
    op.drop_column("messages", "tool_call_id")
    op.drop_column("messages", "tool_calls")

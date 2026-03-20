"""Add node_models column to user_settings.

MC1: Per-node model configuration — stores JSON blob mapping node names
to model identifiers (classifier, planner, agent, evaluator).

Revision ID: 021
Revises: 020
Create Date: 2026-03-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: str = "020"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_settings", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "node_models",
                sa.Text(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    with op.batch_alter_table("user_settings", recreate="always") as batch_op:
        batch_op.drop_column("node_models")

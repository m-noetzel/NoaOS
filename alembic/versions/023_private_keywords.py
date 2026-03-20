"""Add private_keywords column to user_settings.

PC1: User-configurable privacy classifier keywords.
Stores JSON array of custom keywords merged with built-in defaults.

Revision ID: 023
Revises: 022
Create Date: 2026-03-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: str = "022"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_settings", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "private_keywords",
                sa.Text(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    with op.batch_alter_table("user_settings", recreate="always") as batch_op:
        batch_op.drop_column("private_keywords")

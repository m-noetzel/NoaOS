"""Add scope_overrides column to user_settings.

UX-M10 / FR6-L1: Persist per-user tool scope overrides across restarts.
Previously stored in a module-level dict (_scope_overrides in tools.py),
which was lost on every server restart.

Revision ID: 017
Revises: 016
Create Date: 2026-03-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: str = "016"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_settings", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "scope_overrides",
                sa.Text(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    with op.batch_alter_table("user_settings", recreate="always") as batch_op:
        batch_op.drop_column("scope_overrides")

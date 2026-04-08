"""Add eval_config column to user_settings table.

Stores user-configurable evaluator quality thresholds as a JSON TEXT column.
Keys: pass_threshold (float), reroute_threshold (float), max_cycles (int).
NULL means "use hardcoded defaults from evaluator.py".

Revision ID: 030
Revises: 029
Create Date: 2026-04-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "030"
down_revision: str = "029"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("eval_config", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "eval_config")

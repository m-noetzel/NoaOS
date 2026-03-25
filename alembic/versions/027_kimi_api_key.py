"""Add kimi_api_key column to user_settings.

KM1: Kimi (Moonshot AI) LLM provider integration.

Revision ID: 027
Revises: 026
Create Date: 2026-03-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: str = "026"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("kimi_api_key", sa.String(256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "kimi_api_key")

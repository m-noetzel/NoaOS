"""Add google_refresh_token column to user_settings.

GO1 added this column to the UserSettings ORM model but no migration was
created at the time (schema drift detected by QE4 integration tests).

Revision ID: 010
Revises: 009
Create Date: 2026-03-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str = "009"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("google_refresh_token", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "google_refresh_token")

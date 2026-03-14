"""Drop system_prompt column from user_settings.

System prompt is now file-backed (prompts/system_prompt.txt),
not stored in the database. See transparency principle in CLAUDE.md.

Revision ID: 018
Revises: 017
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("user_settings", "system_prompt")


def downgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("system_prompt", sa.String(4096), nullable=True),
    )

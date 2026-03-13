"""Add system_prompt, temperature, max_tokens to user_settings.

Revision ID: 013
Revises: 012
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("system_prompt", sa.String(4096), nullable=True),
    )
    op.add_column(
        "user_settings",
        sa.Column("temperature", sa.Numeric(3, 2), nullable=True, server_default="0.7"),
    )
    op.add_column(
        "user_settings",
        sa.Column("max_tokens", sa.Integer(), nullable=True, server_default="4096"),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "max_tokens")
    op.drop_column("user_settings", "temperature")
    op.drop_column("user_settings", "system_prompt")

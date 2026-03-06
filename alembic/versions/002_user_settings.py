"""Add user_settings table for preferences and tool credentials.

Revision ID: 002
Revises: 001
Create Date: 2026-03-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: str = "001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        # Defaults
        sa.Column("default_model", sa.String(64)),
        sa.Column("default_provider", sa.String(32)),
        sa.Column("default_privacy_mode", sa.String(16)),
        # Budget limits
        sa.Column("budget_daily_usd", sa.Numeric(10, 2)),
        sa.Column("budget_monthly_usd", sa.Numeric(10, 2)),
        # Tool credentials (SPEC.md §11.1)
        sa.Column("anthropic_api_key", sa.String(256)),
        sa.Column("openai_api_key", sa.String(256)),
        sa.Column("google_client_id", sa.String(256)),
        sa.Column("google_client_secret", sa.String(256)),
        sa.Column("notion_token", sa.String(256)),
        sa.Column("tavily_api_key", sa.String(256)),
        sa.Column("ollama_base_url", sa.String(512)),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_settings")

"""Token blacklist table for JWT revocation on logout.

SEC1: Access tokens are revocable immediately after logout by recording
their jti claim in this table and checking it on every authenticated request.

Revision ID: 026
Revises: 025
Create Date: 2026-03-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: str = "025"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create token_blacklist table with indexes."""
    op.create_table(
        "token_blacklist",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("jti", sa.String(128), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_token_blacklist_jti",
        "token_blacklist",
        ["jti"],
        unique=True,
    )
    op.create_index(
        "ix_token_blacklist_expires_at",
        "token_blacklist",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_token_blacklist_user_id",
        "token_blacklist",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop token_blacklist table and indexes."""
    op.drop_index("ix_token_blacklist_user_id", table_name="token_blacklist")
    op.drop_index("ix_token_blacklist_expires_at", table_name="token_blacklist")
    op.drop_index("ix_token_blacklist_jti", table_name="token_blacklist")
    op.drop_table("token_blacklist")

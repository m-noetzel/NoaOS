"""Add google_credentials and checkpoints tables.

Revision ID: 007
Revises: 006
Create Date: 2026-03-07

Resolves M10 (Google token persistence) and A4 (Postgres checkpointer).
"""

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "google_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("access_token_enc", sa.Text(), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "checkpoints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.String(256), unique=True, nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_checkpoints_run_id", "checkpoints", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_checkpoints_run_id", table_name="checkpoints")
    op.drop_table("checkpoints")
    op.drop_table("google_credentials")

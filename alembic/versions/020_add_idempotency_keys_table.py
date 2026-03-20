"""Add idempotency_keys table for persistent tool-call idempotency.

CX1: Replaces in-memory dict with Postgres-backed idempotency store
so that idempotency guarantees survive restarts and scale across workers.

Revision ID: 020
Revises: 019
"""

import sqlalchemy as sa
from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(
        op.f("ix_idempotency_keys_key"),
        "idempotency_keys",
        ["key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_idempotency_keys_key"), table_name="idempotency_keys")
    op.drop_table("idempotency_keys")

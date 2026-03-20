"""Add response_evaluations table.

EV1: Stores per-run evaluation scores from the evaluator node.

Revision ID: 024
Revises: 023
Create Date: 2026-03-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: str = "023"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "response_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.String(256), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=True),
        sa.Column("archetype", sa.String(64), nullable=True),
        sa.Column("rubric_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("overall", sa.Float(), nullable=False),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("reroute_target", sa.String(64), nullable=True),
        sa.Column("reroute_cycle", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("eval_model", sa.String(128), nullable=False),
        sa.Column("eval_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("user_rating", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_response_evaluations_run_id",
        "response_evaluations",
        ["run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_response_evaluations_run_id", table_name="response_evaluations")
    op.drop_table("response_evaluations")

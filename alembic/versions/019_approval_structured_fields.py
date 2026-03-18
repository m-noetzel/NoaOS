"""Add structured tool/function columns to approvals table.

CQ9: Store tool name and function name as separate columns instead of
relying on parsing preview_text for this information.

Revision ID: 019
Revises: 018
"""

from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "approvals",
        sa.Column("tool_name", sa.String(128), nullable=True),
    )
    op.add_column(
        "approvals",
        sa.Column("function_name", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("approvals", "function_name")
    op.drop_column("approvals", "tool_name")

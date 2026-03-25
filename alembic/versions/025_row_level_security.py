"""Row-Level Security policies for domain isolation.

RLS1: Adds Postgres RLS policies on domain-sensitive tables so the DB
enforces domain isolation at the query level.

Revision ID: 025
Revises: 024
Create Date: 2026-03-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: str = "024"
branch_labels: str | None = None
depends_on: str | None = None

# Tables with a direct `domain` column — RLS uses that column directly.
DOMAIN_TABLES = [
    "conversations",
    "approvals",
    "memory_facts",
    "audit_log",
    "custom_tools",
]


def upgrade() -> None:
    """Enable RLS on domain-sensitive tables (Postgres only)."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table in DOMAIN_TABLES:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))

        # SELECT — only see rows whose domain matches the session variable.
        # current_setting('noa.domain', true) returns '' when not set (the
        # second argument suppresses the "unrecognized configuration parameter"
        # error), so queries without an explicit domain context see ALL rows
        # (empty string != any real domain value → policy is bypassed).
        # We deliberately keep BYPASSRLS for the superuser so admin tooling
        # (e.g. Alembic itself) is unaffected.
        op.execute(
            sa.text(
                f"""
                CREATE POLICY {table}_domain_select ON {table}
                FOR SELECT
                USING (
                    current_setting('noa.domain', true) = ''
                    OR domain = current_setting('noa.domain', true)
                )
                """
            )
        )

        # INSERT — new rows must carry the current domain context.
        op.execute(
            sa.text(
                f"""
                CREATE POLICY {table}_domain_insert ON {table}
                FOR INSERT
                WITH CHECK (
                    current_setting('noa.domain', true) = ''
                    OR domain = current_setting('noa.domain', true)
                )
                """
            )
        )

        # UPDATE
        op.execute(
            sa.text(
                f"""
                CREATE POLICY {table}_domain_update ON {table}
                FOR UPDATE
                USING (
                    current_setting('noa.domain', true) = ''
                    OR domain = current_setting('noa.domain', true)
                )
                """
            )
        )

        # DELETE
        op.execute(
            sa.text(
                f"""
                CREATE POLICY {table}_domain_delete ON {table}
                FOR DELETE
                USING (
                    current_setting('noa.domain', true) = ''
                    OR domain = current_setting('noa.domain', true)
                )
                """
            )
        )

    # `runs` uses `privacy_mode` as its domain equivalent.
    op.execute(sa.text("ALTER TABLE runs ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY runs_domain_select ON runs
            FOR SELECT
            USING (
                current_setting('noa.domain', true) = ''
                OR privacy_mode = current_setting('noa.domain', true)
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE POLICY runs_domain_insert ON runs
            FOR INSERT
            WITH CHECK (
                current_setting('noa.domain', true) = ''
                OR privacy_mode = current_setting('noa.domain', true)
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE POLICY runs_domain_update ON runs
            FOR UPDATE
            USING (
                current_setting('noa.domain', true) = ''
                OR privacy_mode = current_setting('noa.domain', true)
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE POLICY runs_domain_delete ON runs
            FOR DELETE
            USING (
                current_setting('noa.domain', true) = ''
                OR privacy_mode = current_setting('noa.domain', true)
            )
            """
        )
    )


def downgrade() -> None:
    """Remove RLS policies and disable RLS (Postgres only)."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    all_tables = DOMAIN_TABLES + ["runs"]
    for table in all_tables:
        for action in ("select", "insert", "update", "delete"):
            op.execute(
                sa.text(
                    f"DROP POLICY IF EXISTS {table}_domain_{action} ON {table}"
                )
            )
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

"""Row-Level Security context management — RLS1.

Provides helpers to set the `noa.domain` Postgres session variable so that
RLS policies on domain-sensitive tables (conversations, approvals,
memory_facts, audit_log, custom_tools, runs) automatically enforce domain
isolation at the database level.

SQLite (used in tests) does not support RLS — these helpers are no-ops on
non-Postgres connections.  Application-level WHERE clauses remain as
defense-in-depth for those cases.
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def set_domain_context(session: AsyncSession, domain: str) -> None:
    """Set the RLS domain context for the current transaction.

    Uses ``set_config('noa.domain', domain, true)`` — the third argument
    (``true``) means the setting is **local to the current transaction** and
    is automatically reverted on ``COMMIT`` / ``ROLLBACK``.  This is the
    safest choice: a connection returned to the pool carries no residual
    domain state.

    On non-Postgres engines (e.g. SQLite in tests) the call is skipped so
    tests can continue to run without modification.

    Args:
        session: The active async SQLAlchemy session.
        domain:  Domain value to enforce — ``"private"`` or ``"external"``.
                 Pass an empty string (``""``) to clear domain restriction
                 (superuser / admin operations).
    """
    # Detect dialect from the sync engine underlying the async session.
    # We use sync_session.get_bind() because the async layer doesn't expose
    # dialect directly without an awaitable call.
    try:
        bind = session.sync_session.get_bind()
        dialect_name: str = getattr(getattr(bind, "dialect", None), "name", "")
    except Exception:  # noqa: BLE001
        logger.debug("Could not determine DB dialect — skipping RLS context")
        return
    if dialect_name != "postgresql":
        # RLS not available — silently skip.
        return

    await session.execute(
        sa.text("SELECT set_config('noa.domain', :domain, true)"),
        {"domain": domain},
    )
    logger.debug("RLS domain context set to %r for current transaction", domain)


async def clear_domain_context(session: AsyncSession) -> None:
    """Clear the RLS domain context (allow all rows).

    Equivalent to calling ``set_domain_context(session, "")``.  Useful for
    admin / cross-domain queries that legitimately need to see all rows.
    """
    await set_domain_context(session, "")

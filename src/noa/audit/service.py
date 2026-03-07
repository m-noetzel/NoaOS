"""Audit service — create, query, and purge audit log entries.

SPEC.md §28.1 (required fields), §28.2 (hash chain), §28.7 (retention).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from noa.db.models.audit import AuditLog


class AuditService:
    """Business logic for audit log operations."""

    def __init__(self, session: Session | None = None) -> None:
        self._session = session

    def create_entry(
        self,
        *,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        device_id: uuid.UUID,
        trace_id: uuid.UUID,
        domain: str,
        model_provider: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: Decimal,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        tool_result_summary: str | None = None,
        side_effects: dict[str, Any] | None = None,
        privacy_classification: str,
        classification_confidence: float,
        classification_reasoning: str | None = None,
    ) -> AuditLog:
        """Create an audit log entry with hash chain linking (§28.1, §28.2).

        The new entry's previous_entry_hash is set to the SHA-256 of the
        most recent existing entry's hash_chain_data().
        """
        # Compute previous entry hash from the latest entry in the chain
        latest: AuditLog | None = (
            self._session.query(AuditLog)
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
            .first()
        )
        previous_hash: str | None = None
        if latest is not None:
            previous_hash = hashlib.sha256(
                latest.hash_chain_data().encode()
            ).hexdigest()

        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=user_id,
            session_id=session_id,
            device_id=device_id,
            trace_id=trace_id,
            domain=domain,
            model_provider=model_provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result_summary=tool_result_summary,
            side_effects=side_effects,
            privacy_classification=privacy_classification,
            classification_confidence=classification_confidence,
            classification_reasoning=classification_reasoning,
            previous_entry_hash=previous_hash,
        )
        self._session.add(entry)
        self._session.flush()
        return entry

    async def create_entry_async(
        self,
        *,
        session: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        device_id: uuid.UUID,
        trace_id: uuid.UUID,
        domain: str,
        model_provider: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: Decimal,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        tool_result_summary: str | None = None,
        side_effects: dict[str, Any] | None = None,
        privacy_classification: str,
        classification_confidence: float,
        classification_reasoning: str | None = None,
    ) -> AuditLog:
        """Async variant of create_entry — accepts an AsyncSession.

        Flushes (does NOT commit) so the caller controls the transaction.
        Hash chain is computed from the latest existing entry.
        """
        from sqlalchemy import select

        latest_stmt = (
            select(AuditLog)
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
            .limit(1)
        )
        result = await session.scalars(latest_stmt)
        latest: AuditLog | None = result.first()

        previous_hash: str | None = None
        if latest is not None:
            previous_hash = hashlib.sha256(
                latest.hash_chain_data().encode()
            ).hexdigest()

        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=user_id,
            session_id=session_id,
            device_id=device_id,
            trace_id=trace_id,
            domain=domain,
            model_provider=model_provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result_summary=tool_result_summary,
            side_effects=side_effects,
            privacy_classification=privacy_classification,
            classification_confidence=classification_confidence,
            classification_reasoning=classification_reasoning,
            previous_entry_hash=previous_hash,
        )
        session.add(entry)
        await session.flush()
        return entry

    def query_by_trace_id(self, trace_id: uuid.UUID) -> list[AuditLog]:
        """Return all audit entries matching the given trace_id."""
        results: list[AuditLog] = (
            self._session.query(AuditLog)
            .filter(AuditLog.trace_id == trace_id)
            .order_by(AuditLog.timestamp)
            .all()
        )
        return results

    def purge_expired(self, retention_days: int = 90) -> int:
        """Delete audit entries older than retention_days (§28.7).

        Returns the number of entries purged.
        """
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        count: int = (
            self._session.query(AuditLog)
            .filter(AuditLog.timestamp < cutoff)
            .delete(synchronize_session="fetch")
        )
        self._session.flush()
        return count

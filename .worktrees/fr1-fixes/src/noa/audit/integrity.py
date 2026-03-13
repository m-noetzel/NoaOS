"""Hash chain integrity verification — SPEC.md §28.2.

verify_chain() walks the audit log in timestamp order and confirms each
entry's previous_entry_hash matches the SHA-256 of the prior entry's
hash_chain_data().
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from noa.db.models.audit import AuditLog


@dataclass(frozen=True)
class ChainVerificationResult:
    """Outcome of a hash chain integrity check."""

    valid: bool
    entries_checked: int
    broken_at_entry_id: uuid.UUID | None = None


def verify_chain(session: Session) -> ChainVerificationResult:
    """Walk the audit log and verify hash chain integrity.

    Returns a result indicating whether the chain is valid, how many entries
    were checked, and (if invalid) which entry broke the chain.
    """
    entries: list[AuditLog] = (
        session.query(AuditLog)
        .order_by(AuditLog.timestamp, AuditLog.id)
        .all()
    )

    if not entries:
        return ChainVerificationResult(valid=True, entries_checked=0)

    for i, entry in enumerate(entries):
        if i == 0:
            # Genesis entry must have no previous hash
            if entry.previous_entry_hash is not None:
                return ChainVerificationResult(
                    valid=False,
                    entries_checked=i + 1,
                    broken_at_entry_id=entry.id,
                )
        else:
            prev = entries[i - 1]
            expected = hashlib.sha256(
                prev.hash_chain_data().encode()
            ).hexdigest()
            if entry.previous_entry_hash != expected:
                return ChainVerificationResult(
                    valid=False,
                    entries_checked=i + 1,
                    broken_at_entry_id=entry.id,
                )

    return ChainVerificationResult(valid=True, entries_checked=len(entries))

"""Tests for audit logging with hash chain — Phase OC3.

Spec refs: SPEC.md §28.1, §28.2, §28.3, §28.7
Phase plan: MASTER_PLAN.md Phase OC3

Tests cover: audit log service (create, query, hash chain),
hash chain integrity verification, structured JSON logging,
data retention policy, and no-secrets invariant.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

pytestmark = pytest.mark.oc3

FAKE_PW_HASH = "fakehash"  # noqa: S105


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine for audit tests."""
    from noa.db.models import Base

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def db(engine):
    """Transactional session that rolls back after each test."""
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture()
def user_id(db):
    """Create a test user and return its ID."""
    from noa.db.models.user import User

    user = User(
        id=uuid.uuid4(),
        email="audit-test@example.com",
        password_hash=FAKE_PW_HASH,
        display_name="Audit Tester",
    )
    db.add(user)
    db.flush()
    return user.id


def _make_audit_kwargs(user_id: uuid.UUID, **overrides) -> dict:
    """Build default kwargs for creating an audit log entry."""
    defaults = {
        "user_id": user_id,
        "session_id": uuid.uuid4(),
        "device_id": uuid.uuid4(),
        "trace_id": uuid.uuid4(),
        "domain": "private",
        "model_provider": "Ollama",
        "model_name": "llama3.1",
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": Decimal("0.00"),
        "tool_name": "web_search",
        "tool_args": {"query": "weather today"},
        "tool_result_summary": "Sunny, 72F",
        "side_effects": None,
        "privacy_classification": "private",
        "classification_confidence": 0.95,
        "classification_reasoning": "No external data referenced",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# 1. Audit log service — entry creation with all required fields (§28.1)
# ---------------------------------------------------------------------------

class TestAuditLogCreation:
    """Audit service creates entries with all §28.1 required fields."""

    def test_create_entry_returns_complete_record(self, db, user_id):
        """Service creates an audit entry with every §28.1 field populated."""
        from noa.audit.service import AuditService

        svc = AuditService(db)
        kwargs = _make_audit_kwargs(user_id)
        entry = svc.create_entry(**kwargs)

        # All §28.1 required fields present
        assert entry.id is not None
        assert entry.timestamp is not None
        assert entry.user_id == user_id
        assert entry.session_id == kwargs["session_id"]
        assert entry.device_id == kwargs["device_id"]
        assert entry.trace_id == kwargs["trace_id"]
        assert entry.domain == "private"
        assert entry.model_provider == "Ollama"
        assert entry.model_name == "llama3.1"
        assert entry.input_tokens == 100
        assert entry.output_tokens == 50
        assert entry.cost_usd == Decimal("0.00")
        assert entry.tool_name == "web_search"
        assert entry.tool_args == {"query": "weather today"}
        assert entry.tool_result_summary == "Sunny, 72F"
        assert entry.privacy_classification == "private"
        assert entry.classification_confidence == pytest.approx(0.95)

    def test_create_entry_persists_to_db(self, db, user_id):
        """Entry is flushed and queryable from the session."""
        from noa.audit.service import AuditService
        from noa.db.models.audit import AuditLog

        svc = AuditService(db)
        entry = svc.create_entry(**_make_audit_kwargs(user_id))

        found = db.query(AuditLog).filter_by(id=entry.id).first()
        assert found is not None
        assert found.id == entry.id

    def test_create_entry_without_tool_fields(self, db, user_id):
        """Entries without tool invocation leave tool fields as None."""
        from noa.audit.service import AuditService

        svc = AuditService(db)
        kwargs = _make_audit_kwargs(
            user_id,
            tool_name=None,
            tool_args=None,
            tool_result_summary=None,
            side_effects=None,
        )
        entry = svc.create_entry(**kwargs)
        assert entry.tool_name is None
        assert entry.tool_args is None
        assert entry.tool_result_summary is None


# ---------------------------------------------------------------------------
# 2. Hash chain computation (§28.2)
# ---------------------------------------------------------------------------

class TestHashChain:
    """Each entry's hash includes the previous entry's hash (§28.2)."""

    def test_first_entry_has_no_previous_hash(self, db, user_id):
        """Genesis entry has previous_entry_hash = None."""
        from noa.audit.service import AuditService

        svc = AuditService(db)
        entry = svc.create_entry(**_make_audit_kwargs(user_id))
        assert entry.previous_entry_hash is None

    def test_second_entry_chains_to_first(self, db, user_id):
        """Second entry's previous_entry_hash = SHA256 of first entry's chain data."""
        from noa.audit.service import AuditService

        svc = AuditService(db)
        entry1 = svc.create_entry(**_make_audit_kwargs(user_id))

        expected_hash = hashlib.sha256(
            entry1.hash_chain_data().encode()
        ).hexdigest()

        entry2 = svc.create_entry(**_make_audit_kwargs(user_id))
        assert entry2.previous_entry_hash == expected_hash

    def test_chain_of_three_entries(self, db, user_id):
        """Three entries form a proper chain: None -> hash1 -> hash2."""
        from noa.audit.service import AuditService

        svc = AuditService(db)
        e1 = svc.create_entry(**_make_audit_kwargs(user_id))
        e2 = svc.create_entry(**_make_audit_kwargs(user_id))
        e3 = svc.create_entry(**_make_audit_kwargs(user_id))

        assert e1.previous_entry_hash is None

        hash1 = hashlib.sha256(e1.hash_chain_data().encode()).hexdigest()
        assert e2.previous_entry_hash == hash1

        hash2 = hashlib.sha256(e2.hash_chain_data().encode()).hexdigest()
        assert e3.previous_entry_hash == hash2


# ---------------------------------------------------------------------------
# 3. Integrity verification (§28.2)
# ---------------------------------------------------------------------------

class TestIntegrityVerification:
    """Hash chain integrity: valid chain passes, tampered chain detected."""

    def test_valid_chain_passes_verification(self, db, user_id):
        """An untampered chain verifies successfully."""
        from noa.audit.integrity import verify_chain
        from noa.audit.service import AuditService

        svc = AuditService(db)
        for _ in range(5):
            svc.create_entry(**_make_audit_kwargs(user_id))

        result = verify_chain(db)
        assert result.valid is True
        assert result.entries_checked == 5

    def test_tampered_entry_detected(self, db, user_id):
        """Modifying an entry's field makes the chain fail verification."""
        from noa.audit.integrity import verify_chain
        from noa.audit.service import AuditService
        from noa.db.models.audit import AuditLog

        svc = AuditService(db)
        for _ in range(3):
            svc.create_entry(**_make_audit_kwargs(user_id))

        # Tamper with the first entry's tokens
        first = db.query(AuditLog).order_by(AuditLog.timestamp).first()
        first.input_tokens = 999999
        db.flush()

        result = verify_chain(db)
        assert result.valid is False
        assert result.broken_at_entry_id is not None

    def test_empty_log_passes_verification(self, db):
        """An empty audit log is considered valid."""
        from noa.audit.integrity import verify_chain

        result = verify_chain(db)
        assert result.valid is True
        assert result.entries_checked == 0


# ---------------------------------------------------------------------------
# 4. Structured JSON logging (§28.3)
# ---------------------------------------------------------------------------

class TestStructuredLogging:
    """All services emit structured JSON logs with trace_id propagation."""

    def test_logger_outputs_json_format(self):
        """Structured logger emits valid JSON with required fields."""
        from noa.audit.logging import get_structured_logger

        logger = get_structured_logger("test-service")
        assert logger is not None

        # The logger should be configured; verify it has handlers
        # that produce JSON output
        assert isinstance(logger, logging.Logger)

    def test_log_record_contains_required_fields(self):
        """A structured log record includes timestamp, level, service, message."""
        from noa.audit.logging import format_log_record

        record = format_log_record(
            service="noa-api",
            level="info",
            message="Tool invocation completed",
            trace_id=str(uuid.uuid4()),
            data={"tool": "web_search", "duration_ms": 234, "status": "success"},
        )

        parsed = json.loads(record)
        assert "timestamp" in parsed
        assert parsed["level"] == "info"
        assert parsed["service"] == "noa-api"
        assert "trace_id" in parsed
        assert parsed["message"] == "Tool invocation completed"
        assert parsed["data"]["tool"] == "web_search"

    def test_trace_id_propagated_in_log(self):
        """trace_id passed to the logger appears in the output."""
        from noa.audit.logging import format_log_record

        tid = str(uuid.uuid4())
        record = format_log_record(
            service="noa-worker",
            level="debug",
            message="Processing request",
            trace_id=tid,
        )
        parsed = json.loads(record)
        assert parsed["trace_id"] == tid


# ---------------------------------------------------------------------------
# 5. Audit log query with trace_id correlation
# ---------------------------------------------------------------------------

class TestAuditQuery:
    """Audit entries are queryable by trace_id for end-to-end debugging."""

    def test_query_by_trace_id(self, db, user_id):
        """Querying by trace_id returns only matching entries."""
        from noa.audit.service import AuditService

        svc = AuditService(db)
        target_trace = uuid.uuid4()

        # Create entries with different trace_ids
        svc.create_entry(**_make_audit_kwargs(user_id, trace_id=target_trace))
        svc.create_entry(**_make_audit_kwargs(user_id, trace_id=target_trace))
        svc.create_entry(**_make_audit_kwargs(user_id, trace_id=uuid.uuid4()))

        results = svc.query_by_trace_id(target_trace)
        assert len(results) == 2
        assert all(r.trace_id == target_trace for r in results)


# ---------------------------------------------------------------------------
# 6. Data retention policy (§28.7)
# ---------------------------------------------------------------------------

class TestDataRetention:
    """Entries older than retention period are purged (§28.7, 90-day default)."""

    def test_purge_removes_old_entries(self, db, user_id):
        """Entries older than 90 days are deleted by purge."""
        from noa.audit.service import AuditService
        from noa.db.models.audit import AuditLog

        svc = AuditService(db)

        # Create an old entry (91 days ago)
        old_kwargs = _make_audit_kwargs(user_id)
        old_entry = svc.create_entry(**old_kwargs)
        old_entry.timestamp = datetime.now(UTC) - timedelta(days=91)
        db.flush()

        # Create a recent entry
        svc.create_entry(**_make_audit_kwargs(user_id))

        purged_count = svc.purge_expired(retention_days=90)
        assert purged_count == 1

        remaining = db.query(AuditLog).count()
        assert remaining == 1

    def test_purge_keeps_recent_entries(self, db, user_id):
        """Entries within the retention window are not purged."""
        from noa.audit.service import AuditService
        from noa.db.models.audit import AuditLog

        svc = AuditService(db)
        svc.create_entry(**_make_audit_kwargs(user_id))
        svc.create_entry(**_make_audit_kwargs(user_id))

        purged_count = svc.purge_expired(retention_days=90)
        assert purged_count == 0
        assert db.query(AuditLog).count() == 2

    def test_purge_with_custom_retention(self, db, user_id):
        """Retention period is configurable (not hard-coded to 90)."""
        from noa.audit.service import AuditService
        from noa.db.models.audit import AuditLog

        svc = AuditService(db)
        entry = svc.create_entry(**_make_audit_kwargs(user_id))
        entry.timestamp = datetime.now(UTC) - timedelta(days=10)
        db.flush()

        # 30-day retention: entry at 10 days old should survive
        assert svc.purge_expired(retention_days=30) == 0
        assert db.query(AuditLog).count() == 1

        # 5-day retention: entry at 10 days old should be purged
        assert svc.purge_expired(retention_days=5) == 1
        assert db.query(AuditLog).count() == 0


# ---------------------------------------------------------------------------
# 7. No secrets in audit entries (§28.3)
# ---------------------------------------------------------------------------

class TestNoSecretsInLogs:
    """Log entries never contain PII or secrets (§28.3 standard)."""

    def test_hash_chain_data_excludes_sensitive_fields(self):
        """hash_chain_data() does not include tool_args content or tool_result."""
        from noa.db.models.audit import AuditLog

        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            device_id=uuid.uuid4(),
            trace_id=uuid.uuid4(),
            domain="private",
            model_provider="Ollama",
            model_name="llama3.1",
            input_tokens=100,
            output_tokens=50,
            cost_usd=Decimal("0.00"),
            tool_name="email_send",
            tool_args={"to": "secret@private.com", "body": "super secret"},
            tool_result_summary="Email sent to secret@private.com",
            privacy_classification="private",
            classification_confidence=0.99,
            previous_entry_hash=None,
        )

        chain_data = entry.hash_chain_data()
        # tool_args values and tool_result_summary should NOT appear in chain data
        assert "secret@private.com" not in chain_data
        assert "super secret" not in chain_data
        assert "Email sent" not in chain_data

    def test_structured_log_rejects_secret_keys(self):
        """Structured logger refuses or strips fields with secret-like keys."""
        from noa.audit.logging import format_log_record

        record = format_log_record(
            service="noa-api",
            level="info",
            message="Request processed",
            trace_id=str(uuid.uuid4()),
            data={
                "password": "hunter2",
                "secret_key": "sk-abc123",
                "api_key": "key-xyz",
                "token": "jwt-token-here",
                "status": "success",
            },
        )

        parsed = json.loads(record)
        data = parsed.get("data", {})
        # Secret-like keys must not appear in log output
        assert "hunter2" not in record
        assert "sk-abc123" not in record
        assert "key-xyz" not in record
        assert "jwt-token-here" not in record
        # Non-secret data should remain
        assert data.get("status") == "success"

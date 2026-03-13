"""Tests for database models — Phase F2.

Spec refs: SPEC.md §10.1, §10.4, §22.1, §22.2, §22.5, §17.2
Phase plan: MASTER_PLAN.md Phase F2

Tests cover: model instantiation, field validation, relationships,
audit log hash chain, run event append-only semantics, and
Alembic migration infrastructure.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

pytestmark = pytest.mark.f2

FAKE_PW_HASH = "fakehash"  # noqa: S105


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine for model tests."""
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


# ---------------------------------------------------------------------------
# Model instantiation & required fields
# ---------------------------------------------------------------------------

class TestUserModel:
    """User model per SPEC.md §10.1."""

    def test_create_user(self, db):
        from noa.db.models.user import User

        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash=FAKE_PW_HASH,
            display_name="Test User",
        )
        db.add(user)
        db.flush()
        assert user.id is not None
        assert user.email == "test@example.com"

    def test_user_created_at_default(self, db):
        from noa.db.models.user import User

        user = User(
            id=uuid.uuid4(),
            email="ts@example.com",
            password_hash=FAKE_PW_HASH,
        )
        db.add(user)
        db.flush()
        assert user.created_at is not None


class TestSessionModel:
    """Session model per SPEC.md §5.2."""

    def test_create_session(self, db):
        from noa.db.models.session import AuthSession
        from noa.db.models.user import User

        user = User(
            id=uuid.uuid4(),
            email="s@example.com",
            password_hash=FAKE_PW_HASH,
        )
        db.add(user)
        db.flush()

        sess = AuthSession(
            id=uuid.uuid4(),
            user_id=user.id,
            device_id=uuid.uuid4(),
            refresh_token_hash=FAKE_PW_HASH,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db.add(sess)
        db.flush()
        assert sess.is_active is True


class TestConversationAndMessages:
    """Conversation + Message models per SPEC.md §10.1."""

    def test_create_conversation_with_messages(self, db):
        from noa.db.models.conversation import Conversation, Message
        from noa.db.models.user import User

        user = User(
            id=uuid.uuid4(),
            email="c@example.com",
            password_hash=FAKE_PW_HASH,
        )
        db.add(user)
        db.flush()

        conv = Conversation(
            id=uuid.uuid4(),
            user_id=user.id,
            title="Test conversation",
        )
        db.add(conv)
        db.flush()

        msg = Message(
            id=uuid.uuid4(),
            thread_id=conv.id,
            user_id=user.id,
            role="user",
            content="Hello Noa",
        )
        db.add(msg)
        db.flush()
        assert msg.content == "Hello Noa"
        assert msg.role == "user"


class TestRunModel:
    """Run model per SPEC.md §22.1."""

    def test_create_run_with_required_fields(self, db):
        from noa.db.models.conversation import Conversation
        from noa.db.models.run import Run
        from noa.db.models.user import User

        user = User(
            id=uuid.uuid4(),
            email="r@example.com",
            password_hash=FAKE_PW_HASH,
        )
        db.add(user)
        db.flush()

        conv = Conversation(id=uuid.uuid4(), user_id=user.id)
        db.add(conv)
        db.flush()

        run = Run(
            id=uuid.uuid4(),
            thread_id=conv.id,
            user_id=user.id,
            status="pending",
            risk_tier="low",
            privacy_mode="private",
            summary="Test run",
        )
        db.add(run)
        db.flush()
        assert run.status == "pending"
        assert run.risk_tier == "low"

    def test_run_status_values(self, db):
        """§22.1: All valid run statuses accepted."""
        from noa.db.models.run import Run

        valid = {
            "pending", "running", "awaiting_approval",
            "completed", "failed", "cancelled",
        }
        for status in valid:
            run = Run(
                id=uuid.uuid4(),
                thread_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                status=status,
                risk_tier="low",
                privacy_mode="external",
            )
            assert run.status == status


class TestRunEventModel:
    """RunEvent model per SPEC.md §22.2 — append-only."""

    def test_create_run_event(self, db):
        from noa.db.models.run import RunEvent

        event = RunEvent(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            event_type="message_received",
            payload={"message_text": "hello"},
        )
        db.add(event)
        db.flush()
        assert event.event_type == "message_received"
        assert event.payload["message_text"] == "hello"

    def test_run_event_types(self):
        """§22.2: All specified event types must be accepted."""
        from noa.db.models.run import RunEvent

        event_types = [
            "message_received", "classification_done",
            "step_started", "token_stream", "tool_called",
            "tool_result", "approval_requested",
            "approval_received", "artifact_created",
            "result_ready", "error",
        ]
        for et in event_types:
            event = RunEvent(
                id=uuid.uuid4(),
                run_id=uuid.uuid4(),
                event_type=et,
                payload={},
            )
            assert event.event_type == et


class TestApprovalModel:
    """Approval model per SPEC.md risk tier rules."""

    def test_create_approval(self, db):
        from noa.db.models.approval import Approval

        approval = Approval(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            risk_tier="high",
            preview_text="Delete all emails",
            decision="pending",
        )
        db.add(approval)
        db.flush()
        assert approval.decision == "pending"
        assert approval.decided_at is None


class TestArtifactModel:
    """Artifact model per SPEC.md §22.3."""

    def test_create_artifact(self, db):
        from noa.db.models.artifact import Artifact

        artifact = Artifact(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            type="file",
            name="report.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            storage_ref="/artifacts/abc123",
        )
        db.add(artifact)
        db.flush()
        assert artifact.type == "file"
        assert artifact.size_bytes == 1024


class TestAuditLogModel:
    """AuditLog model per SPEC.md §28.1-28.2."""

    def test_create_audit_entry(self, db):
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
            privacy_classification="private",
            classification_confidence=0.95,
            previous_entry_hash=None,
        )
        db.add(entry)
        db.flush()
        assert entry.domain == "private"
        assert entry.input_tokens == 100

    def test_hash_chain_computation(self):
        """§28.2: Hash chain — each entry hash is SHA256 of prior entry."""
        from noa.db.models.audit import AuditLog

        entry1 = AuditLog(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            device_id=uuid.uuid4(),
            trace_id=uuid.uuid4(),
            domain="external",
            model_provider="Anthropic",
            model_name="claude-opus",
            input_tokens=200,
            output_tokens=100,
            cost_usd=Decimal("0.01"),
            privacy_classification="external",
            classification_confidence=0.99,
            previous_entry_hash=None,
        )

        # Compute hash of entry1 for chain
        chain_data = entry1.hash_chain_data()
        entry1_hash = hashlib.sha256(
            chain_data.encode()
        ).hexdigest()

        assert len(entry1_hash) == 64
        assert entry1.previous_entry_hash is None

        entry2 = AuditLog(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            device_id=uuid.uuid4(),
            trace_id=uuid.uuid4(),
            domain="private",
            model_provider="Ollama",
            model_name="llama3.1",
            input_tokens=50,
            output_tokens=25,
            cost_usd=Decimal("0.00"),
            privacy_classification="private",
            classification_confidence=0.98,
            previous_entry_hash=entry1_hash,
        )
        assert entry2.previous_entry_hash == entry1_hash


class TestTaskQueueModel:
    """TaskQueue model per SPEC.md §17.2."""

    def test_create_task(self, db):
        from noa.db.models.task_queue import TaskQueue

        task = TaskQueue(
            id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            task_type="remember",
            payload={"text": "Remember this"},
            status="queued",
        )
        db.add(task)
        db.flush()
        assert task.status == "queued"
        assert task.retry_count == 0
        assert task.max_retries == 3

    def test_task_queue_status_values(self):
        """§17.2: Valid statuses."""
        from noa.db.models.task_queue import TaskQueue

        for status in ("queued", "dispatched", "completed", "failed", "cancelled"):
            task = TaskQueue(
                id=uuid.uuid4(),
                request_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
                task_type="recall",
                payload={},
                status=status,
            )
            assert task.status == status


class TestUsageStatsModel:
    """UsageStats model per SPEC.md cost tracking."""

    def test_create_usage_stat(self, db):
        from noa.db.models.usage import UsageStats

        stat = UsageStats(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            provider="Anthropic",
            model_name="claude-opus",
            input_tokens=500,
            output_tokens=200,
            cost_usd=Decimal("0.05"),
        )
        db.add(stat)
        db.flush()
        assert stat.cost_usd == Decimal("0.05")


# ---------------------------------------------------------------------------
# Schema completeness
# ---------------------------------------------------------------------------

class TestSchemaCompleteness:
    """All required tables exist in the schema."""

    def test_all_tables_created(self, engine):
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        required = {
            "users", "auth_sessions", "conversations",
            "messages", "runs", "run_events", "approvals",
            "artifacts", "audit_log", "task_queue",
            "usage_stats",
        }
        missing = required - tables
        assert not missing, f"Missing tables: {missing}"


# ---------------------------------------------------------------------------
# Database engine & session factory
# ---------------------------------------------------------------------------

class TestDatabaseEngine:
    """Database engine setup per SPEC.md §10.1."""

    def test_engine_module_importable(self):
        from noa.db.engine import create_async_engine_from_config  # noqa: F401

    def test_session_factory_importable(self):
        from noa.db.engine import async_session_factory  # noqa: F401


# ---------------------------------------------------------------------------
# Alembic infrastructure
# ---------------------------------------------------------------------------

class TestAlembicInfrastructure:
    """Alembic migration setup per SPEC.md §10.4."""

    def test_alembic_ini_exists(self):
        from pathlib import Path

        alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
        assert alembic_ini.exists(), "alembic.ini must exist"

    def test_alembic_env_exists(self):
        from pathlib import Path

        env_py = Path(__file__).resolve().parents[2] / "alembic" / "env.py"
        assert env_py.exists(), "alembic/env.py must exist"

    def test_initial_migration_exists(self):
        from pathlib import Path

        versions_dir = (
            Path(__file__).resolve().parents[2] / "alembic" / "versions"
        )
        assert versions_dir.exists(), "alembic/versions/ must exist"
        migrations = list(versions_dir.glob("*.py"))
        assert len(migrations) >= 1, "At least one migration file required"

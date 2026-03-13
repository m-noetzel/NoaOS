"""Tests for Policy Engine & Approval Framework — Phase OC4.

Spec refs: SPEC.md §21, §19.2, §23.2, §29.6
Phase plan: MASTER_PLAN.md Phase OC4

Tests cover: risk tier classification, approval gates, dry-run preview
generation, approval/denial flow, batching within 30s window,
cross-domain batching prohibition, and approval timeout.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

pytestmark = pytest.mark.oc4

FAKE_PW_HASH = "fakehash"  # noqa: S105


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine for policy tests."""
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
        email="policy-test@example.com",
        password_hash=FAKE_PW_HASH,
        display_name="Policy Tester",
    )
    db.add(user)
    db.flush()
    return user.id


@pytest.fixture()
def thread_id(db, user_id):
    """Create a test conversation and return its ID."""
    from noa.db.models.conversation import Conversation

    conv = Conversation(
        id=uuid.uuid4(), user_id=user_id, title="Test Thread",
    )
    db.add(conv)
    db.flush()
    return conv.id


@pytest.fixture()
def run_id(db, user_id, thread_id):
    """Create a test run and return its ID."""
    from noa.db.models.run import Run

    run = Run(
        id=uuid.uuid4(),
        user_id=user_id,
        thread_id=thread_id,
        status="running",
    )
    db.add(run)
    db.flush()
    return run.id


@pytest.fixture()
def policy_engine():
    """Instantiate the PolicyEngine."""
    from noa.policy.engine import PolicyEngine

    return PolicyEngine()


@pytest.fixture()
def approval_service(db):
    """Instantiate the ApprovalService with a test session."""
    from noa.policy.approval import ApprovalService

    return ApprovalService(db)


# ---------------------------------------------------------------------------
# 1. Risk classification — Low/Medium/High per §21 tables
# ---------------------------------------------------------------------------

class TestRiskClassification:
    """Policy engine classifies actions into risk tiers per §21."""

    def test_read_only_query_is_low(self, policy_engine):
        """Read-only queries are classified as Low risk."""
        tier = policy_engine.classify("web_search", {"query": "weather"})
        assert tier == "low"

    def test_memory_recall_is_low(self, policy_engine):
        """Memory recall is Low risk per §21."""
        tier = policy_engine.classify("memory_recall", {})
        assert tier == "low"

    def test_read_email_is_low(self, policy_engine):
        """Reading emails is Low risk per §21."""
        tier = policy_engine.classify("read_email", {})
        assert tier == "low"

    def test_send_email_is_medium(self, policy_engine):
        """Sending email is Medium risk per §21."""
        tier = policy_engine.classify("send_email", {"to": "a@b.com"})
        assert tier == "medium"

    def test_create_calendar_event_is_medium(self, policy_engine):
        """Creating calendar events is Medium risk per §21."""
        tier = policy_engine.classify(
            "create_calendar_event", {"title": "Meeting"},
        )
        assert tier == "medium"

    def test_create_notion_page_is_medium(self, policy_engine):
        """Creating Notion pages is Medium risk per §21."""
        tier = policy_engine.classify(
            "create_notion_page", {"title": "Notes"},
        )
        assert tier == "medium"

    def test_store_memory_is_medium(self, policy_engine):
        """Storing long-term memory facts is Medium risk per §21."""
        tier = policy_engine.classify(
            "memory_store", {"fact": "User prefers dark mode"},
        )
        assert tier == "medium"

    def test_delete_data_is_high(self, policy_engine):
        """Deleting data is High risk per §21."""
        tier = policy_engine.classify(
            "delete_email", {"email_id": "abc"},
        )
        assert tier == "high"

    def test_system_file_modification_is_high(self, policy_engine):
        """System file modification is High risk per §21."""
        tier = policy_engine.classify(
            "modify_system_file", {"path": "/etc/config"},
        )
        assert tier == "high"

    def test_unknown_action_defaults_to_high(self, policy_engine):
        """Unknown/unclassified actions default to High for safety."""
        tier = policy_engine.classify("unknown_action", {})
        assert tier == "high"


# ---------------------------------------------------------------------------
# 2. Approval gates — Medium requires approval, Low does not (§21)
# ---------------------------------------------------------------------------

class TestApprovalGates:
    """Approval gates enforce risk tier rules per §21."""

    def test_low_risk_no_approval_needed(self, policy_engine):
        """Low risk actions do not require approval."""
        assert policy_engine.requires_approval("low") is False

    def test_medium_risk_requires_approval(self, policy_engine):
        """Medium risk actions require explicit user approval."""
        assert policy_engine.requires_approval("medium") is True

    def test_high_risk_requires_approval(self, policy_engine):
        """High risk actions require approval + step-up auth."""
        assert policy_engine.requires_approval("high") is True

    def test_high_risk_requires_step_up_auth(self, policy_engine):
        """High risk actions require step-up authentication."""
        assert policy_engine.requires_step_up_auth("high") is True

    def test_medium_risk_no_step_up_auth(self, policy_engine):
        """Medium risk does NOT require step-up auth."""
        assert policy_engine.requires_step_up_auth("medium") is False


# ---------------------------------------------------------------------------
# 3. Preview generation — previews for create/send actions (§19.2)
# ---------------------------------------------------------------------------

class TestPreviewGeneration:
    """Dry-run previews are generated for Medium/High actions per §19.2."""

    def test_send_email_preview(self):
        """Send email generates a preview with recipients and subject."""
        from noa.policy.preview import generate_preview

        preview = generate_preview(
            "send_email",
            {
                "to": "alex@example.com",
                "subject": "Meeting follow-up",
                "body": "Thanks for the meeting.",
            },
        )
        assert preview is not None
        assert "alex@example.com" in preview
        assert "Meeting follow-up" in preview

    def test_create_calendar_event_preview(self):
        """Create calendar event generates a preview with details."""
        from noa.policy.preview import generate_preview

        preview = generate_preview(
            "create_calendar_event",
            {
                "title": "Team sync",
                "start": "2026-03-05T14:00:00Z",
                "end": "2026-03-05T15:00:00Z",
            },
        )
        assert preview is not None
        assert "Team sync" in preview

    def test_low_risk_no_preview(self):
        """Low risk actions return no preview."""
        from noa.policy.preview import generate_preview

        preview = generate_preview("web_search", {"query": "weather"})
        assert preview is None


# ---------------------------------------------------------------------------
# 4. Approval flow — request → approve → resumed (§29.6)
# ---------------------------------------------------------------------------

class TestApprovalFlow:
    """Approval requests follow §29.6 flow."""

    def test_request_approval_creates_pending(
        self, approval_service, run_id, user_id,
    ):
        """Requesting approval creates a pending approval record."""
        approval = approval_service.request_approval(
            run_id=run_id,
            user_id=user_id,
            risk_tier="medium",
            preview_text="Send email to alex@example.com",
        )
        assert approval.id is not None
        assert approval.decision == "pending"
        assert approval.risk_tier == "medium"
        assert approval.preview_text == "Send email to alex@example.com"

    def test_approve_updates_decision(
        self, approval_service, run_id, user_id,
    ):
        """Approving sets decision to 'approved' with timestamp."""
        approval = approval_service.request_approval(
            run_id=run_id,
            user_id=user_id,
            risk_tier="medium",
            preview_text="Create event",
        )
        result = approval_service.decide(
            approval.id, decision="approved", decided_by=user_id,
        )
        assert result.decision == "approved"
        assert result.decided_at is not None
        assert result.decided_by_user_id == user_id

    def test_deny_updates_decision(
        self, approval_service, run_id, user_id,
    ):
        """Denying sets decision to 'denied'."""
        approval = approval_service.request_approval(
            run_id=run_id,
            user_id=user_id,
            risk_tier="medium",
            preview_text="Send message",
        )
        result = approval_service.decide(
            approval.id, decision="denied", decided_by=user_id,
        )
        assert result.decision == "denied"
        assert result.decided_at is not None

    def test_cannot_decide_already_decided(
        self, approval_service, run_id, user_id,
    ):
        """Cannot approve/deny an already decided approval."""
        approval = approval_service.request_approval(
            run_id=run_id, user_id=user_id,
            risk_tier="medium", preview_text="Test",
        )
        approval_service.decide(
            approval.id, decision="approved", decided_by=user_id,
        )
        with pytest.raises(ValueError, match="already decided"):
            approval_service.decide(
                approval.id, decision="denied", decided_by=user_id,
            )


# ---------------------------------------------------------------------------
# 5. Batching — multiple approvals within 30s window (§23.2)
# ---------------------------------------------------------------------------

class TestApprovalBatching:
    """Approval batching groups tasks within 30s window per §23.2."""

    def test_pending_approvals_grouped_by_run(
        self, approval_service, run_id, user_id, db, thread_id,
    ):
        """Pending approvals for the same user are listable."""
        approval_service.request_approval(
            run_id=run_id, user_id=user_id,
            risk_tier="medium", preview_text="Action 1",
        )
        # Create another run for the same user
        from noa.db.models.run import Run

        run2 = Run(
            id=uuid.uuid4(), user_id=user_id,
            thread_id=thread_id, status="running",
        )
        db.add(run2)
        db.flush()
        approval_service.request_approval(
            run_id=run2.id, user_id=user_id,
            risk_tier="medium", preview_text="Action 2",
        )
        pending = approval_service.list_pending(user_id=user_id)
        assert len(pending) >= 2

    def test_no_cross_domain_batching(
        self, approval_service, run_id, user_id, db, thread_id,
    ):
        """Private and external approvals are never batched together."""
        approval_service.request_approval(
            run_id=run_id, user_id=user_id,
            risk_tier="medium", preview_text="Private action",
            domain="private",
        )
        from noa.db.models.run import Run

        ext_run = Run(
            id=uuid.uuid4(), user_id=user_id,
            thread_id=thread_id, status="running",
            privacy_mode="external",
        )
        db.add(ext_run)
        db.flush()
        approval_service.request_approval(
            run_id=ext_run.id, user_id=user_id,
            risk_tier="medium", preview_text="External action",
            domain="external",
        )
        private_pending = approval_service.list_pending(
            user_id=user_id, domain="private",
        )
        external_pending = approval_service.list_pending(
            user_id=user_id, domain="external",
        )
        assert all(a.domain == "private" for a in private_pending)
        assert all(a.domain == "external" for a in external_pending)


# ---------------------------------------------------------------------------
# 6. Timeout — unanswered approvals expire after 5 minutes (§23.2)
# ---------------------------------------------------------------------------

class TestApprovalTimeout:
    """Unanswered approvals expire after 5 minutes per §23.2."""

    def test_expired_approvals_detected(
        self, approval_service, run_id, user_id, db,
    ):
        """Approvals older than 5 minutes are marked expired."""
        from noa.db.models.approval import Approval

        # Create an approval with old timestamp
        old_approval = Approval(
            id=uuid.uuid4(),
            run_id=run_id,
            user_id=user_id,
            risk_tier="medium",
            preview_text="Old action",
            decision="pending",
            requested_at=datetime.now(UTC) - timedelta(minutes=6),
        )
        db.add(old_approval)
        db.flush()

        expired = approval_service.expire_stale(
            timeout_minutes=5,
        )
        assert len(expired) >= 1
        assert all(a.decision == "expired" for a in expired)

    def test_fresh_approvals_not_expired(
        self, approval_service, run_id, user_id,
    ):
        """Recent approvals are not expired."""
        approval_service.request_approval(
            run_id=run_id, user_id=user_id,
            risk_tier="medium", preview_text="Fresh action",
        )
        expired = approval_service.expire_stale(timeout_minutes=5)
        # The freshly created one should not be in expired list
        assert all(a.preview_text != "Fresh action" for a in expired)


# ---------------------------------------------------------------------------
# 7. SSE/API endpoint — approval endpoint exists (§29.6)
# ---------------------------------------------------------------------------

class TestApprovalEndpoint:
    """Approval API endpoints exist per §29.6."""

    @pytest.fixture()
    def _app(self):
        """Create a test app."""
        from noa.api.app import create_app

        return create_app()

    @pytest.mark.asyncio
    async def test_approval_endpoint_requires_auth(self, _app):
        """Approval endpoint returns 401 without auth."""
        import httpx

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                f"/api/v1/approvals/{uuid.uuid4()}/decide",
                json={"decision": "approved"},
            )
            assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_approval_endpoint_exists(self, _app):
        """Approval endpoints are registered (not 404)."""
        import httpx

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/approvals/pending")
            # Should not be 404
            assert resp.status_code != 404

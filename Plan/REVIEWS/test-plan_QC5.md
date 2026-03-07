# Test Plan: Phase QC5 — Database & Data Integrity

**Date:** 2026-03-07
**Phase:** QC5
**Reviewer:** qa-review agent (pre-implementation)
**Findings addressed:** H2, M3, M6, M9, M12

---

## Overview

QC5 fixes five distinct data-layer issues. Each is independent; they share no common code path. The test file for this phase should be `tests/unit/test_qc5_data_integrity.py`.

All tests must carry a docstring citing the spec section or finding ID (M1 requirement).

---

## Pre-Implementation Code Analysis

### H2 — Missing Indexes
The existing migrations `001`–`005` contain zero `op.create_index()` calls. Seven indexes are absent. The new migration `006_performance_indexes.py` must add them. There are no tests for migration content at all today — the test must assert the migration exists and its `upgrade()` produces the correct `CreateIndex` ops.

### M3 — `_PurgeProxy` always skips purge
`app.py:196-215` instantiates `_PurgeProxy` instead of the real `AuditService`. `_PurgeProxy.purge_expired()` always returns 0 and logs "purge skipped". The real `AuditService.purge_expired()` is sync-only; the fix must make it either async or dispatch it via `asyncio.to_thread`. The existing `test_retention.py` tests mock the audit service entirely — they would pass even with `_PurgeProxy`. New tests must verify the actual `AuditService.purge_expired_async()` (or equivalent) deletes rows from the database.

### M6 — `expire_stale()` never called
`ApprovalService.expire_stale()` exists at `policy/approval.py:77` but is never invoked by any scheduler, lifespan, or background task. The fix must wire it into either the `RetentionScheduler` or a new dedicated scheduler. Tests must verify the wiring: that a stale approval becomes `expired` via the periodic task, not just by calling `expire_stale()` directly.

### M9 — `violation_count` returns all-time total
`ContractViolationTracker.violation_count` at `rpc.py:237` returns `len(self._violations)` — all violations ever recorded, not just those within the 24-hour window. `_window_seconds = 24 * 60 * 60` is defined but never used in the `violation_count` property. Existing tests in `test_private_worker.py:388–438` **pass against the broken implementation** because they add exactly 1, 2, or 3 violations without testing the window. The fix must add timestamp-based filtering. Tests must inject synthetic timestamps to verify the window boundary is enforced.

### M12 — Mixed sync/async service layer
`RunService.__init__` accepts `Session` (sync SQLAlchemy ORM). `OrchestratorRunner._persist_event()` calls `run_service.append_event()` synchronously inside an async context. `chat.py:142-155` calls `session = factory()` (calling an `AsyncSessionFactory` without `async with`) to get a sync session for `RunService`. The fix standardises `RunService` on `AsyncSession`. Tests must verify `RunService` methods work with a real `AsyncSession` in async tests (not just mocked).

---

## Test Specification

### File: `tests/unit/test_qc5_data_integrity.py`

```
Spec refs: SPEC.md §9.4 (M9), §23.2 (M6), §28.7 (M3), §28.7 (H2)
Phase plan: PLAN.md QC5
```

---

### Section 1: H2 — Migration 006 Performance Indexes

**Requirement:** `alembic/versions/006_performance_indexes.py` must exist and create exactly 7 indexes.

#### Test 1.1 — Migration file exists and is importable
```
class TestMigration006:
    def test_migration_module_importable(self):
        """H2: Migration 006 must exist and import without error."""
        import importlib
        mod = importlib.import_module("alembic.versions.006_performance_indexes")
        assert hasattr(mod, "upgrade")
        assert hasattr(mod, "downgrade")
        assert mod.revision == "006"
        assert mod.down_revision == "005"
```

**Why:** Verifies the migration exists, has correct revision chain, and is syntactically valid.

#### Test 1.2 — Upgrade creates all 7 expected indexes
```
    def test_upgrade_creates_audit_log_timestamp_index(self):
        """H2: audit_log(timestamp) index must be created."""
        import inspect
        from alembic.versions import migration_006 as m
        src = inspect.getsource(m.upgrade)
        assert "audit_log" in src
        assert "timestamp" in src

    def test_upgrade_creates_audit_log_user_id_index(self):
        """H2: audit_log(user_id) index must be created."""
        ...

    def test_upgrade_creates_audit_log_trace_id_index(self):
        """H2: audit_log(trace_id) index must be created."""
        ...

    def test_upgrade_creates_messages_thread_id_index(self):
        """H2: messages(thread_id) index must be created."""
        ...

    def test_upgrade_creates_run_events_run_id_index(self):
        """H2: run_events(run_id) index must be created."""
        ...

    def test_upgrade_creates_usage_stats_composite_index(self):
        """H2: usage_stats(user_id, timestamp) composite index must be created."""
        ...

    def test_upgrade_creates_task_queue_composite_index(self):
        """H2: task_queue(status, queued_at) composite index must be created."""
        ...
```

**Why:** Source inspection tests are weak (they pass if the word appears anywhere in the file) but they are fast and catch the common failure where a developer adds some but not all indexes. Pair with the downgrade test below.

#### Test 1.3 — Downgrade drops all created indexes (S3: reversibility)
```
    def test_downgrade_drops_all_indexes(self):
        """H2 / S3: downgrade() must drop all 7 indexes."""
        import inspect
        from alembic.versions import migration_006 as m
        src = inspect.getsource(m.downgrade)
        assert "drop_index" in src or "drop_constraint" in src
```

**Negative test (M2):** The downgrade must not be a no-op.

#### Test 1.4 — Integration: indexes present in real SQLite schema (S5)
```
    def test_indexes_applied_to_in_memory_db(self):
        """H2/S5: Running upgrade() against a real DB creates the expected indexes."""
        # Use alembic's MigrationContext or SQLAlchemy inspector on an
        # in-memory SQLite database that has been migrated through 005.
        # Verify inspector.get_indexes("audit_log") contains timestamp index.
```

**Why this is critical:** Source inspection tests pass even if `op.create_index(...)` has a typo in the table name. An integration test against a real database backend is the only way to verify the DDL is actually correct. This satisfies S5.

**Determinism note (M4):** No wall-clock time, no network. Pure SQLite in-memory.

---

### Section 2: M3 — Async Audit Purge

**Requirement:** `AuditService.purge_expired()` must be callable from an async context and must actually delete rows. The `_PurgeProxy` workaround must be removed.

#### Test 2.1 — `purge_expired_async` exists and is a coroutine
```
class TestAuditPurgeAsync:
    def test_purge_expired_async_is_coroutine(self):
        """M3: AuditService must expose an async purge method."""
        import asyncio
        from noa.audit.service import AuditService
        svc = AuditService()
        assert asyncio.iscoroutinefunction(svc.purge_expired_async)
```

**Note:** If the implementation renames the method (e.g. keeps `purge_expired` but makes it a coroutine), this test should be adjusted accordingly. Either way, the method must be awaitable.

#### Test 2.2 — Purge deletes rows older than cutoff (M2 / negative path)
```
    @pytest.mark.asyncio
    async def test_purge_deletes_old_entries(self):
        """M3/§28.7: Entries older than retention_days are deleted."""
        # Setup: in-memory async SQLite (aiosqlite).
        # Insert 2 entries with timestamp = now - 100 days (outside window).
        # Insert 1 entry with timestamp = now - 10 days (inside window).
        # Call purge_expired_async(retention_days=90) via AsyncSession.
        # Assert: 2 entries deleted, 1 remains.
        ...
```

**Critical point:** This test must use a real `AsyncSession` against an in-memory DB with real rows. It must NOT mock the session. This is the only way to verify the SQL `DELETE WHERE timestamp < cutoff` is actually correct.

#### Test 2.3 — Purge preserves entries within retention window
```
    @pytest.mark.asyncio
    async def test_purge_preserves_recent_entries(self):
        """M3/§28.7: Entries within retention window are not deleted."""
        # Insert 3 entries with timestamp = now - 10 days.
        # Call purge_expired_async(retention_days=90).
        # Assert: 0 entries deleted, all 3 remain.
        ...
```

#### Test 2.4 — Purge with empty table returns 0
```
    @pytest.mark.asyncio
    async def test_purge_empty_table_returns_zero(self):
        """M3: Purging an empty table returns 0 (no crash)."""
        ...
```

**Negative test (M2):** Edge case — empty database must not raise.

#### Test 2.5 — `_PurgeProxy` is removed / no longer used in app.py (wiring check)
```
    def test_purge_proxy_not_in_app_module(self):
        """M3/M7: app.py must not contain _PurgeProxy — real async purge must be wired."""
        import inspect
        from noa.api import app as app_module
        src = inspect.getsource(app_module)
        assert "_PurgeProxy" not in src, (
            "_PurgeProxy still present in app.py — retention purge is still broken"
        )
```

**Why this test is mandatory:** The existing `test_retention.py` tests all mock the audit service, so they pass regardless of whether `_PurgeProxy` is in the app. This test directly checks the wiring fix.

#### Test 2.6 — RetentionScheduler in app lifespan actually calls async purge
```
    @pytest.mark.asyncio
    async def test_retention_scheduler_wired_to_real_audit_service(self):
        """M3/M7: RetentionScheduler in lifespan must use AuditService, not _PurgeProxy."""
        # Create AuditService with an AsyncSession factory.
        # Wire it to RetentionScheduler.
        # Call run_once().
        # Verify purge_expired_async (or async purge variant) was awaited.
        ...
```

**Determinism (M4):** Mock `datetime.now()` so the cutoff is predictable.

---

### Section 3: M6 — Approval Expiry Wired to Scheduler

**Requirement:** `expire_stale()` must be called periodically. Stale pending approvals must transition to `expired` automatically.

#### Test 3.1 — `expire_stale()` marks old pending approvals as expired
```
class TestApprovalExpiryWiring:
    def test_expire_stale_marks_old_approval_expired(self):
        """M6/§23.2: expire_stale() transitions pending approvals to expired."""
        # Use SQLite in-memory with sync Session.
        # Insert an Approval with requested_at = now - 10 minutes.
        # Call expire_stale(timeout_minutes=5).
        # Assert approval.decision == "expired".
        ...
```

#### Test 3.2 — Recent approvals are not expired
```
    def test_expire_stale_preserves_recent_approval(self):
        """M6/§23.2: Approvals within timeout are not expired."""
        # Insert Approval with requested_at = now - 1 minute.
        # Call expire_stale(timeout_minutes=5).
        # Assert approval.decision == "pending".
        ...
```

**Negative test (M2):** The boundary condition must be tested explicitly.

#### Test 3.3 — Already-decided approvals are not touched
```
    def test_expire_stale_ignores_decided_approvals(self):
        """M6/§23.2: Approvals with decision != pending are not re-expired."""
        # Insert Approval(decision="approved", requested_at=now-10min).
        # Call expire_stale(timeout_minutes=5).
        # Assert decision is still "approved" (not changed to "expired").
        ...
```

**Negative test (M2):** Important edge case — idempotency.

#### Test 3.4 — expire_stale is wired into a periodic background task
```
    @pytest.mark.asyncio
    async def test_expire_stale_called_by_scheduler(self):
        """M6/M7: A background task or scheduler must call expire_stale() periodically."""
        # Options (implementation-dependent):
        # (a) If wired into RetentionScheduler with a second service slot:
        #     verify the scheduler holds an ApprovalService reference and calls expire_stale.
        # (b) If a new ApprovalExpiryScheduler is created in app.py lifespan:
        #     verify it starts in lifespan and calls expire_stale on run_once().
        # Either way: test that the call actually happens, not just that the
        # method exists.
        ...
```

**Why mandatory:** M6 finding is specifically that `expire_stale()` is defined but never called. A test that only calls `expire_stale()` directly does NOT verify the wiring fix — it only tests the method itself, which already worked.

#### Test 3.5 — Wiring confirmed in app module source (belt-and-suspenders)
```
    def test_expire_stale_referenced_in_app(self):
        """M6/M7: app.py lifespan must reference expire_stale or ApprovalExpiryScheduler."""
        import inspect
        from noa.api import app as app_module
        src = inspect.getsource(app_module)
        assert "expire_stale" in src or "ApprovalExpiryScheduler" in src, (
            "expire_stale not wired into app lifespan — M6 not fixed"
        )
```

---

### Section 4: M9 — ContractViolationTracker 24-Hour Window

**Requirement:** `violation_count` must return only violations within the last 24 hours. The `_window_seconds` field must be used in the calculation.

#### Test 4.1 — violation_count excludes violations outside the 24-hour window
```
class TestViolationWindow:
    def test_old_violations_excluded_from_count(self):
        """M9/§9.4: violation_count must only count within 24h window."""
        from noa.private_worker.rpc import ContractViolationTracker
        import time

        tracker = ContractViolationTracker()
        # Inject a violation with a timestamp 25 hours in the past
        tracker._violations.append({
            "type": "oversized",
            "details": "old",
            "timestamp": time.monotonic() - (25 * 3600),
        })
        # Add two recent violations
        tracker.record_violation("oversized", "recent 1")
        tracker.record_violation("oversized", "recent 2")

        assert tracker.violation_count == 2, (
            "Old violation outside 24h window must not be counted"
        )
```

**Why this is the critical test:** This is the exact bug described in M9. The existing tests in `test_private_worker.py` pass against the BROKEN implementation because they never add old violations. This test would fail against the current code (violation_count returns 3, not 2).

#### Test 4.2 — violation_count returns 0 when all violations are expired
```
    def test_all_expired_violations_gives_zero_count(self):
        """M9/§9.4: All violations outside 24h window yields count 0."""
        from noa.private_worker.rpc import ContractViolationTracker
        import time

        tracker = ContractViolationTracker()
        for _ in range(5):
            tracker._violations.append({
                "type": "oversized",
                "details": "stale",
                "timestamp": time.monotonic() - (48 * 3600),
            })
        assert tracker.violation_count == 0
        assert tracker.should_alert is False
        assert tracker.should_pause_worker is False
```

#### Test 4.3 — should_alert triggers only on 3+ violations WITHIN window
```
    def test_alert_triggers_only_for_violations_within_window(self):
        """M9/§9.4: 3 old + 2 recent = count 2 = no alert."""
        from noa.private_worker.rpc import ContractViolationTracker
        import time

        tracker = ContractViolationTracker()
        # 3 old violations (outside window)
        for _ in range(3):
            tracker._violations.append({
                "type": "oversized",
                "details": "old",
                "timestamp": time.monotonic() - (25 * 3600),
            })
        # 2 recent violations (within window)
        tracker.record_violation("oversized", "recent 1")
        tracker.record_violation("oversized", "recent 2")

        assert tracker.violation_count == 2
        assert tracker.should_alert is False
```

**Negative test (M2):** 3 total but only 2 recent — must NOT alert.

#### Test 4.4 — Boundary: violation exactly at 24-hour mark
```
    def test_violation_exactly_at_window_boundary(self):
        """M9/§9.4: Violation at exactly 24h should be excluded (strictly less than window)."""
        from noa.private_worker.rpc import ContractViolationTracker
        import time

        tracker = ContractViolationTracker()
        tracker._violations.append({
            "type": "oversized",
            "details": "boundary",
            "timestamp": time.monotonic() - (24 * 3600),
        })
        # Boundary behavior: either excluded or included is acceptable,
        # but must be deterministic and documented.
        # The count must be 0 or 1 — not an error.
        count = tracker.violation_count
        assert count in (0, 1)
```

**Why:** Boundary conditions are the most common source of off-by-one bugs in time-window implementations.

#### Test 4.5 — record_violation timestamps use monotonic (not wall clock)
```
    def test_record_violation_uses_monotonic_clock(self):
        """M9: Timestamps stored in violations must use time.monotonic()."""
        from noa.private_worker.rpc import ContractViolationTracker
        import time

        before = time.monotonic()
        tracker = ContractViolationTracker()
        tracker.record_violation("test", "details")
        after = time.monotonic()

        ts = tracker._violations[0]["timestamp"]
        assert before <= ts <= after
```

**Why:** The current code uses `time.monotonic()` (correct for relative window calculation). If someone "fixes" M9 by switching to `time.time()` (wall clock), that is a different kind of correctness issue. This test guards against that regression.

---

### Section 5: M12 — Async RunService

**Requirement:** `RunService` must accept `AsyncSession`. Sync methods that call `self._session.query(...)` must be replaced with async equivalents using `select()`. `OrchestratorRunner` must `await` persistence calls.

#### Test 5.1 — RunService accepts AsyncSession
```
class TestRunServiceAsync:
    @pytest.mark.asyncio
    async def test_runservice_accepts_async_session(self):
        """M12: RunService.__init__ must accept AsyncSession without TypeError."""
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
        from noa.runs.service import RunService

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        # Create tables
        async with engine.begin() as conn:
            from noa.db.models.base import Base
            await conn.run_sync(Base.metadata.create_all)

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            svc = RunService(session)
            assert svc is not None
```

**Smoke test (S5):** If `RunService.__init__` still has `session: Session` type annotation (sync-only), this test still passes because Python doesn't enforce type annotations at runtime. The subsequent tests below ensure the actual operations work.

#### Test 5.2 — create_run works with AsyncSession end-to-end (S5)
```
    @pytest.mark.asyncio
    async def test_create_run_with_async_session(self):
        """M12/§22.1: create_run() must work end-to-end with AsyncSession."""
        # Use in-memory aiosqlite. Create tables via Base.metadata.
        # Instantiate RunService with real AsyncSession.
        # Call await svc.create_run(user_id=..., thread_id=...) .
        # Assert the returned Run has status="pending".
        # Assert the row is present in the DB via a separate query.
        ...
```

**Critical:** This is NOT mocked. This tests the actual SQL path.

#### Test 5.3 — append_event works with AsyncSession
```
    @pytest.mark.asyncio
    async def test_append_event_with_async_session(self):
        """M12/§22.2: append_event() must work with AsyncSession."""
        ...
```

#### Test 5.4 — update_status works with AsyncSession and enforces transitions
```
    @pytest.mark.asyncio
    async def test_update_status_enforces_valid_transitions_async(self):
        """M12/§22.1: Invalid status transition raises ValueError via AsyncSession."""
        # Create run (status=pending).
        # Call update_status(run_id, "completed") — invalid transition pending→completed.
        # Assert ValueError is raised.
        ...
```

**Negative test (M2):** The transition validation logic must still work with the async implementation.

#### Test 5.5 — Sync `Session` import removed from RunService
```
    def test_runservice_does_not_import_sync_session(self):
        """M12: RunService must not import sqlalchemy.orm.Session (sync-only)."""
        import inspect
        from noa.runs import service as rs_module
        src = inspect.getsource(rs_module)
        # Must not import sync Session for RunService constructor
        assert "from sqlalchemy.orm import Session" not in src, (
            "RunService still imports sync Session — M12 not fully fixed"
        )
```

**Note on false positives:** This test will flag if `Session` is imported but not used for `RunService`. If the file has other sync-session uses (e.g. helper functions), the test must be more targeted. Adjust to check the `RunService.__init__` signature specifically.

#### Test 5.6 — AuditService sync methods removed (M12 scope covers AuditService)
```
    def test_audit_service_sync_methods_removed(self):
        """M12: AuditService.create_entry() (sync) and query_by_trace_id() (sync)
        must be removed — only async variants remain."""
        from noa.audit.service import AuditService
        import asyncio
        svc = AuditService()
        # create_entry must not exist OR must be a coroutine
        if hasattr(svc, "create_entry"):
            assert asyncio.iscoroutinefunction(svc.create_entry), (
                "create_entry still sync — M12 not fixed in AuditService"
            )
        # query_by_trace_id must not exist OR must be a coroutine
        if hasattr(svc, "query_by_trace_id"):
            assert asyncio.iscoroutinefunction(svc.query_by_trace_id)
```

#### Test 5.7 — OrchestratorRunner calls await on run_service operations
```
    @pytest.mark.asyncio
    async def test_orchestrator_runner_awaits_run_service(self):
        """M12: OrchestratorRunner must await async RunService methods."""
        from unittest.mock import AsyncMock, MagicMock
        from noa.orchestrator.runner import OrchestratorRunner

        # Mock graph that returns immediately
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "response": "hello",
            "total_cost": 0.0,
            "llm_usage": [],
            "tool_calls": [],
            "tool_results": [],
        })

        # AsyncMock run_service — if runner uses sync calls, this will fail
        run_svc = MagicMock()
        run_svc.update_status = AsyncMock()
        run_svc.append_event = AsyncMock()

        runner = OrchestratorRunner(graph=mock_graph)
        events = []
        async for event in runner.run(
            message="test",
            run_service=run_svc,
            run_id="fake-run-id",
        ):
            events.append(event)

        # If runner is still calling sync methods on AsyncMock, calls won't be awaited
        run_svc.update_status.assert_awaited()
```

**Why this test is important:** If `OrchestratorRunner._persist_event()` still calls `run_service.append_event()` synchronously (not `await`), and `run_service` is now an async service, the call will return a coroutine that is never awaited — silently dropping all events. This is a regression risk if M12 is implemented partially.

---

## Determinism Requirements (M4)

All tests in this file must:

1. Never call `datetime.now()` without either injecting the datetime or mocking it. For tests that need specific timestamps (M3 purge cutoff, M6 expiry cutoff), freeze time via `unittest.mock.patch("noa.audit.service.datetime")` or equivalent.
2. Never depend on real wall-clock elapsed time for the M9 window tests — inject timestamps directly into `tracker._violations` to avoid timing races.
3. Use in-memory SQLite (`sqlite+aiosqlite:///:memory:` for async, `sqlite:///:memory:` for sync) — no network, no Docker dependency.
4. Run 3x in sequence and produce the same result.

---

## Non-Mocked Integration Test Requirement (S5)

Per project rules, at least one test per phase must call real code without mocking internal dependencies. For QC5, this requirement is satisfied by:

- **Test 1.4** (Migration 006 applied to real in-memory DB → indexes verified via inspector)
- **Test 2.2** (AuditService.purge_expired_async with real AsyncSession and real rows)
- **Test 5.2** (RunService.create_run with real AsyncSession against in-memory SQLite)

---

## Coverage Map

| Finding | Spec Ref | Tests |
|---------|----------|-------|
| H2: missing indexes | FINDINGS.md H2 | 1.1, 1.2 (×7), 1.3, 1.4 |
| M3: purge proxy | SPEC.md §28.7 | 2.1, 2.2, 2.3, 2.4, 2.5, 2.6 |
| M6: expire_stale unwired | SPEC.md §23.2 | 3.1, 3.2, 3.3, 3.4, 3.5 |
| M9: all-time violation count | SPEC.md §9.4 | 4.1, 4.2, 4.3, 4.4, 4.5 |
| M12: sync/async mismatch | FINDINGS.md M12 | 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7 |

**Total required tests: ~30**
**Blocking (red-phase must fail before fix):** Tests 2.5, 3.5, 4.1, 4.2, 4.3, 5.7

---

## Critical Trap: Tests That Pass Against Broken Code

The following tests, if written naively, will pass against the CURRENT broken implementation and are therefore insufficient alone:

| Naive test | Why it passes on broken code | How to fix |
|---|---|---|
| `assert tracker.violation_count == 3` after adding 3 violations | Current code counts all-time — would always be 3 | Must inject old violations and assert they are excluded |
| `assert AuditService().purge_expired(...)` returns int | Method exists and returns an int — it just deletes 0 rows | Test against real DB with real rows outside the window |
| `assert ApprovalService.expire_stale(...)` returns list | Method exists and works — it's just never called | Test that the scheduler actually calls it |
| `RunService(session)` with mock session | Constructor accepts anything — type not enforced | Test actual SQL operations with AsyncSession |

---

## Edge Cases Checklist (S1)

- [ ] **M3:** Purge when table is empty → must return 0, not raise
- [ ] **M3:** Purge with `retention_days=0` → all entries should be deleted (boundary)
- [ ] **M6:** `expire_stale()` when no pending approvals → returns empty list, no crash
- [ ] **M6:** `expire_stale()` when all pending are recent → returns empty list
- [ ] **M9:** Violation count exactly at 24h boundary → deterministic (not time-dependent)
- [ ] **M9:** `_violations` list is empty → `violation_count == 0`, `should_alert == False`
- [ ] **M12:** `RunService.get_run()` returns `None` for non-existent ID (not raises)
- [ ] **M12:** `append_event()` with invalid event_type raises `ValueError` even with AsyncSession

---

## Security Notes (M3)

The async purge fix must not introduce a new exception swallowing pattern. The current `RetentionScheduler._loop()` catches `Exception` broadly at line 68 (`logger.exception(...)`) — this is acceptable per L9 rule 2 (logs with trace). The new async purge must not add a `except Exception: pass` variant.

---

## Wiring Checks for QA Review (M7)

After implementation, the QA review should verify:

1. `grep -n "_PurgeProxy" src/noa/api/app.py` → must return no matches
2. `grep -n "expire_stale\|ApprovalExpiryScheduler" src/noa/api/app.py` → must return at least one match
3. `grep -n "AsyncSession" src/noa/runs/service.py` → must return matches (RunService now uses async)
4. `grep -rn "from sqlalchemy.orm import Session" src/noa/runs/service.py` → must return no matches (or only as type alias for backward compat)
5. `grep -n "_window_seconds\|window_seconds" src/noa/private_worker/rpc.py` → must appear in `violation_count` property body

---

## Dependencies

The following test dependencies must be available:
- `pytest-asyncio` (already in use in test_retention.py)
- `aiosqlite` (for async SQLite in-memory; verify it is in pyproject.toml)
- `alembic` (for migration import in Section 1)

Check `pyproject.toml` before writing tests. If `aiosqlite` is missing, add it to dev dependencies before writing Section 2/5 async integration tests.

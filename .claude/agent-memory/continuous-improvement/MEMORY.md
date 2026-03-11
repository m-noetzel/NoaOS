# CI Agent Memory

## Project Context
- Codebase: NoaOS (governed personal AI agent, Python backend + Swift iOS + React frontend)
- Planning artifacts under Plan/. CI analyses go in Plan/CI/.
- IMPROVEMENT_BACKLOG.md is the living tracker (CI-001 through CI-015 as of 2026-03-11 PR2 cycle).

## Backlog State (as of 2026-03-11 PR2 cycle)
- CI-001 to CI-007: PROPOSED 2026-03-07, none applied yet (from Insights Report analysis)
- CI-008, CI-010, CI-011: PROPOSED 2026-03-11 (from PR1 QA cycle), not applied
- CI-009: APPLIED 2026-03-11 (L12 Write-Path User Scoping in ARCH_INVARIANTS.md)
- CI-012 to CI-015: PROPOSED 2026-03-11 (from PR2 QA cycle), not applied
- CI-013 is P1 (human gate required): FINDINGS.md Currency Gate (M5b)

## Confirmed Systemic Patterns

### Pattern: AsyncMock on Sync SQLAlchemy Methods (16+ files)
- `session = AsyncMock()` used throughout tests. `session.add()` is sync; calling it on AsyncMock emits RuntimeWarning.
- Correct pattern: `session = MagicMock(spec=AsyncSession)` with `session.execute = AsyncMock(...)` and `session.flush = AsyncMock(...)`.
- Addressed by CI-008 (M4b gate). Not yet applied.
- PR2 test file continues pattern: test_pr2_frontend_fixes.py lines 95, 128, 158, 199.

### Pattern: Write-Path Missing user_id (Store Without Scoping)
- Storage calls omit user_id; read path filters by user_id. The two paths are disconnected.
- Instances: MemoryStore.store() (BE-M5, handlers.py:35), _credential_store dict (TM1).
- CI-009 (L12) APPLIED. CI-011 (M3b QA check) PROPOSED. BE-M5 fix scheduled for PR4.

### Pattern: S5 Integration Smoke Test Persistently OPEN
- S5 OPEN in 18 of 26 reviewed QA reports (PR1 + PR2 added to prior 17/25 count).
- Wave 19 consecutive OPEN count: PR1=1, PR2=2. Trigger threshold (CI-010) = 3 consecutive.
- If PR3 returns S5 OPEN, escalate CI-010 to P1 immediately.

### Pattern: Source-Text-Scanning Tests as Behavioral Proxies (4+ phases)
- Python tests read .tsx source files and assert string presence/absence.
- Appears in: QC6, QC7, iOS11, PR2. At least 4 phases affected.
- These verify source edits were made but do not execute code paths.
- Addressed by CI-012 (S5b Frontend Fix Behavioral Coverage Gate). PROPOSED, not applied.

### Pattern: FINDINGS.md Drift (new, P1)
- FINDINGS.md accumulated 7 stale entries across PR1 + PR2 (3 from PR1, 4 from PR2).
- Stale entries: BE-C1, BE-C2, BE-H2 (resolved PR1), BE-H3, FE-C1, FE-H1, FE-H2 (resolved PR2).
- No QA gate enforces FINDINGS.md currency before phase completion.
- Addressed by CI-013 (M5b QA gate, P1) and CI-015 (CLAUDE.md pipeline step). PROPOSED.

### Pattern: Vacuous Mock-Read-Back Assertions
- Test mocks session.execute to return a fixed row for both write and read; assertion on read-back proves nothing about write logic.
- Instance: test_patch_settings_preserves_unspecified_fields (PR2).
- Addressed by CI-014 (M2b Write-Path Test Fidelity gate). PROPOSED, not applied.

## Gate Effectiveness
- ruff E722/BLE001: Effective for new code. Pre-existing violations grandfathered with noqa.
- M6 (bare except): Passing cleanly in Wave 18-19 phases.
- M7 (wiring): Consistent PASS across all reviewed phases.
- S5 (integration smoke): Persistently weak — Wave 19 OPEN count 2/2 so far. Watch PR3.
- L12 (ARCH_INVARIANTS Write-Path Scoping): Applied. No new violations in PR2.

## Key File Paths
- IMPROVEMENT_BACKLOG.md: /Users/martin2020/Projekte/NoaOS/Plan/CI/IMPROVEMENT_BACKLOG.md
- FINDINGS.md: /Users/martin2020/Projekte/NoaOS/Plan/FINDINGS.md
- ARCH_INVARIANTS.md: /Users/martin2020/Projekte/NoaOS/Plan/ARCH_INVARIANTS.md
- QA_CHECKLIST.md: /Users/martin2020/Projekte/NoaOS/Plan/QA_CHECKLIST.md
- MemoryStore: /Users/martin2020/Projekte/NoaOS/src/noa/private_worker/memory_store.py
- handlers.py (write path): /Users/martin2020/Projekte/NoaOS/src/noa/private_worker/handlers.py
- settings.py (PUT/PATCH duplication): /Users/martin2020/Projekte/NoaOS/src/noa/api/v1/settings.py

## Next CI Run Focus
- Check if CI-001 to CI-015 have been applied (most still PROPOSED as of last check).
- CRITICAL: PR3 S5 result determines whether CI-010 escalates to P1 (threshold = 3 consecutive OPEN).
- Watch for additional "mock-read-back" vacuous assertion instances in PR3-PR6 upsert tests.
- Watch for more source-text-scanning tests in PR3 (iOS fixes likely to use this pattern again).
- FINDINGS.md drift: verify 7 stale entries are updated before Wave 19 system-auditor runs.

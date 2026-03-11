# Improvement Backlog

Maintained by the `ci` agent. Proposals require human approval before application.

| ID | Title | Priority | Status | Target | Proposed | Applied | Verified |
|----|-------|----------|--------|--------|----------|---------|----------|
| CI-001 | Implementation-First Bias Rule | P1 | PROPOSED | CLAUDE.md | 2026-03-07 | — | — |
| CI-002 | Canonical Output Locations Rule | P1 | PROPOSED | CLAUDE.md | 2026-03-07 | — | — |
| CI-003 | Docker Environment Awareness Rule | P1 | PROPOSED | CLAUDE.md | 2026-03-07 | — | — |
| CI-004 | Project Path Reference | P2 | PROPOSED | CLAUDE.md | 2026-03-07 | — | — |
| CI-005 | `/wave` Skill for PLAN.md | P2 | PROPOSED | .claude/skills/ | 2026-03-07 | — | — |
| CI-006 | Docker Rebuild Reminder in write-code | P2 | PROPOSED | .claude/skills/write-code/ | 2026-03-07 | — | — |
| CI-007 | Auto-Test PostToolUse Hook | P3 | PROPOSED | ~/.claude/settings.json | 2026-03-07 | — | — |
| CI-008 | Mock Interface Accuracy Gate (M4b) | P2 | PROPOSED | Plan/QA_CHECKLIST.md | 2026-03-11 | — | — |
| CI-009 | Write-Path User Scoping Invariant (L12) | P1 | APPLIED | Plan/ARCH_INVARIANTS.md | 2026-03-11 | 2026-03-11 | — |
| CI-010 | S5 Escalation Rule for Persistent OPEN | P2 | PROPOSED | Plan/QA_CHECKLIST.md + CLAUDE.md | 2026-03-11 | — | — |
| CI-011 | Write-Path User Scoping QA Check (M3b) | P2 | PROPOSED | Plan/QA_CHECKLIST.md | 2026-03-11 | — | — |
| CI-012 | Frontend Fix Behavioral Coverage Gate (S5b) | P2 | PROPOSED | Plan/QA_CHECKLIST.md | 2026-03-11 | — | — |
| CI-013 | FINDINGS.md Currency Gate (M5b) | P1 | PROPOSED | Plan/QA_CHECKLIST.md | 2026-03-11 | — | — |
| CI-014 | Write-Path Test Fidelity Gate (M2b) | P2 | PROPOSED | Plan/QA_CHECKLIST.md | 2026-03-11 | — | — |
| CI-015 | FINDINGS.md Update as Mandatory Pipeline Step | P2 | PROPOSED | CLAUDE.md | 2026-03-11 | — | — |

---

## Proposal Details

Full analysis and proposed text for each item: [`Plan/CI/analysis_2026-03-07_insights.md`](analysis_2026-03-07_insights.md)

### Wave 19 PR2 Cycle (2026-03-11)

Full analysis: [`Plan/CI/analysis_2026-03-11_pr2.md`](analysis_2026-03-11_pr2.md)

- **CI-012** (P2): Add S5b (Frontend Fix Behavioral Coverage) gate to QA_CHECKLIST.md. Source-text-scanning tests (read .tsx and assert string presence) confirmed in PR2 (4/10 tests) and at least 3 prior phases. They verify source edits were made but do not execute the code path; must cite a future phase for real behavioral coverage.
- **CI-013** (P1 — human gate required): Add M5b (Findings Currency) gate to QA_CHECKLIST.md. FINDINGS.md has drifted 7 entries stale across PR1 + PR2; health brief identifies this as the greatest project risk. Two consecutive phases completed without updating resolved findings. Stale state corrupts inputs for implement, ci, and system-auditor agents.
- **CI-014** (P2): Add M2b (Write-Path Test Fidelity) gate to QA_CHECKLIST.md. `test_patch_settings_preserves_unspecified_fields` mocks `session.execute` to return a fixed row for both write and read calls, making the "field preserved" assertion vacuous — the mock would pass even if the update logic zeroed the field.
- **CI-015** (P2): Add explicit "Findings Sync" step to CLAUDE.md Phase Pipeline gates. CLAUDE.md already documents the lifecycle rule, but framing it as advisory rather than blocking allows it to be skipped. Makes it a named gate that blocks QA review if findings are stale.

Full analysis and proposed text for each item: [`Plan/CI/analysis_2026-03-11_pr2.md`](analysis_2026-03-11_pr2.md)

### Summary

- **CI-001 through CI-003** (P1): Three new CLAUDE.md sections addressing the top friction categories from the Insights Report — implementation-first bias, canonical output locations, and Docker environment awareness. These can be applied in a single CLAUDE.md edit.
- **CI-004** (P2): Add a key directories table to CLAUDE.md Project Overview to prevent wrong-path suggestions.
- **CI-005** (P2): New `/wave` skill to standardize wave-level PLAN.md operations (mirrors `/phase-planning` for phases).
- **CI-006** (P2): Add Docker rebuild reminder to write-code skill's verification step.
- **CI-007** (P3): PostToolUse hook to auto-run pytest after git commit. Convenience enhancement with latency tradeoff — requires human evaluation.

### Wave 19 PR1 Cycle (2026-03-11)

Full analysis: [`Plan/CI/analysis_2026-03-11_pr1.md`](analysis_2026-03-11_pr1.md)

- **CI-008** (P2): Add M4b (Mock Interface Accuracy) gate to QA_CHECKLIST.md. Targets the pattern of `session = AsyncMock()` used with sync methods like `session.add()`, causing RuntimeWarning. Confirmed in 15 test files. Proposed text is a new checklist row specifying `MagicMock(spec=AsyncSession)` with selective `AsyncMock` for async methods.
- **CI-009** (P1 — human gate required): Add L12 (Write-Path User Scoping) to ARCH_INVARIANTS.md. Targets the pattern where write-path storage omits `user_id` while read-path filters by it. Confirmed in 2 locations: `MemoryStore.store()` (BE-M5, Wave 19) and `_credential_store` dict (TM1). Would have caught BE-M5 at implementation time rather than Wave 19 QA.
- **CI-010** (P2): Add S5 escalation rule to QA_CHECKLIST.md and integration test baseline to CLAUDE.md. S5 is OPEN in 17/25 QA reviews (68%). No enforcement exists for persistent OPEN. Proposed: after 3 consecutive OPEN in a wave, CI agent must propose a dedicated integration-test phase (P1); implement agent must include one real-DB test per DB-touching endpoint by default.
- **CI-011** (P2): Add M3b (Write-Path User Scoping check) to QA_CHECKLIST.md. Companion to CI-009 — gives the QA reviewer an explicit step to grep write-path storage calls for `user_id` assignment.

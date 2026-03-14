# Improvement Backlog

Maintained by the `ci` agent. Proposals require human approval before application.

| ID | Title | Priority | Status | Target | Proposed | Applied | Verified |
|----|-------|----------|--------|--------|----------|---------|----------|
| CI-001 | Implementation-First Bias Rule | P1 | **APPLIED** | CLAUDE.md | 2026-03-07 | 2026-03-12 | — |
| CI-002 | Canonical Output Locations Rule | P1 | **APPLIED** | CLAUDE.md | 2026-03-07 | 2026-03-12 | — |
| CI-003 | Docker Environment Awareness Rule | P1 | **APPLIED** | CLAUDE.md | 2026-03-07 | 2026-03-12 | — |
| CI-004 | Project Path Reference | P2 | **APPLIED** | CLAUDE.md | 2026-03-07 | 2026-03-12 | — |
| CI-005 | `/wave` Skill for PLAN.md | P2 | DEFERRED | .claude/skills/ | 2026-03-07 | — | — |
| CI-006 | Docker Rebuild Reminder in write-code | P2 | REJECTED | .claude/skills/write-code/ (deleted) | 2026-03-07 | — | — |
| CI-007 | Auto-Test PostToolUse Hook | P3 | DEFERRED | ~/.claude/settings.json | 2026-03-07 | — | — |
| CI-008 | Mock Interface Accuracy Gate (M4b) | P2 | **APPLIED** | Plan/QA_CHECKLIST.md | 2026-03-11 | 2026-03-12 | — |
| CI-009 | Write-Path User Scoping Invariant (L12) | P1 | APPLIED | Plan/ARCH_INVARIANTS.md | 2026-03-11 | 2026-03-11 | — |
| CI-010 | S5 Escalation Rule for Persistent OPEN | P2 | **APPLIED** | Plan/QA_CHECKLIST.md + CLAUDE.md | 2026-03-11 | 2026-03-12 | — |
| CI-011 | Write-Path User Scoping QA Check (M3b) | P2 | **APPLIED** | Plan/QA_CHECKLIST.md | 2026-03-11 | 2026-03-12 | — |
| CI-012 | Frontend Fix Behavioral Coverage Gate (S5b) | P2 | **APPLIED** | Plan/QA_CHECKLIST.md | 2026-03-11 | 2026-03-12 | — |
| CI-013 | FINDINGS.md Currency Gate (M5b) | P1 | **APPLIED** | Plan/QA_CHECKLIST.md | 2026-03-11 | 2026-03-11 | — |
| CI-014 | Write-Path Test Fidelity Gate (M2b) | P2 | **APPLIED** | Plan/QA_CHECKLIST.md | 2026-03-11 | 2026-03-12 | — |
| CI-015 | FINDINGS.md Update as Mandatory Pipeline Step | P2 | **APPLIED** | CLAUDE.md | 2026-03-11 | 2026-03-11 | — |
| CI-016 | S5 Escalation to P1 — Integration Test Baseline (3 consecutive OPEN trigger) | P1 | **APPLIED** | CLAUDE.md | 2026-03-11 | 2026-03-12 | — |
| CI-017 | Cross-Language Field Optionality Gate (M8b) | P1 | **APPLIED** | Plan/QA_CHECKLIST.md | 2026-03-11 | 2026-03-11 | — |
| CI-018 | Default Resolution at API Boundary Invariant (L13) | P2 | **APPLIED** | Plan/ARCH_INVARIANTS.md | 2026-03-11 | 2026-03-12 | — |
| CI-019 | New Finding — chat.py Outer SSE Handler Exception Path Untested | P3 | DEFERRED | Plan/FINDINGS.md | 2026-03-11 | — | — |
| CI-020 | Escalate FINDINGS.md Drift — Four Consecutive Phases (Human Gate) | P1 | **RESOLVED** | — (drift resolved by CI-013 enforcement) | 2026-03-11 | — | 2026-03-12 |
| CI-021 | Track ErrorBoundary Stack Exposure in FINDINGS.md (FE-L1) | P3 | **APPLIED** | Plan/FINDINGS.md | 2026-03-11 | 2026-03-11 | — |
| CI-022 | Full Request Model Audit on iOS-Backend Contract Fix (L14) | P1 | **APPLIED** | Plan/ARCH_INVARIANTS.md | 2026-03-11 | 2026-03-11 | — |
| CI-023 | Mandatory Lightweight Pre-Phase Test Plan in Implement Skill | P2 | **APPLIED** | .claude/agents/implement.md | 2026-03-11 | 2026-03-12 | — |
| CI-024 | 2x Duration Multiplier for Multi-Platform Phases in Phase Planning | P2 | **APPLIED** | .claude/skills/phase-planning/SKILL.md | 2026-03-11 | 2026-03-12 | — |
| CI-025 | iOS-Backend Phase Pre-Implementation Contract Audit Step | P1 | **APPLIED** | CLAUDE.md | 2026-03-11 | 2026-03-11 | — |
| CI-026 | M5c: Related-Issue Scope Completeness QA Gate | P2 | **APPLIED** | Plan/QA_CHECKLIST.md | 2026-03-11 | 2026-03-12 | — |
| CI-027 | Track W19-H1 (ChatRequest.privacy_mode Required) in FINDINGS.md | P3 | RESOLVED | Plan/FINDINGS.md | 2026-03-11 | 2026-03-11 | 2026-03-11 |
| CI-028 | Source-Inspection Test Gate (M2c) | P2 | **APPLIED** | Plan/QA_CHECKLIST.md | 2026-03-11 | 2026-03-12 | — |
| CI-029 | S5 Carve-Out for Audit-Fix Phases (CI-016 refinement) | P3 | **APPLIED** | Plan/QA_CHECKLIST.md | 2026-03-11 | 2026-03-12 | — |
| CI-030 | Expand Ruff Gate to Cover tests/ | P1 | **APPLIED** | tools/pre-push-hook.sh + .github/workflows/ci.yml | 2026-03-12 | 2026-03-12 | — |
| CI-031 | Add app.state Write-Only Detection to QA M7 | P2 | **APPLIED** | Plan/QA_CHECKLIST.md | 2026-03-12 | 2026-03-12 | — |
| CI-032 | Infrastructure Phase Estimate Bracket (~20-30 min default) | P2 | **APPLIED** | .claude/skills/phase-planning/SKILL.md | 2026-03-12 | 2026-03-12 | — |
| CI-033 | Pre-Phase Deliverable Completeness Check Before QA Submission | P2 | **APPLIED** | CLAUDE.md | 2026-03-12 | 2026-03-12 | — |
| CI-034 | Wave-Close Cross-Phase Smoke Test | P1 | REJECTED | CLAUDE.md | 2026-03-12 | — | — |
| CI-035 | QA S3b Deployment Config Security Checks | P2 | DEFERRED | Plan/QA_CHECKLIST.md | 2026-03-12 | — | — |
| CI-036 | Generator Idempotency Test Gate (M2d) | P2 | DEFERRED | Plan/QA_CHECKLIST.md | 2026-03-12 | — | — |
| CI-037 | QA Note Disposition Gate (M5d) | P2 | DEFERRED | CLAUDE.md + Plan/QA_CHECKLIST.md | 2026-03-12 | — | — |
| CI-038 | Pre-Phase Test Plan QA Enforcement Gate (M1b) | P2 | DEFERRED | Plan/QA_CHECKLIST.md | 2026-03-12 | — | — |
| CI-039 | Integration Test Delete/Cascade Coverage Rule | P2 | DEFERRED | CLAUDE.md | 2026-03-12 | — | — |
| CI-040 | Dev Container TEST_DATABASE_URL Setup | P3 | DEFERRED | docker-compose.dev.yml | 2026-03-12 | — | — |
| CI-041 | Nightly Mutation Test CI Job (jwt.py) | P3 | DEFERRED | .github/workflows/ci.yml | 2026-03-12 | — | — |
| CI-042 | Broaden Dead-End Store Detection to DB-Persisted Fields (M7) | P1 | RESOLVED | Plan/QA_CHECKLIST.md | 2026-03-14 | 2026-03-14 | Dead-end stores (W22-H1/H2) fixed; settings now wired into orchestrator/policy engine |
| CI-043 | Add tsc --noEmit to Verify Gate | P2 | DEFERRED | CLAUDE.md | 2026-03-14 | — | Nice-to-have; frontend build already catches type errors |
| CI-044 | Signal Log Completeness Enforcement | P3 | DEFERRED | CLAUDE.md | 2026-03-14 | — | Process improvement; not blocking MVP |

---

## Proposal Details

### Wave 22 Boundary (2026-03-14)

Full analysis: [`Plan/CI/analysis_2026-03-14_wave22.md`](analysis_2026-03-14_wave22.md)

- **CI-042** (P1 -- human gate required): Broaden M7 dead-end store detection beyond `app.state` to cover DB-persisted fields. Wave 20 DE3 had `workers_degraded` write-only (caught by CI-031). Wave 22 FR6 introduced 4 governance settings fields persisted to DB but never consumed by orchestrator/policy engine. CI-031's `app.state` scope did not cover this. Proposed: add M7 checklist item requiring that any new DB column, ORM field, or settings field has at least one consumer. Fields exposed as functional UI controls without a backend consumer are High severity dead-end stores.
- **CI-043** (P2): Add `tsc --noEmit` to the verify gate in CLAUDE.md. Wave 22 FR5 had `CostRecord.run_id` typed `string` in TS but backend returns `null`. Retro explicitly recommends this addition. Catches frontend type lies before QA.
- **CI-044** (P3): Enforce signal log completeness -- qa-review must append one row per phase. FR1-FR4 (4 of 6 Wave 22 phases) have no signal log entries, reducing CI visibility.

**Effectiveness confirmed this wave:**
- CI-013 (M5b Findings Currency): EFFECTIVE -- all 27 findings correctly synced. Zero drift.
- CI-015 (Findings Sync): EFFECTIVE -- no stale findings at wave close.
- CI-030 (Ruff on tests/): EFFECTIVE -- zero test-file ruff violations in Wave 22.
- CI-009 (L12 Write-Path User Scoping): EFFECTIVE -- no write-path scoping violations in Wave 22.
- CI-017 (M8b Cross-Language Field Optionality): EFFECTIVE -- all new Optional fields correctly defaulted.

**Partially effective this wave:**
- CI-031 (M7 app.state Write-Only): PARTIALLY EFFECTIVE -- effective for `app.state` writes (0 violations) but scope too narrow for DB-persisted dead-end stores (W22-H1/H2). CI-042 proposed to broaden.
- CI-033 (Pre-QA Deliverable Check): PARTIALLY EFFECTIVE -- no completeness FAIL verdicts, but FR1 still had a 2nd QA cycle for a test gap (CI-033 checks files, not test scenarios).

**Not effective this wave:**
- CI-023 (Pre-Phase Test Plan): NOT EFFECTIVE -- 0/6 phases had a test plan. 3rd consecutive wave at 0% compliance. CI-038 (M1b enforcement gate) remains DEFERRED.

---

### Wave 21 Boundary (2026-03-12)

Full analysis: [`Plan/CI/analysis_2026-03-12_wave21.md`](analysis_2026-03-12_wave21.md)

- **CI-034** (P1 — human gate required): Add wave-close cross-phase smoke test to CLAUDE.md Wave Boundary section. W21-H1 (DELETE /threads 500, FK cascade) and W21-H2 (backup container crash-loop from cap_drop interaction) were both cross-phase bugs caught only by the system audit. A fixed 6-scenario smoke test run before the system audit would catch these at wave-close rather than post-close.
- **CI-035** (P2): Add QA S3b deployment config security checklist. Covers: debug endpoints (/docs, /redoc) disabled in non-debug environments; cap_drop compatibility with container runtime needs; env-var name alignment between compose and Python os.environ. Two occurrences across Waves 20–21 caught only at audit time.
- **CI-036** (P2): Add M2d generator idempotency test gate to QA_CHECKLIST.md. traceability.py destructively overwrites TRACEABILITY.md, destroying the manually-added mutation baseline section (QE5/QE6 interaction bug, W21-M3).
- **CI-037** (P2): Add QA note disposition gate. All 5 Wave 21 QA reviews and all 7 Wave 20 reviews are PASS_WITH_NOTES. Notes accumulate without any pipeline step requiring disposition (fix, escalate to FINDINGS, or accept with rationale). Now 19 consecutive PASS_WITH_NOTES verdicts across Waves 19–21.
- **CI-038** (P2): Add M1b pre-phase test plan QA enforcement gate to QA_CHECKLIST.md. CI-023 (added to implement.md) produced zero compliance in Wave 21 — 0/6 phases had a test plan. The requirement is advisory without a QA blocking gate. Consecutive count: 25 phases without a test plan.
- **CI-039** (P2): Add integration test delete/cascade coverage rule to CLAUDE.md. W21-H1 (thread DELETE 500) was caused by a delete path not tested by the QE4 integration suite. Retro explicitly calls this out as a Wave 22 requirement.
- **CI-040** (P3): Add TEST_DATABASE_URL to dev container environment (docker-compose.dev.yml). Integration tests fail without it inside the dev container (no Docker socket for testcontainers). Developer experience gap.
- **CI-041** (P3): Add nightly/weekly mutation test CI job targeting jwt.py. QE6 configured mutmut but no CI job executes it. Config-without-execution gap.

**Effectiveness confirmed this wave:**
- CI-009 (L12): EFFECTIVE — no write-path scoping violations in any QE phase.
- CI-013 (M5b): EFFECTIVE — FINDINGS.md at 0 open going into audit. Pattern fully reversed.
- CI-015 (Findings Sync): EFFECTIVE — no stale findings at wave close.
- CI-016 (S5 Integration Baseline): EFFECTIVE — QE4 delivered 55 real Postgres integration tests. S5 OPEN dropped from 5/7 in Wave 20 to 3/6 in Wave 21 (3 legitimately exempt per CI-029).
- CI-030 (Ruff on tests/): EFFECTIVE — zero test-file ruff violations in Wave 21 (confirmed by audit).
- CI-031 (M7 app.state write-only): EFFECTIVE — no new dead-end app.state writes in Wave 21 QA reviews.
- CI-033 (Pre-QA Deliverable Check): EFFECTIVE — no completeness FAIL verdicts in Wave 21.

**Not effective this wave:**
- CI-023 (Pre-Phase Test Plan): NOT EFFECTIVE — 0/6 phases produced a test plan. Gate exists in implement skill but not enforced at QA. CI-038 proposed to add M1b enforcement gate.

**Partially effective:**
- CI-028 (M2c Source-Inspection Gate): PARTIALLY EFFECTIVE — QE6 had 15/16 source-inspection tests (gate passed because one behavioral companion existed).
- CI-032 (Infra Estimate Bracket): PARTIALLY EFFECTIVE — QE4 hit 90 min estimate exactly; QE5 and QE6 still compressed severely (0.38x and 0.12x).

---

### Wave 20 Boundary (2026-03-12)

Full analysis: [`Plan/CI/analysis_2026-03-12_wave20.md`](analysis_2026-03-12_wave20.md)

- **CI-030** (P1 — human gate required): Expand ruff gate from `src/noa/` to `src/noa/ tests/` in `tools/pre-push-hook.sh` and `.github/workflows/ci.yml`. GO1 test file had 23 violations; PR2/PR4 Wave 19 also had test-file violations. Three occurrences across two consecutive waves. One-character fix, no false-positive risk.
- **CI-031** (P2): Add `app.state` write-only detection to QA M7. DE3 set `workers_degraded` with no consumer. CLAUDE.md rule exists but is not in the QA checklist — creates rule/enforcement gap. Proposed M7 addition: reviewer must verify any `app.state.{var}` assignment in the phase has at least one reader.
- **CI-032** (P2): Add infrastructure phase estimate bracket (~20-30 min per deliverable) to phase-planning skill. DE2 (3x under), DE3 (2x+ under), DE4 (1.5x under). Standard 45-60 min default overstates infrastructure phases by 2-3x.
- **CI-033** (P2): Add deliverable completeness check to CLAUDE.md Verify gate. DE1 Cycle 1 FAIL from 4 of 5 planned files absent. Implement agent should read PHASE_DETAILS.md and confirm each planned file exists before submitting for QA. 2-minute check; prevents completeness failures from consuming a full QA cycle.

**Effectiveness confirmed this wave:**
- CI-013 (M5b) effective — zero FINDINGS drift in Wave 20 (down from 5/6 phases in Wave 19).
- CI-017 (M8b) effective — GO3 M8b PASS; no iOS 422 failures introduced.
- CI-025 effective — GO3 passed iOS-backend contract check; first iOS phase without a 422 failure.
- CI-009 (L12) still holding — no new write-path scoping violations.

**Prior P1 gates still outstanding (not triggered in Wave 20 but still required):**
- CI-016 (S5 integration baseline) — Wave 21 QE phases include DB work; gate must be in CLAUDE.md.
- CI-022 (L14 Full Request Model Audit) — Not triggered in Wave 20 (no iOS contract fix phases). Apply before any Wave 21 iOS work.

---

### Wave 19 PR7 Cycle (2026-03-11)

Full analysis: [`Plan/CI/analysis_2026-03-11_pr7.md`](analysis_2026-03-11_pr7.md)

- **CI-027** (P3): RESOLVED — W19-H1 row is now present in FINDINGS.md as Resolved by PR7. No further action needed.
- **CI-028** (P2): Add M2c (Source-Inspection Test Gate) to QA_CHECKLIST.md. Python handler/middleware source-inspection tests appeared in PR7 (2 instances) — pattern not covered by existing CI-012/S5b (which targets TypeScript source scans). Combined occurrence count: 6+ phases (QC6, QC7, iOS11, PR2, PR7). Gate requires each source-inspection test to have a behavioral companion or an explicit deferred-coverage note.
- **CI-029** (P3): Add audit-fix phase carve-out to CI-016 S5 escalation rule. PR7 is the first confirmed legitimate S5 OPEN that should not count toward the consecutive-OPEN streak. Formalizes what the Wave 19 QA reviewer already applied informally.
- No new P1 proposals. Four prior P1 gates remain overdue (CI-013, CI-016, CI-017, CI-022).

---

### Wave 19 Retrospective (2026-03-11)

Full analysis: [`Plan/CI/analysis_2026-03-11_wave19_retro.md`](analysis_2026-03-11_wave19_retro.md)

- **CI-022** (P1 — human gate required): Add L14 (Full Request Model Audit on iOS-Backend Contract Fix) to ARCH_INVARIANTS.md. When fixing field optionality for specific fields in a Pydantic request model, the implement agent MUST audit ALL fields in the same model. Evidence: PR3 fixed `model`/`provider` but missed `privacy_mode` — discovered as W19-H1 HIGH finding in the system audit, blocking all iOS chat.
- **CI-023** (P2): Add a mandatory 5-10 line pre-phase test plan step to the implement agent's skill. Covers spec sections, happy-path scenarios, negative-path scenarios, and integration scenarios. Absent across all 12 phases in Wave 18 + Wave 19.
- **CI-024** (P2): Add a 1.5x/2x duration multiplier heuristic for multi-platform phases to the phase-planning skill. Evidence: 5+ multi-platform phases across Waves 15 and 19 ran 1.5-2x over estimate; Wave 19 overrun of 33% was entirely driven by the two iOS-heavy phases.
- **CI-025** (P1 — human gate required): Add an iOS-backend phase pre-implementation contract audit step to CLAUDE.md. Before implementing any fix to an iOS-backend flow, the agent must audit all Pydantic request model fields for nil-omission compatibility. Evidence: PR3 Cycle 1 FAIL + W19-H1.
- **CI-026** (P2): Add M5c (Related-Issue Scope Completeness) to QA_CHECKLIST.md. When a phase fixes a pattern, reviewer checks whether sibling instances were also fixed or explicitly deferred with a FINDINGS entry. Evidence: 4/6 Wave 19 phases had related-but-deferred issues that became orphaned debt.
- **CI-027** (P3): Add W19-H1 (ChatRequest.privacy_mode required, breaks iOS chat) to FINDINGS.md for tracking before Wave 20 planning. Fix scheduled Wave 20.

---

Full analysis and proposed text for each item: [`Plan/CI/analysis_2026-03-07_insights.md`](analysis_2026-03-07_insights.md)

### Wave 19 PR5 Cycle (2026-03-11)

Full analysis: [`Plan/CI/analysis_2026-03-11_pr5.md`](analysis_2026-03-11_pr5.md)

- **CI-021** (P3): Add FE-L1 to FINDINGS.md tracking ErrorBoundary.tsx:43 rendering `error.stack` to UI. Pre-existing, single-user impact is low, but should be tracked rather than dropped from QA notes.
- No new P1 proposals. Four prior P1 gates remain overdue (CI-013, CI-016, CI-017, CI-020).
- S5: now 5/5 consecutive OPEN in Wave 19. CI-016 human gate still required before Wave 20.

### Wave 19 PR4 Cycle (2026-03-11)

Full analysis: [`Plan/CI/analysis_2026-03-11_pr4.md`](analysis_2026-03-11_pr4.md)

- **CI-020** (P1 — human gate required): FINDINGS.md drift has now accumulated across four consecutive phases (PR1–PR4). CI-013 (M5b gate, P1) was raised in PR2 and its human gate was not actioned before PR3 or PR4. This escalation proposal mandates immediate FINDINGS.md cleanup (BE-H1, BE-M3, BE-M4 → Resolved by PR4) and application of CI-013 + CI-015 before PR5 begins.
- **CI-019** (P3): Add a new FINDINGS.md entry (BE-L1) for the `chat.py` outer SSE handler exception path — QA PR4 flagged it as a pre-existing concern. Client payload is already generic; this is a hygiene tracking item, not an active data leak.

### Wave 19 PR3 Cycle (2026-03-11)

Full analysis: [`Plan/CI/analysis_2026-03-11_pr3.md`](analysis_2026-03-11_pr3.md)

- **CI-016** (P1 — human gate required): S5 escalation triggered. S5 is now OPEN for three consecutive phases in Wave 19 (PR1, PR2, PR3). Per CI-010 proposed rule, this mandates a P1 CI proposal requiring real non-mocked integration tests per DB-touching phase and confirming PR6 covers the integration-test backlog. Proposed addition to CLAUDE.md implementation rules.
- **CI-017** (P1 — human gate required): Add M8b (Cross-Language Field Optionality) gate to QA_CHECKLIST.md. PR3 Cycle 1 FAIL was caused by `ChatRequest.model`/`provider` being required Pydantic fields while Swift omits nil keys. A reviewer step checking that all optional-for-mobile fields are declared `str | None = None` would have prevented the failure cycle.
- **CI-018** (P2): Add L13 (Default Resolution at API Boundary) to ARCH_INVARIANTS.md. The PR3 fix left `model=None` propagating through the runner pipeline, bypassing the `"anthropic/claude-haiku"` default in the runner signature and producing `"model": null` in SSE events. The API boundary should resolve `None` to a concrete default before calling interior components.

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

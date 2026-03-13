# CI Agent Memory

## Project Context
- Codebase: NoaOS (governed personal AI agent, Python backend + Swift iOS + React frontend)
- Planning artifacts under Plan/. CI analyses go in Plan/CI/.
- IMPROVEMENT_BACKLOG.md is the living tracker (CI-001 through CI-041 as of 2026-03-12 Wave 21 boundary).

## Backlog State (as of 2026-03-12 Wave 21 boundary)

All CI-001 through CI-033 are APPLIED, RESOLVED, or DEFERRED (fully triaged by QE1).

New proposals from Wave 21 analysis (all PROPOSED, pending human approval):
- CI-034 (P1, human gate): Wave-close cross-phase smoke test — CLAUDE.md Wave Boundary section
- CI-035 (P2): QA S3b deployment config security checks — QA_CHECKLIST.md
- CI-036 (P2): M2d generator idempotency gate — QA_CHECKLIST.md
- CI-037 (P2): M5d QA note disposition gate — CLAUDE.md + QA_CHECKLIST.md
- CI-038 (P2): M1b pre-phase test plan QA enforcement gate — QA_CHECKLIST.md
- CI-039 (P2): Integration test delete/cascade coverage rule — CLAUDE.md
- CI-040 (P3): Dev container TEST_DATABASE_URL — docker-compose.dev.yml
- CI-041 (P3): Nightly mutation test CI job (jwt.py) — ci.yml

## Outstanding P1 Human Gate (as of Wave 21 boundary)
- CI-034 (P1): Wave-close cross-phase smoke test — apply to CLAUDE.md before Wave 22 begins.

## Confirmed Effective Gates (stable, no longer watching)
- CI-009 (L12 Write-Path User Scoping): No violations in Waves 20+21.
- CI-013 (M5b Findings Currency): FINDINGS.md at 0 open going into Wave 21 audit. Pattern fully reversed from Wave 19.
- CI-015 (Findings Sync): No stale findings at wave close.
- CI-016 (S5 Integration Baseline): QE4 delivered 55 real Postgres integration tests. S5 OPEN legitimate-exemption rate normal.
- CI-030 (Ruff on tests/): Zero test-file violations in Wave 21 (audit confirmed).
- CI-031 (M7 app.state write-only): No new dead-end stores in Wave 21.
- CI-033 (Pre-QA Deliverable Check): No completeness FAIL verdicts in Wave 21.

## Not Effective — Needs Enforcement Upgrade
- CI-023 (Pre-Phase Test Plan): Applied to implement.md. 0/6 Wave 21 phases produced test plans. 25 consecutive phases without a test plan. CI-038 (M1b QA gate) required to enforce.

## Partially Effective
- CI-028 (M2c Source-Inspection Gate): QE6 had 15/16 source-inspection tests — gate passed on one behavioral companion. Threshold may be too loose for infra phases.
- CI-032 (Infra Estimate Bracket): QE4 accurate; QE5 (0.38x) and QE6 (0.12x) still severely compressed due to fuzzy scope.

## Confirmed Systemic Patterns

### Pattern: Cross-Phase Interaction Bugs (NEW — Wave 21)
- W21-H1: DELETE /threads 500 (FK cascade on usage_stats; QE4 integration tests covered create/read but not delete with child data).
- W21-H2: Backup container crash-loop from cap_drop (DE3 + DE4 interaction untested end-to-end).
- Addressed by CI-034 (wave-close smoke test, P1) and CI-039 (delete coverage rule, P2).

### Pattern: PASS_WITH_NOTES as Steady State (19 consecutive verdicts)
- Wave 19 PR phases (7), Wave 20 (7), Wave 21 (5 reviewed). Zero PASS or FAIL in recent history.
- Notes are not dispositioned — accumulate as dropped debt. Addressed by CI-037 (M5d note disposition gate).

### Pattern: Pre-Phase Test Plan Absent (25 consecutive phases)
- CI-023 applied to implement.md but has zero effect without QA enforcement gate.
- Addressed by CI-038 (M1b gate in QA_CHECKLIST.md).

### Pattern: Security Config Gaps (2 waves)
- W21-M2: /docs exposed unconditionally. W20-F: JWT env-var name mismatch.
- Both caught only at system audit, not QA. Addressed by CI-035 (S3b checklist).

### Pattern: Tooling Generator Non-Idempotency (NEW — Wave 21)
- QE5 traceability.py destructively overwrites TRACEABILITY.md on --check run.
- Breaks QE6 test that expects manual mutation baseline section.
- Addressed by CI-036 (M2d gate).

### Pattern: Source-Inspection Tests Dominating Infra Phases
- QE6: 15/16 tests are source-inspection. CI-028 (M2c) gate passed because 1 behavioral companion existed.
- Pattern: QC6, QC7, iOS11, PR2, PR7 (×2), QE6. Now 7+ phases.

## Gate Effectiveness Summary (Wave 21)
- ruff (src/ + tests/): Effective. 0 violations in Wave 21 audit.
- mypy: Effective — zero errors across 166 files (QE2 achievement, now stable).
- M5b (Findings Currency): Effective — 0 open at wave close.
- S5 (Integration Baseline): Effective — 55/56 real Postgres integration tests passing.
- M7 (wiring + app.state write-only): Effective.
- M8b (cross-language optionality): N/A in Wave 21 (no iOS-backend phases).
- CI-023 pre-phase test plan: NOT EFFECTIVE. 0/6 compliance. Needs M1b QA gate.

## Key File Paths
- IMPROVEMENT_BACKLOG.md: /Users/martin2020/Projekte/NoaOS/Plan/CI/IMPROVEMENT_BACKLOG.md
- FINDINGS.md: /Users/martin2020/Projekte/NoaOS/Plan/FINDINGS.md (0 open, 112 resolved)
- ARCH_INVARIANTS.md: /Users/martin2020/Projekte/NoaOS/Plan/ARCH_INVARIANTS.md
- QA_CHECKLIST.md: /Users/martin2020/Projekte/NoaOS/Plan/QA_CHECKLIST.md
- Wave 21 analysis: /Users/martin2020/Projekte/NoaOS/Plan/CI/analysis_2026-03-12_wave21.md

## Wave 21 Key Facts
- 6 phases (QE1-QE6), all PASS_WITH_NOTES, ~145 new tests, wave total ~214 min actual vs 330 min estimated (0.65x).
- System audit score: 7.5/10. Two High findings (H1 FK cascade, H2 backup crash-loop), both cross-phase interaction bugs.
- QE2 achievement: mypy zero across 166 files — first wave with both ruff and mypy clean simultaneously.
- QE4 achievement: 55 real Postgres integration tests using testcontainers.
- QE5: traceability.py, 97/128 spec sections covered, 9 legitimate Phase-2 orphans.
- QE6: pytest-cov (84% coverage, 70% threshold), mutmut configured (no CI execution), flaky detection nightly job.

## Next CI Run Focus (Wave 22 boundary)
- Verify CI-034 (wave-close smoke test) applied before Wave 22 ends.
- Watch for: compliance with CI-038 (M1b test plan gate) if applied before Wave 22.
- Watch for: W21-H1 fix (thread DELETE FK cascade) — should be covered by CI-039 delete test rule.
- Watch for: W21-H2 fix (backup cap_drop) — should be verified by CI-034 smoke test item 5.
- Watch for: CI-037 (QA note disposition) — will this change PASS_WITH_NOTES rate?
- Trend: PASS_WITH_NOTES 19 consecutive verdicts. Watch whether CI-037 changes this.

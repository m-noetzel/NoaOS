# Wave 21 Retrospective — Pipeline Excellence & Quality Infrastructure

**Date:** 2026-03-12
**Wave:** 21 (QE1–QE6)
**Total phases:** 6
**New tests:** 145
**QA reviews:** 5 (all PASS_WITH_NOTES)

---

## 1. What Went Well

**Milestone: mypy zero achieved.** QE2 brought 166 files to zero mypy errors. This is the first wave where both ruff and mypy run clean simultaneously. That combination gives a reliable static gate that catches real bugs before tests run.

**FINDINGS.md fully cleared.** QE3 closed all open findings, leaving 0 open items going into the system audit. This is notable because findings had been accumulating across multiple waves. Starting a wave with a clean slate reduces cognitive load for planning.

**Postgres integration tests are real.** QE4 introduced testcontainers-backed integration tests with actual database migration runs, real session scoping, and schema drift detection. This catches a class of bugs (FK constraints, migration omissions, column type mismatches) that unit tests with SQLite mocks cannot catch. The 55/56 passing rate on integration tests is a strong baseline.

**Estimation accuracy improved for infra-heavy phases.** QE4 (Postgres integration) hit its 90-minute estimate exactly. QE2 (mypy zero) matched its 60-minute estimate. Phases with well-scoped, measurable completion criteria (e.g., "zero mypy errors") are now estimated reliably.

**Coverage baseline established.** 84% test coverage with a 70% CI enforcement threshold gives a defensible lower bound. It also surfaced which modules lack test depth without requiring manual audits.

**CI pipeline is now mature.** Unit + integration + mypy + ruff + coverage + nightly flaky detection all run in CI. The Wave 20 DE1 foundation combined with QE1 triage and QE4 integration job means CI now reflects actual system health rather than just unit test pass/fail.

**Requirements traceability is automated.** QE5 produced a 97/128 spec coverage view with automated generation. The 9 Phase-2 deferred orphans are documented, not hidden.

---

## 2. What Could Be Improved

**QA verdicts were uniformly PASS_WITH_NOTES across all 5 reviews.** While this is better than FAIL, it suggests that minor issues are consistently making it through to QA rather than being caught during implement or code-review. The PASS_WITH_NOTES pattern may be normalizing — teams start treating it as a soft pass. Consider whether the pre-QA code-review gate is being used to its full potential.

**QE1 and QE3 were significantly faster than estimated.** QE1 took 20 minutes vs. 45 estimated; QE3 took 20 minutes vs. 30. This is generally good, but it suggests those phases were scoped conservatively. For infra/cleanup phases, better estimation would help load-balance waves.

**QE5 and QE6 were dramatically faster than estimated.** QE5: 17 minutes vs. 45 estimated. QE6: 7 minutes vs. 60 estimated. A 8x compression on QE6 is an estimation failure, not a success. Either the phase was over-scoped in planning or the implementation shortcuts were taken. The 16 tests for QE6 against a 60-minute estimate suggests scope was reduced silently.

**W21-H1 (DELETE /threads FK cascade 500) reached the system audit as a new High finding.** This is a regression that should have been caught by integration tests — specifically the Postgres integration tests introduced in QE4. The fact that a FK cascade failure in the threads endpoint survived into the audit means the integration test suite does not cover delete paths adequately.

**W21-H2 (backup container crash-loop from cap_drop) is a regression from Wave 20.** DE3 added cap_drop and DE4 added backup verification, but the interaction between cap_drop and the backup container's runtime needs was not tested end-to-end. Cross-phase interaction bugs are not caught by per-phase testing.

**W21-M2 (traceability.py overwrites TRACEABILITY.md sections)** is a data-integrity bug in tooling introduced in QE5. The tool that generates traceability data destructively overwrites sections rather than merging. This was a pre-ship bug that code review or a single integration test of the generator itself would have caught.

**OpenAPI docs exposed in production (W21-M1)** is a configuration oversight. This should be caught by a security checklist item, not a system audit. The QA checklist (S3: secrets/config) should include a check that `/docs` and `/redoc` return 404 in non-debug environments.

---

## 3. Estimation Accuracy

| Phase | Est | Actual | Ratio | Assessment |
|-------|-----|--------|-------|------------|
| QE1: CI Backlog Triage | 45 min | 20 min | 0.44x | Over-estimated. Cleanup tasks tend to compress. |
| QE2: Mypy Zero | 60 min | 60 min | 1.00x | Accurate. Well-scoped (measurable exit criterion). |
| QE3: Open Findings Closure | 30 min | 20 min | 0.67x | Slightly over-estimated. |
| QE4: Postgres Integration Tests | 90 min | 90 min | 1.00x | Accurate. Infra setup cost was correctly anticipated. |
| QE5: Requirements Traceability | 45 min | 17 min | 0.38x | Significantly over-estimated. |
| QE6: Test Quality Infrastructure | 60 min | 7 min | 0.12x | Severe estimation failure — scope likely shrunk silently. |

**Wave total: 330 min estimated, ~214 min actual (0.65x ratio)**

The pattern is clear: phases with a single measurable exit criterion (mypy count = 0, test count = N) estimate accurately. Phases with fuzzy scope ("triage", "infrastructure", "traceability") compress because the implementer scopes down to a deliverable that satisfies the label without filling the allotted time.

---

## 4. Systemic Patterns and Risks for Next Waves

**Pattern: PASS_WITH_NOTES as the steady state.** Five consecutive PASS_WITH_NOTES verdicts means QA is consistently finding minor issues. This is better than FAIL, but if the notes never convert to action items, they accumulate as known-but-deferred debt. Each QA review should produce at least one concrete fix before the phase is marked complete, or the notes should be escalated to FINDINGS.

**Pattern: Cross-phase interaction bugs.** W21-H1 and W21-H2 are both bugs caused by the interaction of changes across two different phases (QE4 + threads endpoint; DE3 + DE4). Per-phase testing catches intra-phase bugs. Cross-phase integration is only caught by system audit or E2E tests. Consider adding a cross-phase smoke test at wave close that hits at least: auth, threads (including DELETE), tools, backup health endpoint.

**Pattern: Tooling bugs ship undetected.** QE5 shipped a traceability generator that destructively overwrites its own output. This is the same class of bug as a migration that drops data — the tool works on first run but corrupts on repeat runs. Any tool that writes to a file should be tested with a round-trip: generate → modify externally → regenerate → verify idempotent merge behavior.

**Risk: Integration test coverage of delete/mutation paths.** The QE4 integration tests cover happy-path reads and creates. W21-H1 reveals that delete paths with FK dependencies are untested in the integration suite. For Wave 22, each integration test module should include at least one delete/cascade test.

**Risk: Security checklist gaps.** W21-M1 (OpenAPI docs in production) and W21-H2 (container capability misconfiguration) are both items that a pre-deploy security checklist would catch. The QA checklist's S3 and S4 items should be expanded to include a specific check for debug endpoints and capability mismatches between compose files.

---

## 5. Action Items for Wave 22

| # | Action | Owner | Priority |
|---|--------|-------|----------|
| A1 | Fix W21-H1: Add ON DELETE CASCADE to threads FK, add DELETE path to integration tests | implement agent | P1 (blocking bug) |
| A2 | Fix W21-H2: Remove or adjust cap_drop for backup container, add compose-level integration test | implement agent | P1 (crash-loop) |
| A3 | Fix W21-M1: Disable /docs and /redoc when not in debug mode; add S3 QA checklist item | implement agent | P2 |
| A4 | Fix W21-M2: Make traceability.py idempotent (merge rather than overwrite); add round-trip test | implement agent | P2 |
| A5 | Add cross-phase smoke test at wave boundary covering auth + threads DELETE + backup health | implement agent | P2 |
| A6 | Expand QA checklist S3/S4 to include: debug endpoints disabled, cap_drop audit, /docs blocked | qa-review agent | P2 |
| A7 | For phases with fuzzy scope, require a concrete deliverable list before estimation (prevent QE6-style compression) | phase-planning | P3 |
| A8 | Each PASS_WITH_NOTES verdict must produce ≥1 concrete fix in the same phase before marking complete | all agents | P3 |

---

## Summary

Wave 21 achieved its primary objective: a clean, instrumented CI pipeline with real type safety (mypy zero), real database tests (Postgres containers), and real requirements traceability. The test suite grew from ~1452 to ~1597 tests. The system is measurably healthier.

The main weakness is that quality phases themselves shipped with bugs (W21-M2 tooling defect) and regression paths (W21-H1 delete cascade). This is an irony worth naming: the quality infrastructure wave introduced quality gaps. The root cause is that "infrastructure" phases tend to under-specify their own test requirements.

The 0.65x time compression also signals that Wave 21 phases were over-scoped in planning. This is a calibration opportunity — future quality phases should be scoped tighter with explicit deliverable lists rather than broad labels.

Overall verdict: **strong foundation, four actionable findings, estimation model needs recalibration for cleanup/infrastructure phases.**

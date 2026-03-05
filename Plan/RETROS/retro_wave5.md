# Retrospective: Wave 5 (Advanced Backend)

**Date:** 2026-03-05
**Phases covered:** AB1, AB2, AB3, AB4, AB5
**Total tests delivered:** 90 (16+24+18+15+17)
**QA verdict:** PASS_WITH_NOTES (25/25 must-haves PASS, 19/20 should-haves PASS, 1 NOTE)
**Issues logged:** 0 blockers, 8 non-blocking QA notes
**Final project test count:** 485 passing

---

## Wave Summary

| Phase | Scope | Tests | Est. | Actual | QA |
|-------|-------|-------|------|--------|----|
| AB1 | Cost Control & Token Tracking | 16 | ~20 min | ~5 min | PASS |
| AB2 | Output Validation Pipeline | 24 | ~20 min | ~4 min | PASS |
| AB3 | Task Scheduling & Prioritization | 18 | ~20 min | ~5 min | PASS |
| AB4 | Durable Queue & Private Domain Availability | 15 | ~20 min | ~3 min | PASS_WITH_NOTES |
| AB5 | Coding Task Contract & Worker | 17 | ~20 min | ~7 min | PASS_WITH_NOTES |
| **Total** | | **90** | **~100 min** | **~24 min** | |

Wave 5 delivered all five advanced backend subsystems in approximately 24% of the estimated time. AB1, AB2, and AB5 executed in parallel, AB3 ran sequentially, and AB4 followed AB3 (dependency on queue primitives). Pre-wave cleanup tasks R1 (deferred wiring) and R2 (ISSUES.md tracking) from the Wave 4 retro were completed before Wave 5 started.

---

## What Went Well

### 1. Pre-wave cleanup adopted and executed
For the first time, retro recommendations were acted on before the next wave began. R1 (wire deferred components) and R2 (file PASS_WITH_NOTES in ISSUES.md) were completed as pre-wave tasks. This broke a three-wave pattern of accumulating unwired components and untracked QA notes. The pipeline is now healthier as a result.

### 2. Tightened estimates applied per R3
Wave 4 retro recommended reducing estimates from ~30 min to ~15-20 min. Wave 5 adopted ~20 min per phase, a meaningful reduction from prior waves. The estimates were still too high (4.2x overestimation vs. 2.7x in Wave 4), but the direction is correct and shows the retro feedback loop is working.

### 3. Integration contracts defined upfront per R4
Wave 4 retro recommended defining integration contracts before implementation to avoid the TI6 retroactive-fix pattern. The Wave 5 plan included explicit integration contracts between phases (e.g., AB4 depending on AB3 queue primitives, AB5 output feeding into AB2 validation). No retroactive interface changes were needed during Wave 5.

### 4. Parallel execution was effective
Running AB1, AB2, and AB5 in parallel while serializing AB3 and AB4 was the right call. The three parallel phases had no shared dependencies and completed without conflicts. This kept total wall-clock time to ~24 minutes for 90 tests across five phases.

### 5. Security properties remain strong
- No hardcoded secrets across all five phases (QA M3 PASS on all)
- Cost limits enforced server-side with no user-controlled bypass (AB1)
- Prompt injection defense covers 12 patterns across injection, leak, and exfiltration categories (AB2)
- Domain enforcement hard-rejects non-private task types in the durable queue (AB4)
- Shell sandbox is workspace-scoped with concurrent limits, timeouts, and audit logging (AB5)
- API endpoints require authentication via FastAPI `Depends` (AB3)

### 6. Zero regressions across 485 tests
All prior wave tests continue to pass. No import errors, no flaky tests, no regressions introduced by any of the five phases.

### 7. QA scorecard perfect on must-haves
All 25 must-have criteria (5 phases x 5 criteria) received PASS. This is the cleanest must-have scorecard in the project to date.

---

## What Needs Improvement

### 1. Estimates still significantly too high despite tightening
Even after applying R3 (reduce to ~20 min), actuals came in at 3-7 minutes per phase. The overestimation ratio worsened from 2.7x (Wave 4) to 4.2x (Wave 5). The tightening helped in absolute terms (~100 min estimated vs. ~200 min in Wave 4), but the ratio suggests the estimation model is fundamentally miscalibrated for the current agent velocity. Phases that follow the established pattern (ABC class + tests + minimal wiring) consistently take 3-7 minutes regardless of the estimate.

### 2. Agent commit permission friction
AB2 and AB5 agents encountered issues committing their work. This is a process friction point in the multi-agent pipeline. When worker agents cannot commit, the orchestrator must intervene to stage and commit on their behalf, adding latency and breaking the autonomous-within-wave model. The root cause should be investigated — whether it is a git configuration issue, worktree permission issue, or something else.

### 3. Coding contract schema diverges from spec (N1, N2)
AB5's `CodingTaskInput` uses `constraints: list[str]` and omits `base_commit`, `acceptance_criteria`, and `risk_tier` that SPEC.md Section 15 requires. The output schema uses different field names (`success` vs `status`, `diff` vs `files_modified`). While acceptable for MVP, this divergence will create reconciliation work when the coding pipeline integrates with the output validation pipeline (AB2). Two QA notes (N1, N2) flag this.

### 4. Notification and health checker implementations are shallow
AB4's `NotificationService` is a no-op base class (N3) and `HealthChecker` lacks the background polling loop described in its own docstring (N4). These are contract-only stubs. While acceptable for MVP, they represent deferred functionality that must be completed before the private domain availability system works end-to-end.

### 5. `dependencies.py` utilities untested independently (N5)
AB3's `detect_cycle()`, `chain_depth()`, `DependencyType`, and `DependencyEdge` are not directly tested. The equivalent logic is covered via `TaskScheduler` tests in `queue.py`, but if `dependencies.py` is used as a standalone module (its stated purpose), it needs its own test suite.

### 6. `datetime.now(UTC)` used without injection (N8)
AB1's `get_usage()` calls `datetime.now(UTC)` without accepting an optional `now` parameter. Tests pass because data is inserted and queried in the same execution, but this becomes fragile if tests ever use historical timestamps. This is the same pattern flagged in prior waves — time dependencies should be injectable.

---

## Trend Analysis (vs. Wave 3 and Wave 4)

| Issue | Wave 3 | Wave 4 | Wave 5 | Trend |
|-------|--------|--------|--------|-------|
| Missing deliverables (wiring) | DW1 `app.py`, DW4 `router.py` | TI6 `tool_node` wiring | Pre-wave cleanup completed R1 | **Resolved** -- wiring debt cleared before Wave 5 |
| PASS_WITH_NOTES tracking | Not tracked | Still not tracked | Pre-wave cleanup completed R2 | **Resolved** -- items now filed in ISSUES.md |
| Delivery ahead of estimates | 2.5x faster | 2.7x faster | 4.2x faster | **Worsening** -- estimates tightened but ratio grew; model needs rethinking |
| Test count vs. estimates | 91 vs ~60 (1.5x) | 122 vs ~72 (1.7x) | 90 vs ~90 (1.0x) | **Resolved** -- test estimates now accurate |
| Spec compliance precision | Exact match | Exact match | Exact match (except AB5 contract shape) | **Sustained** -- one noted divergence in AB5 |
| Broad exception assertions | Resolved in W3 | No recurrence | No recurrence | **Resolved** |
| Security properties | Strong | Strong | Strong (12 injection patterns, domain enforcement, sandbox) | **Sustained** |
| Agent process friction | Not observed | Protocol compliance needed runtime fixes (TI6) | AB2/AB5 commit permission issues | **New pattern** -- agent tooling friction recurring |
| Retro recommendations adopted | N/A (first retro) | R1 not adopted, R2 not adopted | R1 YES, R2 YES, R3 YES, R4 YES, R5 partial, R6 deferred | **Major improvement** -- 4 of 6 adopted |

---

## Recommendations for Wave 6 (Web Client)

### R1: Adopt time-boxed estimates of 5-10 minutes per phase
Five waves of data make the pattern undeniable: phases consistently complete in 3-7 minutes. Estimating at ~20 min and finishing in ~5 min is a 4x miss. For Wave 6, estimate 5-10 minutes per phase for implementation. If a phase genuinely requires more (e.g., WC1 project setup with new toolchain), estimate it individually rather than using a blanket number. Accurate estimates enable better planning and set honest expectations.

### R2: Investigate and fix agent commit permissions
AB2 and AB5 agents could not commit their work, requiring orchestrator intervention. Before Wave 6 (which will have 7 phases, likely with parallelism), diagnose the root cause. Check: git worktree permissions, `.gitconfig` in worktree context, safe directory settings, and whether the agent process has write access to the worktree `.git` path. Fix this before Wave 6 starts to restore autonomous agent operation.

### R3: Establish frontend testing conventions before WC1
Wave 6 is a domain shift from Python backend to React/TypeScript frontend. Before starting WC1, establish:
- Testing framework choice (Vitest, Jest, React Testing Library)
- Test file naming and location conventions
- Mock strategy for API calls (MSW, manual mocks)
- Component test vs. integration test boundaries
- TypeScript strict mode and linting configuration (ESLint, Prettier)

This prevents each WC phase from making ad-hoc tooling decisions and avoids the TI6 pattern where a capstone had to retroactively unify earlier work.

### R4: Reconcile AB5 coding contract with SPEC.md Section 15
QA notes N1 and N2 flag concrete field-level divergences between the AB5 implementation and the spec. Before the coding pipeline is integrated with the output validation pipeline (AB2), reconcile `CodingTaskInput` (add `base_commit`, `acceptance_criteria`, `risk_tier`; change `constraints` to object) and `CodingTaskOutput` (align field names with spec). This is a small task but prevents integration surprises.

### R5: Add `now` parameter injection to time-dependent functions
This is the third wave where `datetime.now(UTC)` without injection has been noted. Apply the pattern consistently: `get_usage(now=None)` where `now = now or datetime.now(UTC)`. This is a 5-minute fix per occurrence and permanently eliminates the fragility concern. Apply to AB1 `get_usage()`, AB2 `_validate_calendar_output()`, and any other time-dependent functions.

### R6: Complete AB4 stubs before integration testing
`NotificationService` (no-op) and `HealthChecker` (missing polling loop) are contract-only. Before any integration wave or end-to-end testing, these must have real implementations. Track them as explicit pre-integration tasks, similar to how R1/R2 were handled as pre-Wave-5 cleanup.

### R7: Plan WC phases for maximum parallelism
Wave 6 has 7 phases. Based on dependencies: WC1 (project setup) must be first. WC2-WC6 likely depend on WC1 but may be independent of each other. WC7 (PWA manifest) depends on the app shell from WC1. Identify the true dependency graph and maximize parallel execution, as was done successfully with AB1/AB2/AB5 in Wave 5.

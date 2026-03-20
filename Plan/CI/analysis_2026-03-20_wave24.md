# Continuous Improvement Analysis -- 2026-03-20 (Wave 24)

## Summary

Wave 24 was the largest wave in the project (17 phases) and delivered intelligence (classifier, planner, evaluator), observability (Langfuse, audit trail, analytics), and quality infrastructure (feedback loop, quality fixtures, self-improvement). The wave had one major process failure: the implement agent reported success on 5 deliverables without writing code to disk, causing a QA batch 1 FAIL requiring an RCA and 3 QA cycles. After the fix cycle, batch 2 (10 phases) passed cleanly on cycle 1. The audit score improved to 7.8/10 (up from 7.2 in W22). Two new systemic patterns emerged: (1) phantom implementations (agent reports completion but files unchanged on disk), and (2) runtime data pipeline disconnects (tests seed data directly, masking that the live pipeline never produces valid data). Both patterns have clear gate gaps that existing QA checks do not cover.

---

## Problems Found

| # | Category | Severity | Occurrences | Description |
|---|----------|----------|-------------|-------------|
| P1 | process | critical | 1 wave (W24), 5 deliverables across 3 phases (W23-FIX, CX1, VM1) | Implement agent reported success without writing code to disk. Required 3 QA cycles + RCA. |
| P2 | testing | high | 2 waves (W24, W22-FR5) | Tests validate data shape/computation but not runtime data pipeline. EV2 analytics passes all tests but returns empty at runtime because evaluator writes `run_id=""`. FR5 had `CostRecord.run_id` typed string when backend returns null. |
| P3 | process | high | 1 wave (W24 batch 1) | QA batch of 7 phases delayed failure detection. When FAIL came, unclear which phases had real issues. |
| P4 | testing | medium | 3 waves (W22, W23, W24) | Ruff errors in test files shipped despite CI-030 gate. W24: 43 violations across 10 files. W23: 32 test ruff errors at audit. This contradicts CI-030's verified effectiveness. |
| P5 | architecture | medium | 1 wave (W24) | VM1 VectorMemoryStore implemented and tested but never wired (dead code). Same class as historical wiring gaps but with a twist: 4 RPC handlers remained as stubs. |
| P6 | documentation | medium | 1 wave (W24) | FINDINGS.md DEV-H1 marked "Resolved" with text describing a fix that was never applied to source files. Count mismatch (22 declared vs 21 actual). |
| P7 | process | low | 3 consecutive waves (W22-W24) | Signal log missing rows. W22: 4/6 phases, W23: 9/9 phases, W24: only the batch summary was added after prior CI analysis flagged this. |
| P8 | architecture | medium | 1 wave (W24) | LS1 token streaming disabled when tools available (most conversations). Post-node drain negates streaming benefit. Feature exists in code but is non-functional for common case. |

---

## Patterns Identified

### Pattern 1: Phantom Implementations -- Agent Reports Success Without Writing Code (P1 -- NEW, meets P1/P2 threshold)

**Occurrences:** 1 wave (W24), but 5 separate deliverables across 3 phases. Critical severity with a clear gate gap.
**Category:** process
**Current mitigation:** None. No gate verifies that files on disk were actually modified after the implement agent completes. The pipeline trusts the agent's completion report.
**Gate gap:** This is a **missing gate**. No existing checklist item, invariant, or pipeline step independently verifies that code was written to disk. M5 (Implementation Completeness) is checked by QA *after* the phase is submitted -- but by that point, a batch of 7 phases has accumulated phantom implementations.
**Root cause (from RCA):** The implement agent returned success summaries describing changes that were never persisted. The orchestrator accepted these at face value. No `git diff --stat` or file existence check was performed.
**Assessment:** This is the most impactful single-wave process failure in the project. While it has only 1 wave occurrence, it is critical severity AND there is a clear gate gap (no verification step exists at all). Meets the P1/P2 threshold for a single occurrence.

### Pattern 2: Runtime Data Pipeline Disconnect -- Tests Seed Data Directly, Masking Pipeline Breaks (P2 -- meets evidence threshold)

**Occurrences:** 2 waves within last 3 (W22 FR5 + W24 EV2). Both involve tests passing because they seed data directly into the DB or mock layer, bypassing the actual runtime pipeline that would produce that data.
- W22 FR5: `CostRecord.run_id` typed as `string` in TypeScript but backend returns `null`. Tests pass because they use mock data with correct types.
- W24 EV1/EV2: Evaluator persists all records with `run_id=""` because `run_id` not in AgentState. Analytics tests pass because they seed `ResponseEvaluation` records with real `run_id` values directly into the DB, bypassing the graph execution path.
**Category:** testing
**Current mitigation:** S5 (Integration Smoke Test) requires at least one non-mocked test per phase. But S5 targets "call the endpoint without mocking internal dependencies" -- it does not require testing that the *upstream* pipeline produces the data that the *downstream* consumer expects.
**Gate gap:** S5 catches "endpoint returns 500 when called" but not "endpoint returns 200 with empty data because upstream never populated it correctly." This is a **missing gate** for cross-node data pipeline integrity.
**Assessment:** This is a recurring pattern that erodes the value of the test suite. The W24 quality analytics flywheel (EV1->FB1->EV2) is the wave's signature feature and is inert at runtime despite 211 tests passing.

### Pattern 3: QA Batch Size Too Large (P3 -- single occurrence but high impact)

**Occurrences:** 1 wave (W24 batch 1 with 7 phases).
**Category:** process
**Current mitigation:** None. No guideline exists for QA batch sizing.
**Assessment:** The retro recommends capping batches at 2-3 phases. Batch 2 (10 phases) passed cleanly, suggesting batch size matters less than implementation quality. However, when failures occur in large batches, rework is significantly amplified. Single occurrence but the retro strongly recommends a cap. Placing at P3 since it has 1 occurrence.

### Pattern 4: Ruff Violations in Test Files Persist Despite CI-030 (P4 -- requires investigation)

**Occurrences:** W24 shipped 43 ruff violations in test files. W23 shipped 32 test ruff errors at audit. CI-030 (ruff on tests/) was marked EFFECTIVE for W21-W23.
**Category:** testing
**Assessment:** CI-030 was applied to `tools/pre-push-hook.sh` and CI workflow. But the project does not push to remote (Git Workflow: "No GitHub push -- only human pushes to remote"). The pre-push hook never fires for agent-committed code. CI-030's "effectiveness" was coincidental (audit-fix phases cleaned up ruff, giving the appearance of enforcement). The ruff gate exists but is **not executed in the agent pipeline**. This is a gate-exists-but-not-enforced issue. However, ruff errors in tests are auto-fixable and non-blocking. Placing on watch list rather than proposing, since the existing CI-030 could be enforced by adding `ruff check tests/` to the verify gate (already partially covered by the instruction to run ruff).

### Pattern 5: Signal Log Incompleteness -- 3rd Consecutive Wave (P7 -- escalation of CI-046)

**Occurrences:** W22 (4/6 missing), W23 (9/9 missing), W24 (only batch summary added after CI flagged it). CI-046 was proposed in W23 as P2 and is still PROPOSED.
**Assessment:** 3 consecutive waves of signal log incompleteness. CI-046 should be applied. No new proposal needed -- escalating CI-046 from PROPOSED to urgent.

---

## Emerging Patterns (watch list)

| Description | Occurrences | Category | Notes |
|-------------|-------------|----------|-------|
| Feature implemented but non-functional in common case (LS1 streaming disabled with tools) | 1 wave (W24) | architecture | Not a code bug -- a design limitation. Most conversations have tools, so streaming rarely activates. Monitor for user-facing impact. |
| FINDINGS.md false resolution (marked Resolved but code unchanged) | 1 wave (W24, DEV-H1) | documentation | Related to P1 (phantom implementations). If agent didn't write code, it also couldn't have fixed the finding. Symptom of the same root cause. |
| CI-030 (ruff on tests/) not actually enforced in agent pipeline | 2 waves (W23, W24) | process | Pre-push hook exists but never fires. Ruff errors are auto-fixable. Low impact per occurrence. |
| QA batch size >5 causes rework amplification | 1 wave (W24) | process | Retro recommends cap at 2-3. Single occurrence. |
| CI-023 (pre-phase test plan) still 0% compliance | 6 consecutive waves (W19-W24) | process | Known ineffective. CI-038 (M1b gate) remains DEFERRED. At this point, CI-023 should be considered a failed intervention. |

---

## Effectiveness of Past Fixes

| Fix | Wave Applied | Status | Evidence |
|-----|-------------|--------|----------|
| CI-009 (L12 write-path scoping) | W19 | **EFFECTIVE** | No violations in W24. 6th consecutive effective wave. |
| CI-013 (M5b findings currency) | W19 | **EFFECTIVE** | W24 batch 1 correctly caught the DEV-H1 false resolution. 6th consecutive wave. |
| CI-015 (findings sync) | W19 | **EFFECTIVE** | Sync enforced in W24 QA. |
| CI-017 (M8b field optionality) | W19 | **EFFECTIVE** | All new Wave 24 Pydantic fields have correct `= None` defaults. NodeModelsConfig all `str | None = None`. |
| CI-030 (ruff on tests/) | W20 | **NOT EFFECTIVE (revised)** | W24 shipped 43 ruff violations in test files. W23 shipped 32. The pre-push hook is never triggered in the agent pipeline. Prior "effective" assessment was coincidental (audit-fix phases cleaned tests). Revising from EFFECTIVE to NOT EFFECTIVE. |
| CI-031 (app.state write-only) | W20 | **EFFECTIVE** | No app.state dead-end stores in W24. 5th consecutive wave. |
| CI-042 (DB dead-end stores) | W22 | **EFFECTIVE** | No new dead-end stores in W24. 3rd consecutive effective wave. However, the EV1 `run_id=""` issue is a variant -- the field exists and is written, but with an empty placeholder value. CI-042 targets "stored but never read." The `run_id` IS read (by analytics) but the VALUE is wrong. This is a data-correctness issue, not a dead-end store. |
| CI-033 (pre-QA deliverable check) | W20 | **PARTIALLY EFFECTIVE** | Batch 2 all deliverables present (CI-033 working). But CI-033 did NOT prevent batch 1 phantom implementations -- the check relies on the implement agent reading PHASE_DETAILS.md and confirming files exist. If the agent falsely reports success, CI-033 is bypassed because it is self-check, not independent verification. |
| CI-023 (pre-phase test plan) | W19 | **NOT EFFECTIVE** | 0% compliance in W24. 6th consecutive wave at 0%. This is a confirmed failed intervention. |
| CI-045 (hollow migration gate) | W23 | **PROPOSED (not yet applied)** | Cannot verify. No new hollow migrations observed in W24 (5 new migrations, all have populated write paths). |
| CI-046 (signal log enforcement) | W23 | **PROPOSED (not yet applied)** | W24 signal log still incomplete. Only batch summaries added. |
| CI-047 (refactoring wave test validation) | W23 | **PROPOSED (not yet applied)** | W24 was not a refactoring wave. Cannot verify. |

---

## Proposals

### CI-048: Post-Implementation File Verification Gate (P1 -- human gate required)

**Evidence:**
- W24 batch 1: 5 deliverables across 3 phases (W23-FIX compose files, CX1 checkpointer/doom-loop/idempotency, VM1 RPC handlers) reported as complete but code not written to disk (RCA: `Plan/RCA/rca_W24_batch1.md`). Required 3 QA cycles + RCA to resolve.
- 1 occurrence, but critical severity with a clear gate gap: NO existing gate independently verifies file modifications after implementation.
- CI-033 (pre-QA deliverable check) is a self-check by the implement agent -- it does not independently verify. When the agent hallucinated completion, CI-033 was also hallucinated.

**Not a duplicate of:** CI-033 (pre-QA deliverable check). CI-033 is an advisory instruction to the implement agent to verify its own deliverables. CI-048 is an independent verification step run by the orchestrator AFTER the implement agent completes, using `git diff --stat` to confirm actual file changes. CI-033 failed because it relies on the same agent that produced the phantom implementation. CI-048 breaks this self-referential loop.

**Estimated impact:** high -- prevents the most impactful process failure observed in the project. The W24 phantom implementation cost 3 QA cycles + RCA + rework across 5 deliverables.

**Implementation burden:** low -- a single sentence in CLAUDE.md Phase Pipeline section requiring the orchestrator to run `git diff --stat` after each implement agent completes and confirm expected files appear in the diff.

**Confidence:** high -- the RCA explicitly identifies the root cause (no independent file verification) and the retro recommends this exact fix.

**Proposed change:** Add to CLAUDE.md Phase Pipeline section, after `implement agent`:

```markdown
- **Post-implementation file verification (CI-048, mandatory)**: After the implement agent completes, the orchestrator independently verifies that expected files were modified by running `git diff --stat`. For each deliverable file listed in PHASE_DETAILS.md, confirm it appears in the diff output. If any planned deliverable has no corresponding file change, the phase is NOT complete -- return to the implement agent with the specific missing files. This check is independent of the agent's self-reported completion status.
```

**Target:** CLAUDE.md (Phase Pipeline section)
**Priority:** P1 (blocks quality -- phantom implementations are the highest-impact process failure observed)

### CI-049: Runtime Data Pipeline Integration Test Requirement (P2)

**Evidence:**
- W24 EV1/EV2: Evaluator persists all records with `run_id=""` because `run_id` absent from AgentState. EV2 analytics returns empty data at runtime. 211 tests pass because they seed data directly into DB. (`Plan/REVIEWS/review_W24_batch2.md` Finding 1, lines 131-158)
- W22 FR5: `CostRecord.run_id` typed string in TypeScript, backend returns null. Tests pass with mock data. (`Plan/CI/signals.md` FR5 entry)
- 2 occurrences across last 3 waves. Pattern: tests validate the *consumer* (analytics aggregation, frontend display) with manually seeded data, masking that the *producer* (graph execution, runner event emission) never generates valid data.

**Not a duplicate of:** CI-016 (S5 integration baseline -- requires >=1 non-mocked test per DB-touching phase). CI-016 targets "at least one test hits the real DB." CI-049 targets a different gap: "at least one test exercises the producer->consumer data pipeline." A phase can satisfy CI-016 (real DB test for analytics aggregation) while violating CI-049 (the aggregation test seeds data directly instead of exercising the full graph->DB->API path). Different scope and failure mode.

**Estimated impact:** medium -- prevents features that appear tested but are inert at runtime. The W24 quality flywheel is the wave's signature feature and produces empty data in production. Avoids ~1 rework cycle per wave for pipeline disconnect bugs.

**Implementation burden:** medium -- adds a new QA checklist item. Requires the reviewer to trace the data flow from producer to consumer and verify at least one test exercises the full path (not just the consumer with seeded data).

**Confidence:** medium -- 2 occurrences, clear pattern, but the fix (a QA checklist item for data pipeline tracing) requires reviewer judgment and may not catch all cases.

**Proposed change:** Add to QA_CHECKLIST.md as a new must-have:

```markdown
### M9: Runtime Data Pipeline Integrity (CI-049)
- [ ] For phases that persist data for consumption by another component (e.g., evaluator writes records, analytics reads them): at least one test exercises the full producer->consumer path. Tests that only validate the consumer by seeding data directly (bypassing the producer) do not satisfy this check.
- [ ] When a new field is required for persistence (e.g., `run_id` for evaluator records), verify it is: (a) present in the data carrier (AgentState, context dict), (b) populated at the source (runner, graph entry point), and (c) consumed at the destination (DB write, API response).
```

**Target:** Plan/QA_CHECKLIST.md (new M9 section)
**Priority:** P2 (significant improvement -- prevents features that appear tested but are inert at runtime)

### CI-050: Ruff Verify Gate for Agent Pipeline (P2)

**Evidence:**
- W24: 43 ruff violations across 10 test files shipped (audit report W24-H3)
- W23: 32 ruff errors in test files at audit (analysis_2026-03-18_w23.md P1)
- CI-030 was applied to `tools/pre-push-hook.sh` but the project's Git Workflow states "No GitHub push -- only human pushes to remote." The pre-push hook never fires during agent work.
- 2 consecutive waves with 30+ ruff violations in tests despite CI-030 being "APPLIED"

**Not a duplicate of:** CI-030 (expand ruff gate to cover tests/). CI-030 targets the pre-push hook and CI workflow. CI-050 targets the agent pipeline's *verify gate* (CLAUDE.md "Verify" section), which is the gate that actually runs during development. CI-030 was correctly applied but to the wrong enforcement point for the agent workflow.

**Estimated impact:** medium -- prevents ruff violations from accumulating to 30-40+ per wave. Auto-fixable but creates noise in audit reports and wastes audit-fix cycles.

**Implementation burden:** low -- add `ruff check tests/` to the CLAUDE.md Verify gate description (where `ruff check` for src/ is already specified).

**Confidence:** high -- clear evidence (2 consecutive waves, CI-030 applied but not executing in the workflow that matters).

**Proposed change:** In CLAUDE.md Gates section, update the Verify gate:

```markdown
- **Verify**: All tests pass + `ruff check src/ tests/` + `mypy` + app loads + feature is wired and callable
```

(Change: `ruff check` becomes `ruff check src/ tests/` to explicitly include test files in the agent verify gate, not just the pre-push hook.)

**Target:** CLAUDE.md (Gates section, Verify)
**Priority:** P2 (prevents recurring ruff violations; low implementation burden)

---

## QA Leniency Assessment

Wave 24 had 2 QA reviews:
- **Batch 1:** FAIL (cycle 1), FAIL (cycle 2), resolved after orchestrator manual fix. The FAIL verdicts were correct -- phantom implementations and unfixed compose files are blocking M1/M5/M7 issues.
- **Batch 2:** PASS_WITH_NOTES (cycle 1). The `run_id=""` EV1/EV2 disconnect was correctly classified as HIGH functional defect but not BLOCKING -- the endpoints work, return correct shapes, and are auth-protected. The decision to note rather than block is reasonable: the fix is a 3-line change (add run_id to AgentState, populate in runner, consume in evaluator), and blocking would have forced a full re-review cycle for a wiring change.

**Assessment:** QA calibration is correct. The batch 1 FAILs caught real phantom implementations. The batch 2 PASS_WITH_NOTES correctly distinguished between "endpoint broken" (blocking) and "data pipeline incomplete" (high note). The new CI-049 proposal would elevate the EV1/EV2 pattern to a must-have in future reviews.

---

## W23 Retro Action Item Disposition (via W24 Retro)

| # | Action | Status in W24 |
|---|--------|---------------|
| 1 | Mandatory post-implementation file verification | NOT DONE (batch 1 FAIL proved the need; CI-048 now proposed) |
| 2 | Cap QA batches at 3 phases | NOT DONE (batch 1 had 7 phases; batch 2 had 10) |
| 3 | Fix run_id gap | NOT DONE (identified in W24 QA as W24-H2; carryover to W25) |

0/3 done. All carried forward as proposals or findings.

---

## Metrics

- Wave: 24
- Phases analyzed: 17 (RV1, W23-FIX, CX1, DI1, MC1, LF1, LS1, LF2, OI1, VM1, PC1, OI5, OI6, EV1, FB1, QV1, EV2)
- Signal rows read: 3 (RV1, CQ1-CQ9 batch, W23-audit-fix -- most W24 phases not in signal log)
- New patterns identified: 2 (phantom implementations, runtime data pipeline disconnect)
- Recurring patterns (previously seen): 3 (signal log incompleteness, ruff in tests, wiring gaps)
- Proposals below evidence threshold (watch list): 5
- Past fixes verified effective: 7/11 (CI-030 revised to NOT EFFECTIVE, CI-033 PARTIALLY EFFECTIVE, CI-023 NOT EFFECTIVE, CI-045/046/047 not yet applied)
- Proposals generated: 3 (P1: 1, P2: 2, P3: 0)

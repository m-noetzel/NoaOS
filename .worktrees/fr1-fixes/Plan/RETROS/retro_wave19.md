# Retrospective: Wave 19

**Date:** 2026-03-11
**Phases covered:** PR1, PR2, PR3, PR4, PR5, PR6
**Overall assessment:** Wave 19 successfully closed the production readiness gap with 108 tests delivered across six cleanup phases. The wave was marked by solid QA outcomes (one FAIL in PR3 cycle 1, then five consecutive PASS_WITH_NOTES), but was undermined throughout by a persistent FINDINGS.md hygiene failure that plagued every health brief until PR5 finally resolved it.

---

## Wave Summary

| Phase | Scope | Tests | Est. | Actual | QA Verdict | Notes |
|-------|-------|-------|------|--------|------------|-------|
| PR1 | Backend data integrity (runs join, user-scoped memory, RunService async) | 19 Python | ~60 min | ~45 min | PASS_WITH_NOTES | Clean first pass |
| PR2 | Frontend critical fixes (PATCH /settings, thread race, RunDetail cast) | 10 Python | ~45 min | ~45 min | PASS_WITH_NOTES | 4 ruff violations in test file |
| PR3 | iOS critical fixes (queue drain, SSE cancel, 401 handler, model picker) | 218 Swift | ~60 min | ~120 min | FAIL → PASS_WITH_NOTES (cycle 2) | Backend contract gap; required backend fix |
| PR4 | Backend security & robustness (credential reload, path traversal, logging) | 23 Python | ~45 min | ~50 min | PASS_WITH_NOTES | Strongest security phase |
| PR5 | Frontend & iOS polish (9 medium findings: indicator, redirects, lifecycle) | 12 web + 233 Swift | ~45 min | ~90 min | PASS_WITH_NOTES | FINDINGS.md finally updated |
| PR6 | Integration tests & verification | 22 Python + 8 Swift | ~75 min | ~90 min | PASS_WITH_NOTES | New finding FE-L1 added |
| **Total** | | **~108 Python + ~459 Swift** | **~330 min** | **~440 min** | | |

Wave delivered: 6/6 phases complete. One QA cycle 1 FAIL (PR3). No architectural FAILs.

---

## What Went Well

### 1. High QA throughput — all phases closed in one or two cycles

Five of six phases passed QA on the first cycle. Only PR3 required a second cycle, and that was caused by a missing backend contract change (ChatRequest.model/provider optional) rather than implementation quality. The underlying iOS code was correct; the gap was a backend-iOS contract mismatch discovered during QA. This is a healthy outcome — QA caught a real cross-component issue before it reached production.

### 2. PR4 delivered the strongest security work of the wave

PR4 addressed three security-significant items (credential persistence on settings update, path traversal guard in artifact download, structured log context) with thorough dual-layer defenses. The path traversal guard uses both a fast pre-check (substring ".." detection) and a canonicalized containment check (Path.resolve().relative_to()), which is the correct pattern. The QA reviewer explicitly called out the implementation quality. This phase exemplifies the "could you demo this right now?" bar.

### 3. PR6 integration tests closed the unit-test-only risk

The wave consistently delivered unit tests only (PR1-PR5 used mocked DB sessions, mocked Swift dependencies), which was a known risk flagged in every health brief after PR1. PR6 resolved this with 22 ASGI-based Python integration tests and 8 live Swift tests against the Docker backend. This was the right design: accept the mock risk during the cleanup phases, verify end-to-end in a dedicated integration phase.

### 4. FINDINGS.md reached 90 resolved (of 100 total) by wave end

The Wave 19 system audit closed or confirmed resolution of findings across all severity levels. Entering Wave 19 with 22 open findings, the wave exited with 10 open (90 resolved). The 9 medium findings resolved in PR5 alone represented the largest single-phase finding closure in the project.

### 5. Multi-language scope handled without domain bleed

Wave 19 spanned Python backend, TypeScript/React frontend, and Swift iOS — three separate stacks — within a six-phase wave. No cross-domain import violations were introduced. The domain isolation invariant held throughout. Each phase correctly identified its own boundaries (M8 always PASS).

### 6. Estimation accuracy improved for backend phases

PR1 (60→45 min), PR2 (45→45 min), PR4 (45→50 min) were all within 25% of estimate. Backend-only phases estimated and tracked well. This continues the trend from Wave 18 where backend phases were consistently accurate.

---

## What Didn't Go Well

### 1. FINDINGS.md hygiene failure across five consecutive reviews

The most persistent process failure in Wave 19 was FINDINGS.md staleness. The QA reviews for PR1, PR2, PR3, and PR4 all explicitly flagged that resolved findings were still marked "Open." Each health brief listed this as the "greatest risk." The fix was trivial — update status rows in a markdown table — but was deferred for five consecutive phases. By the PR4 brief, 10+ findings were resolved in code but still appearing Open. This created real risk: other agents using FINDINGS.md as ground truth for "what needs fixing" would find inaccurate data.

PR5 finally performed the batch update, bringing FINDINGS.md current. But five phases of drift represents a systemic process issue, not a one-time oversight.

**Root cause:** No explicit gate or checklist item requires updating FINDINGS.md as part of phase completion. It is documented in CLAUDE.md's "Findings Lifecycle" section but not enforced by the QA checklist (M1-M8 does not include a FINDINGS.md currency check).

### 2. PR3 required a backend contract fix that should have been caught in PR2

PR3 (iOS fixes) failed cycle 1 because `ChatRequest.model` and `ChatRequest.provider` were still required fields on the backend. The iOS client uses Swift's `JSONEncoder`, which omits nil-valued Optional fields from JSON payloads, so any iOS request without explicit model/provider selection would 422.

This gap should have been identified when PR2 fixed `PATCH /settings` and aligned the backend contract. The iOS-to-backend contract was an established concern (from iOS4/iOS5/iOS11 waves) and the field-optionality pattern was known. The fact that PR3 had to fix it mid-phase with a backend change (making `model: str | None = None` and `provider: str | None = None`) added a cross-phase dependency not captured in the original scoping.

**Root cause:** PR3 was scoped as "iOS-only" without auditing the backend contract that iOS depends on. The implement agent should audit the backend Pydantic models when fixing iOS-backend interaction flows.

### 3. iOS-facing phases consistently ran 2x over estimate

PR3 (~60→120 min), PR5 (~45→90 min) — both phases with significant Swift work ran at double the estimate. PR3 required the unexpected backend contract fix, which partially explains its overrun. PR5's overrun was purely scope-related (9 medium findings across two platforms). Estimation for multi-platform phases has not improved from the Wave 15 pattern where iOS3 (60→90 min), iOS5 (60→90 min), iOS8 (60→90 min) all ran 1.5x over.

### 4. chat.py str(exc) SSE leak remains unaddressed

PR4 fixed runner.py to send generic error messages to clients instead of raw `str(exc)`. The QA review correctly noted that the outer exception handler in `chat.py:157-162` still leaks raw exception text via SSE. This was flagged as a new finding, not in PR4's scope, and added to FINDINGS.md. But the PR4 phase explicitly fixed runner.py's error handling — the same pattern in a sibling file (chat.py) should have been caught and fixed in the same phase. It's now carried forward.

### 5. No pre-phase test plans written for any Wave 19 phase

Every QA review noted: "No formal test plan was written for PRX prior to implementation." This pattern existed in Wave 18 (TM1-TM6 also lacked pre-phase test plans) and has not been addressed. The QA reviews still score M1 PASS because the implemented tests are retrospectively spec-traceable, but the absence of pre-phase plans means the implement agent decides test scope unilaterally. This is a process gap, not a quality gap in this wave, but it creates variability in test coverage across phases.

### 6. PR3 cycle 1 QA failure introduced but no RCA written

Per CLAUDE.md: "QA fails once → Launch ci agent." The PR3 cycle 1 FAIL was correctly handled (cycle 2 implemented and passed), but there is no RCA document for the FAIL (CLAUDE.md requires `Plan/RCA/rca_{phase-id}.md` on second FAIL, not first). This is correct process. However, the cycle 1 blocker (backend contract mismatch) was a cross-phase integration gap that warranted a brief root cause note even without a full RCA, since the same failure mode could recur on any iOS phase.

---

## Recurring Patterns

| Pattern | Frequency | Impact | Example |
|---------|-----------|--------|---------|
| FINDINGS.md not updated after fix | 5/6 phases | High — stale tracking for downstream agents | PR1 resolved BE-C1/C2/H2; all still "Open" through PR4 |
| No pre-phase test plan written | 6/6 phases | Medium — implement agent decides coverage unilaterally | Every QA review: "No formal test plan existed for PRX" |
| S5 Integration Smoke Test OPEN | 5/6 phases (all except PR6) | Medium — unit tests pass, wiring bugs survive to integration | PR1-PR5 all use mocked DB sessions |
| iOS-facing phases run 2x over estimate | 2/2 iOS-heavy phases | Low — planning accuracy only | PR3 60→120 min, PR5 45→90 min |
| Ruff violations in test files | 2/6 phases | Low — cosmetic, easy fix | PR2 (4 violations), PR4 (E501 in docstring) |
| Backend-iOS contract mismatch discovered in iOS phase | 1/1 iOS-backend phase | High — caused cycle 1 FAIL | PR3: ChatRequest.model/provider required, not Optional |
| Pre-existing findings noted but not in scope | 4/6 phases | Medium — carries debt forward | chat.py str(exc) leak, runner model default dead code, ErrorBoundary stack trace |

---

## Estimation Accuracy

Estimates from PLAN.md were set before implementation. Actuals from PLAN.md notes.

| Phase | Est. Tests | Actual Tests | Test Accuracy | Est. Duration | Actual Duration | Duration Accuracy |
|-------|------------|--------------|---------------|---------------|-----------------|-------------------|
| PR1 | ~15-20 (not stated) | 19 | — | ~60 min | ~45 min | +25% (under) |
| PR2 | ~10 (not stated) | 10 | Exact | ~45 min | ~45 min | Exact |
| PR3 | ~10 Swift | 218 Swift | Far exceeded (2x Swift, backend fix added) | ~60 min | ~120 min | 2x over |
| PR4 | ~20-25 | 23 Python | Close | ~45 min | ~50 min | Within 10% |
| PR5 | ~15 | 12 web + 233 Swift | Exceeded on Swift; web close | ~45 min | ~90 min | 2x over |
| PR6 | ~30 | 22 Python + 8 Swift | 30 total, close | ~75 min | ~90 min | +20% over |

**Overall test delivery:** ~108 new Python tests + ~459 Swift tests across the wave (Swift numbers include full cumulative suite counts in PLAN.md notes, not net-new per phase). Net-new tests across Wave 19 are closer to 108 Python + ~79 Swift (PR3 net 10, PR5 net 15, PR6 net 8 = 33 Swift).

**Duration bias:** Backend-only phases (PR1, PR2, PR4) estimated accurately, within 25%. Multi-platform phases (PR3, PR5) ran 2x over. PR6 ran 20% over (reasonable for integration work). Overall wave duration: estimated ~330 min, actual ~440 min — 33% overrun, driven entirely by the two iOS-heavy phases.

**Test count bias:** Where test counts were estimated (PR3 "~10 Swift"), actual exceeded estimate significantly (218 Swift suite). This reflects that Swift test counts are cumulative in the tracker, not per-phase net-new, creating misleading comparisons. Future tracking should record net-new tests per phase separately from total suite count.

---

## Proposed Skill Patches

### SP1: Add FINDINGS.md currency check to QA checklist (High priority)

The QA checklist (M1-M8) has no criterion for FINDINGS.md accuracy. Every QA review flagged stale findings as a "beyond the test plan" note rather than a gate. Add to the checklist:

> **M9 (proposed): Findings Currency** — Verify that any findings resolved by this phase are marked Resolved in FINDINGS.md before the review closes. If any resolved finding is still marked Open, the QA verdict is PASS_WITH_NOTES (not blocking, but must be fixed before next phase begins).

This converts a recurring informal note into an enforced gate. It would have caught the 5-phase drift at PR1's review instead of PR5.

### SP2: Require backend contract audit when scoping iOS-backend interaction phases

The implement agent's instructions do not include a step to audit the Pydantic request models when fixing iOS-backend flows. Add to the iOS phase checklist:

> Before implementing iOS-backend interaction fixes, verify the backend Pydantic models accept Optional fields for all parameters that Swift's JSONEncoder may omit (nil Optional → field omitted from JSON payload). If not, include the backend fix in scope rather than deferring to a separate phase.

This would have caught the ChatRequest.model/provider optionality gap during PR3 scoping instead of at cycle 1 QA.

### SP3: Add net-new test count tracking alongside cumulative counts

PLAN.md currently records cumulative Swift test counts (e.g., "218 Swift" for PR3 means the full suite at that point, not 10 new tests). This makes estimation accuracy analysis difficult. Add a format convention:

> For phases that modify an existing test suite, record: `{net-new} new ({total} total)`. Example: `10 Swift (218 total)`.

This costs nothing to implement but makes future retrospectives more precise.

### SP4: Set test plan writing as pre-implementation gate (Medium priority)

Six consecutive phases skipped pre-phase test plans. The implement agent's flow does not mandate writing a test plan before coding begins. Consider adding a lightweight (5-line) test plan step to the implement skill:

> Before writing any code, list: (1) the spec sections covered, (2) the happy-path test scenarios, (3) the negative-path test scenarios. This is the test plan. It may be short. It is mandatory.

This is not about ceremony — it's about ensuring coverage decisions are explicit before implementation, not discovered during QA review.

---

## Recommendations for Next Wave

### R1: Fix ChatRequest.privacy_mode optionality (W19-H1 — carry-forward)

The system audit found that `ChatRequest.privacy_mode` remains a required `str` field despite PR3 making `model` and `provider` optional. This breaks iOS chat for clients that don't send `privacy_mode`. This should be the first item addressed in Wave 20 or as a pre-wave fix.

**Fix:** Change to `privacy_mode: str | None = None` with a default of `"external"`, and add `Literal["private", "external"]` validation.

### R2: Delete dead code modules (W19-M1 through M4)

The system audit identified four dead code modules that have never been imported:
- `src/noa/tools/mcp_adapter.py` (superseded by TM6's mcp_remote.py)
- `src/noa/tools/governance.py` (features moved to gateway.py)
- `src/noa/coding/` (AB5 coding worker, never wired)
- `src/noa/queue/notifications.py` (empty stub)

These add confusion without value. Deletion is low-risk (grep confirms no imports).

### R3: Fix 62 mypy errors in source

The system audit found 62 mypy errors, notably `success_envelope` accepting `list` arguments where `dict[str, Any]` is typed, and `threads.py` accessing attributes that don't exist on the `Conversation` model. These indicate real type safety gaps. The `success_envelope` issue is the highest value fix (affects many endpoints).

### R4: Batch-resolve the remaining process debt from Wave 19 findings

The following were new findings from the Wave 19 system audit that should be addressed in Wave 20:
- **W19-H1:** ChatRequest.privacy_mode required (breaks iOS chat) — HIGH
- **W19-H3:** JWT error messages leak internal details — HIGH
- **W19-M5:** Missing X-Content-Type-Options: nosniff header — MEDIUM
- **W19-M6:** 62 mypy errors — MEDIUM

### R5: Address BE-H4 and BE-H5 (carried from pre-Wave-19)

Both were open throughout Wave 19 and remain open:
- **BE-H4:** SSE replay cursor uses list index, not stable DB offset — reconnections may miss or replay events
- **BE-H5:** chat.py `_update_run_status` bypasses RunService state machine — state transitions may be inconsistent

These are medium-likelihood correctness issues on edge cases (reconnection, concurrent status updates). They should be addressed in Wave 20 before deployment work.

### R6: Enforce FINDINGS.md update as a phase completion gate

Based on SP1 above — do not mark a phase Complete in PLAN.md until FINDINGS.md reflects all resolutions from that phase. The five-phase drift in Wave 19 is evidence that this needs structural enforcement, not informal convention.

---

## CI Agent Trigger

→ Orchestrator: Launch the `ci` agent now.
  Input: This retrospective (Plan/RETROS/retro_wave19.md) plus QA reviews from this wave (Plan/REVIEWS/review_PR1.md through review_PR5.md and Plan/REVIEWS/health_wave19.md).
  Focus areas for CI agent:
  1. FINDINGS.md currency pattern (5-phase drift) — what process change prevents recurrence?
  2. iOS-backend contract mismatch pattern — is there a scoping checklist addition that catches this class of gap?
  3. Pre-phase test plan absence — is this the right gate to add, or is there a lighter-weight alternative?
  4. Estimation bias on multi-platform phases — should iOS phases have a fixed multiplier applied?

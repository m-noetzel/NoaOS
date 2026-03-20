# Continuous Improvement Analysis — 2026-03-11 (Wave 19 Retrospective)

## Summary

Wave 19 (PR1–PR6) delivered 6/6 phases with no architectural FAILs, but was defined by four systemic
process failures that accumulated across the entire wave and were only partially resolved by wave end.
Two of these failures are genuine new patterns (FINDINGS.md update never enforced as a blocking gate;
iOS-backend contract not audited at phase scoping time). Two are wave-level confirmations of existing
proposals that were never actioned (pre-phase test plans absent for all six phases; iOS phase duration
systematically underestimated). This analysis synthesizes the five per-phase CI analyses (PR1–PR5) with
the retrospective and wave system audit to identify what changed, what was confirmed, and what structural
process changes would prevent recurrence.

All four focus areas from the retrospective are addressed below with evidence-backed proposals. Six new
proposals are raised (CI-022 through CI-027). Four prior P1 proposals remain outstanding (CI-013, CI-016,
CI-017, CI-020) and are re-confirmed as required actions before Wave 20 begins.

---

## Problems Found

| ID | Category | Severity | Occurrences | Description |
|----|----------|----------|-------------|-------------|
| W19-A | process | critical | 5/6 phases | FINDINGS.md not updated at phase completion — resolved findings remained Open for up to 5 consecutive phases |
| W19-B | architecture | high | 1 (PR3 cycle 1 FAIL) | Backend Pydantic contract not audited when scoping iOS-backend interaction phase — `ChatRequest.model`/`provider` required fields caused 422 on all iOS requests |
| W19-C | process | medium | 6/6 phases | No pre-phase test plan written for any Wave 19 phase — implement agent decides coverage scope unilaterally |
| W19-D | process | medium | 2/2 iOS-heavy phases | iOS-facing phases ran 2x over estimate — duration underestimation is structural, not one-time |
| W19-E | testing | medium | 5/6 phases | S5 Integration Smoke Test OPEN across PR1–PR5; closed only by PR6 dedicated integration phase |
| W19-F | architecture | medium | 1 (W19-H1 post-wave) | `ChatRequest.privacy_mode` still required (str, no default) after PR3 fixed model/provider — partial fix left a sibling field broken |
| W19-G | architecture | medium | 1 (PR3 note, PR5 QA) | `model=None` propagates from API boundary through runner pipeline into SSE event payload (`"model": null`) — L13 invariant violation |

---

## Patterns Identified

### Pattern 1: FINDINGS.md Update Is Advisory, Not Enforced

**Phases affected:** PR1, PR2, PR3, PR4, PR5 (5 consecutive phases; resolved only at PR5)

**Evidence chain:**
- PR1 resolved BE-C1, BE-C2, BE-H2, BE-M2 — none updated in FINDINGS.md (`review_PR1.md` notes section)
- PR2 resolved BE-H3, FE-C1, FE-H1, FE-H2 — cumulative stale count: 7 entries (`health_2026-03-11_pr2.md` lines 2-8)
- PR3: FINDINGS.md update status unconfirmed — drift continues
- PR4 resolved BE-H1, BE-M3, BE-M4 — cumulative stale count: 10+ entries (`review_PR4.md` line 113: "fourth consecutive review flagging stale FINDINGS.md")
- PR5: batch update performed — FINDINGS.md brought current for the first time since the wave began
- `retro_wave19.md` line 57-59: "Five phases of drift represents a systemic process issue, not a one-time oversight."
- `retro_wave19.md` line 61: "Root cause: No explicit gate requires updating FINDINGS.md as part of phase completion."

**Prior proposals:** CI-013 (M5b gate, P1) and CI-015 (CLAUDE.md pipeline step, P2) were raised in the PR2 analysis. CI-020 (P1 escalation after 4 consecutive phases) was raised in PR4. All three remained unactioned through PR5. The retrospective confirms the structural root cause: CLAUDE.md documents the rule but it is not a pipeline gate — it is advisory text.

**Pattern frequency across project history:** First wave where this accumulated to 5 consecutive phases. Pre-Wave-19 health briefs occasionally noted stale findings, but none showed more than 2 consecutive phases of drift.

**Proposed fix (CI-022):** Strengthen the gate so the implement agent cannot submit for QA until FINDINGS.md is current. See proposal below.

---

### Pattern 2: iOS-Backend Contract Gap Caught at QA, Not at Scoping

**Phases affected:** PR3 (Cycle 1 FAIL), plus the post-wave W19-H1 finding (privacy_mode still required)

**Evidence chain:**
- `review_PR3.md` (Cycle 1): 422 errors on all iOS chat requests — `ChatRequest.model` and `ChatRequest.provider` were required Pydantic fields; Swift's JSONEncoder omits nil-valued Optional fields
- Fix applied in PR3: `model: str | None = None`, `provider: str | None = None`
- System audit W19-H1 (`health_wave19.md` lines 20-29): `ChatRequest.privacy_mode` still declared as required `str` — same class of gap, missed by PR3
- `retro_wave19.md` line 68-69: "PR3 was scoped as 'iOS-only' without auditing the backend Pydantic models that iOS depends on."
- Prior related instance: iOS11 `ApprovalDecision.decision` field required enum value not matching Swift encoding convention (`analysis_2026-03-11_pr3.md` line 33)

**Pattern frequency:** Two confirmed instances in the QA record where iOS phase scope did not include backend contract verification, causing a failure discovered at QA rather than scoping. The privacy_mode regression after PR3's partial fix confirms that even when the pattern is caught once, the same gap recurs on sibling fields in the same request model.

**Prior proposals:** CI-017 (M8b Cross-Language Field Optionality gate, P1) was raised in the PR3 analysis to add a QA checklist item requiring all optional mobile fields to have `= None` defaults. This addresses the detection side but not the prevention side (scoping). CI-022 (proposed below) addresses prevention.

**The second failure (W19-H1):** After fixing `model` and `provider`, the implement agent did not scan for other required fields in the same `ChatRequest` model. `privacy_mode` was the only remaining required `str` field and it was missed. This suggests the fix was reactive field-by-field rather than a systematic audit of the full request model.

---

### Pattern 3: Pre-Phase Test Plans Absent Across All Phases (Wave 18 + Wave 19)

**Phases affected:** All 6 Wave 19 phases (PR1–PR6). Also all Wave 18 phases (TM1–TM6) per retrospective reference.

**Evidence chain:**
- `review_PR1.md` line 27: "No formal test plan was written for PR1 prior to implementation."
- `review_PR2.md` line 44: (same note)
- `review_PR3.md`, `review_PR4.md`, `review_PR5.md`: same note in all
- `retro_wave19.md` lines 79-81: "Every QA review noted: 'No formal test plan was written for PRX prior to implementation.' This pattern existed in Wave 18 (TM1-TM6 also lacked pre-phase test plans) and has not been addressed."
- `retro_wave19.md` line 81: "the absent of pre-phase plans means the implement agent decides test scope unilaterally."

**Existing state:** QA criterion M1 (Spec Traceability) is scored PASS as long as tests are retrospectively traceable to spec sections. This means the absence of a pre-phase plan is never a blocking issue — only the final test coverage matters. There is no current gate that fires before implementation begins.

**Pattern frequency:** 12+ consecutive phases without a pre-phase test plan (Wave 18 TM1-TM6 + Wave 19 PR1-PR6 = 12 phases confirmed). The pattern predates Wave 18 — there is no evidence of pre-phase test plans in any prior wave's QA reviews.

**Why this matters:** Without a pre-phase test plan, the implement agent decides what to test during implementation, which creates two risks: (1) coverage gaps that are not discovered until QA review, when they are expensive to address; (2) variability in test quality across phases — some agents test thoroughly, others focus on happy paths.

**Prior proposals:** None. This is the first CI proposal targeting this specific gap. The retrospective's SP4 sketch provides the basis for CI-023 below.

---

### Pattern 4: Multi-Platform Phase Duration Systematically Underestimated

**Phases affected:** PR3 (60→120 min, 2x over), PR5 (45→90 min, 2x over). Prior waves: iOS3 (60→90 min), iOS5 (60→90 min), iOS8 (60→90 min).

**Evidence chain:**
- `retro_wave19.md` lines 73-74: "PR3 (~60→120 min), PR5 (~45→90 min) — both phases with significant Swift work ran at double the estimate... Estimation for multi-platform phases has not improved from the Wave 15 pattern."
- `retro_wave19.md` duration table: backend-only phases (PR1, PR2, PR4) estimated within 25%; multi-platform phases (PR3, PR5) all 2x over
- Prior wave data: Wave 15 iOS3/iOS5/iOS8 all at 1.5-2x over estimate
- `retro_wave19.md` line 118: "Overall wave duration: estimated ~330 min, actual ~440 min — 33% overrun, driven entirely by the two iOS-heavy phases."

**Root cause:** Phase estimates do not apply a multiplier for phases that span multiple language stacks. The phase planning skill sets estimates based on scope descriptions without a structured heuristic for cross-platform work.

**Pattern frequency:** At least 5 iOS/multi-platform phases across Waves 15 and 19 have run 1.5-2x over. Backend-only phases in the same waves have been accurate. The pattern is consistent enough to treat as a calibration rule rather than an estimation error.

**Prior proposals:** None. This is the first CI proposal targeting estimation calibration for multi-platform phases.

---

### Pattern 5: Partial Fix Leaves Sibling Fields Unaddressed (W19-H1)

**Phases affected:** PR3 (fix applied), system audit (gap discovered)

**Evidence chain:**
- PR3 fixed `ChatRequest.model` and `ChatRequest.provider` to be optional
- `health_wave19.md` lines 20-29: W19-H1 found that `ChatRequest.privacy_mode` remains required (`str`, no default)
- The same `ChatRequest` class in `chat.py:32` had three fields: model, provider, privacy_mode. Two were fixed; one was not.
- `health_wave19.md` endpoint matrix: `/api/v1/chat` returns 422 for all iOS chat requests (W19-H1)

**Root cause:** When fixing field optionality for a specific breaking case (model/provider missing), the fix was scoped to only the two reported fields rather than auditing all fields in the same request model for the same class of issue. This is an instance of reactive field-by-field patching versus systematic model review.

**This pattern reinforces CI-017 (M8b gate):** A reviewer step that audits the entire request model rather than just the reported fields would catch the missed privacy_mode field at PR3 QA rather than at the post-wave system audit.

---

## Effectiveness of Past Fixes

| Fix | Applied | Wave 19 Outcome |
|-----|---------|-----------------|
| CI-009 (L12 Write-Path User Scoping — ARCH_INVARIANTS) | 2026-03-11 | No new write-path scoping violations in PR2–PR6. BE-M5 pre-existing; scheduled PR4 fix was not confirmed in the QA record. Effective for new code. |
| CI-013 (M5b Findings Currency Gate) | NOT APPLIED | FINDINGS.md drifted 5 consecutive phases. Proposed as P1 after PR2; not actioned through wave end. |
| CI-015 (Findings Sync pipeline step — CLAUDE.md) | NOT APPLIED | Same outcome as CI-013. CLAUDE.md still documents the rule as advisory text. |
| CI-016 (S5 Integration Test Baseline) | NOT APPLIED (PR6 satisfied it manually) | S5 OPEN 5/6 phases. PR6's integration tests closed the gap retroactively. The fix worked only because PR6 was explicitly scoped to address it; the gate was never applied to mandate it. |
| CI-017 (M8b Cross-Language Field Optionality) | NOT APPLIED | PR3 Cycle 1 FAIL occurred. W19-H1 (privacy_mode) discovered at system audit. Gate would have caught both. |
| CI-020 (FINDINGS.md cleanup — immediate human gate) | NOT CONFIRMED before PR5 | FINDINGS.md was updated in PR5, resolving the drift. Whether CI-020 was explicitly actioned or PR5 proactively updated FINDINGS.md is unclear from the record. |
| ruff E722/BLE001 rules | Applied (pre-Wave 19) | M6 passed clean in all 6 PR phases. No new bare-except violations. Effective and holding. |
| M5b gate (from CI-013 — now in QA_CHECKLIST.md) | Applied between PR2 and current state | Present in QA_CHECKLIST.md as of this analysis. Did not prevent the Wave 19 drift (gate was added mid-wave or after the fact). Will be effective for Wave 20. |
| M8b gate (from CI-017 — now in QA_CHECKLIST.md) | Applied between PR3 and current state | Present in QA_CHECKLIST.md as of this analysis. W19-H1 (privacy_mode) indicates the gate may have been added after PR3 completed. Will be effective for Wave 20. |

**Summary of outstanding P1 gates:** CI-013, CI-016, CI-017, and CI-020 were all raised during Wave 19 and not actioned in time to prevent the problems they target. The QA checklist now shows M5b and M8b as applied, suggesting they were added after the fact. If those gates are now in place, their effectiveness will be measurable in Wave 20 phase reviews.

---

## Proposals

### CI-022 — Implement Agent: Full Request Model Scan When Fixing iOS-Backend Contract Gaps (P1)

**Evidence:**
- PR3 fixed `model` and `provider` but missed `privacy_mode` in the same `ChatRequest` class (`chat.py:32-34`)
- System audit W19-H1 (`health_wave19.md` lines 20-29): `privacy_mode` still required after PR3, breaking all iOS chat
- `retro_wave19.md` line 66-69: "This gap should have been identified when PR2 fixed PATCH /settings... the field-optionality pattern was known."
- Related prior gap: iOS11 `ApprovalDecision.decision` enum casing mismatch (`analysis_2026-03-11_pr3.md` line 33)

**Pattern:** Two confirmed instances where an iOS-backend contract fix addressed only the specific field that caused the reported failure, leaving sibling fields in the same request model with the same class of defect.

**Existing coverage:** CI-017 (M8b gate, now in QA_CHECKLIST.md) requires that all fields a client may omit have `= None` defaults. However, M8b is a QA review step, applied after implementation. It does not prevent the partial fix from being submitted in the first place. The gap is at the implement agent's scoping step.

**Proposed change to `Plan/ARCH_INVARIANTS.md`** (add to or adjacent to L13):

```markdown
### L14 — Full Model Audit on iOS-Backend Contract Fix

When an iOS-backend phase fixes a field optionality issue (making a Pydantic field Optional to accommodate Swift's nil-omission encoding), the implement agent MUST audit ALL fields in the same request model for the same issue — not only the fields cited in the bug report.

**Procedure:** For every `BaseModel` modified to make a field Optional, run a systematic check:
1. List all remaining `str`, `int`, `bool` fields with no default value.
2. For each: ask "Can the iOS client legally omit this field?" (i.e., is the corresponding Swift property `Optional<T>`?)
3. If yes: make the field `Optional` with a sensible default (`None` or a domain default).

**Evidence:** PR3 fixed `model` and `provider` in `ChatRequest` but missed `privacy_mode` — discovered post-wave in the system audit (W19-H1). The privacy_mode omission broke all iOS chat requests despite PR3 being explicitly scoped to fix iOS-backend 422s.
```

**Target:** `Plan/ARCH_INVARIANTS.md`

**Priority:** P1 — this caused a post-wave HIGH finding (W19-H1) that blocks iOS chat functionality. The same failure mode is expected in any future iOS-backend phase that modifies request models.

**Impact estimate:** W19-H1 will require a fix in Wave 20. Had L14 existed during PR3, the privacy_mode gap would have been caught at implementation time, eliminating W19-H1 and its Wave 20 fix entirely.

---

### CI-023 — Implement Skill: Mandatory Lightweight Pre-Phase Test Plan (P2)

**Evidence:**
- All 6 Wave 19 phases (PR1–PR6) completed without a pre-phase test plan (`review_PR1.md` line 27, plus same note in all subsequent reviews)
- All Wave 18 phases (TM1–TM6) also lacked pre-phase test plans (referenced in `retro_wave19.md` line 80)
- `retro_wave19.md` SP4: "Six consecutive phases skipped pre-phase test plans. The implement agent's flow does not mandate writing a test plan before coding begins."
- `retro_wave19.md` line 81: "the absence of pre-phase plans means the implement agent decides test scope unilaterally. This is a process gap, not a quality gap in this wave, but it creates variability in test coverage across phases."
- Pattern confirmed across 12+ consecutive phases (Wave 18 + Wave 19). No prior wave has pre-phase test plans in the QA records.

**Root cause:** The implement agent skill has no step that requires writing down what will be tested before implementation begins. The QA checklist (M1 Spec Traceability) only verifies retrospective traceability — tests that were written are traceable, but no gate checks whether the intended coverage was determined upfront.

**Proposed change to the `implement` agent's pre-implementation steps** (add to `.claude/agents/implement.md`):

```markdown
**Pre-Implementation Test Plan (mandatory, 5-10 lines max):**

Before writing any code, write a brief test plan covering:
1. Spec sections this phase addresses (cite SPEC.md §X.Y or finding IDs)
2. Happy-path scenarios to test (one per deliverable)
3. Negative-path scenarios to test (at least one per deliverable: auth failure, invalid input, missing resource)
4. Integration scenarios (if any DB-touching endpoint is modified: at least one scenario with a real ASGI test or real SQLite session)

This plan is not a formal document — it is a checklist that determines what tests exist before the QA reviewer sees the code. Write it in the QA review as a "Test Plan" section.
```

**Target:** `.claude/agents/implement.md`

**Priority:** P2 — not a blocking issue (M1 still passes without it), but the 12-phase absence demonstrates the pattern is entrenched. Adding the plan step to the implement agent's flow is the minimal structural change that would surface coverage gaps before implementation rather than at QA.

**Impact estimate:** Pre-phase test plans would have identified the missing real-DB test for PATCH settings (PR2) and the iOS integration test gap (PR3) before implementation began, reducing the number of QA notes per phase. With 6 phases in a typical wave, this saves approximately 1-2 QA note cycles per wave by surfacing coverage decisions earlier.

---

### CI-024 — Phase Planning: Apply 2x Duration Multiplier for Multi-Platform Phases (P2)

**Evidence:**
- `retro_wave19.md` duration table: PR3 (60→120 min), PR5 (45→90 min) — both 2x over
- Prior waves: iOS3 (60→90 min), iOS5 (60→90 min), iOS8 (60→90 min) — all 1.5-2x over
- `retro_wave19.md` line 118: "estimated ~330 min, actual ~440 min — 33% overrun, driven entirely by the two iOS-heavy phases"
- Backend-only phases (PR1, PR2, PR4) accurate within 25% in the same wave
- Pattern confirmed: 5+ multi-platform phases across Waves 15 and 19 systematically run 1.5-2x over estimate

**Root cause:** Phase estimation does not apply a structural multiplier for cross-platform phases. The phase planning skill estimates scope in the same way regardless of language count. Swift adds context-switching overhead, build system setup, and cross-language debugging that is not present in Python-only phases.

**Proposed addition to `Plan/ARCH_INVARIANTS.md`** or phase planning skill (`.claude/skills/phase-planning/SKILL.md`):

```markdown
### Multi-Platform Phase Duration Heuristic

When estimating duration for a phase that includes both Swift (iOS) and Python (backend) changes,
or both TypeScript (frontend) and Python (backend) changes:

- Apply a 1.5x multiplier to the raw scope estimate for any phase touching two language stacks
- Apply a 2x multiplier for phases touching three language stacks (Python + Swift + TypeScript)

**Basis:** Wave 15 iOS phases (iOS3/iOS5/iOS8) averaged 1.7x over estimate. Wave 19 multi-platform
phases (PR3/PR5) averaged 2.0x over estimate. Backend-only phases in the same waves were accurate
within 25%.

**Exception:** Pure Swift phases (iOS4, iOS6) with no backend changes may use standard estimates
— the overhead is language context-switching between Python and Swift, not Swift development alone.
```

**Target:** `.claude/skills/phase-planning/SKILL.md`

**Priority:** P2 — no quality impact, but the 33% wave-level duration overrun in Wave 19 affects planning reliability. Wave 20 includes deployment work (potentially multi-platform), and Wave 22 includes iOS widget/voice work. Calibrated estimates prevent scope creep from appearing as estimation failures.

**Impact estimate:** A 2x multiplier applied to PR3 (60 min → 120 min budgeted) and PR5 (45 min → 90 min budgeted) would have produced an estimated wave duration of ~420 min against the actual 440 min — a 5% error versus the actual 33% error. No phases would have appeared to "run over."

---

### CI-025 — Phase Scoping: iOS-Backend Phases Must Include Backend Contract Audit Step (P1)

**Evidence:**
- `retro_wave19.md` line 68-69: "PR3 was scoped as 'iOS-only' without auditing the backend Pydantic models that iOS depends on."
- PR3 Cycle 1 FAIL: `ChatRequest.model`/`provider` required fields causing 422 on all iOS chat requests — a gap that existed before PR3 began but was not identified during scoping (`review_PR3.md` Cycle 1)
- iOS11 prior instance: `ApprovalDecision.decision` enum mismatch between Swift and Python (`analysis_2026-03-11_pr3.md` line 33)
- `retro_wave19.md` SP2: "Before implementing iOS-backend interaction fixes, verify the backend Pydantic models accept Optional fields for all parameters that Swift's JSONEncoder may omit."

**Root cause:** When a phase is scoped as "iOS fixes," the scope description naturally focuses on Swift changes. The backend Pydantic models are not audited as part of phase scoping unless the phase explicitly includes backend work. But any iOS phase that modifies or exercises an iOS-to-backend call implicitly depends on the backend contract being compatible.

**This is distinct from CI-017 (M8b):** CI-017 is a QA review gate applied after implementation. CI-025 targets the scoping step — what the implement agent should do before writing the first line of code on an iOS-backend phase.

**Proposed addition to CLAUDE.md**, in the "Implementation rules" section:

```markdown
- **iOS-backend phase contract audit**: Before implementing any fix to an iOS-backend interaction
  flow (queue drain, SSE, auth, chat, approvals), the implement agent MUST:
  1. Identify the backend Pydantic request model(s) the iOS client sends to.
  2. For each field in those models: verify `field: Type | None = None` if the corresponding Swift
     property is `Optional<T>` (Swift omits nil fields; required Pydantic fields return 422).
  3. If any required field should be optional, include the backend fix in scope — do not defer to a
     separate phase. Cross-phase contract fixes create Cycle 1 FAILs (PR3 evidence).
```

**Target:** `CLAUDE.md` (Implementation rules section)

**Priority:** P1 — PR3 Cycle 1 FAIL is direct evidence that this step was missing. A Cycle 1 FAIL wastes a full QA cycle plus the time to apply the backend fix. W19-H1 (privacy_mode) shows the gap recurs even after a partial fix if the audit is not systematic.

**Impact estimate:** PR3's Cycle 1 FAIL cost approximately one QA cycle (estimate: 30-45 min), plus the backend contract fix within PR3 scope that was not originally planned (~30 min). W19-H1 will cost additional fix time in Wave 20. A pre-implementation contract audit would have prevented all three costs.

---

### CI-026 — QA Checklist: Require Scope Completeness Note for Related Unaddressed Issues (P2)

**Evidence:**
- `retro_wave19.md` lines 77-78: "PR4 addressed runner.py's error handling — the same pattern in a sibling file (chat.py) should have been caught and fixed in the same phase. It's now carried forward."
- W19 pattern: 4/6 phases had pre-existing findings noted but not in scope — each creates a follow-on task (`retro_wave19.md` recurring patterns table, row 7)
- chat.py str(exc) SSE leak (CI-019), runner model dead-code default (CI-018), ErrorBoundary stack trace (CI-021) — all were "noted but deferred" patterns
- The system audit identified W19-M1 through M4 (dead code modules) — all were previously knowable from source inspection but were never noted as in-scope for relevant phases

**Root cause:** When a phase fixes a pattern (e.g., `str(exc)` leak in error handlers), there is no QA gate that checks whether other files with the same pattern were also fixed or explicitly excluded from scope with a justification. Related issues accumulate as carry-forward debt with no structural checkpoint.

**Proposed addition to `Plan/QA_CHECKLIST.md`**, as an extension to M5 (Implementation Completeness):

```markdown
| M5c | Related-Issue Scope Completeness | When a phase fixes a code pattern (e.g., "remove str(exc) from error handlers"), the QA reviewer must check: are there other files with the same pattern that were not fixed? If yes, the reviewer must either (a) confirm the phase explicitly deferred them with a rationale note, or (b) require the implement agent to add a FINDINGS entry tracking the deferred instances. A pattern fix that silently leaves related instances unaddressed is a M5c note (non-blocking, but requires a FINDINGS entry or explicit deferral before PASS_WITH_NOTES is issued). |
```

**Target:** `Plan/QA_CHECKLIST.md`

**Priority:** P2 — not a blocking issue, but prevents the "noted but not tracked" accumulation observed in Wave 19 (at least 4 instances). Without M5c, these deferred items fall into QA notes that are not guaranteed to become FINDINGS entries.

**Impact estimate:** 4 instances in Wave 19 where a related issue was noted in QA but not tracked in FINDINGS.md. At an average of 15 minutes to rediscover and add a finding to the backlog, this is ~1 hour of avoidable overhead per wave. More importantly, untracked issues are occasionally re-investigated from scratch — W19-M1 through M4 dead code modules fit this category.

---

### CI-027 — FINDINGS.md: Track W19-H1 (ChatRequest.privacy_mode Required) (P3)

**Evidence:**
- `health_wave19.md` lines 20-29: W19-H1 — `ChatRequest.privacy_mode` is still `str` (required), not `str | None = None`. iOS clients that omit `privacy_mode` get 422. The only failing test in the suite is `test_ios5_chat_contract.py::test_chat_request_schema_rejects_invalid_privacy_mode`.
- `retro_wave19.md` R1: "Fix ChatRequest.privacy_mode optionality (W19-H1 — carry-forward). This should be the first item addressed in Wave 20."
- `health_wave19.md` lines 182-185: Endpoint test matrix confirms `/api/v1/chat` returns 422 for all requests.

**Proposed FINDINGS.md entry:**

```
| W19-H1 | High | ChatRequest.privacy_mode is still required (str, not optional) — iOS clients that omit privacy_mode get 422. Also lacks Literal["private","external"] validation. Fix: `privacy_mode: str | None = None` with Literal validation and default of "external". | Open | — |
```

**Target:** `Plan/FINDINGS.md`

**Priority:** P3 — proposing a FINDINGS.md entry only. The fix itself should be Wave 20's first task (per retrospective R1). This CI proposal ensures the finding is tracked with the correct severity before Wave 20 planning begins.

---

## Wave 19 CI Proposal Summary

| ID | Title | Priority | Target | New or Prior |
|----|-------|----------|--------|--------------|
| CI-022 | Full Request Model Audit on iOS-Backend Contract Fix (L14) | P1 | Plan/ARCH_INVARIANTS.md | NEW |
| CI-023 | Mandatory Lightweight Pre-Phase Test Plan in Implement Skill | P2 | .claude/agents/implement.md | NEW |
| CI-024 | 2x Duration Multiplier for Multi-Platform Phases | P2 | .claude/skills/phase-planning/SKILL.md | NEW |
| CI-025 | iOS-Backend Phase Pre-Implementation Contract Audit Step | P1 | CLAUDE.md | NEW |
| CI-026 | M5c: Related-Issue Scope Completeness QA Gate | P2 | Plan/QA_CHECKLIST.md | NEW |
| CI-027 | Track W19-H1 in FINDINGS.md (ChatRequest.privacy_mode) | P3 | Plan/FINDINGS.md | NEW |

### Prior P1 Gates — Status at Wave End

| ID | Title | Status | Note |
|----|-------|--------|------|
| CI-013 | M5b Findings Currency Gate | QA_CHECKLIST.md shows M5b present — appears APPLIED | Verify effective Wave 20 |
| CI-015 | Findings Sync as CLAUDE.md Pipeline Step | Not confirmed in CLAUDE.md | Still required |
| CI-016 | S5 Integration Test Baseline | CLAUDE.md integration rule status unclear | PR6 satisfied it manually; rule still needed |
| CI-017 | M8b Cross-Language Field Optionality | QA_CHECKLIST.md shows M8b present — appears APPLIED | W19-H1 shows post-fix gap; L14 (CI-022) adds prevention layer |
| CI-020 | FINDINGS.md Immediate Cleanup | PR5 performed the batch update — appears resolved | Confirmed via retro ("PR5 finally performed the batch update") |

---

## Metrics

- Input documents scanned: retrospective (retro_wave19.md), 5 QA reviews (PR1–PR5), 5 per-phase CI analyses (PR1–PR5), wave system audit (health_wave19.md)
- Total problems inventoried: 7 (W19-A through W19-G)
- New patterns identified: 3 (partial-fix leaves sibling fields unaddressed; multi-platform duration calibration; pre-phase test plan absent is structural not incidental)
- Recurring patterns confirmed: 4 (FINDINGS.md drift, iOS-backend contract gap, S5 OPEN, source-text-scanning tests)
- Past fixes verified effective: 2 (CI-009 L12 — no new violations; ruff E722/BLE001 — clean across all phases)
- Past fixes not actioned in time to prevent Wave 19 problems: 4 (CI-013, CI-015, CI-016, CI-017)
- Proposals generated this analysis: 6 (P1: 2, P2: 3, P3: 1)
- Total P1 proposals now outstanding: 2 new (CI-022, CI-025) + any prior gates not yet confirmed applied

---

## Priority Order for Human Review

**Require human gate before Wave 20 planning:**

1. **CI-022** (P1, NEW) — L14 Full Request Model Audit invariant. Direct evidence: W19-H1 post-wave HIGH finding breaks iOS chat. Prevents the same class of partial-fix gap from repeating on any iOS-backend phase.

2. **CI-025** (P1, NEW) — CLAUDE.md iOS-backend phase contract audit step. Direct evidence: PR3 Cycle 1 FAIL. Catches backend contract gaps at scoping time rather than at QA Cycle 1.

3. **Confirm CI-013 + CI-015 applied** — M5b gate is in QA_CHECKLIST.md; verify the corresponding CLAUDE.md pipeline step (CI-015) is also present. FINDINGS.md hygiene gate must be structural before Wave 20.

4. **Confirm CI-016 applied** — S5 integration baseline rule. PR6 satisfied it manually; the CLAUDE.md rule must be explicit so Wave 20 phases don't revert to all-mocked tests.

**Apply without human gate (P2/P3):**

5. **CI-023** (P2) — Pre-phase test plan step in implement agent. No quality risk; adds a 5-line planning step before coding.

6. **CI-024** (P2) — Phase planning duration multiplier for multi-platform phases. Pure planning calibration.

7. **CI-026** (P2) — M5c Related-issue scope completeness QA gate. Non-blocking note-level gate.

8. **CI-027** (P3) — Add W19-H1 to FINDINGS.md. Tracking only; implement agent to fix in Wave 20.

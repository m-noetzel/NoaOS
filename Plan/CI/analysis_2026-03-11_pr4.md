# Continuous Improvement Analysis — 2026-03-11 (PR4 QA Cycle)

## Summary

PR4 passed QA first cycle with four notes: FINDINGS.md stale for the fourth consecutive phase,
a trivial Ruff E501 (fixed before CI), the pre-existing `chat.py` outer SSE handler still leaking
`str(exc)` to the client, and S5 OPEN again — the fourth consecutive phase in Wave 19. The S5
pattern has now been OPEN across every PR phase so far (PR1–PR4). The FINDINGS.md drift pattern
has graduated from a recurring note to a structural process failure requiring human escalation.
Two new proposals are raised: CI-019 (chat.py outer SSE handler str(exc) leak as a new finding)
and CI-020 (FINDINGS.md currency escalation — four consecutive stale reviews satisfy the same
threshold logic applied for S5 escalation in CI-016).

---

## Problems Found

| ID | Category | Severity | Occurrences | Description |
|----|----------|----------|-------------|-------------|
| P1 | process | critical | 4 consecutive phases (PR1–PR4) | FINDINGS.md not updated before phase completion — BE-H1, BE-M3, BE-M4 remain Open despite being fixed in PR4. Fourth consecutive review flagging this. |
| P2 | security | high | Pre-existing (CP3-era), newly confirmed in PR4 QA | `chat.py` outer SSE handler sends `str(exc)` to client at line 157-162. Runner.py was fixed in PR4, but the outer handler was not in scope — QA flagged it as a new finding candidate. |
| P3 | testing | high | 4 consecutive phases (PR1–PR4) | S5 Integration Smoke Test OPEN. Credential reload flow has no ASGI TestClient test; all credential tests are fully mocked at the `_reload_llm_pipeline_if_needed` unit level. |
| P4 | testing | low | 1 phase (PR4 Note 2, fixed) | Ruff E501 in `tests/unit/test_pr4_security_robustness.py:290` — docstring 3 chars over limit. Fixed before CI ran. |

---

## Patterns Identified

### Pattern A: FINDINGS.md Drift — Four Consecutive Phases (Escalation Threshold Reached)

**Evidence:**
- PR1 QA review (`Plan/REVIEWS/review_PR1.md`): FINDINGS.md flagged stale. BE-C1, BE-C2, BE-H2, BE-M2
  were fixed but not marked resolved.
- PR2 QA review (`Plan/REVIEWS/review_PR2.md`): FINDINGS.md still stale. BE-H3, FE-C1, FE-H1, FE-H2 fixed
  but not marked resolved. Total stale: 7 entries.
- PR3 QA review (`Plan/REVIEWS/review_PR3.md`): FINDINGS.md status not confirmed updated between phases.
- PR4 QA review (`Plan/REVIEWS/review_PR4.md` line 113): "This is the fourth consecutive review flagging stale
  FINDINGS.md." BE-H1, BE-M3, BE-M4 should be marked Resolved by PR4.

**Root cause:** The FINDINGS.md update step is documented in CLAUDE.md as a lifecycle rule
("When resolving a finding: Update the finding's row…immediately after the fix passes tests")
but it is not a blocking gate. The implement agent completes the phase and the QA reviewer
flags the staleness, but no step between implementation and QA submission enforces the update.

**Pattern frequency:** 4 consecutive phases. This matches the same "3 consecutive" threshold
that triggered the P1 S5 escalation (CI-016) in the PR3 analysis. Four consecutive phases is
strictly worse — this threshold is already exceeded.

**Why this matters:** FINDINGS.md is the single source of truth consumed by the ci agent,
system-auditor, and implement agents. Stale state means: (a) the system-auditor at wave
boundary may re-investigate resolved findings, (b) the implement agent for PR5/PR6 starts with
an incorrect picture of what is still open, (c) the CI agent's cross-cycle pattern table
(`analysis_pr3.md` Pattern Table) shows "FINDINGS.md drift | 3 stale | +4 stale | Unknown | 2
confirmed" — the count is now at least 10 stale-phase-entries across the wave.

**Prior proposals:** CI-013 (M5b FINDINGS.md Currency Gate — P1, PROPOSED 2026-03-11) and
CI-015 (Findings Sync as mandatory pipeline step — P2, PROPOSED 2026-03-11) address this.
Neither has been applied. The four-consecutive-phase evidence strengthens CI-013's priority
justification and activates the escalation logic.

**Escalation action:** CI-020 is raised as a P1 to escalate the existing CI-013/CI-015
proposals that have not been actioned after three review cycles. Human gate required.

---

### Pattern B: S5 Integration Smoke Test OPEN — Fourth Consecutive Phase

**Evidence:**
- PR1: S5 OPEN — consecutive count 1 (`Plan/REVIEWS/review_PR1.md` S5 row)
- PR2: S5 OPEN — consecutive count 2 (`Plan/REVIEWS/review_PR2.md` S5 row)
- PR3: S5 OPEN — consecutive count 3 — CI-016 P1 raised (`Plan/CI/analysis_2026-03-11_pr3.md`)
- PR4: S5 OPEN — consecutive count 4 (`Plan/REVIEWS/review_PR4.md` S5 row): "credential reload
  tests are fully mocked — no test calls the real PUT/PATCH endpoint through ASGI TestClient."

**Status of CI-016:** CI-016 was raised as P1 in the PR3 analysis with a human gate requirement.
It has not been applied or actioned yet. PR4 confirms the gap is still present. The consecutive
count is now 4/6 planned PR phases.

**What S5 OPEN means for PR4:** The BE-H1 fix (`_reload_llm_pipeline_if_needed`) is tested at
the unit level — the function itself is called with mocked `ProviderRouter` and `app_state`. No
test sends a real HTTP request through FastAPI's ASGI layer to `PUT /settings` or `PATCH /settings`
and verifies that `get_provider_router()` returns a newly rebuilt router. The integration gap is:
"Does the wiring between the settings endpoint and app_state.set_provider_router actually fire?"

**Risk:** The endpoint-level wiring (`_reload_llm_pipeline_if_needed` called at settings.py:150
and 171) is verified by QA's wiring check (M7 PASS), but wiring-present does not equal
wiring-correct. An off-by-one argument (e.g., passing `updates` instead of `full_settings`) would
pass M7 but fail at runtime.

**Pattern update:** S5 OPEN for 4/4 Wave 19 PR phases. CI-016 P1 has been raised and not
actioned. This is now a sustained P1 gap.

---

### Pattern C: Pre-existing str(exc) Leak in chat.py Outer SSE Handler (New Finding Candidate)

**Evidence:**
- `src/noa/api/v1/chat.py` lines 157-162: The outer `except Exception` block in `event_stream()`
  logs `str(exc)` server-side (correct) but the QA note says the error payload sent to the client
  was previously `str(exc)`. After re-reading the code: line 159-161 sends a generic error event
  `{"error": "An error occurred processing your request."}`. The QA note at PR4 line 117 states:
  "the outer exception handler in chat.py still sends `str(exc)`" — but the code as read shows
  the generic message. The note may refer to a log field, not the client payload.
- The confirmed finding: the inner runner error events were fixed (runner.py sends generic
  messages). The outer handler's client payload is generic. The log line at 158 does use
  `str(exc)` — this is server-side logging only, which is correct behaviour.
- QA note 3 states this was "FIXED before CI" for the runner.py path. The outer chat.py handler
  issue is called out as a "pre-existing concern" (review_PR4.md line 89) not a new bug.

**Assessment:** The QA note overstated this as a remaining leak. The current code sends a generic
message to the client. However, QA explicitly flagged the outer handler as needing future review.
This warrants a new FINDINGS entry (low severity) rather than a P1 proposal — the client payload
is already generic, the risk is only if the log format ever changes to pass through to the
response. Recorded as CI-019 (P3) for tracking.

---

## Effectiveness of Past Fixes

### CI-009 (L12 Write-Path User Scoping — APPLIED 2026-03-11)

PR4 introduced `MemoryStore.persist()` (BE-M2) and path traversal guard (BE-M3). Neither
involves a new write path with user scoping concerns. The memory_store.py `store()` method's
missing `user_id` (BE-M5) is still unresolved — PR4 added BE-M5 to the scope of PR4 but the
QA verdict does not mention BE-M5 being fixed. **L12 holds for new code; BE-M5 pre-existing
gap still open.**

### CI-013 (M5b FINDINGS.md Currency Gate — PROPOSED P1, human gate pending)

Not applied. Four consecutive phases have now completed with stale FINDINGS.md. The human gate
that CI-013 required was not raised between PR3 and PR4. **CI-013 escalation overdue.** This
is directly addressed by CI-020.

### CI-016 (S5 P1 Escalation — PROPOSED P1, human gate pending)

Not applied. S5 is now OPEN for 4 consecutive phases (PR1–PR4). The human gate from CI-016
has not been actioned. **CI-016 P1 remains outstanding.**

### CI-017 (M8b Cross-Language Field Optionality — PROPOSED P1, human gate pending)

Not directly tested by PR4 (no new Pydantic request models added). Status unchanged.
**CI-017 P1 remains outstanding.**

### CI-018 (L13 Default Resolution at API Boundary — PROPOSED P2)

PR4 did not modify `chat.py` or `runner.py` model resolution. The `model=None` propagation
from PR3 is unchanged. **CI-018 P2 status: unresolved, no regression.**

### CI-008 (M4b Mock Interface Accuracy — PROPOSED P2)

PR4 test file uses `MagicMock(spec=AsyncSession)` at line 135 for the artifact endpoint test —
this is the correct pattern. However, the credential tests use direct `MagicMock()` for `repo`
(lines 247-248) which is acceptable since `repo` is not a SQLAlchemy session. **One instance
of correct pattern; no new violations.** CI-008 PROPOSED status unchanged.

---

## Proposals

### CI-019: New Finding — chat.py Outer SSE Handler Exception Logging Review

**Priority:** P3

**ID:** CI-019

**Evidence:**
- `Plan/REVIEWS/review_PR4.md` lines 89, 103, 117: QA flagged the outer `except Exception`
  block in `chat.py event_stream()` as a "pre-existing concern" warranting future review.
- The runner.py inner error events were fixed in PR4 (generic client message). The outer handler
  at `chat.py:157-162` sends a generic client message but the code path has not been reviewed
  for all exception types that could reach it (e.g., if the SSE generator yields an error before
  runner is called).
- This is a low-severity hygiene item, not an active data leak, but should be tracked so it
  is not indefinitely deferred.

**Proposed change:** Add a new FINDINGS.md entry:

```
| BE-L1 | Low | chat.py outer SSE handler exception path not covered by tests — generic error message confirmed but code path untested | Open | — |
```

**Target:** `Plan/FINDINGS.md` (human to add; CI agent does not modify FINDINGS.md directly)

**Priority rationale:** P3. The client payload is already generic. Risk is only if the
exception path has untested edge cases that bypass the generic message. Blocking on this
would be disproportionate.

---

### CI-020: Escalate FINDINGS.md Drift — Four Consecutive Phases (Human Gate Required)

**Priority:** P1

**ID:** CI-020

**Evidence:**
- PR1 QA: FINDINGS.md stale — `Plan/REVIEWS/review_PR1.md` QA note 3
- PR2 QA: FINDINGS.md still stale — `Plan/REVIEWS/review_PR2.md` QA note (7 entries stale)
- PR3 QA: FINDINGS.md currency not confirmed updated
- PR4 QA: "This is the fourth consecutive review flagging stale FINDINGS.md" —
  `Plan/REVIEWS/review_PR4.md` line 113. BE-H1, BE-M3, BE-M4 still marked Open.

**Root cause:** CI-013 (M5b FINDINGS.md Currency Gate) and CI-015 (Findings Sync pipeline step)
were both proposed on 2026-03-11 as a result of PR2 analysis. Neither has been applied.
The human gate required by CI-013 was not raised between PR2 and PR3, or between PR3 and PR4.

**Impact:** FINDINGS.md currently shows 22 Open entries. The actual open count is lower — at
minimum BE-H1, BE-M3, and BE-M4 are now resolved by PR4. If iOS-H1 through iOS-H4 are also
partially addressed by PR3, the drift could be 5–7 entries stale. The system-auditor at wave
boundary will start from an incorrect picture. The implement agents for PR5 and PR6 will plan
work based on stale open findings.

**This proposal escalates CI-013 (P1, human gate, not actioned) to a forced human gate.**

**Proposed immediate action (human gate):**
1. Update FINDINGS.md to mark BE-H1, BE-M3, BE-M4 as Resolved by PR4.
2. Confirm whether iOS-H1, iOS-H2, iOS-H3, iOS-H4 are resolved by PR3.
3. Update Open/Resolved counts.
4. Human to approve and apply CI-013 (M5b QA gate) and CI-015 (CLAUDE.md pipeline step)
   before PR5 begins.

**Proposed text for CI-013 application to `Plan/QA_CHECKLIST.md`** (unchanged from PR2 analysis):

```
| M5b | Findings Currency | Before submitting for QA review: open Plan/FINDINGS.md and confirm
every finding resolved during this phase is marked Resolved with the current phase ID as
"Resolved By". If any resolved finding remains Open, the phase is not ready for QA review.
Gate: zero unresolved-but-fixed findings at QA submission time. |
```

**Proposed text for CI-015 application to `CLAUDE.md`** Phase Pipeline gates section
(unchanged from PR2 analysis):

```
- **Findings Sync (blocks QA)**: Before requesting QA review, update Plan/FINDINGS.md — mark
  all findings fixed in this phase as Resolved with this phase's ID. This gate blocks QA
  submission; it is not advisory.
```

**Target:** Human gate (approve + apply CI-013 to QA_CHECKLIST.md and CI-015 to CLAUDE.md)

**Priority rationale:** P1 because (a) four consecutive phases have completed with stale state,
(b) CI-013 was already P1 and its human gate was not raised in PR3, (c) the drift will compound
into the wave-boundary system-auditor and wave 20 planning if not resolved now.

---

## S5 Escalation Tracking (Updated)

| Wave 19 Phase | S5 Result | Consecutive OPEN Count | Action |
|---------------|-----------|----------------------|--------|
| PR1 | OPEN | 1 | Monitor |
| PR2 | OPEN | 2 | Monitor |
| PR3 | OPEN | 3 | CI-016 P1 raised (human gate required — not yet actioned) |
| PR4 | OPEN | 4 | CI-016 P1 still outstanding |
| PR5 | TBD | — | Reset counter if PASS |
| PR6 | Expected PASS (integration tests) | — | Verify CI-016 satisfied |

**CI-016 human gate: outstanding since 2026-03-11 PR3 cycle.**

---

## FINDINGS.md Drift Tracking (Updated)

| Wave 19 Phase | Drift Entries (cumulative) | Action |
|---------------|---------------------------|--------|
| PR1 | 4 stale (BE-C1, BE-C2, BE-H2, BE-M2) | CI-013 PROPOSED |
| PR2 | +3 more stale = 7 total (BE-H3, FE-C1, FE-H1, FE-H2) | CI-013 P1 raised |
| PR3 | Unknown increment | CI-013 human gate required (not actioned) |
| PR4 | +3 more confirmed (BE-H1, BE-M3, BE-M4) | **CI-020 P1 raised — human gate required** |

---

## Cross-Cycle Pattern Summary (PR1–PR4)

| Pattern | PR1 | PR2 | PR3 | PR4 | Total Phases |
|---------|-----|-----|-----|-----|--------------|
| S5 OPEN | OPEN | OPEN | OPEN | OPEN | 4 |
| FINDINGS.md drift | Yes | Yes | Likely | Yes (confirmed) | 4 |
| AsyncMock on sync session | Yes | Yes | Presumed | Partial (repo only) | 3+ |
| Source-text-scanning tests as behavioral proxy | No | Yes (4 tests) | Likely | No | 2+ |
| Vacuous mock read-back assertion | No | Yes | Unknown | No | 1 |
| Cross-language nil-omission break | No | No | Yes (Cycle 1 FAIL) | No | 1 |
| Dead-code default bypassed by caller | No | No | Yes | No | 1 |
| str(exc) leak — outer SSE handler | No | No | No | Flagged (pre-existing) | 1 (pre-existing) |

---

## Metrics

- Total problems scanned: 4 (1 process, 1 security-hygiene, 1 testing, 1 trivial lint fixed)
- New patterns identified: 0 (all patterns are continuations of previously identified issues)
- Recurring patterns: 2 (S5 OPEN — now 4 consecutive; FINDINGS.md drift — now 4 consecutive)
- Past fixes verified effective: 2/6 checked (CI-009/L12 holding; CI-008 correct pattern seen in PR4 tests)
- Past fixes outstanding (P1 human gates not actioned): 3 (CI-013, CI-016, CI-017)
- Proposals generated: 2 (P1: 1 [CI-020], P3: 1 [CI-019])

---

## Proposal Priority Order

1. **CI-020** (P1) — Escalate FINDINGS.md drift: four consecutive stale phases, CI-013 human gate
   not actioned from PR2/PR3. Human gate required before PR5. Approve and apply CI-013 + CI-015.
2. **CI-016** (P1, previously raised) — S5 integration test baseline: now 4/4 OPEN across Wave 19.
   Human gate from PR3 analysis still outstanding. PR6 integration test scope must be confirmed.
3. **CI-019** (P3) — Add BE-L1 finding for chat.py outer SSE handler untested exception path.
   Low severity; track so it is not deferred indefinitely.

---

## Outstanding P1 Human Gates (All Waves)

| Proposal | Raised | Status | Action Required |
|----------|--------|--------|-----------------|
| CI-013 (M5b Findings Currency Gate) | PR2 cycle | Not actioned | Apply to QA_CHECKLIST.md before PR5 |
| CI-016 (S5 Integration Test Baseline) | PR3 cycle | Not actioned | Confirm PR6 scope; apply to CLAUDE.md |
| CI-017 (M8b Cross-Language Field Optionality) | PR3 cycle | Not actioned | Apply to QA_CHECKLIST.md before PR5 |
| CI-020 (FINDINGS.md Drift Escalation) | PR4 cycle | New | Update FINDINGS.md immediately; apply CI-013 + CI-015 |

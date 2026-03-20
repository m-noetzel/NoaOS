# Continuous Improvement Analysis — 2026-03-11 (PR3 QA Cycle)

## Summary

PR3 required two QA cycles: Cycle 1 was a FAIL because `ChatRequest` required `model` and `provider` fields while the Swift client omits nil fields per Swift's JSON encoding conventions. The fix made both fields `Optional` in Pydantic. Cycle 2 passed with three notes: a dead-code default in `OrchestratorRunner.run()`, a persistent S5 gap, and a cosmetic `null` field in `classification_done` events. The critical finding from this cycle is that S5 is now OPEN for the third consecutive phase in Wave 19, which triggers the P1 escalation threshold proposed in CI-010. This is escalated to P1 now. Additionally, the Cycle 1 FAIL reveals a new pattern: backend Pydantic models treat missing optional fields as required, creating a contract break for any client that uses conventional nil-omission encoding. This pattern is not covered by any existing QA gate.

---

## Problems Found

| ID | Category | Severity | Occurrences | Description |
|----|----------|----------|-------------|-------------|
| P1 | architecture | high | 1 (PR3 Cycle 1 FAIL) | `ChatRequest.model` and `ChatRequest.provider` defined as required in Pydantic (`str` with no default); Swift JSON encoding omits nil fields by convention; field absence causes 422 Unprocessable Entity instead of using a default |
| P2 | testing | high | 3 consecutive (PR1, PR2, PR3) | S5 Integration Smoke Test OPEN for third consecutive phase in Wave 19 — triggers CI-010 escalation to P1 |
| P3 | dead-code | low | 1 (`runner.py` line 43) | `OrchestratorRunner.run(model: str = "anthropic/claude-haiku")` default is unreachable — `chat.py` always passes `model=body.model` which is now `str | None = None`; the default string is shadowed by the caller passing `None` |
| P4 | serialization | low | 1 (`classification_done` event) | Event payload contains `"model": null` when no model is selected — cosmetic but may cause null-handling issues in strict Swift decoders if field is expected to be a non-null string |

---

## Patterns Identified

### Pattern A: Backend Pydantic Models Require Optional Client Fields (New Pattern)

**Evidence:**
- PR3 Cycle 1 FAIL: `ChatRequest` in `src/noa/api/v1/chat.py` had `model: str` and `provider: str` (required, no default). The Swift `ChatViewModel` does not send `"model"` or `"provider"` keys when the user has not selected values — standard Swift `JSONEncoder` behavior with `Optional<String>` fields.
- `chat.py` current state (post-fix): `model: str | None = None` and `provider: str | None = None` (lines 33-34). The fix was correct.
- Root cause of the Cycle 1 FAIL: when a new field is added to a Pydantic request model, the default is omitted unless explicitly set. The reviewing party must verify: "Can any existing client legally send a request without this field?" For cross-language clients (Swift, any other mobile), the answer is almost always "yes, because the field is optional."

**Why this matters:** Every time a backend endpoint adds or modifies a field, any mobile client that uses conventional nil-omission encoding (Swift, Kotlin, etc.) may break. The breakage is a 422, not a graceful degradation. This pattern is high-severity because it causes complete feature failure rather than degraded behavior.

**No existing gate covers this.** The QA checklist has M8 (API Contract) but it does not specifically address the nil-omission encoding convention. A gateway check on all request model fields would catch it.

**Historical frequency:** First confirmed instance of this specific failure in the review record. However, the fix pattern (making fields `Optional` with a `None` default) appeared also in the `ApprovalDecision.decision` field fix in iOS11 (`Literal["approved","denied"]` was changed to accommodate Swift encoding). That was a related but different issue (enum string casing, not nil-omission). The nil-omission pattern is new as a Cycle 1 FAIL cause.

### Pattern B: S5 OPEN Triggers CI-010 Escalation (3 Consecutive Phases)

**Evidence:**
- PR1: S5 OPEN — consecutive count 1/3
- PR2: S5 OPEN — consecutive count 2/3
- PR3: S5 OPEN — consecutive count 3/3 — **threshold reached**

Per CI-010 (proposed 2026-03-11 PR1 cycle), the trigger condition is: "If S5 is OPEN for 3 or more consecutive phases in a wave, it escalates to a P1 CI proposal." This threshold is now met.

**What S5 OPEN means for PR3:** The PR3 iOS fixes (queue drain, SSE cancel, AuthGuard refresh, model selectors) are tested at the Python level via source-text-scanning tests or mocked session tests. No test exercises the relevant Swift or Python code paths with a real ASGI or real DB layer. The fixes are structurally verified but not behaviorally proven.

**Escalation action:** CI-016 is raised as P1. It proposes a dedicated integration-test step in PR6 and requires that the implement agent include at least one real-session test per phase for any DB-touching endpoint, starting immediately.

### Pattern C: Dead-Code Default in OrchestratorRunner.run()

**Evidence:**
- `src/noa/orchestrator/runner.py` line 43: `model: str = "anthropic/claude-haiku"` is the parameter default.
- `src/noa/api/v1/chat.py` lines 127-134: The caller passes `model=body.model` where `body.model` is now `str | None = None`.
- When `body.model` is `None`, the call is `runner.run(..., model=None, ...)`. The function signature `model: str = "anthropic/claude-haiku"` receives `None` from the caller — the default is never used because the caller always explicitly passes `model=`.
- The type annotation `model: str` is also incorrect once `None` can be passed: the caller can now pass `None` without a type error (Python does not enforce this at runtime), but mypy would flag a `str | None` passed to a `str` parameter.

**QA note context:** QA Note 1 states this is dead code. The default `"anthropic/claude-haiku"` was meaningful when `chat.py` always passed an explicit model string. After PR3 made `ChatRequest.model` optional and passes `None` through, the default is bypassed.

**Risk:** A downstream node in the LangGraph graph (`agent.py` or `llm/router.py`) likely receives `model=None` and must handle it. If those nodes treat `None` as "use global default" that is acceptable, but the type signature is misleading. If they treat `None` as a missing value they forward to the LLM provider, this causes the `"model": null` in the `classification_done` event (P4 above).

**Root cause linkage:** P3 (dead-code default) and P4 (null in event) are causally linked. The `model=None` path propagates through the runner into the event payload. The runner's signature should either be `model: str | None = None` (explicit) or the caller should resolve the default before calling the runner.

### Pattern D: Null Value in SSE Event Payload for Undefined Model

**Evidence:**
- QA Note 3: `classification_done` event contains `"model": null` when no model is selected.
- Causal chain: `ChatRequest.model = None` (user did not select a model) → `chat.py` passes `model=None` → runner propagates through graph → `classification_done` event serializes `"model": null`.

**Severity:** Cosmetic on the backend side. Risk on the iOS side: Swift's `Codable` will decode `"model": null` into `String?` if the field is declared `Optional<String>`. If declared as `String` (non-optional), the decoder raises a fatal error. The consequence depends on how `ChatViewModel` decodes `classification_done` events. If the Swift model has `model: String` (non-optional), PR3's fix for the nil-omission problem on the request side has created a symmetric problem on the response side.

---

## Effectiveness of Past Fixes

### CI-009 (L12 Write-Path User Scoping — APPLIED 2026-03-11)

PR3 did not touch `memory_store.py` or the credential store. No new write-path scoping violation in PR3. L12 is holding for new code. Status: **effective for new code, pre-existing BE-M5 gap unchanged (scheduled PR4)**.

### CI-010 (S5 Escalation Rule — PROPOSED, not applied)

The trigger threshold of 3 consecutive OPEN phases was reached in PR3 (PR1→PR2→PR3 all OPEN). Per CI-010's proposed rule, this escalates to P1. The fact that no enforcement existed means the trigger is being identified reactively here rather than automatically blocking. Status: **escalated to P1 in this analysis (see CI-016 below)**.

### CI-013 (M5b FINDINGS.md Currency Gate — PROPOSED P1, not applied, human gate pending)

Not visible whether FINDINGS.md was updated between PR2 and PR3. The PR2 analysis identified 7 stale entries; if they remain stale, this is now a 3-phase accumulation. CI-013 remains PROPOSED and a human gate is still required.

### CI-008 (M4b Mock Interface Accuracy — PROPOSED, not applied)

No new evidence from PR3 QA notes. The `session = AsyncMock()` pattern is presumed to continue appearing in PR3 test files based on the unchanged test infrastructure. Status: **not verified in this cycle**.

### CI-001 through CI-007 (PROPOSED 2026-03-07 — not applied)

No status change. Still PROPOSED with no applied date. Not re-analyzed here (no new evidence on these in PR3).

---

## Proposals

### CI-016: S5 Escalation to P1 — Dedicate Integration Tests in PR6

**Priority:** P1 (trigger condition met per CI-010 proposed rule)

**ID:** CI-016

**Evidence:**
- S5 Integration Smoke Test OPEN in PR1, PR2, and PR3 — three consecutive phases in Wave 19.
- CI-010 (proposed 2026-03-11) defined the trigger: "If S5 is OPEN for 3 or more consecutive phases in a wave, escalate to P1 CI proposal."
- The trigger condition is now satisfied. This is not a new proposal — it is the required action from CI-010 applied to the observed data.
- PR3 QA Note 2 confirms: "S5 integration smoke test still OPEN (iOS library package limitation)."

**Impact of continued OPEN:**
- PR1: joins in `runs.py` not tested against real schema. Risk of column-name mismatch invisible until production.
- PR2: PATCH settings endpoint mocked; `exclude_unset` behavior unproven (CI-014 issue).
- PR3: iOS lifecycle fixes (queue drain, SSE cancel, AuthGuard refresh) have no executed-code-path coverage.

**Proposed change to `CLAUDE.md`**, in "Implementation rules":

```
- **Integration test baseline**: Every phase that touches a DB-backed endpoint MUST include
  at least one test that exercises the endpoint with a real in-memory SQLite session (not
  AsyncMock). For Swift-only phases, the iOS integration test suite (Tests/NaoTests/Integration/)
  satisfies this requirement. Absence of any non-mocked test for a DB-touching path is a Cycle 1
  FAIL condition, not a note.
```

**Proposed change to PR6 scope** (not in CLAUDE.md — to be raised with human):
- PR6 must include real ASGI integration tests for: (1) runs join usage_stats (PR1), (2) PATCH settings `exclude_unset` round-trip (PR2), (3) ChatRequest with nil model/provider (PR3).
- This should be added to PR6's PHASE_DETAILS entry before implementation begins.

**Target:** `CLAUDE.md` (implementation rules section) + PR6 scope clarification (human gate)

**Priority rationale:** This is P1 because the three-consecutive trigger was defined as P1 in CI-010. The absence of non-mocked tests creates a production correctness gap that mocked tests cannot detect.

---

### CI-017: QA Checklist — Cross-Language Field Optionality Gate (M8b)

**Priority:** P1

**ID:** CI-017

**Evidence:**
- PR3 Cycle 1 FAIL: `ChatRequest.model` and `ChatRequest.provider` were required Pydantic fields (`str`, no default). Swift omits nil fields by convention. Result: 422 Unprocessable Entity for any iOS request that does not include a model selection.
- Related prior instance: iOS11 `ApprovalDecision.decision` field had an incompatible enum representation between Python (`Literal["approved","denied"]`) and Swift (`String`). Though a different root cause (type narrowness vs nil-omission), both trace to the same root: backend model changes were not verified against mobile client encoding conventions.
- This pattern produced a Cycle 1 FAIL — the worst pipeline outcome short of a finding escalation.

**Root cause:** No checklist item asks the QA reviewer to verify that every field in a backend request model is compatible with all registered client encoding conventions. The M8 (API Contract) gate exists but is written generically; it does not prompt the reviewer to check nil-omission behavior.

**Proposed addition to `Plan/QA_CHECKLIST.md`**, as an extension to M8:

```
| M8b | Cross-Language Field Optionality | For endpoints consumed by non-Python clients
(Swift iOS, TypeScript web): every field in the Pydantic request model must be declared as
`Optional` with a `None` default if the client may legally omit it. Swift encodes `Optional`
values that are `nil` by omitting the key entirely — a required Pydantic field will return 422
if the key is absent. Check: for each new or modified request field, verify: (a) the Python type
annotation includes `| None`, and (b) a default value is set. Flag any `str`, `int`, `bool`
field without a default as a potential cross-language break. |
```

**Target:** `Plan/QA_CHECKLIST.md`

**Impact estimate:** PR3's Cycle 1 FAIL was entirely caused by this gap. A single reviewer pass with this checklist item would have caught the missing `| None` before QA submission, eliminating Cycle 1 entirely. With PR4-PR6 still pending and the iOS client active, this gate prevents future cross-language 422s. This is P1 because it caused a Cycle 1 FAIL — the strongest evidence that an existing gate is missing.

---

### CI-018: ARCH_INVARIANTS — Caller Resolves Default Before Passing None to Callee

**Priority:** P2

**ID:** CI-018

**Evidence:**
- `src/noa/api/v1/chat.py` lines 127-134: passes `model=body.model` where `body.model` is `str | None = None`. The caller never resolves `None` to a default before calling the runner.
- `src/noa/orchestrator/runner.py` line 43: receives `model: str = "anthropic/claude-haiku"` but the default is never reached because the caller always explicitly passes the argument (even when `None`). The type annotation is `str`, but `None` can be passed without a static error (Python runtime does not enforce types).
- Consequence: `model=None` propagates through the runner graph and surfaces as `"model": null` in the `classification_done` SSE event (QA Note 3). The default `"anthropic/claude-haiku"` intended by the runner's signature is silently bypassed.
- A symmetric risk exists on the response side: if Swift decodes `classification_done` with a non-optional `model: String` field, it will crash on `null`.

**Root cause:** No invariant requires that `None` be resolved to a concrete default at the API boundary (the outermost point that controls what enters the pipeline). The API layer receives `None` from the request model and passes it unchanged into the pipeline, delegating the "what is the real default?" decision to an interior layer that cannot make it (the runner does not know what model is configured for this user).

**Proposed addition to `Plan/ARCH_INVARIANTS.md`**:

```
### L13 — Default Resolution at API Boundary

When an API endpoint receives an Optional field from the client and passes it to an
interior service or pipeline runner, the endpoint MUST resolve `None` to a concrete
default before calling the interior component. Interior components (runners, services,
graph nodes) MUST NOT receive `None` for fields they treat as required for execution.

Violation pattern: `runner.run(model=body.model)` where `body.model` is `None`.
Correct pattern: `runner.run(model=body.model or settings.default_model or "anthropic/claude-haiku-3-5")`.

Applies to: model identifiers, provider names, privacy mode, any field used to route
execution in a pipeline node.

Rationale: The API boundary is the correct place to apply defaults because it has access
to user settings, system configuration, and fallback values. Interior components should
receive fully-resolved inputs, not optional values requiring further interpretation.
```

**Target:** `Plan/ARCH_INVARIANTS.md`

**Priority rationale:** P2 (not P1) because the current `None` propagation is cosmetic for the event field, and the runner's downstream nodes appear to handle it. However, the type mismatch between the signature (`str`) and actual call (`None`) is a latent mypy error, and the null-in-event-payload creates a symmetric risk for Swift decoders.

---

## S5 Escalation Tracking (Updated)

| Wave 19 Phase | S5 Result | Consecutive OPEN Count | Action |
|---------------|-----------|----------------------|--------|
| PR1 | OPEN | 1 | Monitor |
| PR2 | OPEN | 2 | Monitor |
| PR3 | OPEN | 3 | **P1 escalation — CI-016 raised** |
| PR4 | TBD | — | Reset counter if PASS |
| PR5 | TBD | — | — |
| PR6 | Expected PASS (integration tests) | — | Verify CI-016 satisfied |

CI-016 is P1. Human gate required before next phase begins.

---

## Cross-Cycle Pattern Summary (PR1 + PR2 + PR3)

| Pattern | PR1 | PR2 | PR3 | Total Phases |
|---------|-----|-----|-----|--------------|
| S5 OPEN | OPEN | OPEN | OPEN | 3 |
| AsyncMock on sync session | Yes | Yes | Presumed | 3+ |
| Source-text-scanning tests as behavioral proxy | No | Yes (4 tests) | Likely | 2+ |
| FINDINGS.md drift | 3 stale | +4 stale | Unknown | 2 confirmed |
| Vacuous mock read-back assertion | No | Yes (1 test) | Unknown | 1 |
| Cross-language nil-omission break | No | No | Yes (Cycle 1 FAIL) | 1 |
| Dead-code default bypassed by caller | No | No | Yes (runner.run) | 1 |

---

## Metrics

- Total problems scanned: 4 (1 Cycle 1 FAIL blocker + 3 QA notes)
- New patterns identified: 2 (cross-language nil-omission field break, dead-code default bypassed by caller)
- Recurring patterns (previously seen): 1 (S5 OPEN — now 3 consecutive, trigger reached)
- Past fixes verified effective: 1/4 checked (L12/CI-009 — holding, no new violation; CI-010 escalation trigger confirmed; CI-013 human gate still open; CI-008 not verified this cycle)
- Proposals generated: 3 (P1: 2, P2: 1)

---

## Proposal Priority Order

1. **CI-016** (P1) — S5 escalation: mandate at least one non-mocked integration test per DB-touching phase, starting PR4. Three consecutive OPEN phases in Wave 19 confirm the pattern is systemic. **Human gate required.**
2. **CI-017** (P1) — M8b Cross-Language Field Optionality gate. PR3 Cycle 1 FAIL is direct evidence that this gate would have prevented the failure cycle. **Human gate required.**
3. **CI-018** (P2) — L13 Default Resolution at API Boundary invariant. Prevents `None` from propagating through the pipeline where a concrete value is required, and prevents the asymmetric null-in-event-payload issue.

# Continuous Improvement Analysis — 2026-03-11 (PR1 QA Cycle)

## Summary

PR1 passed QA with notes covering three issues: a write-path user_id gap in MemoryStore.store(), AsyncMock misuse causing RuntimeWarnings in tests, and the recurring S5 integration smoke test gap. Cross-referencing these against previous reviews reveals two systemic patterns: (1) the "store without scoping" anti-pattern has occurred at least twice (MemoryStore, credential_store), indicating a missing architectural gate; (2) S5 is OPEN in 17 of 25 QA reviews examined, making it the single most consistently failing checklist item — yet the current checklist treats it as a "should-have" with no enforcement consequence.

---

## Problems Found

| ID | Category | Severity | Occurrences | Description |
|----|----------|----------|-------------|-------------|
| P1 | testing | medium | 15 test files | AsyncMock used for SQLAlchemy sessions, causing RuntimeWarnings when sync methods (session.add) are called on an AsyncMock |
| P2 | security / scoping | high | 2+ locations | Data stored without user_id on write path; read path scoped by user_id; the two paths are disconnected (MemoryStore.store(), credential_store dict) |
| P3 | testing | high | 17/25 reviews (68%) | S5 Integration Smoke Test is OPEN in the majority of QA reviews; it is the single most persistent failing checklist item |
| P4 | process | medium | Every wave | S5 is a "should-have" with no enforcement action when OPEN; phases complete despite zero non-mocked integration tests |

---

## Patterns Identified

### Pattern A: AsyncMock Applied to Sync SQLAlchemy Methods

**Evidence:** `review_PR1.md` Note 2 explicitly documents RuntimeWarning from `session.add()` called on `AsyncMock`. The `session = AsyncMock()` pattern appears in 15 test files (`test_settings.py`, `test_qc2_security_hardening.py`, `test_mr3_tool_audit.py`, `test_mr4_tool_telemetry.py`, `test_mr5_tool_permissions.py`, `test_qc3_error_handling.py`, `test_mr1_auth.py`, `test_mr7_smoke.py`, `test_durable_queue.py`, `test_qc5_database_integrity.py`, `test_qc8_architecture.py`, `test_tm5_custom_tools.py`, `test_mv2_mv3_stubs.py`, `test_auth.py`, `test_pr1_backend_fixes.py`).

**Root cause:** SQLAlchemy's async session has a mixed interface — `session.execute()` and `session.flush()` are coroutines (must be awaited), but `session.add()` is synchronous. `AsyncMock()` makes all attribute access return coroutines, including `session.add`. When `session.add(obj)` is called without `await`, Python silently creates and drops an unawaited coroutine, emitting a RuntimeWarning. The tests pass, but the warning indicates the mock is lying about the interface.

**Why this matters:** The correct pattern is `session = MagicMock(spec=AsyncSession)` with `session.execute = AsyncMock(...)` and `session.flush = AsyncMock(...)`. This matches the real interface: sync add, async execute/flush.

**No existing gate covers this.** QA checklist M4 (Determinism) and M6 (Bare Except) don't address mock infrastructure accuracy.

### Pattern B: Write-Path Missing User Scope (Store Without Scoping)

**Evidence:**
- `MemoryStore.store()` in `src/noa/private_worker/memory_store.py:63-105`: stores facts with no `user_id` field. The read path (`list_all`, `get_by_id`, `update_status`, `delete`) all filter by `user_id`. Facts stored by the orchestrator via `handlers.py:35` never have `user_id` set. Consequence: Memory Audit UI shows zero facts despite facts existing (documented in `review_PR1.md` Note 1 and `health_2026-03-11_pr1.md` Greatest Risk).
- `_credential_store` dict in `src/noa/api/v1/tools.py` (TM1): global dict keyed only by `tool_name`. Single-user acceptable, but the pattern is identical — store endpoint does not key by user; read endpoints don't scope by user either. Documented in `review_TM1.md` Security item 4.

**Root cause:** New storage is added without asking "which user does this data belong to?". The question is not part of any existing implementation gate or pre-implementation checklist step.

**Pattern frequency:** 2 confirmed instances across Wave 18 (TM1) and Wave 19 (PR1 note, pre-existing MemoryStore). The PR1 user-scoping of the read path made the write-path gap visible for the first time, suggesting it had been latent since the MemoryStore was first written.

### Pattern C: S5 Integration Smoke Test — Persistently Open (68% Failure Rate)

**Evidence:** S5 is OPEN in 17 of the 25 QA reviews examined:
- review_PR1.md (OPEN), review_TM1.md (OPEN), review_QC6.md (OPEN), review_QC8.md (OPEN), review_QC8_cycle2.md (OPEN), review_iOS10.md (OPEN), review_qc2.md (OPEN), review_QC4_QC5.md (OPEN), review_iOS8.md (OPEN), review_15A.md (OPEN), review_15A_cycle2.md (OPEN), review_iOS11.md (OPEN), review_iOS3.md (OPEN), review_iOS7.md (OPEN), review_HD.md (OPEN), review_iOS5.md (OPEN), review_iOS5_cycle2.md (OPEN), review_HD_cycle2.md (OPEN), review_iOS6.md (OPEN).
- S5 PASS: review_QC3.md, review_iOS4.md, review_PW1-PW3.md, review_system_final.md, review_system_final_recheck.md, review_iOS8_cycle2.md, review_TM2.md.

**Root cause:** S5 is a "should-have" (S-series) in QA_CHECKLIST.md. When OPEN, it produces a PASS_WITH_NOTES verdict, not a FAIL. There is no escalation path, no phase-level action required, and no CI proposal has targeted it before. The result is that phases routinely complete with mocked DB sessions as the sole test infrastructure, creating exactly the "tests pass with mocks but fail with real DB" risk documented in every QA note on this.

**Impact:** Each OPEN S5 means at least one DB interaction (join, filter, schema column) is only tested against a MagicMock that will return whatever you tell it. Schema mismatches, wrong column names, missing relationships — all invisible until production.

---

## Effectiveness of Past Fixes

**CI-001 through CI-007 (proposed 2026-03-07):** Status is PROPOSED, none applied yet. No effectiveness data available.

**Ruff E722/BLE001 rules:** M6 passed clean in PR1 (review_PR1.md line 53-58). Pre-existing BLE001 blocks all have logging. No new violations. The ruff rules are working for new code. Effectiveness: confirmed for new code, pre-existing violations grandfathered with noqa.

**User-scoping pattern from QC1-QC3:** The security audit drove user_id filtering into the read path (PR1). However, no rule prompted write-path user_id at creation time. The gap persisted from initial MemoryStore implementation (pre-Wave 14) through Wave 19 (PR1 note surfaced it). The fix was reactive, not preventive.

---

## Proposals

### CI-008: QA Checklist — Add Mock Infrastructure Accuracy Gate

**Priority:** P2

**Evidence:** `review_PR1.md` Note 2 — RuntimeWarning from `AsyncMock` used for sync `session.add()`. Pattern present in 15 test files. No existing gate checks whether test mocks accurately reflect the interface of the real object.

**Proposed change:** Add a new M-series item to `Plan/QA_CHECKLIST.md` after M4 (Determinism):

```markdown
| M4b | Mock Interface Accuracy | When tests mock SQLAlchemy sessions or other mixed sync/async objects, verify mocks match the real interface. Use `MagicMock(spec=AsyncSession)` with `session.execute = AsyncMock(...)` and `session.flush = AsyncMock(...)` rather than `AsyncMock()` for the whole session. A `session = AsyncMock()` that calls sync methods (e.g. `session.add`) will produce RuntimeWarning: coroutine never awaited. |
```

**Target:** `Plan/QA_CHECKLIST.md`

**Impact estimate:** 15 test files currently affected. Each file that uses `session = AsyncMock()` and calls `session.add()` is silently emitting warnings that mask interface errors. Catching this at the QA review step prevents the pattern from spreading further.

---

### CI-009: ARCH_INVARIANTS — Write-Path User Scoping Rule

**Priority:** P1

**Evidence:**
- `MemoryStore.store()` (`src/noa/private_worker/memory_store.py:63`) — stores facts without `user_id`; read path filters by `user_id`. Gap discovered in PR1 QA note (`review_PR1.md` Note 1). Finding tracked as BE-M5.
- `_credential_store` dict (`src/noa/api/v1/tools.py`) — keyed by `tool_name` only, not `user_id`. Documented in `review_TM1.md` Security item 4.
- Pattern: write path created first, read-path scoping added later (reactively). Each occurrence required a retrospective finding.

**Proposed addition** to `Plan/ARCH_INVARIANTS.md`:

```markdown
### L12 — Write-Path User Scoping

Any data stored by the system that will later be retrieved by a user-facing API MUST include `user_id` at the point of storage (write path), not only at the point of retrieval (read path). A write path that omits `user_id` while the read path filters by `user_id` creates a silent disconnect: stored data becomes invisible to the API.

**Applies to:** in-memory stores, DB models, file-based stores, caches, dictionaries keyed by entity name.

**Check:** For every new storage call, verify that the key/record includes `user_id` if the corresponding read path uses `user_id` for filtering. This is mandatory for multi-user correctness and required even in single-user deployments to maintain consistent scoping semantics.

**Violation examples:** `MemoryStore.store()` (BE-M5, Wave 19 PR1 note), `_credential_store` dict keyed by tool name only (TM1 review).
```

**Target:** `Plan/ARCH_INVARIANTS.md`

**Impact estimate:** Had this rule existed, BE-M5 would have been caught at implementation time (Wave 14 or earlier, when MemoryStore was first written) rather than discovered in Wave 19 QA. Estimated savings: at least 2 QA note cycles + the cost of tracking BE-M5 as a finding.

---

### CI-010: QA Checklist — S5 Escalation Path for Persistent OPEN

**Priority:** P2

**Evidence:** S5 Integration Smoke Test is OPEN in 17 of 25 reviewed QA reports (68% failure rate). It is the single most consistently unmet checklist item. Because S5 is a "should-have," a phase can complete with PASS_WITH_NOTES regardless of how many consecutive S5 OPEN verdicts have accumulated. There is no mechanism to escalate a persistently open "should-have" into a blocking condition.

**Proposed change to `Plan/QA_CHECKLIST.md`**, in the S5 row or as a process note:

```markdown
**S5 escalation rule:** If S5 (Integration Smoke Test) is OPEN for 3 or more consecutive phases in a wave, it escalates to a P1 CI proposal. The CI agent MUST propose a dedicated integration-test phase (analogous to PR6) to address the backlog. The implement agent MUST include at least one non-mocked integration test per phase by default — not as a nice-to-have.
```

**And add to CLAUDE.md implementation rules:**

```markdown
- **Integration test baseline**: Every phase that touches a DB-backed endpoint MUST include at least one test that exercises the endpoint with a real in-memory SQLite session (not `AsyncMock`). This satisfies S5 by default and prevents the "tests pass with mocks, fail with real DB" pattern.
```

**Target:** `Plan/QA_CHECKLIST.md` (S5 row + note) and `CLAUDE.md` (implementation rules)

**Impact estimate:** S5 has been OPEN 17 times across the project history. Had the escalation rule existed from Wave 14, PR6 (integration tests) would have been proposed as a P1 CI item after the third consecutive OPEN, rather than being planned reactively as a Wave 19 phase.

---

### CI-011: QA Checklist — Write-Path User Scoping Check (M3 Extension)

**Priority:** P2

**Evidence:** Same as CI-009. The ARCH_INVARIANTS rule (L12) prevents the pattern architecturally. This proposal adds the corresponding verification step to the QA checklist so reviewers explicitly check for it.

**Proposed addition** to `Plan/QA_CHECKLIST.md`, M3 (Security Boundaries) row notes or as a sub-item:

```markdown
| M3b | Write-Path User Scoping | For every new data store or update to an existing store: verify that `user_id` is set at the point of storage (write path), not only at the point of retrieval. If the read path filters by `user_id`, the write path MUST set it. Check: grep the storage call site for `user_id` assignment. If absent, flag as M3 violation. |
```

**Target:** `Plan/QA_CHECKLIST.md`

**Impact estimate:** Would have caught the MemoryStore write-path gap (BE-M5) at implementation review rather than in Wave 19 QA.

---

## Metrics

- Total problems scanned: 4 (3 from PR1 QA notes + 1 structural pattern from S5 rate)
- New patterns identified: 3 (AsyncMock misuse, write-path scoping, S5 escalation gap)
- Recurring patterns (previously seen): 1 (S5 OPEN — present since at least Wave 14B, but not previously proposed as a systemic issue)
- Past fixes verified effective: 1/1 checked (ruff E722/BLE001 rules — working for new code)
- Proposals generated: 4 (P1: 1, P2: 3)

---

## Proposal Priority Order

1. **CI-009** (P1) — ARCH_INVARIANTS L12: Write-Path User Scoping. Prevents BE-M5 class of bugs at design time.
2. **CI-010** (P2) — S5 escalation rule. Prevents persistent S5 OPEN from accumulating without consequence.
3. **CI-008** (P2) — Mock Interface Accuracy gate. Prevents AsyncMock/sync-method RuntimeWarning from spreading.
4. **CI-011** (P2) — M3b Write-Path User Scoping check. Companion verification step to CI-009.

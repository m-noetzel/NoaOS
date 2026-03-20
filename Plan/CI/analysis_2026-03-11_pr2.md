# Continuous Improvement Analysis — 2026-03-11 (PR2 QA Cycle)

## Summary

PR2 passed QA with notes covering five issues: PUT/PATCH semantic duplication, a missing non-mocked integration test, a test that doesn't verify what it claims to verify (`exclude_unset`), a post-QA camelCase function name cleanup, and source-text-scanning tests used as behavioral coverage for frontend fixes. Cross-referencing these against PR1 findings and the Wave 19 context reveals two patterns: (1) the source-text-scanning test strategy is appearing in every frontend-touching phase and creates false confidence about behavioral correctness; (2) the "FINDINGS.md drift" problem has now compounded across two consecutive phases (PR1 and PR2) into a 7-entry stale state that is actively referenced by other agents. Both patterns are addressable with specific process steps.

---

## Problems Found

| ID | Category | Severity | Occurrences | Description |
|----|----------|----------|-------------|-------------|
| P1 | testing | medium | 1 phase (PR2) | Test `test_patch_settings_preserves_unspecified_fields` does not verify `exclude_unset` behavior — the mock returns the same row regardless of what was passed to `session.execute`, so the assertion on preserved fields proves nothing about the actual update logic |
| P2 | testing | medium | 2 phases (PR2 FE tests; QC6/QC7 frontend tests previously) | Source-text-scanning tests (grep pattern on .tsx files) used as behavioral coverage — they verify a fix was applied to source text but do not execute the code path |
| P3 | architecture | low | 1 instance (PR2 settings.py) | PATCH and PUT handlers are identical code — semantic duplication where PUT should ideally require all fields but both use `exclude_unset=True` |
| P4 | process | high | 2 consecutive phases (PR1, PR2) | FINDINGS.md has drifted 7 entries behind reality across PR1 and PR2; both QA reviews flagged this and it remains unresolved between phases |
| P5 | process | medium | PR2 (post-QA fix) | camelCase test function name `test_create_thread_mutation_uses_mutate_async_in_handleSend` — violates L4 naming conventions; required a post-QA cleanup commit |
| P6 | testing | high | 2 phases (PR1, PR2) | S5 Integration Smoke Test OPEN for 2 consecutive phases in Wave 19 — mocked DB sessions are the sole test infrastructure for all endpoint tests |

---

## Patterns Identified

### Pattern A: Source-Text-Scanning Tests as Behavioral Proxies

**Evidence:** `test_pr2_frontend_fixes.py` lines 244-324. Three of the ten PR2 tests are source-text scans: `test_create_thread_mutation_uses_mutate_async_in_handle_send`, `test_thread_id_from_response_used_in_chat_body`, `test_double_cast_removed_from_run_detail`, and `test_events_query_has_explicit_return_type`. These read the `.tsx` source files and assert that specific strings are present or absent.

**QA note:** `review_PR2.md` lines 44-48 explicitly flags this: "FE-H1 and FE-H2 tests are source-text-scanning tests (grep-style). They verify the fix exists in source but don't execute the code path." And the review notes (line 5): "Source-level text-search tests are lightweight canaries but could give false confidence."

**Root cause:** Python test files cannot execute TypeScript/React code. When a frontend fix needs coverage in a Python test file, source scanning is the path of least resistance. The problem is that source-scanning tests can be trivially passed by adding the searched string anywhere in the file — the test is not coupled to the behavior it claims to verify.

**Historical pattern:** This is not new to PR2. QA reviews for QC6, QC7, and iOS11 all included Python source-inspection tests for frontend fixes. The pattern is systemic to the dual-language frontend/backend architecture.

**Why this matters:** A source-scanning test that passes does not mean the behavior works. If the fix was applied but introduced a bug nearby, the source-scan passes while the user experiences a broken UI. The test gives coverage credit for something that hasn't been executed. True coverage for these fixes requires either (a) React Testing Library tests in the `web/` test suite, or (b) Playwright E2E tests (PR6).

**Current coverage gap:** PR2's frontend fixes (thread creation race, unsafe type cast) have zero executed-code-path coverage until PR6.

### Pattern B: Mock-Returns-Same-Row Makes Partial-Update Test Vacuous

**Evidence:** `test_pr2_frontend_fixes.py` lines 112-146, `test_patch_settings_preserves_unspecified_fields`. The test constructs `existing_row = _make_settings_row(default_model=..., default_provider=..., default_privacy_mode="external")`, mocks `session.execute` to always return that same row, sends a PATCH with only `default_privacy_mode`, and then asserts that `data["default_model"]` equals `"claude-sonnet-4-20250514"` and `data["default_privacy_mode"]` equals `"private"`.

**The flaw:** `session.execute` returns `existing_row` regardless of what was passed to it. The `SettingsService.update_settings()` calls `session.execute(upsert_stmt)` to write, then calls `session.execute(select_stmt)` to read back. Both calls return the same `_make_settings_row(...)` mock. The assertion that `default_model` is preserved is trivially true because the mock always returns it — not because the PATCH logic preserved it. If `update_settings` accidentally set `default_model=None`, the mock would still return `"claude-sonnet-4-20250514"` and the test would pass.

**QA note:** `review_PR2.md` line 3 (Notes section): "Test for partial-update preservation doesn't actually verify `exclude_unset` behavior (mock always returns same row)."

**Root cause:** The test was written to verify `exclude_unset=True` behavior, but the mock intercepts at too low a level (the session) without tracking what was actually written to the session. The correct approach is either:
- A real SQLite in-memory session (S5-style integration test), or
- A mock that captures the `upsert_stmt` argument and asserts `exclude_unset` was applied to it.

**Pattern frequency:** This is the first confirmed instance of this specific anti-pattern, but it reflects the broader S5 gap: when all DB interaction is mocked at `session.execute`, tests can pass while verifying nothing about the actual SQL generated.

### Pattern C: FINDINGS.md Drift Compounds Across Phases

**Evidence:** `health_2026-03-11_pr2.md` lines 2-8: "FINDINGS.md is now 7 findings behind reality — PR1 resolved 3 (BE-C1, BE-C2, BE-H2) and PR2 resolved 4 (BE-H3, FE-C1, FE-H1, FE-H2), but none are updated in the tracking table yet." The health brief identifies this as "Greatest Risk" and "most dangerous project-level risk right now."

**Prior instance:** The PR1 QA review (`review_PR1.md`) did not flag FINDINGS.md as stale, but the PR1 CI analysis noted the BE-M5 gap was pre-existing. The drift accumulation is traceable: PR1 resolved 3 findings, PR2 resolved 4 more — and neither phase updated FINDINGS.md before completion.

**Root cause:** FINDINGS.md updating is not part of any pipeline step that blocks phase completion. CLAUDE.md documents the lifecycle rules (section "Findings Lifecycle") but there is no gate in the QA checklist that verifies FINDINGS.md is current before a PASS verdict. The QA reviewer flags it as a note, but PASS_WITH_NOTES still allows completion.

**Systemic risk:** The health brief states the consequence clearly: "Other agents (implement, CI, system-auditor) use FINDINGS.md to decide what to work on. If they read stale data, they will either re-fix already-fixed issues or miss the real remaining gaps." With four phases remaining in Wave 19 (PR3-PR6) and 7 findings still stale, there is a real risk of a Wave 19 system-auditor or the Wave 20 planner operating on incorrect state.

### Pattern D: PUT/PATCH Semantic Duplication

**Evidence:** `src/noa/api/v1/settings.py` lines 52-84. The `update_settings` (PUT, lines 52-66) and `patch_settings` (PATCH, lines 69-84) handlers are byte-for-byte identical except for the route decorator and docstring. Both call `body.model_dump(exclude_unset=True)`. `review_PR2.md` line 4 (Notes): "PATCH and PUT handlers are identical code. Consider extracting to a shared helper."

**Severity assessment:** This is low-severity currently because the correct behavior for both verbs in this API is partial update (given that all fields in `UpdateSettingsRequest` are `Optional`). The risk is forward-looking: if a future developer wants to distinguish PUT (require all fields) from PATCH (partial), they must remember to change only one handler and keep them in sync manually.

**Pattern frequency:** 1 instance. Does not rise to systemic yet, but represents a technical debt that is easier to address before it diverges.

---

## Effectiveness of Past Fixes

### CI-009 (L12 Write-Path User Scoping — APPLIED 2026-03-11)

L12 is confirmed added to `Plan/ARCH_INVARIANTS.md` lines 177-188. The rule targets the MemoryStore.store() pattern (BE-M5). PR2 did not touch `memory_store.py`, so no new occurrence of this anti-pattern appeared in PR2.

**Effectiveness:** Cannot yet verify the fix (BE-M5 remains Open in FINDINGS.md; the actual MemoryStore fix is scheduled for PR4). L12 is in place as a design gate for future write-path decisions. No new "store without user_id" instances in PR2.

### CI-010 / CI-011 (S5 Escalation, M3b Write-Path Check — PROPOSED, not applied)

S5 is OPEN in PR2 (2nd consecutive OPEN in Wave 19). Per the proposed escalation rule (CI-010), the trigger threshold is 3 consecutive OPEN within a wave. At 2/3, this is not yet a P1 trigger, but tracking is active.

### CI-008 (M4b Mock Interface Accuracy — PROPOSED, not applied)

PR2 test file uses `session = AsyncMock()` at lines 95, 128, 158, 199. The AsyncMock-on-sync-session pattern (from PR1 analysis) is continuing to appear in new test files, confirming that the absence of the M4b gate is allowing the pattern to persist.

### CI-001 through CI-007 (PROPOSED 2026-03-07 — not applied)

No status change. Still PROPOSED with no applied date. Not re-analyzed here (no new evidence on these in PR2).

---

## Proposals

### CI-012: QA Checklist — Frontend Fix Behavioral Coverage Gate

**Priority:** P2

**ID:** CI-012

**Evidence:**
- `review_PR2.md` Note 5: "Source-level text-search tests are lightweight canaries but could give false confidence."
- `test_pr2_frontend_fixes.py` lines 244-324: 4 of 10 tests are `.tsx` source scans with no code execution.
- Pattern appears in QC6, QC7, iOS11, and PR2 — at least 4 phases use this approach for frontend fixes.

**Root cause:** No checklist item asks whether frontend fix tests actually execute code vs. inspect source text.

**Proposed addition to `Plan/QA_CHECKLIST.md`**, in the S5 row or as an extension to M1:

```markdown
| S5b | Frontend Fix Behavioral Coverage | When a fix modifies TypeScript/React source, the test must either: (a) execute the code path via React Testing Library in `web/src/test/`, or (b) exercise the fix via Playwright E2E test in `web/e2e/`. Source-text-scanning tests (read .tsx and assert string presence) count as canaries only — they do not satisfy S5 and must be accompanied by a note citing the phase that will provide real behavioral coverage (e.g., "PR6 E2E will cover this"). |
```

**Target:** `Plan/QA_CHECKLIST.md`

**Impact estimate:** PR2 has 4 tests in this category. QC6, QC7, iOS11 each had 2-5 such tests. If S5b had existed from Wave 15, it would have either: (a) prompted real web/ tests to be written at implementation time, or (b) explicitly documented the gap rather than silently counting source scans as coverage. Prevents false-confidence in at least one PR per wave for the remaining roadmap (Waves 20-22 all have frontend work).

---

### CI-013: QA Checklist — FINDINGS.md Currency Gate (M1 Extension)

**Priority:** P1

**ID:** CI-013

**Evidence:**
- `health_2026-03-11_pr2.md` lines 2-16: 7 findings are stale across 2 phases (PR1 + PR2). The health brief calls this "Greatest Risk" and "most dangerous project-level risk right now."
- `review_PR2.md` Note 3: "FINDINGS.md update needed: Mark BE-H3, FE-C1, FE-H1, FE-H2 as Resolved by PR2."
- `review_PR1.md` did not flag this, but `review_PR2.md` did — meaning FINDINGS.md became stale at PR1 and accumulated 3 more entries at PR2 before anyone raised it as a blocker.
- CLAUDE.md "Findings Lifecycle" section documents the rule but there is no QA gate that enforces it.

**Root cause:** FINDINGS.md updating is defined as a process rule in CLAUDE.md but not as a QA checklist item. QA reviewers flag it as a note, but notes are non-blocking. The checklist has no M-series item for this.

**Proposed addition to `Plan/QA_CHECKLIST.md`**, as a new M-series item under M5 (Implementation Completeness):

```markdown
| M5b | Findings Currency | If this phase resolves any open finding in `Plan/FINDINGS.md`, that finding's row must be updated to `**Resolved**` with the phase ID before the QA review completes. A phase that resolves a finding without updating FINDINGS.md fails this check. The QA reviewer must grep the finding ID in FINDINGS.md and verify the row status. If the phase introduces a new finding, the finding must be added to FINDINGS.md before the review verdict. |
```

**Target:** `Plan/QA_CHECKLIST.md`

**Impact estimate:** Would have blocked PR1 and PR2 from receiving PASS_WITH_NOTES until FINDINGS.md was updated. The 7 stale entries represent 1-2 hours of potential misdirected agent work if a downstream agent re-fixes already-resolved issues. At Wave 19's pace (one phase per cycle), a 7-entry backlog is the equivalent of 1-2 phases of planning noise.

**Note:** This is P1 because stale FINDINGS.md directly corrupts the inputs used by other agents (implement, ci, system-auditor). A human gate is triggered on P1 proposals.

---

### CI-014: Test Authoring Standard — Assert What Was Written, Not Just What Was Read Back

**Priority:** P2

**ID:** CI-014

**Evidence:**
- `test_pr2_frontend_fixes.py` lines 112-146, `test_patch_settings_preserves_unspecified_fields`: mock returns same row unconditionally; assertion on preserved fields proves nothing about the update logic.
- `review_PR2.md` Note 3: "Test for partial-update preservation doesn't actually verify `exclude_unset` behavior (mock always returns same row)."
- Root cause documented in Pattern B above.

**Proposed change to `Plan/QA_CHECKLIST.md`**, as an extension to M4 (Determinism) or as a note in M2:

```markdown
| M2b | Write-Path Test Fidelity | Tests that verify "field X was preserved by a partial update" must check the actual write operation, not just the read-back result when the read is also mocked. If `session.execute` is mocked to return a fixed row for both writes and reads, an assertion on the read-back value proves nothing about the write. Acceptable approaches: (a) use a real in-memory DB session (S5-style), (b) capture the argument passed to the write call and assert on it (e.g., `session.execute.call_args_list[0]` contains `exclude_unset`-trimmed values), or (c) use a two-call mock that distinguishes the upsert execute from the select execute. |
```

**Target:** `Plan/QA_CHECKLIST.md`

**Impact estimate:** The `test_patch_settings_preserves_unspecified_fields` test currently provides false assurance that `exclude_unset=True` works. If `SettingsService.update_settings` had a bug that zeroed unset fields, this test would still pass. Catching this at the QA review step prevents similar vacuous tests from accumulating across PR3-PR6 (all of which involve upsert-style DB operations).

---

### CI-015: CLAUDE.md — FINDINGS.md Update as Mandatory Pipeline Step

**Priority:** P2

**ID:** CI-015

**Evidence:**
- Same as CI-013. FINDINGS.md is updated as a process rule in CLAUDE.md "Findings Lifecycle" section, but the section describes what to do when resolving/discovering findings — it does not name this as a pipeline gate.
- The problem is not that the rule is missing from CLAUDE.md — it is there. The problem is that it is framed as documentation rather than as a gate that blocks phase completion.

**Proposed addition to CLAUDE.md**, in the "Phase Pipeline" section gates list:

```markdown
- **Findings Sync**: Before QA review, update `Plan/FINDINGS.md` — mark any finding resolved by this phase as `**Resolved**` with the phase ID. Add any new findings discovered during implementation. QA review fails M5b if findings are stale.
```

**Target:** `CLAUDE.md`

**Impact estimate:** Makes the FINDINGS.md update step explicit and gate-blocking rather than advisory. Prevents the accumulating-stale-findings pattern observed in PR1 + PR2. This is a companion to CI-013 (M5b QA gate) — the QA checklist enforces it, CLAUDE.md names it as a pipeline step.

---

## S5 Escalation Tracking

| Wave 19 Phase | S5 Result | Consecutive OPEN Count |
|---------------|-----------|----------------------|
| PR1 | OPEN | 1 |
| PR2 | OPEN | 2 |
| PR3 | TBD | — |
| PR4 | TBD | — |
| PR5 | TBD | — |
| PR6 | Expected PASS (integration tests) | — |

Per CI-010 proposed rule: 3 consecutive OPEN within a wave triggers a P1 CI proposal. PR3 result will determine whether the trigger fires. The CI agent must flag this as P1 if PR3 QA returns S5 OPEN.

---

## Metrics

- Total problems scanned: 6 (5 from PR2 QA notes + 1 structural from FINDINGS.md drift observation)
- New patterns identified: 3 (source-text-scanning as behavioral proxy, vacuous mock-read-back tests, FINDINGS.md drift compounding)
- Recurring patterns (previously seen): 2 (S5 OPEN — 18th occurrence; AsyncMock on sync session — CI-008 pattern continuing)
- Past fixes verified effective: 1/3 checked (L12 in ARCH_INVARIANTS: confirmed present, no new violation in PR2; CI-010/CI-011 not yet applied; CI-008 not yet applied, pattern still appearing)
- Proposals generated: 4 (P1: 1, P2: 3)

---

## Proposal Priority Order

1. **CI-013** (P1) — QA Checklist M5b: FINDINGS.md Currency Gate. Two consecutive phases have completed with stale findings; 7 entries now incorrect. Other agents are using corrupted state.
2. **CI-012** (P2) — QA Checklist S5b: Frontend Fix Behavioral Coverage Gate. Prevents source-text-scanning tests from counting as behavioral coverage. Affects every frontend-touching phase.
3. **CI-015** (P2) — CLAUDE.md: Name FINDINGS.md update as an explicit pipeline gate step. Companion enforcement to CI-013.
4. **CI-014** (P2) — QA Checklist M2b: Write-Path Test Fidelity. Prevents vacuous mock-read-back assertions on partial-update tests.

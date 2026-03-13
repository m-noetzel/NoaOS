# Continuous Improvement Analysis — 2026-03-11 (PR7 QA Cycle)

## Summary

PR7 (Wave 19 audit fix cleanup) passed QA PASS_WITH_NOTES with 10/10 must-haves and 4/5 should-haves. Three issues were flagged: (1) S5 gap — no test exercises the full privacy_mode → orchestrator flow end-to-end; (2) FINDINGS.md open count stated as 10 but actual open rows total 11; (3) source-inspection tests (checking handler source text) remain a fragile testing pattern. Cross-referencing against the backlog and memory, none of these are new root causes — all three map to existing patterns already tracked. However, two have measurable change since the last analysis: S5 broke a consecutive OPEN streak (PR7 is an audit-fix phase, not DB-touching, so S5 OPEN is expected and appropriate here), and source-text-scanning tests have now appeared across six distinct phases, crossing from "confirmed pattern" into "structural testing gap." One new proposal is warranted (CI-028, P2: prohibit source-inspection tests from satisfying M2 negative-test coverage). No P1 proposals in this cycle.

---

## Problems Found

| ID | Category | Severity | Occurrences | Description |
|----|----------|----------|-------------|-------------|
| P1 | testing | low | PR7 (S5 OPEN; expected) | No test exercises full privacy_mode → runner invocation. Handler source inspection is a behavioral proxy. Acceptable for audit-fix phase. |
| P2 | documentation | low | Wave 19 (persistent) | FINDINGS.md open count states 10; actual `\| Open \|` rows = 11 (8 tracking table + 3 user-reported). Off-by-one error in summary line. |
| P3 | testing | medium | 6+ phases (PR2, QC6, QC7, iOS11, PR7 × 2) | Source-inspection tests (read handler source as string, assert substring presence) used as behavioral coverage for wiring. Tests pass even if behavior is wrong, as long as source text matches. |

---

## Patterns Identified

### Pattern A: Source-Inspection Tests as Behavioral Proxies (Expanded — 6+ Phases)

**Evidence:**
- `review_PR7.md` line 94: "Source-inspection tests (checking handler source for fallback expression) are somewhat fragile but acceptable for verifying wiring."
- `review_PR7.md` line 113: "`test_privacy_mode_none_defaults_to_external_in_handler` and `test_jwt_decode_error_sanitized_in_middleware` inspect source code strings rather than testing behavior."
- `test_pr7_audit_fixes.py` (implied by review structure): Two tests in `TestChatRequestPrivacyMode` and `TestJWTErrorSanitization` rely on `inspect.getsource()` or equivalent to check that fallback logic is present in the handler source, rather than invoking the handler with a live request and asserting the response.
- Prior occurrences: QC6, QC7, iOS11, PR2 (CI-012/Pattern A confirmed across 4 phases in `analysis_2026-03-11_pr2.md`). PR7 adds 2 more instances.

**New count:** 6+ phases affected (QC6, QC7, iOS11, PR2, PR7 × 2). This crosses from "occasional pattern" to "structural testing gap."

**Root cause:** Unchanged from PR2 analysis. Python test infrastructure cannot execute TypeScript or Swift code paths, and for Python handler behavioral gaps, source inspection is taken as the path of least resistance when the behavior involves a default expression (`or "external"`) or a middleware chain that is hard to isolate.

**Why the PR7 QA reviewer accepted it:** The two PR7 source-inspection tests cover (a) the `or "external"` fallback in the handler body, and (b) the fact that the middleware calls `TokenError` rather than re-raising `JWTError`. Both are quick to write and hard to test behaviorally without setting up a full auth middleware stack. The reviewer correctly noted they are "acceptable for an audit-fix phase."

**Why the pattern still needs a gate:** Acceptability at QA review time is a judgment call that varies by reviewer. Without a gate, source-inspection tests accumulate across phases without triggering escalation. The current form of CI-012 (S5b Frontend Fix Behavioral Coverage) targets TypeScript source scans specifically — it does not cover Python handler/middleware source inspection. PR7's instances are in Python, and CI-012 would not have caught them.

**Distinction from CI-012:** CI-012 (`Plan/QA_CHECKLIST.md` S5b) targets `test_pr2_frontend_fixes.py`-style scanning of `.tsx` files from Python. PR7's source-inspection tests scan Python handler source from Python — a different (but structurally identical) anti-pattern. A companion gate for Python-side source inspection is needed.

**Proposed fix:** CI-028 (see Proposals section). Add a M2c check: tests that verify behavior by reading source text (via `inspect.getsource`, string matching against source files, or reading `.py` / `.tsx` source files) must be accompanied by a behavioral test that invokes the code path and asserts on the output.

---

### Pattern B: FINDINGS.md Summary Count Off-By-One (Persistent)

**Evidence:**
- FINDINGS.md line 114: `**Open:** 10 | **Partially Resolved:** 0 | **Resolved:** 97 | **Total:** 107`
- Actual grep of `| Open |` rows: 11 rows (BE-M1, BE-M5, BE-H4, BE-H5, FE-M5, iOS-L1, iOS-L2, FE-L1 = 8 in tracking table; L10, L11, L12 = 3 in user-reported section).
- `review_PR7.md` line 101: "counting rows with `| Open |` in the tracking summary yields 8 main-table entries... plus 3 in the user-reported section... = 11 total open. The count may include or exclude the user-reported section differently."

**Root cause:** The `**Open:** N` summary line does not automatically count rows — it is a manually maintained integer. The Wave 19 retro CI analysis (analysis_2026-03-11_wave19_retro.md) noted FINDINGS.md was batch-updated at PR5, but did not verify the summary count against actual row counts. The off-by-one is consistent with the user-reported section (L10/L11/L12) being excluded from the manual count while included in the table.

**Is this new?** The pattern of a stale summary count was the major FINDINGS.md drift problem throughout Wave 19 (CI-013, CI-015, CI-020). The M5b gate (CI-013) was proposed to enforce currency; per the IMPROVEMENT_BACKLOG.md, its status is PROPOSED (not applied). If M5b were applied, the QA reviewer would grep-verify the count, which would have caught this off-by-one in PR7.

**Severity assessment:** Low. FINDINGS.md rows are accurate; only the summary count is wrong. But the error persists across cycles and is a symptom of M5b not yet being enforced.

**No new proposal needed:** CI-013 (P1, M5b Findings Currency Gate) already addresses this. If M5b were applied, the QA reviewer would verify the count as part of the checklist, catching this automatically.

---

### Pattern C: S5 Integration Smoke Test — Status Clarification for PR7

**Evidence:**
- `review_PR7.md` line 26: "Tests use TestClient (real ASGI), but no test exercises the full privacy_mode -> runner flow end-to-end"
- `review_PR7.md` line 109: "This is acceptable for an audit-fix phase but should be covered in a future integration test."

**Assessment:** PR7 is an audit-fix phase. The S5 gap is structural (privacy_mode → orchestrator → runner is a live flow that would require spawning a real runner with DB state), not a consequence of missing test effort. This is the first phase since PR1 where S5 OPEN is not a consecutive-count concern — PR7 is not a DB-touching endpoint phase and has a legitimate reason for the gap.

**S5 consecutive OPEN tracking for Wave 19:**

| Phase | S5 Result | Consecutive OPEN | Notes |
|-------|-----------|-----------------|-------|
| PR1 | OPEN | 1 | DB-touching; no real session |
| PR2 | OPEN | 2 | DB-touching; no real session |
| PR3 | OPEN | 3 | DB-touching; CI-016 P1 triggered |
| PR4 | OPEN | 4 | DB-touching |
| PR5 | OPEN | 5 | Non-DB; legitimate |
| PR6 | PASS (integration tests) | 0 | PR6 closed the streak |
| PR7 | OPEN | 1 | Audit-fix; legitimate; not a DB-touching phase |

**No new proposal warranted.** The CI-016 rule (triggered after 3 consecutive OPEN in a wave) should distinguish audit-fix and non-DB phases from DB-touching endpoint phases. This distinction is not currently in the CI-016 proposal text. Adding a carve-out would reduce false escalations in future audit-fix phases.

**Proposed refinement:** CI-029 (see Proposals section, P3) — add "audit-fix phases and non-DB-touching phases may annotate S5 as N/A with a justification note; the consecutive OPEN counter resets only for DB-touching phases."

---

## Effectiveness of Past Fixes

| Fix | Applied | Effectiveness in PR7 |
|-----|---------|----------------------|
| CI-009 (L12 Write-Path User Scoping) | 2026-03-11 | No new write-path user_id violations in PR7. Effective. |
| CI-013 (M5b Findings Currency Gate) | PROPOSED — not yet applied | Not enforced. FINDINGS.md off-by-one count was not caught before QA. M5b would have caught this. |
| CI-015 (CLAUDE.md Findings Sync step) | PROPOSED — not yet applied | Not confirmed present. FINDINGS.md is otherwise current (W19-H1 through W19-M6 resolved in PR7). |
| CI-016 (S5 escalation) | PROPOSED — not yet applied | S5 OPEN in PR7 but phase is audit-fix (legitimate). Rule text should carve out non-DB-touching phases. |
| CI-017 (M8b Cross-Language Optionality) | PROPOSED — not yet applied | PR7's `privacy_mode: Literal["private","external"] \| None = None` fix directly addressed the gap CI-017 was raised to prevent. The fix is correct. The gate is still needed for future iOS-backend phases. |
| CI-022 (L14 Full Request Model Audit) | PROPOSED — not yet applied | PR7 Q/A notes M8b PASS: `privacy_mode: Literal["private", "external"] \| None = None` explicitly verified. This is exactly what CI-022 targets. The gate being present would have surfaced the privacy_mode gap earlier (at PR3 time, not PR7 time). |
| CI-025 (iOS-backend contract audit step) | Noted as DONE in review_PR7.md line 42: "Added to CLAUDE.md pipeline" | Confirmed applied. This is the first cycle where CI-025 shows as applied. Monitor next iOS-backend phase for compliance. |
| CI-027 (Add W19-H1 to FINDINGS.md) | PROPOSED — RESOLVED (W19-H1 now in FINDINGS.md as Resolved by PR7) | W19-H1 row confirmed in FINDINGS.md line 105. CI-027 is effectively resolved by PR7 implementation. Update backlog status. |

---

## Proposals

### CI-028: QA Checklist — Source-Inspection Test Gate (M2c)

**Priority:** P2

**ID:** CI-028

**Evidence:**
- `review_PR7.md` lines 94, 113: Two PR7 tests read handler/middleware source as strings to verify fallback logic and error handling wiring.
- Prior occurrences: QC6, QC7, iOS11, PR2 (TypeScript source scans, addressed by CI-012/S5b); PR7 (Python source scans, not covered by CI-012).
- Pattern spans at least 6 phases across the project. The CI-012/S5b gate covers TypeScript scans but not Python-side source inspection of handler source.
- Impact: a source-inspection test passes even when the code path is broken, as long as the source text matches. Example: if the privacy_mode handler were refactored to use a match statement, `test_privacy_mode_none_defaults_to_external_in_handler` would fail — but the behavior would be correct. Conversely, the test would pass if the fallback string is present but unreachable due to a condition guard.

**Root cause:** No existing checklist item distinguishes behavioral tests (invocation → assertion on output) from structural tests (source code → assertion on text presence). CI-012 is scoped to TypeScript source scans only.

**Proposed addition to `Plan/QA_CHECKLIST.md`**, as M2c:

```markdown
| M2c | Source-Inspection Test Gate | Tests that verify behavior by reading source text (via `inspect.getsource()`, string matching against `.py` / `.tsx` source files, or module `__doc__` inspection) count as structural canaries only — they do not satisfy M2 (negative tests) or S5 (integration smoke). Each source-inspection test must be accompanied by either: (a) a behavioral test that invokes the code path with a real request and asserts on the response, or (b) a note citing the phase that will provide real behavioral coverage. The QA reviewer must flag any source-inspection test used without a behavioral companion as an S5 gap. |
```

**Target:** `Plan/QA_CHECKLIST.md`

**Impact estimate:** PR7 has 2 source-inspection tests; prior phases had 2-5 each. If M2c existed from QC6 onward, at least 12 tests across 6 phases would have been required to have behavioral companions, pushing coverage gaps into the explicit backlog rather than silently accumulating. Prevents this pattern in all Wave 20+ phases that fix wiring or middleware behavior.

**Human gate required?** No. P2 proposals do not require a human gate. Human approval required before application per standard process.

---

### CI-029: S5 Carve-Out for Audit-Fix and Non-DB-Touching Phases (P3)

**Priority:** P3

**ID:** CI-029

**Evidence:**
- PR7 S5 OPEN is described as "acceptable for an audit-fix phase" by the QA reviewer (`review_PR7.md` line 109).
- The CI-016 proposed rule (triggered after 3 consecutive OPEN within a wave) does not distinguish audit-fix phases from DB-touching endpoint phases.
- Without this distinction, the CI-016 rule would misfire on audit-fix and documentation phases, consuming escalation budget on legitimate gaps and reducing signal fidelity.

**Proposed refinement to CI-016 text in CLAUDE.md** (when CI-016 is applied):

```markdown
For S5 tracking purposes, a phase is "DB-touching" if it modifies or queries DB state via a SQLAlchemy session in the implementation path. Audit-fix phases (those that fix constants, headers, type annotations, or delete dead code without touching DB query paths) may annotate S5 as "N/A — audit-fix phase" and are excluded from the consecutive OPEN counter. The QA reviewer must confirm the N/A annotation is accurate.
```

**Target:** CLAUDE.md (as a clarifying note to the S5 rule when CI-016 is applied) and/or `Plan/QA_CHECKLIST.md` S5 row.

**Impact estimate:** Low individual impact but prevents false-positive P1 escalations on audit cleanup phases. PR7 is the first clear example of a legitimate S5 OPEN that should not count as a streak extension.

**Human gate required?** No. P3, no gate.

---

## Summary: Wave 19 PR Cycle S5 Final State

With PR7, the S5 picture for Wave 19 is complete:

| Phase | Type | S5 | Streak (DB-touching phases only) |
|-------|------|----|----------------------------------|
| PR1 | DB-touching | OPEN | 1 |
| PR2 | DB-touching | OPEN | 2 |
| PR3 | DB-touching | OPEN | 3 — CI-016 P1 triggered |
| PR4 | DB-touching | OPEN | 4 |
| PR5 | Mixed | OPEN | 5 |
| PR6 | Integration | PASS | 0 (reset) |
| PR7 | Audit-fix | OPEN | 0 (excluded per CI-029 proposed carve-out) |

CI-029 formalizes what the Wave 19 QA reviewer already applied informally.

---

## Outstanding P1 Human Gates (Restated for Wave 20)

These were raised in prior cycles. PR7 does not add new P1 proposals. All four remain required before Wave 20 begins.

| ID | Title | Overdue Since | Target |
|----|-------|---------------|--------|
| CI-013 | M5b Findings Currency Gate | PR2 | QA_CHECKLIST.md |
| CI-016 | S5 Integration Test Baseline (+ CI-029 carve-out when applying) | PR3 | CLAUDE.md |
| CI-017 | M8b Cross-Language Field Optionality Gate | PR3 | QA_CHECKLIST.md |
| CI-022 | L14 Full Request Model Audit on iOS-Backend Fix | Wave19 retro | ARCH_INVARIANTS.md |
| CI-025 | iOS-Backend Contract Audit Step | Wave19 retro | CLAUDE.md — **APPLIED** (verify at next iOS phase) |

Note: CI-025 appears applied (added to CLAUDE.md per review_PR7.md line 42). Verify during first Wave 20 iOS-backend phase. If confirmed effective, mark as Verified.

---

## Metrics

- Total problems scanned: 3 (from PR7 QA notes)
- New patterns identified: 0 (all map to existing tracked patterns)
- Recurring patterns (previously seen): 3 (source-inspection tests, FINDINGS.md count drift, S5 OPEN)
- Past fixes verified effective: 3/8 checked (CI-009 no new violations; CI-025 confirmed applied; CI-027 resolved by PR7 implementation)
- Past fixes verified not yet applied: 5 (CI-013, CI-015, CI-016, CI-017, CI-022)
- Proposals generated: 2 (P1: 0, P2: 1 (CI-028), P3: 1 (CI-029))
- P1 human gates triggered this cycle: 0
- Outstanding P1 human gates (overdue): 4 (CI-013, CI-016, CI-017, CI-022)

# Retrospective: Wave 3 (Domain Workers & Isolation)

**Date:** 2026-03-05
**Phases covered:** DW1, DW2, DW3, DW4
**Total tests delivered:** 91 (38+16+16+21)
**QA verdicts:** 2 PASS (DW2, DW3), 2 PASS_WITH_NOTES (DW1, DW4)
**Issues logged:** 0 (ISSUES.md clean)

---

## What Went Well

### 1. Continued delivery ahead of estimates
All four phases completed under their estimates: DW1 (45→20 min), DW2 (30→15 min), DW3 (30→10 min), DW4 (45→15 min). The conservative estimation pattern from Waves 1-2 continues to work well.

### 2. Test counts exceeded estimates again
Plan estimated ~60 tests; delivered 91. DW1 was the standout with 38 tests (planned ~20), covering every RPC limit from §9.1-9.2 with exact-at-limit and over-limit variants.

### 3. Spec compliance is precise
DW1's RPC limits match the spec exactly (query=4096, fact=2048, payload=16KB, etc.). DW3's egress allowlist matches §20.3's 8 domains. DW4's routing priority chain matches §18 exactly. QA deep-dives confirmed no spec drift.

### 4. Security hardening applied correctly
DW3 delivered real container hardening: `read_only: true`, `cap_drop: ALL`, `no-new-privileges`, `internal: true` on private network, `127.0.0.1` bind for API. These are non-trivial security controls applied correctly on the first pass.

### 5. Clean architecture boundaries maintained
DW2 has zero imports from `noa.private_worker`. DW1 has zero imports from external packages. The domain isolation model is enforced at the code level, not just the network level.

### 6. All 273 project tests pass
No regressions. The 7 langsmith/langgraph import failures from Wave 1-2 retro have been resolved (those tests were refactored to not require native extensions).

---

## What Could Improve

### 1. Missing deliverables: thin wiring layers skipped
DW1 skipped `app.py` (private worker FastAPI app). DW4 skipped the `router.py` edit (wiring PrivacyClassifier into orchestrator). Both QA reviews noted these as non-blocking because the core logic is complete, but these wiring gaps accumulate. Two phases in a row skipping planned EDIT/CREATE files is a pattern worth addressing.

**Recommendation:** Code agents should use their file table as a checklist before declaring done. If a file is intentionally deferred, note it in the commit message.

### 2. Keyword duplication between classifier and router
DW4's `PrivacyClassifier` has its own `_PRIVATE_KEYWORDS` list, while `orchestrator/nodes/router.py` still has a separate `_classify_privacy` function with a potentially different keyword list. This is a drift risk. The router should delegate to the classifier.

**Recommendation:** Wire `PrivacyClassifier` into the orchestrator router as a follow-up before Wave 4 starts, or track it explicitly.

### 3. LLM-based classification not implemented
DW4 plan called for "keyword + LLM-based analysis per §18" but delivered keyword-only. The `_raw_classify` method is mockable/extensible, but no LLM pathway exists. This is acceptable for Phase 1 since fail-safe handles low-confidence cases, but it should be tracked.

### 4. 24-hour windowing missing in contract violation tracker
DW1's `ContractViolationTracker` counts all violations since creation, not per 24-hour window as spec §9.4 requires. Acceptable for single-process lifecycle but will need fixing when persistence is added.

---

## Trend Analysis (vs. Wave 1-2 Retro)

| Issue | Wave 1-2 | Wave 3 | Trend |
|-------|----------|--------|-------|
| Missing deliverables (API endpoints, wiring) | OC3 missing audit endpoint | DW1 missing app.py, DW4 missing router edit | **Recurring** — needs explicit checklist step |
| PASS_WITH_NOTES follow-up tracking | No tracking mechanism | Still no tracking mechanism | **Unchanged** — recommend ISSUES.md entries |
| Broad exception assertions | F4 used `pytest.raises(Exception)` | Not seen in Wave 3 | **Improved** |
| Missing Alembic migrations | OC3, OC4 skipped migrations | No new models in Wave 3 (N/A) | N/A |
| Langsmith/langgraph import errors | 7 failing tests | All 273 tests pass | **Resolved** |
| Async mock warnings | Present in Wave 1-2 | Still present (5 warnings in auth tests) | **Unchanged** |

---

## Recommendations for Wave 4

### R1: Track PASS_WITH_NOTES items in ISSUES.md
Carry forward from Wave 1-2 retro. Four waves of PASS_WITH_NOTES items are accumulating without tracking:
- F4: mock session, broad exception assertions
- OC3: missing audit endpoint
- DW1: missing app.py, 24h windowing
- DW4: router.py not wired, LLM classification deferred

File these as LOW-severity items so they don't silently accumulate.

### R2: Code agent file-table checklist
Add a step to the `/write-code` skill: after implementation, verify each file in the phase plan's file table. If a file is intentionally deferred, add a note to the commit. This addresses the recurring "missing deliverable" pattern.

### R3: Wire PrivacyClassifier into router before Wave 4
The keyword duplication is a concrete drift risk. A 5-minute task to make `router.py` delegate to `PrivacyClassifier` eliminates it.

### R4: Fix async mock warnings
Still present from Wave 1-2. Four auth tests produce `RuntimeWarning: coroutine was never awaited`. Fix by using `AsyncMock` explicitly. This is a 5-minute cleanup.

### R5: Wave 4 tool phases are highly parallelizable
TI1-TI5 are independent of each other (TI3 depends on TI2's shared Google auth, but that's the only dependency). Consider executing TI1-TI5 in parallel where possible, with TI6 (governance) as the serialized capstone that depends on all five.

# Retrospective: Wave 4 (Tool Integrations)

**Date:** 2026-03-05
**Phases covered:** TI1, TI2, TI3, TI4, TI5, TI6
**Total tests delivered:** 122 (29+17+14+13+13+36)
**QA verdicts:** All PASS or PASS_WITH_NOTES
**Issues logged:** 0 (ISSUES.md clean)
**Final project test count:** 395 passing

---

## Wave Summary

| Phase | Scope | Tests | Est. | Actual | QA |
|-------|-------|-------|------|--------|----|
| TI1 | Memory Tool (Remember/Recall) | 29 | ~30 min | ~15 min | PASS |
| TI2 | Google Calendar Tool | 17 | ~30 min | ~10 min | PASS |
| TI3 | Gmail Tool | 14 | ~30 min | ~10 min | PASS |
| TI4 | Notion Tool | 13 | ~30 min | ~10 min | PASS |
| TI5 | Web Search Tool (Provider-Agnostic) | 13 | ~20 min | ~10 min | PASS |
| TI6 | Tool Interface, Registry & Governance | 36 | ~60 min | ~20 min | PASS_WITH_NOTES |
| **Total** | | **122** | **~200 min** | **~75 min** | |

Wave 4 delivered all six MVP tool integrations plus the governance layer in approximately 37% of the estimated time. TI6 served as the capstone phase, unifying all five tools under a `ToolInterface` Protocol with `ToolRegistry`, `GovernanceWrapper` (idempotency, rate limiting, dry-run previews), and an MCP adapter stub.

---

## What Went Well

### 1. Strongest delivery-to-estimate ratio yet
Wave 4 completed in ~75 minutes vs. ~200 estimated (2.7x faster). This continues the trend from Wave 3 (~60 min vs. ~150 est.) and is the best ratio in the project. The estimates were conservative but the tooling phases had clear, repetitive structure (ABC class + execute dispatcher + mock tests) that made each successive tool faster to implement.

### 2. Test count exceeded estimates significantly
Plan estimated ~72 tests across TI1-TI5 plus ~30 for TI6; delivered 122. TI1 was the standout at 29 tests (est. ~15), covering CRUD operations, tag filtering, search, and all RPC contract limits. TI6 delivered 36 tests covering interface compliance for all 5 tools, registry allowlisting, governance wrapper behaviors, idempotency TTL, and rate limiting.

### 3. Mid-wave scope changes handled cleanly
Two significant scope adjustments were made during Wave 4, both at user request:
- **TI5 made provider-agnostic:** Added `SearchProvider` ABC with Tavily as the first implementation, rather than a Tavily-only tool. This was a good architectural decision that adds extensibility at minimal cost.
- **TI0 merged into TI6:** The original plan had a separate TI0 phase for the Tool Interface. Merging it into TI6 (governance) eliminated a phase boundary and produced a more cohesive capstone that covers interface, registry, and governance together.

Both changes were absorbed without delays or rework.

### 4. Uniform tool architecture achieved
All five tools now implement the same `ToolInterface` Protocol: `name`, `domain`, `risk_tiers`, `execute(function, params)`. The `ToolRegistry` provides static allowlisting (SPEC.md section 2.1), and the `GovernanceWrapper` layers idempotency, rate limiting, and dry-run previews on every tool call. This is a clean, extensible architecture.

### 5. Security properties maintained
- No hardcoded secrets or API keys in any tool implementation
- API keys are constructor parameters, not embedded
- `ToolRegistry` enforces static allowlists (unknown tools raise `KeyError`)
- Domain isolation preserved: `MemoryTool.domain = "private"`, external tools have `domain = "external"`
- `GovernanceWrapper` applies rate limiting per-function, matching SPEC.md section 19.3

### 6. Zero regressions across 395 tests
All prior wave tests continue to pass. No import errors, no flaky tests, no mock leakage between phases.

---

## What Needs Improvement

### 1. tool_node wiring deferred (recurring pattern)
TI6's phase plan included editing `src/noa/orchestrator/nodes/tools.py` to replace `execute_tool` with `ToolRegistry.dispatch()`. This was not done. QA flagged it as N1 (non-blocking) because the dispatch path is fully tested in isolation. However, this continues the pattern from Wave 3 where DW1 skipped `app.py` and DW4 skipped `router.py` wiring. Three consecutive waves have deferred "thin wiring" deliverables.

**Impact:** The accumulation of unwired components means the system has tested parts that are not yet connected. Integration testing will surface these gaps, but they should not be allowed to grow further.

### 2. PASS_WITH_NOTES items still not tracked in ISSUES.md
Wave 3 retro (R1) recommended filing PASS_WITH_NOTES items as LOW-severity entries in ISSUES.md. This was not done during Wave 4. The untracked items now span five phases:
- F4: mock session, broad exception assertions
- OC3: missing audit endpoint
- DW1: missing `app.py`, 24h windowing
- DW4: `router.py` not wired, LLM classification deferred
- TI6: `tool_node` not wired, `pytest.mark.ti6` not registered, rate limiter is fixed-window not sliding, `extract_idempotency_key` is case-sensitive

This list is growing. Without tracking, items risk being forgotten.

### 3. Protocol compliance required runtime fixes
Two tools (`MemoryTool` and `WebSearchTool`) had `risk_tier` (singular) instead of `risk_tiers` (dict), breaking `ToolInterface` compliance. This was caught and fixed during TI6 implementation, but it indicates the tool phases (TI1, TI5) were implemented before the interface contract was finalized. When the interface was defined in TI6, retroactive edits were needed.

**Lesson:** When a capstone phase defines a protocol that earlier phases must implement, the protocol should be sketched (even informally) before the earlier phases begin.

### 4. `from __future__ import annotations` breaks Protocol runtime checks
The code agent discovered that `from __future__ import annotations` (PEP 563 deferred evaluation) prevents `hasattr`-based Protocol attribute checks at runtime. This required workarounds in tests. This is a known Python gotcha but it cost debugging time.

**Recommendation:** Document this in a project conventions file or test utilities, so future phases avoid the same pitfall.

### 5. Rate limiter described as sliding-window but implements fixed-window
QA N3 noted that `RateLimiter` docstring says "Sliding-window rate limiter" but the implementation is a fixed-window counter that resets entirely when the window expires. This is acceptable for Phase 1 but the docstring is misleading. Docstrings should accurately describe behavior.

---

## Trend Analysis (vs. Wave 3 Retro)

| Issue | Wave 3 | Wave 4 | Trend |
|-------|--------|--------|-------|
| Missing deliverables (wiring layers) | DW1 missing `app.py`, DW4 missing `router.py` edit | TI6 missing `tool_node` wiring | **Recurring** -- 3 consecutive waves now. Needs intervention. |
| PASS_WITH_NOTES tracking | Not tracked, retro recommended ISSUES.md | Still not tracked despite recommendation | **Unchanged** -- recommendation not adopted |
| Delivery ahead of estimates | 2.5x faster (Wave 3) | 2.7x faster (Wave 4) | **Improving** -- consider tightening estimates |
| Test count vs. estimates | 91 vs. ~60 (1.5x) | 122 vs. ~72 (1.7x) | **Consistent** -- estimates are conservative |
| Broad exception assertions | Improved in Wave 3 | Not observed in Wave 4 | **Resolved** |
| Async mock warnings | Present (5 warnings) | Not explicitly checked | **Unknown** -- should verify |
| Import/extension errors | Resolved in Wave 3 | No recurrence | **Resolved** |
| Spec compliance precision | Exact match in Wave 3 | Exact match in Wave 4 | **Sustained** |

---

## Recommendations for Wave 5 (Advanced Backend)

### R1: Wire deferred components before starting Wave 5
Three deferred wiring tasks should be completed as a pre-wave cleanup:
1. `src/noa/orchestrator/nodes/tools.py` -- replace `execute_tool` with `ToolRegistry.dispatch()`
2. `src/noa/orchestrator/nodes/router.py` -- delegate to `PrivacyClassifier`
3. Register all custom pytest markers in `pyproject.toml`

These are each 5-10 minute tasks. Completing them before Wave 5 prevents further accumulation and ensures the orchestrator is properly wired before AB3 (Task Scheduling) touches it.

### R2: File PASS_WITH_NOTES items in ISSUES.md now
This is the third time this recommendation appears. Create LOW-severity entries for all untracked notes from F4, OC3, DW1, DW4, and TI6. This takes 10 minutes and provides a single place to track technical debt.

### R3: Tighten time estimates for Wave 5
Four waves of data show consistent 2.5-2.7x overestimation. Wave 5 phases are estimated at ~30 min each. Consider reducing to ~15-20 min each based on observed velocity. More accurate estimates improve planning and set realistic expectations.

### R4: Define integration contracts before implementation phases
Wave 5 includes AB3 (Task Scheduling) which will need to integrate with the orchestrator, tool registry, and policy engine. Define the integration points and function signatures before the implementation phases begin, avoiding the TI6 retroactive-fix pattern where the capstone had to patch earlier work.

### R5: Address rate limiter accuracy before AB1 (Cost Control)
AB1 implements cost control and token tracking, which will likely use rate limiting or similar windowed counters. The fixed-window-masquerading-as-sliding-window issue (TI6 N3) should be resolved before building more rate-sensitive features on top of it.

### R6: Validate header case sensitivity during integration
TI6 QA noted that `extract_idempotency_key` is case-sensitive for header lookup. Wave 5 or integration testing should validate this works correctly with actual FastAPI/Starlette request objects, where headers may be normalized to lowercase.

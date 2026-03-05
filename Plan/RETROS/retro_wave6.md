# Retrospective: Wave 6 (Web Client)

**Date:** 2026-03-05
**Phases covered:** WC1, WC2, WC3, WC4, WC5, WC6, WC7
**Total tests delivered:** 75 (25+9+8+7+8+8+10)
**QA verdict:** PASS_WITH_NOTES (35/35 must-haves PASS, 10/10 should-haves PASS, 5 non-blocking notes)
**Issues logged:** 0 blockers, 5 non-blocking QA notes
**Final project test count:** 569 passing (494 backend + 75 frontend)

---

## Wave Summary

| Phase | Scope | Tests | Est. | Actual | QA |
|-------|-------|-------|------|--------|----|
| WC1 | React Project Setup & Chat UI with SSE | 25 | ~10 min | ~8 min | PASS |
| WC2 | Run Timeline & Event Details | 9 | ~7 min | ~3 min | PASS |
| WC3 | Approval Interface with Dry-Run Previews | 8 | ~7 min | ~3 min | PASS |
| WC4 | Task Queue Visualization | 7 | ~5 min | ~2 min | PASS |
| WC5 | Memory Audit UI | 8 | ~7 min | ~4 min | PASS |
| WC6 | Cost Dashboard & Settings | 8 | ~5 min | ~3 min | PASS |
| WC7 | Artifact Viewer & PWA Manifest | 10 | ~7 min | ~3 min | PASS |
| **Total** | | **75** | **~48 min** | **~26 min** | |

Wave 6 delivered all seven web client phases in approximately 54% of estimated time. WC1 executed sequentially (project setup + conventions). WC2-WC7 executed in parallel across 6 independent agents. This was the first wave with a domain shift (Python → TypeScript/React) and the highest parallelism factor (6 concurrent agents).

---

## What Went Well

### 1. Successful domain shift to frontend
This was the first wave building React/TypeScript instead of Python backend. The transition was smooth: Vitest+RTL+MSW conventions were established during WC1 and all 6 subsequent agents adopted them without issues. No ad-hoc tooling decisions were needed, validating the Wave 5 retro recommendation R3 (establish frontend conventions before WC1).

### 2. Maximum parallelism achieved (R7 adopted)
Wave 5 retro recommended maximizing parallel execution. Wave 6 achieved 6-way parallelism for WC2-WC7 — the highest concurrency in the project. All 6 agents completed independently with no merge conflicts, no shared state issues, and no interface mismatches. The dependency graph (WC1 → WC2-WC7) was correctly identified and exploited.

### 3. Tightened estimates closer to reality (R1 partially adopted)
Wave 5 retro recommended 5-10 min per phase. Wave 6 adopted 5-10 min estimates. The overestimation ratio improved from 4.2x (Wave 5) to 1.8x (Wave 6). WC1 was the most accurate at 1.25x (10 min est, 8 min actual). The remaining phases averaged ~2x overestimation. This is the best estimate accuracy in the project, though still room for improvement.

### 4. Consistent component architecture across all 7 phases
Every phase followed the same pattern: Zustand store → API client → React components → tests. This consistency emerged naturally from the WC1 conventions and was replicated by all 6 parallel agents. The result is a uniform codebase with predictable file locations and patterns:
- `web/src/store/{feature}.ts` — Zustand state management
- `web/src/api/{feature}.ts` — API client functions
- `web/src/components/{Feature}/*.tsx` — React components
- `web/src/__tests__/{Feature}.test.tsx` — Test suites

### 5. Perfect QA scorecard
All 35 must-have criteria (7 phases × 5 criteria) and all 10 should-have criteria received PASS. This matches Wave 5's must-have performance and improves on its should-have score (10/10 vs 19/20). The QA scorecard has been clean for two consecutive waves.

### 6. Zero backend regressions
All 494 backend tests continue to pass. The frontend is fully isolated — no backend files were modified during Wave 6 (except a pre-existing ruff import ordering fix in `app.py`).

### 7. Comprehensive spec coverage
All major SPEC.md web client requirements from §29 are covered:
- Chat UI with SSE streaming (§29.2, §22.4) ✓
- Run timeline with all event types from §22.2 ✓
- Approval interface with dry-run previews (§19.2, §29.6) ✓
- Batch approval (§23.2) ✓
- Task queue visualization (§23.4) ✓
- Memory audit with category filter (§13.2) ✓
- Cost dashboard with budget bars (§24) ✓
- Model selection and privacy toggle (§14.4) ✓
- PWA manifest (§29.3) ✓
- Artifact viewer (§22.3) ✓

---

## What Needs Improvement

### 1. Agent commit permissions still not fixed (R2 not adopted)
Wave 5 retro R2 recommended investigating and fixing agent commit permissions before Wave 6. This was not done. All 6 parallel agents (WC2-WC7) could not commit their work — the orchestrator had to stage and commit everything in a single batch. The WC1 test agent also failed to commit, requiring orchestrator intervention. This is now a 3-wave-old recurring issue (AB2/AB5 in Wave 5, all agents in Wave 6). The root cause remains uninvestigated.

**Impact:** When agents can't commit, the orchestrator loses granular per-phase commit history. Wave 6's entire WC2-WC7 implementation landed in a single monolithic commit (36 files, 8268 insertions) instead of 6 focused commits. This makes git history less useful for debugging and rollback.

### 2. No App.tsx router or layout shell (N1)
The web client has 7 independent component trees but no `App.tsx` connecting them. There's no routing (React Router), no navigation, no layout structure. Each component works in isolation but the application is not runnable as a unified SPA. This is the same "missing wiring" pattern seen in backend waves (DW1 app.py, DW4 router.py, TI6 tool_node). The pattern has now crossed domains from backend to frontend.

### 3. No CSS or visual design (N2)
All 31 implementation files render bare HTML with ARIA attributes but zero styling. While this is acceptable for MVP testing, the web client is not visually usable. A dedicated styling pass will be needed before the UI can be shown to users.

### 4. Hardcoded API base URL (N4)
`http://localhost:8000/api/v1` is hardcoded in `client.ts` and all MSW handlers. For deployment flexibility, this should use an environment variable (`VITE_API_BASE_URL`). This is a 2-minute fix but affects multiple files.

### 5. Disk space constraint caused installation friction
npm install failed initially because `/home/devuser` is a 256MB tmpfs that filled up. The fix (redirecting npm cache to `/workspace/.npm-cache`) worked but required manual intervention. This could have blocked all 6 parallel agents if they'd each needed `npm install`. For future sessions, the npm cache redirect should be pre-configured.

### 6. Test-to-implementation ratio is low for some phases
WC4 has only 7 tests for 2 components + 1 store. WC6 has 8 tests covering a dashboard, settings panel, and model selector. While all tests are meaningful, the coverage is thinner than backend phases. The backend averaged ~18 tests/phase across 5 waves; Wave 6 averaged ~10.7 tests/phase.

---

## Trend Analysis (vs. Waves 3-5)

| Issue | Wave 3 | Wave 4 | Wave 5 | Wave 6 | Trend |
|-------|--------|--------|--------|--------|-------|
| Missing wiring | DW1 `app.py`, DW4 `router.py` | TI6 `tool_node` | Cleared pre-wave | No `App.tsx` router | **Recurring** — crossed to frontend; systemic pattern |
| PASS_WITH_NOTES tracking | Not tracked | Not tracked | Cleared pre-wave | 5 notes in QA review | **Stable** — tracked in reviews but not ISSUES.md |
| Delivery ahead of estimates | 2.5x faster | 2.7x faster | 4.2x faster | 1.8x faster | **Improving** — best ratio yet, estimates now realistic |
| Test count vs. estimates | 91 vs ~60 | 122 vs ~72 | 90 vs ~90 | 75 vs ~81 | **Accurate** — second wave with close match |
| Spec compliance | Exact match | Exact match | One divergence (AB5) | Full coverage | **Sustained** |
| Security properties | Strong | Strong | Strong | Strong (no XSS, proper auth) | **Sustained** |
| Agent commit friction | Not observed | Not observed | AB2/AB5 can't commit | All agents can't commit | **Worsening** — now affects 100% of agents |
| Retro adoption | N/A | 0/2 adopted | 4/6 adopted | 3/7 adopted (R1, R3, R7) | **Mixed** — key items adopted, R2 still ignored |
| Parallel execution | Not used | TI1-TI5 parallel | AB1/AB2/AB5 parallel | WC2-WC7 6-way parallel | **Improving** — highest concurrency yet |

---

## Wave 5 Retro Recommendation Adoption

| ID | Recommendation | Adopted? | Notes |
|----|---------------|----------|-------|
| R1 | Adopt 5-10 min estimates | **YES** | Estimates ranged 5-10 min; ratio improved from 4.2x to 1.8x |
| R2 | Fix agent commit permissions | **NO** | Still broken; all 7 agents couldn't commit |
| R3 | Establish frontend testing conventions | **YES** | Vitest+RTL+MSW established in WC1; adopted by all phases |
| R4 | Reconcile AB5 coding contract | **DEFERRED** | Not addressed; remains backend debt |
| R5 | Add `now` parameter injection | **DEFERRED** | Not addressed; remains backend debt |
| R6 | Complete AB4 stubs | **DEFERRED** | Not addressed; remains backend debt |
| R7 | Maximize WC parallelism | **YES** | 6-way parallel execution achieved |

**Score: 3 adopted, 1 not adopted, 3 deferred (backend items, reasonable to defer for a frontend wave)**

---

## Recommendations for Post-Wave 6

### R1: Create App.tsx with routing and navigation layout
The wiring gap is now the #1 blocker for a runnable application. Create:
- `web/src/App.tsx` with React Router
- `web/src/components/Layout/Sidebar.tsx` for navigation
- Routes: `/chat`, `/runs`, `/queue`, `/memory`, `/costs`, `/settings`
- This connects all 7 component trees into a working SPA

This is a single focused task that should take ~10 minutes.

### R2: Fix agent commit permissions (CRITICAL — 3rd consecutive recommendation)
This has been recommended in Wave 4, Wave 5, and now Wave 6 retros without being addressed. The problem is worsening (2 agents affected in Wave 5 → all 7 in Wave 6). Root cause investigation is overdue. Check:
- Git safe.directory settings in worktree contexts
- Whether the Agent tool's `isolation: "worktree"` mode has different git config
- Whether agents are spawned with correct `HOME` / git identity
- If the issue is permission-based or configuration-based

Until fixed, the orchestrator must batch-commit for all agents, losing granular history.

### R3: Extract API base URL to environment variable
Replace `http://localhost:8000/api/v1` with `import.meta.env.VITE_API_BASE_URL || '/api/v1'` in:
- `web/src/api/client.ts`
- `web/src/test/mocks/handlers.ts`

This is a 5-minute fix that unblocks deployment configuration.

### R4: Add CSS framework and basic styling
The web client is functionally complete but visually unusable. Options:
- Tailwind CSS (utility-first, no custom CSS needed)
- CSS Modules (scoped, no framework dependency)
- Plain CSS files colocated with components

Recommend Tailwind for speed. A dedicated styling pass would make the app presentable.

### R5: Add integration wiring for backend stubs (pre-integration cleanup)
Carry forward from Wave 5 retro: R4 (AB5 coding contract), R5 (datetime injection), R6 (AB4 stubs). These are small backend tasks that should be addressed before any end-to-end integration testing.

### R6: Consider end-to-end smoke tests
With both backend (494 tests) and frontend (75 tests) complete, the next valuable testing layer is e2e smoke tests. A minimal Playwright or Cypress setup that verifies:
- Login → Chat → Send message → SSE streaming renders
- Approval flow renders and responds to user action
- Settings changes persist

This bridges the gap between unit tests and manual testing.

### R7: Estimate at 3-5 minutes per phase for future waves
Six waves of data show that phases consistently complete in 2-8 minutes, with the median around 3-4 minutes. The 5-10 min estimates used in Wave 6 were better but still ~2x high. For maximum accuracy, estimate 3-5 minutes per standard phase and 8-10 minutes only for setup phases (like WC1) that involve new toolchain bootstrapping.

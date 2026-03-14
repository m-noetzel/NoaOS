# CI Agent Memory

## Backlog State

- `Plan/CI/IMPROVEMENT_BACKLOG.md` has CI-001 through CI-044
- Last analysis: `Plan/CI/analysis_2026-03-14_wave22.md`
- CI-042 (P1): dead-end store broadening -- awaiting human approval

## Validated Recurring Categories (3+ waves)

### Dead-end stores (confirmed persistent -- Waves 20, 21 partial, 22)
- Wave 20 DE3: `workers_degraded` app.state flag, never read
- Wave 22 FR6: 4 governance settings fields (DB-persisted), never consumed by orchestrator/policy
- CI-031 (app.state detection) is effective but too narrow -- does not cover DB fields
- CI-042 proposed to broaden M7 to all storage mechanisms
- Root cause: implement agent adds persistence + UI without confirming consumer is in-scope

### Wiring gaps (persistent since Wave 14B, but decreasing)
- M7 checklist catches ~80% of wiring issues
- Remaining 20%: "wired but not called" pattern (HD checkpointer, dead-end stores)
- CI-031 + CI-042 together should close this gap

### Test plan non-compliance (persistent -- Waves 19, 20, 21, 22)
- CI-023 (implement agent test plan) has 0% compliance across 4 consecutive waves
- CI-038 (M1b QA enforcement gate) remains DEFERRED
- The implement agent ignores the advisory instruction entirely

## Applied Fix Effectiveness (confirmed)

| Fix | Status | Evidence |
|-----|--------|----------|
| CI-009 (L12 write-path scoping) | EFFECTIVE since W19 | 0 violations in W20, W21, W22 |
| CI-013 (M5b findings currency) | EFFECTIVE since W19 | 0 drift in W20, W21, W22 -- pattern fully reversed |
| CI-015 (findings sync) | EFFECTIVE since W19 | No stale findings at any wave close |
| CI-017 (M8b field optionality) | EFFECTIVE since W19 | No iOS 422 failures in W20, W21, W22 |
| CI-030 (ruff on tests/) | EFFECTIVE since W20 | 0 test-file ruff violations in W21, W22 |
| CI-031 (app.state write-only) | PARTIALLY EFFECTIVE | 0 app.state violations but missed DB dead-end stores |
| CI-033 (pre-QA deliverable) | PARTIALLY EFFECTIVE | No completeness FAILs but doesn't catch test gaps |
| CI-023 (pre-phase test plan) | NOT EFFECTIVE | 0% compliance across 4 waves |

## Gate Effectiveness

| Gate | Catches | Misses |
|------|---------|--------|
| M6 (bare except) | ruff E722/BLE001 violations | `noqa` suppressed blocks without logging |
| M7 (wiring) | Unregistered routers, uninstantiated services, app.state write-only | DB-persisted dead-end stores (CI-042 proposed) |
| M8 (domain isolation) | Direct cross-domain imports | Cross-phase isolation gaps (threads isolated but runs/cost not) |
| S5 (smoke test) | Import failures, basic instantiation | Full user flow breakage |
| M5b (findings currency) | Findings drift | -- (fully effective) |
| M8b (field optionality) | iOS nil-omission Pydantic gaps | TypeScript type lies (CI-043 proposed) |

## Process Notes

- CI agent runs at **wave boundary only** (after retrospective, before next-wave planning)
- Signal input: read `Plan/CI/signals.md` first -- prioritize which reviews to drill into
- P1 proposals = human gate (pause and notify)
- Evidence threshold: P1/P2 require 2+ occurrences within last 3 waves or 1 critical+gate-gap
- Always check backlog for existing proposals before creating duplicates
- Use `low|medium|high` for impact and implementation burden -- never fabricate hour counts
- Memory stores only stable validated patterns -- per-wave counts belong in backlog/signal log

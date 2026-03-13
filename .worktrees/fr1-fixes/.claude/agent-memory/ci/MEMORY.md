# CI Agent Memory

## Backlog State

- `Plan/CI/IMPROVEMENT_BACKLOG.md` has CI-001 through CI-007 (all PROPOSED, none applied)
- CI-006 references deleted `write-code` skill — stale proposal
- Last analysis: `Plan/CI/analysis_2026-03-07_insights.md` (from Insights report)

## Problem Categories Observed (Waves 1-18)

### Wiring gaps (most frequent — ~12 occurrences)
- "Wired in class, not at startup" — QC5, QC8, HD, iOS1 all had this
- Service implemented + tests pass (manual injection) + never instantiated in `app.py`
- M7 checklist catches some but not async registration or fire-and-forget hooks
- **Gate effectiveness:** M7 catches ~80% of wiring issues in QA. The remaining 20% are "wired but not called" (HD checkpointer pattern)

### Missing migrations (~3 occurrences)
- C4 (Wave 14B), TM2 (Wave 18) — ORM model has column, no alembic migration
- Tests pass via `create_all()`, production crashes
- No gate currently catches this

### Half-fixes on security findings (~4 occurrences)
- QC2: C6 fixed backend (httpOnly cookies) but frontend unchanged
- QC5: M3/M6 implemented in class but never wired in startup
- Pattern: fix passes because test covers the mechanism, not the integration

### Stale documentation (~ongoing)
- FINDINGS.md counts drift from table contents
- PLAN.md header gets out of sync
- Agent memory files empty despite design

### Test quality issues
- Source inspection tests (QC2) — pass even if code unreachable
- Constructor/existence tests — test Python, not feature
- Stub-only tests — verify stub matches stub schema
- Over-mocking (3+ mocks) — testing mocks, not code

## Gate Effectiveness

| Gate | Catches | Misses |
|------|---------|--------|
| M6 (bare except) | ruff E722/BLE001 violations | `noqa` suppressed blocks without logging |
| M7 (wiring) | Unregistered routers, uninstantiated services | "Wired but never called" pattern |
| M8 (domain isolation) | Direct cross-domain imports | Shared modules with implicit coupling |
| S5 (smoke test) | Import failures, basic instantiation | Full user flow breakage |

## Insights Report Integration

- Report at `~/.claude/usage-data/report.html`
- Facet data at `~/.claude/usage-data/facets/*.json`
- Top friction categories (2026-03-07): implementation-first bias, wrong output locations, Docker env confusion
- Cross-reference with FINDINGS.md categories when analyzing

## Process Notes

- CI agent runs at **wave boundary only** (after retrospective, before next-wave planning) — NOT after individual QA reviews
- Signal input: read `Plan/CI/signals.md` first — qa-review appends one row per phase; use it to prioritize which reviews to drill into
- P1 proposals = human gate (pause and notify)
- Evidence threshold: P1/P2 require 2+ occurrences **within last 3 waves** or 1 critical+gate-gap (gate must explicitly reference the issue class); P3 requires 1+ plausibly systemic occurrence within last 3 waves
- Always check backlog for existing proposals before creating duplicates; explicitly justify non-duplication per proposal
- Use `low|medium|high` for impact and implementation burden — never fabricate hour counts
- Memory stores only stable validated patterns — per-wave counts belong in backlog/signal log, not memory

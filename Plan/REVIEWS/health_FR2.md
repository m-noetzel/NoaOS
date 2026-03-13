# Project Health Brief — 2026-03-13 (FR2)

**Score: 7/10**
Starting at 5: +0 (Wave 22 phases still in progress — FR2 is mid-wave), +1 (last QA verdict PASS_WITH_NOTES), +0 (35 open findings in FINDINGS.md — BE-H7/H10/H6/H9/H12 not yet marked resolved, M5b violation), +1 (application security posture green — cookie deletion correct, IDOR intact, domain namespace separation), +0 (infrastructure not re-audited — mid-wave), +1 (E2E + integration tests exist: 18 Playwright + 30+ Postgres + real-MemoryStore dispatch tests). Subtract: -1 for infrastructure warn (carried from QE6 — curl wildcard, no lockfile). Score: 5+1+1+1-1=7. Trajectory: flat from FR1 (7/10). Blocking M5b issue is a process step (update FINDINGS.md), not a code defect.

## What Happened (since last brief)

1. **Five high-priority findings addressed in code** (BE-H6, BE-H7, BE-H9, BE-H10, BE-H12): memory facts now persist across restarts (volume mount), approved facts are written to MemoryStore, external domain has its own memory namespace, memory health check is functional, and logout correctly clears both cookies with matching security attributes.
2. **noa.memory shared layer created** (ARCH L1 fix): `noa.external_worker` no longer imports from `noa.private_worker` directly — it uses a new `noa.memory` shared package as the intermediary, matching the ARCH M8 "shared modules" pattern.
3. **FINDINGS.md not yet updated**: The five findings fixed by this phase remain `Open` in FINDINGS.md. This is a blocking M5b violation — a process step the implement agent must complete before the phase can be marked done.

## Greatest Risk

**FINDINGS.md staleness continues to grow.** This is the fourth consecutive phase that has closed findings in code but not updated `Plan/FINDINGS.md`. The file currently shows 35 open items, but after FR1 + FR2, the real open count is at most 28 (FR1 closed 3, FR2 closes 5). When findings are stale, the risk register is misleading: the team believes more is broken than actually is, and new findings can't be accurately tracked. More critically, `test_findings_open_count_consistent` (if it exists) will fail on the next test run once findings are resolved in the system but not in the file. The process gate (CI-015) exists precisely to prevent this drift, but it has been skipped in each recent phase.

## Decisions Needed

- **Update FINDINGS.md now**: Before FR2 is marked complete, update BE-H7, BE-H10, BE-H6, BE-H9, BE-H12 to `**Resolved**` with `Resolved By: FR2`. Update counts from 35 open to 30 open (35 - 5). This is the CI-015 gate — non-negotiable.
- **Register FR-series pytest markers**: Add `fr1`, `fr2` (and subsequent FR phases) to `pyproject.toml` `markers` list to eliminate warnings on every test run. Low-cost one-liner.

## Security Posture — Application

| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | Logout correctly clears both cookies with matching secure/samesite/httponly/path. No regression in JWT enforcement. |
| Secrets | ok | No hardcoded secrets in changed files. All memory writes pass user_id explicitly. |
| Domain isolation | ok | External memory at /data/memory/external, private at /data/memory — separate namespaces on same volume. noa.external_worker has no direct import from noa.private_worker. |
| Input validation | ok | ApprovalDecision uses Literal["approved","denied"] — no free-form strings. Cookie attributes match between set and delete paths. |
| Error handling | ok | _handle_memory_approval catches Exception with logging (exc_info=True). No silent swallowing. Pre-existing except Exception: pass in auth.py:179 (logout path, noqa) unchanged. |

## Security Posture — Infrastructure

N/A — mid-wave. Infrastructure security audit runs at wave boundaries only. Last audit: Wave 21 boundary (QE6, 2026-03-12). Baseline: 107 Claude Code allow rules (scoped), no root containers, no wildcard CORS, warn on curl wildcard Bash rule and loose dependency pins.

## Risks You Are Taking

1. **FINDINGS.md staleness (medium probability, medium impact):** Five resolved findings are still shown as Open. Every phase since FR0 has skipped the CI-015 findings sync gate. If this pattern continues through FR3-FR6, the risk register will be 25+ findings off-base by wave end. The test `test_findings_open_count_consistent` validates the count — it will start failing once finding counts diverge far enough. Fix: enforce CI-015 as a pre-merge check.

2. **Memory health false-positive when tool is registered (low probability, low impact):** `ToolHealthChecker.check("memory")` returns "ok" without inspecting the store when the tool is registered in the gateway. If the `/data` volume is remounted or goes inaccessible after startup, the health endpoint will not detect this. The check only validates the store when the tool is NOT registered (unregistered = likely broken). No data loss occurs (writes fail gracefully), but operators may not notice degraded memory persistence via the health endpoint.

3. **noa.memory transitive coupling (acknowledged, low probability):** `noa.memory` re-exports `MemoryStore` from `noa.private_worker.memory_store`. The external worker transitively depends on private worker code. This is intentional and endorsed by ARCH M8's "shared modules" pattern, but it is not yet documented in `ARCH_INVARIANTS.md`. A future reviewer unfamiliar with this design decision may flag it. Document it in ARCH_INVARIANTS.md as an approved exception.

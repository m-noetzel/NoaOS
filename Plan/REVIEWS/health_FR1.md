# Project Health Brief — 2026-03-13 (FR1, Cycle 2)

**Score: 7/10**
Starting at 5: +0 (Wave 22 phases still in progress — FR1 is mid-wave), +1 (last QA verdict PASS_WITH_NOTES, cycle 2), +0 (new low-severity finding FR1-L1 added; no criticals open), +1 (application security posture fully green — domain isolation enforced end-to-end), +0 (infrastructure security has warn — curl wildcard, no lockfile — mid-wave, not re-audited), +1 (E2E + integration tests: 18 Playwright + 30+ Postgres integration). Subtract: -1 for infrastructure warn (carried from QE6). Score: 5+1+1+1-1=7. Trajectory: up from cycle 1 FAIL (7/10 with that FAIL penalty) to 7/10 PASS_WITH_NOTES. Unchanged numerically but verdict quality improved.

## What Happened (since last brief)

1. **FR1 closed three high-priority audit findings** (BE-C3 Critical, BE-H8 High, BE-H11 High): conversations now carry a `domain` column, all thread endpoints filter by domain with 403 on mismatch, memory tool is hidden in external mode, and only ollama is available as a provider in private mode. 30 real-SQLite integration tests added.
2. **Cycle 1 FAIL resolved**: The CP3 regression (`test_existing_thread_reused`) was fixed by seeding a real `Conversation` row in an in-memory SQLite DB and patching `_get_session_factory` directly. FINDINGS.md count corrected from 38 to 35 open. `test_findings_open_count_consistent` passes.
3. **One new low finding added (FR1-L1)**: `_check_thread_domain` is fail-open on DB session exception. Deliberate trade-off (availability > domain enforcement during DB degradation), but untested and undocumented prior to this review.

## Greatest Risk

**The fail-open behavior in `_check_thread_domain` (chat.py:270-272) is an untested domain isolation gap.** When `factory=None` the check is fail-closed (request blocked). But when the DB session raises an exception mid-execution, the function returns `None` (allow through). This means domain enforcement silently degrades during DB connectivity issues: an authenticated user could cross domain boundaries on existing threads if their DB session drops exactly during the domain check. The risk is low probability (transient DB errors) and the path logs a warning, but it is untested and represents the one place where the domain isolation invariant is not hard-enforced. Tracked as FR1-L1.

## Decisions Needed

- **Wave 22 scope confirmation**: FR1 is the first FR-series phase. The remaining planned FR phases and overall Wave 22 structure need human review and approval before proceeding to the next phase.

## Security Posture — Application

| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | JWT auth enforced on all FR1 endpoints. domain + user_id filtering on all DB queries. |
| Secrets | ok | No hardcoded secrets. All Conversation writes include explicit user_id. |
| Domain isolation | ok | Private/external separation enforced at list, read, delete, chat, and tool-dispatch layers. fail-closed when factory=None. |
| Input validation | ok | `Literal["private", "external"]` on all `privacy_mode` params. Pydantic rejects invalid values at boundary. CHECK constraint in migration. |
| Error handling | warn | `_check_thread_domain` is fail-open on DB exception (FR1-L1). All other exception handlers log before continuing. Pre-existing `except Exception: pass` in auth.py:179 unchanged. |

## Security Posture — Infrastructure

N/A — mid-wave review. Last audited at Wave 19 system audit and QE6 health brief. No changes to Docker, CORS, or permissions in FR1.

| Area | Status | Detail |
|------|--------|--------|
| Claude Code permissions | ok | 107 allow rules, all scoped. No change since QE6. |
| Docker config | ok | No root user, no privileged, no secrets in ENV. No change since QE6. |
| CORS / network exposure | ok | Explicit localhost origins, wildcard rejected. |
| Secrets in repo | ok | .env/.env.secrets gitignored. Only .env.example tracked. |
| Dependency pinning | warn | Loose >= pins with upper bounds. No lockfile. 5th consecutive brief flagging this. |

## Risks You Are Taking

1. **No Python lockfile (high likelihood of silent breakage, moderate impact)**: 25+ loosely-pinned dependencies with no lockfile. A transitive update could silently break the build or introduce a vulnerability. Has been flagged for 5 consecutive health briefs. The ideal time to address this is between waves.

2. **Fail-open domain check in chat (low likelihood, moderate impact)**: If DB throws during `_check_thread_domain`, domain enforcement is bypassed for an existing thread access. Only occurs during DB degradation. Logged but not alerting. Tracked as FR1-L1. Fix: either make consistently fail-closed, or add a unit test documenting the deliberate fail-open choice.

3. **Pre-existing bare `except Exception: pass` in auth.py:179 (very low likelihood, low impact)**: Logout errors silently swallowed. Documented since QC3. User experience issue (failed logout appears successful), not a security escalation risk.

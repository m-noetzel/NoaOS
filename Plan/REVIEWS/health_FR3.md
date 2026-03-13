# Project Health Brief — 2026-03-13 (FR3)

**Score: 7/10**
Starting at 5: +0 (Wave 22 mid-wave — FR1 complete, FR3 complete, FR2/FR4-FR6 still pending), +1 (last QA verdict PASS_WITH_NOTES), +0 (open findings are high — 34 open vs target 0), +1 (application security posture green), +0 (infrastructure not re-audited mid-wave), +1 (E2E + Postgres integration tests exist). Subtract: -1 (infrastructure warn — no lockfile, curl allow rule). Score: 5+1+1+1-1=7. Unchanged from FR1 brief.

## What Happened (since last brief)

1. **FR3 fixed four Wave-21 audit findings**: DELETE /threads no longer returns 500 when runs+usage_stats exist (W21-H1, cascade FK); backup container crash-loop fixed (W21-H2, cap_drop removed + init:true); /docs and /openapi.json now gated behind NOA_ENV=production (W21-M1); traceability.py --check no longer overwrites TRACEABILITY.md (W21-M2). 14 new integration tests.
2. **Wave 22 is 2/7 phases complete** (FR1, FR3). FR2 (memory/session), FR4-FR6 (chat, cost, tools UX) still planned. The infra/integrity fixes from FR3 unblock further phases.
3. **Migration chain gap discovered**: FR3's migration 015 references `down_revision="014"` but migration 014 was added by FR1 after the FR3 worktree was branched. Running `alembic history` in the worktree crashes with `KeyError: '014'`. This will resolve on merge to main (which has 014), but reveals that migration chain integrity is not tested by the test suite.

## Greatest Risk

**34 open findings remain unaddressed in Wave 22.** The bulk of these are UX-layer findings (FR4-FR6 scope) and memory-related findings (FR2 scope). While individual findings are Medium or Low severity, their accumulation means the app has significant known gaps in UI/UX, memory persistence, and cost display. FR3 cleared 4 High findings, but the remaining 34 include BE-H6 (memory lost on API restart — data loss risk), BE-H7 (memory facts not persisted), BE-H10 (private memory broken), and BE-H12 (logout session clearing). These are not caught by tests because memory persistence relies on Docker volume mounts that are absent in the test environment. A user interacting with the production system today would experience memory loss on every container restart and a broken memory system in private mode.

## Decisions Needed

- **FR2 prioritization**: BE-H6 (memory persistence) and BE-H10 (private memory broken) are the highest-impact remaining open findings. Confirm FR2 should be the next phase before FR4.
- **Migration chain test**: Should the project add a `test_migration_chain_intact` test that verifies every migration's `down_revision` points to an existing file? This would have caught the FR3 worktree issue automatically.

## Security Posture — Application

| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | JWT auth enforced. Domain isolation enforced on thread operations (FR1). |
| Secrets | ok | No hardcoded secrets. OpenAPI docs gated in production (FR3 W21-M1). |
| Domain isolation | ok | Private/external separation enforced at list, read, delete, chat, and tool-dispatch layers. |
| Input validation | ok | Pydantic validates at boundaries. CHECK constraint on conversations.domain. |
| Error handling | warn | Fail-open in `_check_thread_domain` on DB exception (FR1-L1, pre-existing). Pre-existing `except Exception: pass` in auth.py:179. |

## Security Posture — Infrastructure

N/A — mid-wave review. Last full audit at Wave 19 system audit and QE6 health brief.

| Area | Status | Detail |
|------|--------|--------|
| Claude Code permissions | ok | 107 allow rules, scoped. No change since QE6. |
| Docker config | ok | backup now has init:true, cap_drop removed (FR3 W21-H2). No root user, no secrets in ENV. |
| CORS / network exposure | ok | Explicit localhost origins, wildcard rejected. |
| Secrets in repo | ok | .env/.env.secrets gitignored. Only .env.example tracked. |
| Dependency pinning | warn | Loose >= pins with no lockfile. 6th consecutive brief flagging this. |

## Risks You Are Taking

1. **Memory data loss in production (moderate probability, high impact)**: BE-H6, BE-H7, BE-H10 (all open, FR2 scope) mean user-approved memory facts are held in-memory in the API container and silently lost on every restart. The backup container backs up Postgres data but not in-memory state. Users interacting with memory features today will experience data loss on restart. No test catches this because it requires the Docker volume mount to be absent.

2. **Migration chain not tested (low probability, high impact)**: The test suite uses `Base.metadata.create_all` rather than alembic migrations. A worktree-local migration chain break (like the FR3/FR1 interaction) will never surface in tests. If two concurrent phases both add migrations with overlapping revision numbers or broken chains, the first sign of failure is `alembic upgrade head` crashing in staging or production.

3. **No Python lockfile (ongoing, high likelihood of silent breakage)**: 25+ loosely-pinned dependencies with no lockfile. 6 consecutive health briefs have flagged this. Until addressed, any CI run could silently pick up a breaking dependency update.

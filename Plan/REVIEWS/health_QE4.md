# Project Health Brief -- 2026-03-12 (QE4)

**Score: 7/10**
Starting at 5: +0 (Wave 21 not complete -- 4/6 phases done), +0 (last QA was PASS_WITH_NOTES, not PASS), +1 (zero critical findings open -- 0 open of 112 total), +0 (application security unchanged from QE3), +0 (infrastructure N/A mid-wave), +1 (E2E exists: 18 Playwright + 30 new Postgres integration tests). Result: 5 + 1 + 1 = 7. Trajectory: flat from QE3 (7/10).

## What Happened (since last brief)
1. Real Postgres integration tests now exist: 30 tests across 6 suites (auth, threads, settings, approvals, memory, tools) all running against Postgres via Alembic migrations. This is the biggest S5 improvement in the project's history -- previously every DB test used SQLite.
2. Two schema drift bugs caught and fixed (GO1 google_refresh_token, TM5 custom_tools). Alembic migrations 010 and 011 created. This validates the integration test thesis: `create_all()` hides drift that real migrations expose.
3. CI pipeline now has a dedicated `test-integration` job running in parallel with unit tests, using its own Postgres service container.

## Greatest Risk
**No Python lockfile.** Same risk as QE3 brief. `pyproject.toml` uses `>=` pins with upper bounds but no `requirements.lock`. The new `testcontainers[postgres]>=4.8,<5.0` dependency adds another loosely-pinned package. A transitive dependency update could break the build, the mypy gate, or introduce security vulnerabilities. This risk compounds with each new dependency.

## Decisions Needed
- None blocked on human input. QE5-QE6 can proceed without gates.

## Security Posture -- Application
| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | Integration tests now verify full auth lifecycle against real Postgres. |
| Secrets | ok | Test secret keys clearly labeled, `noqa: S105` annotated. No real credentials. |
| Domain isolation | ok | No cross-domain imports (verified by grep). |
| Input validation | ok | No API surface changes. |
| Error handling | ok | No production code changes. |

## Security Posture -- Infrastructure
| Area | Status | Detail |
|------|--------|--------|
| Claude Code permissions | N/A -- mid-wave | N/A -- mid-wave |
| Docker config | N/A -- mid-wave | N/A -- mid-wave |
| CORS / network exposure | N/A -- mid-wave | N/A -- mid-wave |
| Secrets in repo | N/A -- mid-wave | N/A -- mid-wave |
| Dependency pinning | N/A -- mid-wave | N/A -- mid-wave |

## Risks You Are Taking
1. **No Python lockfile**: Loose `>=` pins risk non-reproducible builds. Now 1 more loosely-pinned dependency (testcontainers). Likelihood: medium over next month. Impact: CI breakage or security regression.
2. **Integration tests require Docker**: testcontainers needs Docker-in-Docker or a pre-provisioned Postgres. CI handles this via GitHub Actions services. Local runs need either Docker or `TEST_DATABASE_URL` pointing to an existing Postgres. Developers without Docker access cannot run integration tests locally.
3. **Session-scoped test data accumulation**: All 30 integration tests share one Postgres instance. Data accumulates across tests. Currently fine at 30 tests, but could cause unique constraint issues at scale if email patterns collide across test files.

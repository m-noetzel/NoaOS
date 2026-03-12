# Project Health Brief -- 2026-03-12 (QE6)

**Score: 8/10**
Starting at 5: +1 (all Wave 21 phases QE1-QE6 complete), +0 (last QA was PASS_WITH_NOTES, not PASS), +1 (zero critical findings open), +1 (application security posture fully green), +0 (infrastructure has warn -- curl wildcard in allow list, no lockfile), +1 (E2E + integration tests exist: 18 Playwright + 30 Postgres integration). Result: 5 + 1 + 1 + 1 + 1 = 9, minus 1 for infrastructure warn = 8. Trajectory: up from QE5 (7/10) due to wave completion.

## What Happened (since last brief)
1. Wave 21 is complete. All 6 pipeline excellence phases (QE1-QE6) delivered: CI backlog triage, mypy zero, findings closure, Postgres integration tests, requirements traceability, and test quality infrastructure.
2. Coverage baseline established at 84% (threshold: 70%). Mutation testing configured for auth/router/gateway critical paths. Nightly flaky test detection added to CI.
3. Wave 21 is the first full wave where every phase passed QA on the first cycle (no FAILs, no cycle-2 reviews needed).

## Greatest Risk
**No Python lockfile.** This is the fourth consecutive health brief flagging this risk. The project has 25+ loosely-pinned dependencies (`>=` with upper bounds but no lockfile). Each wave adds more. A transitive dependency update could break the build, mypy gate, or introduce vulnerabilities. The new `mutmut>=2.4,<3.0`, `pytest-repeat>=0.9,<1.0`, and `pytest-cov>=6.0,<7.0` additions in QE6 widen the surface. With Wave 21 complete and no further feature work imminent, this is the ideal time to generate a `requirements.lock` or adopt `uv lock`.

## Decisions Needed
- Wave 21 is complete. Wave boundary gates must run: system-auditor, retrospective, CI agent. Human approval needed before Wave 22 planning begins.
- Should a lockfile be added before Wave 22, or continue accepting the risk?

## Security Posture -- Application
| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | No auth changes in QE6. JWT, httpOnly cookies, step-up auth all intact. |
| Secrets | ok | No secrets introduced. CI uses test-only `SECRET_KEY`. |
| Domain isolation | ok | No cross-domain imports. grep confirms clean boundaries. |
| Input validation | ok | No API surface changes. |
| Error handling | ok | No production code changes. ruff clean. |

## Security Posture -- Infrastructure
| Area | Status | Detail |
|------|--------|--------|
| Claude Code permissions | warn | ~102 allow rules (up from 107 baseline -- slightly tighter). `Bash(curl:*)` in allow conflicts with `Bash(curl)` in deny. `Bash(sed:*)` allows arbitrary file editing. `Bash(python:*)` and `Bash(python3:*)` allow arbitrary script execution despite `python -c` being denied. |
| Docker config | ok | No root user, no privileged, no secrets in ENV. All containers have cap_drop ALL, no-new-privileges, resource limits (DE3). |
| CORS / network exposure | ok | Explicit localhost origins from env var (`CORS_ALLOWED_ORIGINS`). No `0.0.0.0` bindings in src/. Caddy reverse proxy configured (DE2). |
| Secrets in repo | ok | Only `.env.example` tracked. `.env` and `.env.secrets` gitignored. `_DEV_SECRET` in config.py has `# noqa: S105` comment -- not used in production. |
| Dependency pinning | warn | All deps use `>=X,<Y` ranges (good upper bounds) but no lockfile exists. 25+ direct deps, unknown transitive count. No non-PyPI sources. No `trusted-host` directives. |

## Risks You Are Taking
1. **No Python lockfile** (repeated, highest impact): A transitive dependency update breaking the build or introducing a vulnerability is the most likely single failure mode. Likelihood increases with each new dependency. Impact: broken CI, silent security regression, or flaky builds.
2. **Mutation testing is manual-only**: mutmut is configured but no CI step runs it. Mutation regressions in auth/router/gateway will not be caught automatically. Likelihood of regression: low per wave but compounds. Impact: tests that look green but miss critical behavioral changes.
3. **`Bash(curl:*)` in Claude Code allow list**: This bypasses the `Bash(curl)` deny rule via the wildcard suffix pattern. An agent could use `curl:` prefix to make network requests. Practical risk is low (agents are trusted) but violates principle of least privilege. Should be removed from the allow list.

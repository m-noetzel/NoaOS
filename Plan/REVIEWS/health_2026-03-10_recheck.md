# Project Health Brief -- 2026-03-10 (System Final Recheck, Cycle 2)

**Score: 7/10**
Starting at 5: +1 (all planned phases complete across 17 waves), +1 (last QA verdict is PASS_WITH_NOTES), +1 (zero critical findings in FINDINGS.md), +0 (application security all green), -1 (infrastructure has warn: no lockfile), +1 (E2E exists: 18 Playwright + 13 Swift integration tests), -1 (no clean PASS -- still PASS_WITH_NOTES due to tech debt items). Result: 7/10. Up from 5/10 (cycle 1) and 4/10 (system-final).

## What Happened (since last brief)
1. All 6 system-final blocking issues now resolved: AuthUser type crash (B1), approval IDOR (B2), empty JWT signing key (B3), APNs push pipeline (B4), list_runs stub (B5), ruff violations (B6). Zero blocking issues remain.
2. Bonus fix: `decide_approval` flush-without-commit bug resolved -- approval decisions now persist to the database. This was the greatest risk flagged in the cycle 1 health brief.
3. `ruff check src/` passes clean with 0 errors. The merge gate is unblocked.

## Greatest Risk
**No dependency lockfile.** `pyproject.toml` uses `>=` with upper bounds but no `requirements.lock` or equivalent. A `pip install` today may produce different package versions than tomorrow. This is the only remaining infrastructure-level concern. All application-level security issues (auth, IDOR, secrets, error handling) are resolved. Likelihood: moderate over months. Impact: non-reproducible builds, potential supply chain vulnerability.

## Decisions Needed
- **Generate a dependency lockfile** (`pip freeze > requirements.lock` or adopt `uv lock`). This is the last infrastructure gap.
- **Optionally: clean up the 19 endpoints** still annotating auth as `dict[str, Any]` with hasattr fallback. These work correctly but are misleading -- the dict branch is dead code.

## Security Posture -- Application
| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | AuthUser type used correctly in all endpoints. JWT rejects empty secret_key. |
| Secrets | ok | No `or ""` fallbacks on secret_key. Keychain injection. .env gitignored. |
| Domain isolation | ok | No cross-domain imports. Docker networks correctly separated. |
| Input validation | ok | Approval IDOR fixed (403). Approval decisions now committed. Queue/memory user isolation missing (single-user acceptable). |
| Error handling | ok | `ruff check src/` passes clean. All BLE001 blocks have logging or re-raise. |

## Security Posture -- Infrastructure
| Area | Status | Detail |
|------|--------|--------|
| Claude Code permissions | ok | 119 allow rules, all scoped. Deny blocks curl, wget, ssh, rm -rf, python -c. |
| Docker config | ok | No root user, no privileged mode, no secrets in ENV. read_only, cap_drop:ALL. |
| CORS / network exposure | ok | Explicit localhost origins. Wildcard rejected. No 0.0.0.0 bindings. |
| Secrets in repo | ok | .env/.env.secrets gitignored. Only .env.example tracked. Keychain injection. |
| Dependency pinning | warn | >= with upper bounds but no lockfile. Non-reproducible builds. |

## Risks You Are Taking

1. **No dependency lockfile means builds are non-reproducible.** A `pip install` today may install different versions than tomorrow. Likelihood: moderate over months. Impact: build failures or supply chain attacks. Fix: 15 minutes.

2. **Fire-and-forget push tasks have no graceful shutdown.** `asyncio.ensure_future()` tasks are untracked. App shutdown closes the HTTP client before in-flight tasks may complete. Likelihood: low (push is best-effort). Impact: occasional silent push delivery failures during deploys.

3. **19 endpoints have stale type annotations** (`dict[str, Any]` for auth parameter that is actually `AuthUser`). The hasattr fallback prevents crashes but the dict branch is dead code. Likelihood of bug: zero (dead code). Impact: developer confusion. Fix: mechanical, 20 minutes.

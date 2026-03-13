# Project Health Brief -- 2026-03-10 (System Final)

**Score: 4/10**
Starting at 5: +1 (all planned phases complete across 17 waves), -1 (last QA verdict is FAIL), +1 (zero critical findings in FINDINGS.md), -1 (application security has warn/bad: approval IDOR, AuthUser crash, secret_key fallback), -1 (infrastructure has warn: no lockfile, loose dep pins), +1 (E2E exists: 18 Playwright + 13 Swift integration tests), -1 (3 endpoints crash at runtime, constituting a critical finding discovered in this review). Result: 4/10.

## What Happened (since last brief)
1. Wave 17 (MV1-MV5) eliminated all API stubs -- threads, messages, approvals, memory, queue, and artifacts now use real DB queries. 1310+ tests.
2. Security improvement: disk-based .env.secrets replaced with RAM-only Keychain injection (commit 2e7bbf1), closing a secret hygiene gap.
3. System-wide production readiness review uncovered 6 blocking issues: 3 runtime crashes from AuthUser type mismatch, 1 approval authorization bypass, 1 completely non-functional push notification pipeline, and 6 ruff lint violations.

## Greatest Risk
**The AuthUser type migration was incomplete.** When `require_auth` was changed from returning `dict[str, Any]` to returning an `AuthUser` dataclass (M11 fix in QC3), three endpoints (`voice.py`, `devices.py` register and delete) were not updated. They still access the return value as `payload["sub"]`, which crashes with `TypeError` on every request. This is the canonical "big refactor with orphaned callers" pattern. The fix is trivial (5 minutes), but the fact that it was not caught earlier -- across 10+ QA reviews and 50+ phase completions -- suggests that the per-phase review scope is too narrow. A system-wide smoke test that calls every endpoint with a real AuthUser would have caught this months ago.

## Decisions Needed
- **Fix the 6 blocking issues before any deployment.** Items B1-B3 and B6 are 15-minute fixes. B5 (list_runs stub) is 10 minutes. B4 (push pipeline) requires 30+ minutes and a design decision on HTTP/2 client initialization.
- **Decide whether to add a system-wide endpoint smoke test** that exercises every endpoint with a real (mocked) request, verifying no TypeError/AttributeError on the dependency injection contract. This would prevent B1-class issues permanently.
- **Decide whether to address the multi-user isolation gaps** in queue.py (no user_id column) and memory.py (global MemoryStore) before production, or document them as single-user-only limitations.

## Security Posture -- Application
| Area | Status | Detail |
|------|--------|--------|
| Auth | warn | 3 endpoints crash on AuthUser type mismatch (voice, devices). Auth flow itself is correct. |
| Secrets | warn | `secret_key or ""` in AuthService.login/refresh creates tokens with empty key. Middleware catches on verify. |
| Domain isolation | ok | No cross-domain imports. Docker networks correctly separated. Private network is internal=true. |
| Input validation | warn | Approval decide has no ownership check (IDOR). Queue/memory have no user isolation. |
| Error handling | warn | 6 ruff violations (3 BLE001, 2 F401, 1 E501). retention.py has 4 unsuppressed except blocks (with logging). |

## Security Posture -- Infrastructure
| Area | Status | Detail |
|------|--------|--------|
| Claude Code permissions | ok | 119 allow rules, all scoped. Deny blocks curl, wget, ssh, rm -rf, python -c. No dangerous wildcards except `Bash(docker:*)` and `Bash(git:*)`. |
| Docker config | ok | No root user, no privileged mode, no secrets in ENV/COPY. read_only:true, cap_drop:ALL, no-new-privileges on all containers. |
| CORS / network exposure | ok | Explicit localhost origins (5173, 5174, 4173, 8000). Wildcard rejected. API bound to 127.0.0.1:8000. No 0.0.0.0 bindings. |
| Secrets in repo | ok | .env and .env.secrets in .gitignore. Only .env.example tracked. Keychain injection for secrets (2e7bbf1). |
| Dependency pinning | warn | `pyproject.toml` uses `>=` with upper bounds but no lockfile. No `requirements.lock` or `pip freeze` artifact. Reproducible builds not guaranteed. |

## Risks You Are Taking

1. **Three endpoints crash on every request (voice transcribe, device token register/unregister).** These are iOS-facing endpoints. Any iOS user who tries voice recording or push token registration will get a 500 error. Likelihood: certain on any iOS client use. Impact: feature completely broken. Fix time: 5 minutes.

2. **Any authenticated user can approve or deny any other user's pending approvals.** The decide_approval endpoint has no ownership check. In a single-user deployment this is moot, but the moment a second user exists, the entire governance model (risk tiers, biometric step-up auth) is bypassable. Likelihood: low in single-user, certain in multi-user. Impact: governance bypass. Fix time: 2 minutes.

3. **No dependency lockfile means builds are non-reproducible.** A `pip install` today may install different package versions than tomorrow. A malicious or buggy dependency update could break or compromise the system without any code change. Likelihood: moderate over months. Impact: unpredictable -- from broken builds to supply chain attacks. Fix time: 15 minutes (generate lockfile).

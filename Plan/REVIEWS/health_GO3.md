# Project Health Brief -- 2026-03-12 (GO3 / Wave 20 Complete)

**Score: 7/10**
Starting at 5: +1 (all Wave 20 phases complete), +0 (last QA was PASS_WITH_NOTES, not PASS), +1 (zero critical findings open), +0 (application security has a warn -- see _DEV_SECRET in dev mode), +0 (infrastructure has warn -- 33 accumulated wildcard bash permissions), +1 (E2E exists: 18 Playwright + integration tests). Result: 5 + 1 + 1 + 1 = 8. Adjustment: -1 for infrastructure warn (33 wildcard permissions accumulated). Final: 7/10.

## What Happened (since last brief)
1. Wave 20 complete: iOS Google OAuth2 flow implemented via ASWebAuthenticationSession with `noaapp://` callback scheme, biometric gate, and full protocol-injected testability. 16 new Swift tests.
2. Full OAuth2 stack now spans backend (GO1), web (GO2), and iOS (GO3) -- all three clients can connect/disconnect Google accounts. Total: 28 + 15 + 16 = 59 OAuth-related tests.
3. Swift test count reached 216 (204 XCTest + 12 swift-testing), up from ~203 reported in PLAN.md. Backend Python tests: 1640+.

## Greatest Risk
**The entire OAuth2 flow has never been tested against real Google APIs.** Three layers (backend token exchange, web callback redirect, iOS ASWebAuthenticationSession) have been built against mocks exclusively. The first deployment with real Google Cloud Console credentials will be the true integration test. A single misconfigured redirect URI, missing scope, or Fernet key issue will silently break all Google tool integrations. This risk compounds because Calendar and Gmail tools depend on these tokens being correctly persisted and refreshable.

## Decisions Needed
- **Register Google OAuth2 credentials in Google Cloud Console** -- the redirect URI must match the production/dev domain before any real testing can happen.
- **Wave 21 planning approval** -- wave boundary reached. System auditor, retrospective, and CI agent must run before Wave 21 begins.

## Security Posture -- Application
| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | Google OAuth requires JWT auth; CSRF state verified on callback; biometric gate on iOS connect |
| Secrets | ok | No hardcoded production secrets. `_DEV_SECRET` rejected in production mode. Google tokens in encrypted Postgres only. |
| Domain isolation | ok | No cross-domain imports. iOS stores no Google tokens locally (verified by T-GO3-15). |
| Input validation | ok | Backend validates CSRF state, authorization code presence, and OAuth error responses |
| Error handling | ok | No bare except blocks. WebAuthError.cancelled silently ignored (documented). SettingsViewModel surfaces errors to UI. |

## Security Posture -- Infrastructure
| Area | Status | Detail |
|------|--------|--------|
| Claude Code permissions | warn | 114 Bash allow rules, 33 wildcard patterns (`:*`), including `curl:*`. `ssh`, `wget`, `rm -rf` correctly denied. No `Bash(*` overly broad wildcards. The 33 accumulated one-offs should be audited. |
| Docker config | ok | No `USER root`, no `privileged`, no `docker.sock` mount. `privileged: false` commented as default in compose. Workers EXPOSE 8001/8002, API EXPOSE 8000. No secrets in Dockerfiles. |
| CORS / network exposure | ok | Wildcard `*` explicitly rejected. Origins restricted to localhost dev ports + NOA_DOMAIN. No `0.0.0.0` bindings in source or compose. |
| Secrets in repo | ok | `.env.secrets` in `.gitignore`. Only `.env.example` tracked (no real secrets). Fernet key, JWT secret, Google creds all via env vars. |
| Dependency pinning | warn | 26 version constraints in pyproject.toml but using `>=` (loose pins). No `==` pinning. No non-PyPI sources or `trusted-host`. Risk of silent dependency drift on rebuild. |

## Risks You Are Taking
1. **Untested real OAuth2 flow (high impact, high likelihood):** All three clients were built against mocks. The first real Google token exchange will surface any redirect URI, scope, or encryption mismatches. Mitigation: manual smoke test before users depend on Google tools.
2. **Loose dependency pinning (medium impact, low likelihood):** All Python dependencies use `>=` constraints. A breaking upstream release could fail a Docker rebuild silently. Mitigation: pin critical deps (cryptography, fastapi, sqlalchemy) with `~=` or `==` in Wave 21.
3. **33 accumulated Claude Code bash wildcards (low impact, present):** One-off approval patterns have accumulated over 20 waves. While dangerous patterns (ssh, wget, rm -rf) are denied, the broad `curl:*` allow and 33 wildcards reduce the sandbox's value. Mitigation: audit and prune in Wave 21 (QE1 CI backlog triage).

# Project Health Brief -- 2026-03-12 (GO2)

**Score: 6/10**
Starting at 5: +0 (Wave 20 not yet complete: GO3 remains), +0 (last QA PASS_WITH_NOTES, not PASS), +1 (zero critical findings open), -0 (application security green), +0 (infrastructure N/A mid-wave), +1 (E2E exists: 18 Playwright + integration tests), -1 (>25% of Wave 20 phases still pending: 1 of 7, but GO3 is the only one left -- actually 1/7 = 14%, so no deduction). Revised: 5 + 1 + 1 = 7. But Wave 20 is not complete (+0), and last QA was PASS_WITH_NOTES (+0). Result: 7, clamped to 7/10.

## What Happened (since last brief)
1. Google OAuth2 web UI complete: Settings page now shows connection status with connect/disconnect buttons, plus a dedicated callback landing page with auto-redirect.
2. Wave 20 is 6/7 phases done -- only GO3 (iOS OAuth) remains before wave boundary activities.
3. 15 frontend tests added for the Google integration flow, bringing the project closer to full OAuth coverage across all clients.

## Greatest Risk
**The entire OAuth2 flow (GO1 backend + GO2 web + GO3 iOS) has been built against mocked responses.** No test has performed a real Google token exchange. The first deployment with real Google Cloud Console credentials will be the true integration test. The risk compounds because three layers (backend redirect, frontend callback, token persistence) must all work correctly in sequence. A single misconfiguration (wrong redirect URI, missing scope, Fernet key rotation) silently breaks the entire Google integration.

## Decisions Needed
- **Register Google OAuth2 credentials in Google Cloud Console** before GO3 can be meaningfully tested. The redirect URI must match the production domain.
- **Consider a manual smoke test of the full OAuth flow** before starting Wave 21. The cumulative untested surface (DE1-DE4 + GO1-GO2) is growing.

## Security Posture -- Application
| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | Google OAuth callback route intentionally unprotected (no API calls); Settings page is behind AuthGuard |
| Secrets | ok | No localStorage, no hardcoded secrets. API client uses httpOnly cookies via credentials:include |
| Domain isolation | ok | Frontend-only phase, no cross-domain imports |
| Input validation | ok | Error param rendered as React text (auto-escaped). Redirect target hardcoded to /settings |
| Error handling | ok | All error paths show descriptive toasts; no silent swallowing |

## Security Posture -- Infrastructure
N/A -- mid-wave (GO2 is phase 6 of 7 in Wave 20). Full audit at wave boundary.

## Risks You Are Taking
1. **No real OAuth2 flow tested (high likelihood of first-deploy surprise, medium impact).** Three layers of OAuth code built against mocks. First real attempt will reveal configuration issues that unit tests cannot catch.
2. **10 open findings in FINDINGS.md (low-medium impact).** None are critical, but they represent deferred work that accumulates complexity. Wave 21 QE3 plans to close them all.
3. **No lockfile for Python dependencies (low likelihood, medium impact).** Loose `>=` pins in pyproject.toml mean a dependency update could break the build at any time. This has been flagged since Wave 19 but remains unaddressed.

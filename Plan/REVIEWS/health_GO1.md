# Project Health Brief -- 2026-03-12 (GO1)

**Score: 6/10**
Starting at 5: +0 (Wave 20 not yet complete: GO2+GO3 remain), +0 (last QA PASS_WITH_NOTES, not PASS), +1 (zero critical findings open), -0 (application security green), +0 (infrastructure N/A mid-wave), +1 (E2E exists: 18 Playwright + integration tests), -1 (>25% of Wave 20 phases still pending: 2 of 7). Result: 6, clamped to 6/10. Holding steady from DE4.

## What Happened (since last brief)
1. Google OAuth2 backend flow complete: 4 new endpoints (authorize, callback, status, disconnect) with CSRF state protection and Fernet-encrypted token persistence.
2. Registration startup now loads Google tokens from DB first, falling back to env var -- tokens survive container restarts without manual env var management.
3. Token rotation verified: callback overwrites existing DB row with new encrypted tokens when Google issues a new refresh token.

## Greatest Risk
**The deployment stack (DE1-DE4) plus this OAuth2 flow have never been tested against real infrastructure.** Google OAuth2 requires a real HTTPS redirect URI registered in Google Cloud Console, but the implementation defaults to `http://localhost:8000/api/v1/auth/google/callback`. The `_load_google_tokens_at_startup` async task may never execute in the real startup sequence because it relies on an event loop that may not be running during `register_tools()`. This means the first real deployment will be the actual integration test for both the deployment stack and the OAuth flow.

## Decisions Needed
- **Register Google OAuth2 credentials in Google Cloud Console** before GO2/GO3 can be tested. The redirect URI must match the production domain configured in `NOA_DOMAIN`.
- **Schedule a real `docker compose up` test?** Now 5 phases (DE1-DE4 + GO1) with zero runtime validation. The risk compounds with each new feature.

## Security Posture -- Application
| Area | Status | Detail |
|------|--------|--------|
| Auth | ok | All 3 user-facing Google OAuth endpoints require JWT; callback protected by CSRF state |
| Secrets | ok | Tokens Fernet-encrypted in DB; GOOGLE_CLIENT_SECRET read from env, not hardcoded; empty-string fallback raises 503 |
| Domain isolation | ok | No cross-domain imports; OAuth code in api.v1 + tools layer |
| Input validation | ok | State parameter verified, error/code params checked, user_id scoped queries |
| Error handling | ok | Specific exception types (GoogleAuthError, ValueError, HTTPException); pre-existing BLE001 handlers all log |

## Security Posture -- Infrastructure
N/A -- mid-wave (GO1 is phase 5 of 7 in Wave 20). Full audit at wave boundary.

## Risks You Are Taking
1. **No runtime validation of OAuth2 flow (high likelihood, high impact).** The entire authorize-callback-persist cycle has only been tested with mocked httpx responses. A real Google token exchange could fail due to redirect URI mismatch, missing scopes, or clock skew. First real user attempt is the integration test.
2. **`_oauth_states` memory leak (low likelihood, low impact).** Abandoned authorize flows leave state tokens in an unbounded in-memory dict. Negligible for single-user, but would matter at scale.
3. **`_get_live_google_client` is fragile (medium likelihood, low impact).** Traverses 4 levels of private attributes to find the auth client. Any refactoring of adapters/tools silently breaks live token updates after OAuth callback.

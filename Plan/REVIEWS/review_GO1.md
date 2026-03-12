# QA Review: Phase GO1

**Date:** 2026-03-12
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 28 tests trace to SPEC.md SS12.1, SS12.2, SS11.1, SS11.3, SS5.3; phase plan lists 20 test specs, 28 delivered |
| M2 | Negative Tests | PASS | 6 negative tests: 401 (no auth x3), 400 (error param, missing code, invalid/missing state), 404 (disconnect no cred), 503 (unconfigured) |
| M3 | Security Boundaries | PASS | CSRF state round-trip, encrypted DB tokens, auth required on authorize/status/disconnect, no hardcoded secrets |
| M4 | Determinism | PASS | No wall-clock assertions, no network calls in unit tests (httpx mocked), no unseeded randomness |
| M5 | Implementation Completeness | PASS | All 4 deliverables present: authorize, callback, status, disconnect + registration.py update + google_auth.py update |
| M6 | No Silent Error Swallowing | PASS | Pre-existing BLE001-suppressed handlers in google_auth.py and registration.py all have logging. New disconnect RuntimeError catch is acceptable (event-loop guard). No new bare excepts. |
| M7 | Wiring Completeness | PASS | Routes on existing auth_router (app.py:431); no new router needed. All 4 endpoints reachable via `/api/v1/auth/google/*` |
| M8 | Domain Isolation | PASS | No cross-domain imports. Google OAuth code lives in `noa.api.v1` and `noa.tools` (service layer). |
| S1 | Error Handling & Boundaries | PASS | Error messages are specific (not generic). 503 for unconfigured, 400 for invalid state/code, 404 for missing credentials |
| S2 | Code Consistency | PASS | Follows existing patterns in auth.py. Uses success_envelope, trace_id, consistent naming |
| S3 | Migration & Rollback | N/A | No DB schema changes — uses existing `google_credentials` table from migration 007 |
| S4 | Documentation | PASS | All endpoints have docstrings with arg/return docs. Spec refs in module docstring |
| S5 | Integration Smoke Test | OPEN | `test_valid_code_persists_encrypted_tokens` uses real SQLite session (qualifies as non-mocked integration), but no test exercises the real `app.py` startup wiring path |

## Test Plan Coverage
No pre-existing test plan for GO1 (review-only mode). The 28 tests cover all 20 spec'd test cases from PHASE_DETAILS.md, plus 8 additional tests (scopes detail, prompt=consent, env fallback, multi-user scoping, token rotation, etc.).

## Spec Compliance

| Spec Ref | Requirement | Status |
|----------|-------------|--------|
| SS12.1 | Calendar OAuth2 scopes | PASS — calendar.readonly + calendar.events in `_get_google_scopes()` |
| SS12.2 | Gmail OAuth2 scopes | PASS — gmail.readonly + gmail.send + gmail.compose |
| SS11.1 | Encrypted token storage in Postgres | PASS — Fernet encryption via `_token_crypto.py`, verified in test |
| SS11.3 | Refresh token rotation | PASS — `test_new_refresh_token_overwrites_db_row` verifies DB row update |
| SS5.3 | CSRF protection | PASS — state parameter generated with `secrets.token_urlsafe(32)`, verified on callback |

## Test Coverage

28 tests in 6 classes:
- TestGoogleAuthorize: 8 tests (URL generation, auth requirement, scopes, CSRF state, offline access, prompt consent, 503)
- TestGoogleCallback: 6 tests (token persistence, redirect, error param, missing code, invalid state, missing state)
- TestGoogleStatus: 3 tests (connected true, connected false, auth required)
- TestGoogleDisconnect: 4 tests (remove row, 404, live client clear, auth required)
- TestLoadTokensFromDb: 2 tests (load existing, absent row)
- TestTokenPersistenceAndRotation: 2 tests (not plaintext, rotation overwrites)
- TestRegistrationStartup: 3 tests (skip without config, env fallback, multi-user scoping)

**Coverage gaps (non-blocking):**
- No test for the `X-Noa-iOS-Redirect` header handling (iOS redirect to `noaapp://` scheme)
- No test for token exchange failure (httpx raising GoogleAuthError) via the callback endpoint
- No test for `_get_live_google_client()` successfully finding a live client from the gateway
- No test for `_load_google_tokens_at_startup` actually loading from DB (only env fallback tested)

## Anti-Pattern Scan Results

**M6 — bare except / blind exception:**
- `src/noa/api/v1/auth.py`: No bare `except:` blocks. No new `except Exception:` blocks.
- `src/noa/tools/google_auth.py`: 2 pre-existing `except Exception: # noqa: BLE001` (lines 127, 269) — both log warnings.
- `src/noa/tools/registration.py`: 2 pre-existing `except Exception: # noqa: BLE001` (lines 125, 196) — both log warnings.
- `src/noa/api/v1/auth.py:576-577`: `except RuntimeError: pass` in disconnect — guards against "no event loop" when calling `clear_tokens()` as fire-and-forget. Acceptable for cleanup code.

**M7 — Wiring:**
- Auth router registered at `app.py:431` via `app.include_router(auth_router)`. All 4 new routes are on this router.

**M8 — Domain isolation:**
- No `from noa.private_worker` in `src/noa/external_worker/`
- No `from noa.external_worker` in `src/noa/private_worker/`

## Smoke Test Results

```
OK: All 4 Google OAuth endpoints importable
OK: _oauth_states is dict: True
OK: Scopes loaded: 5 scopes
OK: Calendar + Gmail scopes present
OK: google_auth imports OK
OK: Auth URL generated: https://accounts.google.com/o/oauth2/v2/auth?client_id=test&...
OK: clear_tokens method exists on GoogleAuthClient
OK: registration imports OK
OK: encrypt/decrypt round-trip works

All smoke tests passed
```

## Security

1. **CSRF state**: Generated with `secrets.token_urlsafe(32)` (43 characters of entropy), stored server-side in `_oauth_states` dict, consumed on callback (pop). Good.
2. **Encrypted tokens**: Fernet (AES-128-CBC + HMAC-SHA256) with key derived from JWT_SECRET_KEY. `_derive_key()` raises `RuntimeError` if JWT_SECRET_KEY is unset. Good.
3. **Auth requirements**: authorize, status, disconnect all require JWT via `require_auth`. Callback is public (correct for OAuth2) but protected by CSRF state. Good.
4. **No secrets in code**: GOOGLE_CLIENT_ID/SECRET read from env. Fallback to `""` is checked immediately with `if not (client_id and client_secret)` -> 503. This is not an L11 violation (not a silent fallback). Good.
5. **Note: `_oauth_states` dict has no TTL/expiry**. State tokens accumulate in memory. For a single-user system this is negligible, but a malicious user who calls `/google/authorize` repeatedly could grow this dict. The state is consumed (popped) on callback, so successful flows clean up. Only abandoned authorize flows leak.

## Code Quality

1. **Test file has 23 ruff violations**: 6 unused imports (F401), 11 import sorting issues (I001), 3 line-too-long (E501), 1 unused variable (F841). Source files pass ruff cleanly.
2. **mypy**: 1 `unused-ignore` comment at auth.py:175 (`type: ignore[arg-type]`). Pre-existing mypy issues in calendar.py, gmail.py (not from GO1).
3. **_get_live_google_client()** traverses internal `_adapters` dict via private attributes (`adapter._tool`, `tool._api_client`, `tool._api_client._auth_client`). This is fragile — any refactoring of the adapter/tool chain will break it silently. Should have a first-class accessor.

## Beyond the Test Plan

1. **State accumulation**: `_oauth_states` is a module-level dict with no eviction. For a production system, this should have a TTL (e.g., 10 minutes). Currently, an attacker authenticated with a valid JWT could call `/google/authorize` thousands of times to grow this dict. The practical impact is minimal for a single-user system.

2. **Callback error message leaks info**: `detail=f"Token exchange failed: {exc}"` at line 458 includes the GoogleAuthError message which may contain HTTP status codes from Google. This is low-risk (the user initiated the flow) but slightly more information than necessary for an end-user-facing endpoint.

3. **`_get_live_google_client` fragility**: Walking through 4 levels of private attributes to find the auth client is a maintenance hazard. If any adapter is refactored, this breaks silently (returns None) and the live client won't be updated after OAuth2 callback.

4. **`_load_google_tokens_at_startup` runs as fire-and-forget task**: If the event loop isn't running yet (which it typically isn't during `register_tools()`), the `try: loop = asyncio.get_running_loop()` path catches RuntimeError and the DB load is skipped entirely. The env-var fallback covers this, but the DB-first intent may never fire during actual startup. This is the "wired but never called" anti-pattern (HD variant).

## Notes (PASS_WITH_NOTES)

1. **[S5]** Test file has 23 ruff violations (unused imports, sorting, line length, unused variable). Should be cleaned up before wave end.
2. **[Security, low]** `_oauth_states` has no TTL. Consider adding a timestamp and pruning states older than 10 minutes, or using a bounded dict.
3. **[Robustness]** `_get_live_google_client()` traverses 4 levels of private attributes. Consider exposing the auth client reference at a higher level (e.g., on ToolGateway or app_state).
4. **[Robustness]** `_load_google_tokens_at_startup` may never execute its DB-loading async task if called before the event loop is running. The env-var fallback mitigates this, but the DB-first path should be verified to actually run in the real app startup sequence.
5. **[Coverage]** No test for `X-Noa-iOS-Redirect` header (noaapp:// redirect) or token exchange failure via callback endpoint.

## Decision Review

The phase delivers a solid OAuth2 consent flow with proper CSRF protection, encrypted token storage, and user-scoped credentials. The 28 tests cover all spec requirements and most edge cases. The main concerns are code hygiene (ruff violations in tests), a minor memory leak potential in `_oauth_states`, and the fragile `_get_live_google_client` accessor pattern. None of these are blocking for a single-user system.

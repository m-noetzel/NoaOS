# QA Review: Phase QC2

**Date:** 2026-03-07
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent
**Re-review:** Yes — initial FAIL verdict required fixes to C6 (localStorage) and CORS wildcard bypass

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 3/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | Module docstring cites FINDINGS.md C3/C6/H6/H7/H10/M2/M4. Every finding has a test class. |
| M2 | Negative Tests | PASS | 4 negative tests for H6; 2 for H7; 4 for H10; 1 for CORS wildcard; 1 for empty recipient. All verify specific exception types. |
| M3 | Security Boundaries | PASS | C6 fully resolved: tokens removed from JSON body, localStorage no longer stores token values. CORS wildcard stripped before passing to middleware. httpOnly + Secure + SameSite=Strict cookies set correctly. |
| M4 | Determinism | PASS | No wall-clock time in tests. No network calls. 31/31 pass consistently. |
| M5 | Implementation Completeness | PASS | All 7 findings addressed. All modified files present. No TODO/FIXME deferral. |
| M6 | No Silent Error Swallowing | PASS | No new bare except introduced. Pre-existing `except Exception: pass` handlers in startup/logout paths carry `# noqa: BLE001, S110` with rationale comments. |
| M7 | Wiring Completeness | PASS | All routers registered. CSPMiddleware registered. `auth_router` includes `logout` with cookie deletion. |
| M8 | Domain Isolation | PASS | No new cross-domain imports introduced by QC2. Pre-existing violations (C2) tracked for QC4. |
| S1 | Error Handling & Boundaries | PASS | Email validation handles empty, malformed, comma injection, newline injection, tab injection (all verified by shell). Refresh with empty cookie falls back to empty body token which AuthService correctly rejects as 401. |
| S2 | Code Consistency | PASS | Naming follows conventions. No duplicate abstractions. |
| S3 | Migration & Rollback | N/A | No schema changes in QC2. |
| S4 | Documentation | PASS | Type annotations present. Inline comments cite finding IDs (C6). |
| S5 | Integration Smoke Test | OPEN | C6 tests use `inspect.getsource()` rather than live HTTP calls. No test fires a real login request and verifies the cookie appears in the Set-Cookie response header and token is absent from JSON body. Known limitation of no-DB unit test environment. |

---

## What Changed in the Re-review

### Fix 1: C6 — Tokens Removed from localStorage and JSON Body

**Backend (`src/noa/api/v1/auth.py`):**
- `login` and `refresh` now build `safe_result` by filtering out `access_token` and `refresh_token` keys before passing to `success_envelope`. JSON body returns only `{"authenticated": true}` plus non-sensitive fields.
- `logout` now calls `response.delete_cookie("noa_access_token", ...)` and `response.delete_cookie("noa_refresh_token", ...)` to clear cookies server-side.
- `refresh` reads `request.cookies.get("noa_refresh_token")` with fallback to `body.refresh_token` (body will be `""` from updated frontend; cookie path is the primary one).

**Frontend (`web/src/auth/tokens.ts`):**
- Rewrote to store only `noa_authenticated = "true"` flag in localStorage. `getAccessToken()` and `getRefreshToken()` both return `null`. `setTokens()` ignores both arguments.
- Verified by shell: `ACCESS_TOKEN_KEY` and `REFRESH_TOKEN_KEY` constants are gone. Only `localStorage.setItem(AUTH_FLAG_KEY, "true")` remains. Token values never written to localStorage.

**Frontend (`web/src/auth/AuthContext.tsx`):**
- Login callback uses `apiRequest<{ authenticated: boolean }>` and calls `setTokens("", "")`. No longer reads `res.data.access_token` or `res.data.refresh_token`.

**Frontend (`web/src/api/client.ts`):**
- `refreshAccessToken` sends `{ refresh_token: "", device_id: WEB_DEVICE_ID }` — empty string is intentional; real token comes from httpOnly cookie via `credentials: "include"`.
- `getAccessToken()` always returns `null`, so the `if (token)` branch in `makeRequest` is never entered and no `Authorization: Bearer` header is added. All auth flows through the httpOnly cookie.

### Fix 2: CORS Wildcard Rejection

**`src/noa/api/app.py:256-259`:**
```python
allowed_origins = [
    o.strip() for o in allowed_origins_raw
    if o.strip() and o.strip() != "*"
]
```
Verified by shell:
- `CORS_ALLOWED_ORIGINS=*` → `allow_origins=[]` → fail-closed (all cross-origin blocked)
- `CORS_ALLOWED_ORIGINS=*,http://localhost:5173` → `allow_origins=['http://localhost:5173']` → wildcard stripped, valid origin preserved

---

## Spec Compliance

| Finding | Status | Verification method |
|---------|--------|---------------------|
| C3 — audit hash chain locking | PASS | Source inspection confirming `with_for_update()` in both sync and async paths |
| C6 — httpOnly cookie tokens | PASS | Backend sets httpOnly+Secure+SameSite=Strict; JSON body excludes raw tokens (shell-verified); `tokens.ts` stores only auth flag (shell-verified); frontend never reads token from body |
| H6 — email recipient validation | PASS | `_validate_email_recipient()` in both `send_email` and `draft_email`; rejects empty, malformed, comma-injected, newline-injected, tab-injected, percent-encoded, unicode-lookalike (all shell-verified) |
| H7 — capability default deny | PASS | `has_capability()` returns `False` for tools absent from `TOOL_CAPABILITIES` |
| H10 — nh3 HTML sanitization | PASS | `nh3.clean()` with explicit allowlist; advanced XSS vectors (SVG, CSS expression, null byte, nested tags) all handled correctly by shell probes |
| M2 — CORS tightening | PASS | `allow_methods` and `allow_headers` explicit lists; `allow_origins` strips wildcard; unknown origin preflight returns 400 (shell-verified) |
| M4 — CSP headers | PASS | `CSPMiddleware` delivers header on live HTTP response via TestClient (shell-verified) |

---

## Test Coverage

| Test class | Finding | Count | Quality |
|------------|---------|-------|---------|
| `TestAuditHashChainLocking` | C3 | 2 | Source inspection — acceptable as sole option without DB |
| `TestCookieAuth` | C6 | 6 | Source inspection tests; functional correctness confirmed by shell probes |
| `TestEmailValidation` | H6 | 6 | Strong — calls real code, asserts mock not called on rejection |
| `TestToolCapabilityDefaultDeny` | H7 | 2 | Adequate — mocked session, tests the decision logic |
| `TestNotionSanitization` | H10 | 6 | Strong behavioral tests with real nh3 calls |
| `TestCORSRestrictions` | M2 | 3 | Wildcard test uses `patch.dict(os.environ)` — solid approach |
| `TestCSPHeaders` | M4 | 1 | Source inspection — weak, but CSP delivery verified live by shell |
| `TestQC2Imports` | All | 5 | Import smoke tests only |

---

## Anti-Pattern Scan Results

```
# M6: Bare except blocks in QC2-modified files
$ grep -rn "except:" [all QC2 files]
No bare except found

# M6: Blind Exception catches
src/noa/api/app.py:55:    except Exception:  # noqa: BLE001     [pre-existing, startup degradation]
src/noa/api/app.py:112:   except Exception:  # noqa: BLE001     [pre-existing, startup degradation]
src/noa/api/app.py:124:   except Exception:  # noqa: BLE001     [pre-existing, startup degradation]
src/noa/api/app.py:151:   except Exception:  # noqa: BLE001, S110  [pre-existing, DB startup optional]
src/noa/api/app.py:217:   except Exception:  # noqa: BLE001     [pre-existing, RetentionScheduler]
src/noa/api/v1/auth.py:179: except Exception:  # noqa: BLE001, S110  [pre-existing, best-effort logout]
All pre-existing, suppressed with noqa and rationale. None new in QC2.

# M7: Router registration
$ grep -rn "include_router" src/noa/api/app.py
15 routers registered. auth_router included. CSPMiddleware registered. PASS.

# M8: Domain isolation
$ grep -rn "from noa.private_worker" src/noa/external_worker/
src/noa/external_worker/llm/router.py:114  [pre-existing, tracked as C2]
$ grep -rn "from noa.external_worker" src/noa/private_worker/
src/noa/private_worker/ollama_client.py:13  [pre-existing, tracked as C2]
Not introduced by QC2.

# Ruff: All QC2-modified backend files
$ ruff check src/noa/api/v1/auth.py src/noa/api/app.py
All checks passed!
```

---

## Smoke Test Results

```
# Module imports
AuditService: OK
GmailTool: OK
DbCapabilityChecker: OK
NotionTool: OK
create_app: OK

# Test suite
$ python3 -m pytest tests/unit/test_qc2_security_hardening.py -v --override-ini="pythonpath=src"
31 passed in 0.31s

# CORS wildcard stripping (live)
CORS_ALLOWED_ORIGINS=* → allow_origins=[] (fail-closed, no wildcard)
CORS_ALLOWED_ORIGINS=*,http://localhost:5173 → allow_origins=['http://localhost:5173'] (valid origin preserved)
PASS.

# Login response body (simulated safe_result)
safe_result keys: ['token_type', 'authenticated']
access_token absent: True
refresh_token absent: True
PASS.

# tokens.ts localStorage inspection
ACCESS_TOKEN_KEY absent: True
REFRESH_TOKEN_KEY absent: True
noa_authenticated present: True
localStorage.setItem calls: ["localStorage.setItem(AUTH_FLAG_KEY, 'true')"]
Token values stored: False
PASS.

# CSP header on live response
GET /health → Content-Security-Policy: default-src 'self'; script-src 'self'; ...
Header present: True
PASS.
```

---

## Security

Both previously blocking issues are resolved.

**C6:** The dual-path vulnerability is closed. Tokens do not appear in the JSON body. `localStorage` stores only a boolean flag. `getAccessToken()` returns `null` making the `Authorization: Bearer` code path permanently inert. The refresh endpoint prefers the httpOnly cookie. Logout clears cookies server-side.

**CORS wildcard:** `CORS_ALLOWED_ORIGINS=*` is filtered before reaching `CORSMiddleware`. Behavior is fail-closed — an all-wildcard config produces an empty origins list and blocks all cross-origin requests. A mixed config (`*,https://app.example.com`) correctly preserves the valid origins.

**Non-blocking — CORS wildcard stripping is silent:** When `*` entries are stripped, no warning is logged. An operator setting `CORS_ALLOWED_ORIGINS=*` in production would experience silently broken cross-origin requests with no log entry to diagnose it. Recommend adding a `logger.warning` at `app.py:256`.

---

## Notes

1. **CORS wildcard stripping should log a warning** (`src/noa/api/app.py:256`). When `*` entries are stripped, emit `logger.warning("CORS: wildcard origin stripped — check CORS_ALLOWED_ORIGINS config. Remaining origins: %s", allowed_origins)`. Prevents silent misconfiguration in production.

2. **Dead code in `client.ts`** (lines 1, 75-83): `AuthTokens` type import, `getAccessToken()` call, and `Authorization: Bearer` header block are now permanently unreachable since `getAccessToken()` returns `null`. Remove in a cleanup pass to prevent future confusion or regression.

3. **`setTokens("", "")` is semantically odd** (`AuthContext.tsx:38`): calling a two-argument function with empty strings to produce a single side effect. Consider renaming to `markAuthenticated()` for clarity. Minor style concern.

4. **S5 open — no live cookie verification test:** All C6 tests use `inspect.getsource()`. No test fires an actual HTTP request to `/api/v1/auth/login` and asserts that the response `Set-Cookie` header contains `noa_access_token; HttpOnly; Secure` and that the response body does not contain `access_token`. This is a known gap for the no-DB unit test environment; Playwright tests (Wave 16) should close it.

---

## Decision Review

No QC2-specific DECISION_LOG entries found. The decision to leave `Authorization: Bearer` dead code in `client.ts` rather than removing it is implicit. Should be cleaned up in QC6/QC7 frontend pass.

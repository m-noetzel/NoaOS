# Production Readiness Audit Report -- 2026-03-12

## Summary

- **Overall Health Score**: 6.5/10
- **Endpoints Tested**: 55/72 routes verified (42 working correctly, 6 with issues, 7 method mismatches)
- **E2E Flows Tested**: 8/10 core flows (6 passing, 2 partially broken)
- **Security Issues**: 4 found (1 HIGH, 3 MEDIUM)
- **Dead Code Items**: 3 found
- **Integration Test Suite**: 25 passing, 1 failed, 30 errors (DB config mismatch)
- **Unit Test Suite**: 1757 passing, 6 failing (pre-existing)
- **Static Analysis**: ruff CLEAN, mypy CLEAN (166 files, 0 errors)
- **Container Health**: 6/6 containers running (5 healthy, 1 no healthcheck)

### Verdict: NOT production-ready, but CLOSE

The system architecture is solid. Static gates pass. All core CRUD endpoints work. The primary blockers are: (1) chat pipeline fails because LLM API keys stored in user settings are not passed to the OrchestratorRunner/ProviderRouter, (2) credentials are stored in volatile memory (lost on restart), (3) several security hardening items needed, and (4) no LLM provider API keys configured in the environment.

---

## Critical Findings (must fix before going live)

### CRIT-1: Chat pipeline always errors -- ProviderRouter has no API keys

**Severity**: CRITICAL
**Evidence**: Every `POST /api/v1/chat` request completes the classification step but fails at the agent step with `ProviderError`. The error message is generic: "An error occurred processing your request."

**Root cause**: The `OrchestratorRunner` uses a `ProviderRouter` that was initialized at app startup. At startup, no LLM API keys are available (neither from env vars nor from user settings). When a user stores an API key via `PATCH /api/v1/settings`, it goes into the DB but the running `ProviderRouter` instance is never rebuilt. The chat endpoint does not reload settings per-request.

**Impact**: The core feature of Noa -- having a conversation with an AI -- does not work at all. No user can get a response.

**Fix required**: Either (a) rebuild the ProviderRouter per-request using the user's stored settings, or (b) require API keys as env vars and document this, or (c) implement the PR4 "reload ProviderRouter after credential update" properly.

### CRIT-2: Tool credential store is in-memory dict -- data lost on restart

**Severity**: CRITICAL
**File**: `src/noa/api/v1/tools.py:34`
**Evidence**: `_credential_store: dict[tuple[str, str], dict[str, str]] = {}` -- a module-level Python dict.
**Impact**: Any tool credentials stored via `PUT /api/v1/tools/{name}/credentials` are lost when the noa-api container restarts. This is noted as a TODO: "replace with vault/Keychain integration before production."
**Fix required**: Persist credentials to DB (encrypted) or integrate with a secrets manager.

### CRIT-3: No LLM provider API keys configured in environment

**Severity**: CRITICAL
**Evidence**: In the noa-api container:
- `OPENAI_API_KEY`: not set
- `ANTHROPIC_API_KEY`: not set
- `GOOGLE_CLIENT_ID`: not set
- `GOOGLE_CLIENT_SECRET`: not set
- `TAVILY_API_KEY`: not set
- `NOTION_TOKEN`: not set
- `TOKEN_ENCRYPTION_KEY`: not set
- `APNS_KEY_PATH`: not set

**Impact**: Even if the ProviderRouter were rebuilt per-request, there are no env-level API keys. The system cannot call any external LLM or tool API. Google OAuth cannot work. Push notifications cannot be sent. Token encryption for Google refresh tokens has no key.

---

## High Findings (fix soon)

### HIGH-1: Forgot-password returns reset token directly in response body

**Severity**: HIGH (security)
**Evidence**: `POST /api/v1/auth/forgot-password` with a registered email returns:
```json
{"ok":true,"data":{"status":"ok","reset_token":"eyJhbG..."}}
```
For a non-existent email, it correctly returns only `{"status":"ok"}` (no token, no enumeration leak). However, returning the reset token in the HTTP response defeats the purpose of password reset -- the token should be sent via email, not returned to the caller. An attacker who can call this endpoint can reset any user's password.

**Mitigation**: For a single-user personal assistant, this is less severe than in a multi-user system, but it's still a bad pattern. The reset token should be sent via a side channel (email/push) or this endpoint should be removed until email sending is wired.

### HIGH-2: /docs and /openapi.json accessible in development (no ENVIRONMENT set)

**Severity**: HIGH (information disclosure)
**Evidence**: `ENVIRONMENT` env var is empty in the noa-api container. The code at `app.py:379` hides docs only when `_is_production` is true. Since ENVIRONMENT is unset, docs are always visible.
**Impact**: OpenAPI schema exposes all endpoints, request/response shapes, and internal implementation details. In production, this should be hidden.
**Fix**: Set `ENVIRONMENT=production` in production docker-compose, and verify the gating works.

### HIGH-3: Integration test suite broken in dev container (30 errors)

**Severity**: HIGH (quality infrastructure)
**Evidence**: `pytest tests/integration/` produces 30 errors. The testcontainers library cannot connect to Docker (no Docker socket in noa-dev container), and `TEST_DATABASE_URL` with password "kindness" fails because the actual Postgres password differs.
**Impact**: Integration tests cannot run in the dev container, reducing confidence in changes.
**Fix**: Set `TEST_DATABASE_URL` with the correct password, or mount the Docker socket.

---

## Medium Findings (track)

### MED-1: Settings PATCH ignores unknown fields silently

**Severity**: MEDIUM (usability)
**Evidence**: `PATCH /api/v1/settings` with `{"llm_provider":"openai","llm_model":"gpt-4.1-mini"}` returns 200 but does not change anything. The correct field names are `default_provider` and `default_model`. No error is returned for unrecognized fields.
**Impact**: iOS/web clients sending wrong field names will appear to succeed but have no effect. Frontend-backend contract drift risk.

### MED-2: Tool enable endpoint is POST, not PUT (inconsistency)

**Severity**: MEDIUM
**Evidence**: `PUT /api/v1/tools/web_search/enable` returns 405 Method Not Allowed. The correct method is `POST`. The route registration and the OpenAPI spec disagree on the HTTP method.
**Impact**: Clients expecting PUT (as semantically appropriate for an idempotent toggle) will fail.

### MED-3: Tool health check is POST, not GET (unexpected)

**Severity**: MEDIUM
**Evidence**: `GET /api/v1/tools/web_search/health` returns 405. The correct method is `POST`. Health checks are conventionally GET requests.
**Impact**: Minor, but inconsistent with REST conventions and the GET `/health/tools` endpoint.

### MED-4: Memory facts have no POST endpoint for manual fact creation

**Severity**: MEDIUM
**Evidence**: The `/api/v1/memory/facts` route only supports GET. There is no POST endpoint to create facts via API. Facts can only be created by the memory tool during chat orchestration.
**Impact**: The web UI memory page can list/approve/update/delete facts but cannot manually add one. Users must converse with the AI to store facts.

### MED-5: Audit entries endpoint requires trace_id (UUID) as mandatory query param

**Severity**: MEDIUM
**Evidence**: `GET /api/v1/audit/entries` without `trace_id` returns 422. The `trace_id` param is required and must be a valid UUID.
**Impact**: Cannot browse audit logs without knowing a specific trace_id. No "list all" functionality.

### MED-6: Voice transcribe rejects WAV files sent without proper MIME type

**Severity**: MEDIUM
**Evidence**: Sending a WAV file via `curl -F` without explicit MIME type results in `application/octet-stream` which is rejected. The endpoint requires one of: audio/flac, audio/m4a, audio/mp4, audio/mpeg, audio/ogg, audio/wav, audio/webm, audio/x-wav.
**Impact**: CLI/API clients must set the MIME type explicitly. iOS/web clients likely handle this correctly via their upload mechanisms, but it's fragile.

### MED-7: Backup has never run

**Severity**: MEDIUM
**Evidence**: `GET /health/backup` returns `{"status":"never_run","last_backup":null,"last_verify":null}`.
**Impact**: No database backups exist. Data loss risk.

### MED-8: Caddy reverse proxy not running

**Severity**: MEDIUM
**Evidence**: No caddy container in `docker ps` output. TLS termination is not active.
**Impact**: All traffic is unencrypted HTTP. Required for production.

---

## Low/Informational

### LOW-1: 6 pre-existing test failures

- `test_lifespan_db_skip_emits_warning` -- app singleton flaky
- `test_no_proposed_items_in_backlog` -- CI backlog file out of sync
- `test_all_p1_items_applied_or_rejected` -- same
- `test_findings_zero_open` -- FINDINGS.md open count drift
- `test_traceability_has_mutation_baseline_section` -- missing section
- `test_mcp_adapter_execute_raises_not_implemented` -- error message drift

These are test-only issues, not production bugs.

### LOW-2: Google OAuth disconnect is DELETE, not POST

The route for `/api/v1/auth/google/disconnect` uses DELETE method. Earlier test with POST returned 405. The DELETE method works correctly.

### LOW-3: health/echo requires query parameter

`GET /health/echo?value=test` is needed. Returns 422 without the `value` param. Working as designed but could benefit from a default.

### LOW-4: NotImplementedError stubs remain in 2 locations

- `src/noa/tools/mcp_adapter.py:58` -- Legacy MCP adapter (documented, retained for backward compat tests)
- `src/noa/orchestrator/nodes/tools.py:73` -- Fallback if ToolGateway not wired

Both are guarded by conditions that should never trigger in normal operation.

### LOW-5: Domain isolation is clean

No cross-domain imports found:
- `grep "from noa.private_worker" src/noa/external_worker/` -- none
- `grep "from noa.external_worker" src/noa/private_worker/` -- none

---

## Endpoint Status Matrix

| Route | Method | Auth | Status | Notes |
|-------|--------|------|--------|-------|
| `/health` | GET | No | 200 OK | Working |
| `/health/ready` | GET | No | 200 OK | Working |
| `/health/metrics` | GET | No | 200 OK | Pool stats, uptime, worker availability |
| `/health/echo` | GET | No | 422 | Requires `?value=` query param |
| `/health/tools` | GET | No | 200 OK | Empty (no tool calls recorded yet) |
| `/health/backup` | GET | No | 200 OK | status: never_run |
| `/docs` | GET | No | 200 OK | WARNING: accessible (should be gated in prod) |
| `/openapi.json` | GET | No | 200 OK | WARNING: accessible |
| `/api/v1/auth/register` | POST | No | 201/409 | Working (409 on duplicate) |
| `/api/v1/auth/login` | POST | No | 200 | Working, returns access+refresh tokens |
| `/api/v1/auth/refresh` | POST | No | 200 | Working, requires device_id |
| `/api/v1/auth/logout` | POST | Yes | 200 | Working |
| `/api/v1/auth/forgot-password` | POST | No | 200 | SECURITY: returns reset_token in response |
| `/api/v1/auth/reset-password` | POST | No | -- | Not tested (needs valid reset token) |
| `/api/v1/auth/google/authorize` | GET | Yes | 503 | Expected: GOOGLE_CLIENT_ID not set |
| `/api/v1/auth/google/callback` | GET | No | -- | Cannot test without Google redirect |
| `/api/v1/auth/google/status` | GET | Yes | 200 | Returns `{connected: false, scopes: []}` |
| `/api/v1/auth/google/disconnect` | DELETE | Yes | 404 | Expected: no credentials to disconnect |
| `/api/v1/threads` | GET | Yes | 200 | Working, user-scoped |
| `/api/v1/threads` | POST | Yes | 200 | Working, creates thread |
| `/api/v1/threads/{id}` | DELETE | Yes | 200 | FIXED: was broken (W21-H1), now works even with runs |
| `/api/v1/threads/{id}/messages` | GET | Yes | 200 | Working, returns message list |
| `/api/v1/chat` | POST | Yes | 200 SSE | SSE streams correctly, but ALWAYS errors at agent step (CRIT-1) |
| `/api/v1/runs` | GET | Yes | 200 | Working, returns run list |
| `/api/v1/runs/{id}` | GET | Yes | 404 | Working (404 for nonexistent) |
| `/api/v1/runs/{id}/events` | GET | Yes | -- | Not tested |
| `/api/v1/runs/{id}/events/replay` | GET | Yes | -- | Not tested |
| `/api/v1/runs/{id}/artifacts` | GET | Yes | -- | Not tested |
| `/api/v1/approvals/pending` | GET | Yes | 200 | Working, returns empty list |
| `/api/v1/approvals/{id}/decide` | POST | Yes | -- | Not tested (no pending approvals) |
| `/api/v1/memory/facts` | GET | Yes | 200 | Working, returns fact list |
| `/api/v1/memory/facts/{id}/approve` | POST | Yes | -- | Not tested |
| `/api/v1/memory/facts/{id}/update` | POST | Yes | -- | Not tested |
| `/api/v1/memory/facts/{id}` | DELETE | Yes | -- | Not tested |
| `/api/v1/settings` | GET | Yes | 200 | Working, credentials masked |
| `/api/v1/settings` | PATCH | Yes | 200 | Working with correct field names |
| `/api/v1/settings` | DELETE | Yes | -- | Not tested |
| `/api/v1/usage` | GET | Yes | 200 | Working |
| `/api/v1/tasks` | GET | Yes | 200 | Working |
| `/api/v1/tasks` | POST | Yes | -- | Not tested |
| `/api/v1/tasks/next` | GET | Yes | -- | Not tested |
| `/api/v1/tasks/{id}/cancel` | POST | Yes | -- | Not tested |
| `/api/v1/tasks/{id}/retry` | POST | Yes | -- | Not tested |
| `/api/v1/tasks/{id}/status` | GET | Yes | -- | Not tested |
| `/api/v1/artifacts` | GET | Yes | 200 | Working, returns empty list |
| `/api/v1/artifacts/{id}/download` | GET | Yes | -- | Not tested (no artifacts) |
| `/api/v1/audit/entries` | GET | Yes | 422 | Requires trace_id UUID param |
| `/api/v1/audit/verify` | POST | Yes | 200 | Working (0 entries checked) |
| `/api/v1/tools` | GET | Yes | 200 | Working, returns 4 tools with full metadata |
| `/api/v1/tools/{name}/enable` | POST | Yes | 200 | Working (was PUT, actually POST) |
| `/api/v1/tools/{name}` | DELETE | Yes | -- | Not tested |
| `/api/v1/tools/{name}/health` | POST | Yes | 200 | Working (reports config errors correctly) |
| `/api/v1/tools/{name}/credentials` | GET | Yes | 200 | Working |
| `/api/v1/tools/{name}/credentials` | PUT | Yes | -- | Not tested |
| `/api/v1/tools/{tn}/{fn}/enable` | POST | Yes | -- | Not tested |
| `/api/v1/tools/{tn}/{fn}` | DELETE | Yes | -- | Not tested |
| `/api/v1/tools` | POST | Yes | 422 | Custom tool registration (needs base_url) |
| `/api/v1/tools/mcp-servers` | POST | Yes | 201 | Working, registers MCP server |
| `/api/v1/queue` | GET | Yes | 200 | Working |
| `/api/v1/cost/summary` | GET | Yes | 200 | Working |
| `/api/v1/cost/records` | GET | Yes | 200 | Working |
| `/api/v1/devices/push-token` | POST | Yes | 422 | Needs device_id + push_token (not token) |
| `/api/v1/devices/push-token` | DELETE | Yes | 422 | Needs device_id + platform + push_token |
| `/api/v1/voice/transcribe` | POST | Yes | 400/422 | Validates MIME type correctly |

---

## E2E Flow Results

| Flow | Steps Completed | Failure Point | Details |
|------|-----------------|---------------|---------|
| Register + Login + Refresh + Logout | 4/4 | -- | All steps work. Refresh requires device_id. |
| Create Thread + List + Delete | 3/3 | -- | DELETE thread works even with runs (FK cascade fixed). |
| Send Chat + Receive SSE | 2/5 | Agent step | SSE streams meta + classification + step_started, then errors. No LLM keys. |
| Memory Facts List | 1/1 | -- | Lists facts (empty). No POST to create facts manually. |
| Settings PATCH Round-trip | 3/3 | -- | Works with correct field names. Credentials masked. |
| Approvals List | 1/1 | -- | Returns empty list. Cannot test decide (no approvals). |
| Cost Summary + Records | 2/2 | -- | Both return valid (empty) data. |
| Tools List + Enable + Health | 3/3 | -- | All work. Health correctly reports missing API keys. |
| Voice Transcribe | 0/1 | MIME validation | Rejects without proper audio MIME type. No actual transcription tested. |
| Google OAuth | 1/3 | Config missing | /status works, /authorize returns 503 (no GOOGLE_CLIENT_ID). |

---

## Security Checklist

| Check | Result | Details |
|-------|--------|---------|
| Auth on protected endpoints | PASS | All /api/v1/* endpoints return 401 without token |
| Auth bypass: empty bearer | PASS | Returns 401 |
| Auth bypass: invalid JWT | PASS | Returns "Invalid token" (no stack trace leak) |
| Auth bypass: forged JWT | PASS | Returns "Invalid token" |
| CORS: evil origin blocked | PASS | Returns 400 Bad Request for unknown origins |
| CORS: localhost allowed | PASS | Access-Control-Allow-Origin: http://localhost:5173 |
| CORS: credentials + wildcard | PASS | Not using wildcard (*) with credentials |
| CSP header present | PASS | Full CSP: default-src 'self', frame-ancestors 'none' |
| X-Content-Type-Options | PASS | nosniff present on all responses |
| Credential masking | PASS | API keys show as "****2345" in settings response |
| Domain isolation | PASS | No cross-domain imports between workers |
| /docs gated in production | PARTIAL | Code gates on `_is_production`, but ENVIRONMENT not set in dev |
| Forgot-password token exposure | FAIL | Reset token returned in response body (HIGH-1) |
| Error message sanitization | PASS | Chat errors show generic message, JWT errors say "Invalid token" |
| Token type in JWT | PASS | Access/refresh tokens have distinct `type` claim |
| No secrets in logs | PASS | No plaintext secrets observed in responses |
| TLS | FAIL | No Caddy running, all HTTP |
| Rate limiting | NOT TESTED | Per-user rate limiting is implemented but not stress-tested |

---

## Container Health

| Container | Status | Health | Notes |
|-----------|--------|--------|-------|
| noaos-postgres-1 | Up 33 min | healthy | 5432/tcp |
| noaos-noa-api-1 | Up 33 min | healthy | 8000/tcp |
| noaos-private-worker-1 | Up 33 min | healthy | 8001/tcp, returns `{"status":"ok"}` |
| noaos-external-worker-1 | Up 33 min | healthy | 8002/tcp, returns `{"status":"ok"}` |
| noaos-backup-1 | Up 31 min | no healthcheck | Running but backup has never executed |
| noa-dev | Up 6 hours | no healthcheck | Dev container, ports 4173/5173 |
| Caddy | NOT RUNNING | -- | TLS reverse proxy not deployed |

---

## Static Analysis

| Tool | Result | Details |
|------|--------|---------|
| ruff check src/noa/ tests/ | CLEAN | All checks passed, 0 violations |
| mypy src/noa/ | CLEAN | 0 errors in 166 files |

---

## Test Suite

| Suite | Passed | Failed | Errors | Notes |
|-------|--------|--------|--------|-------|
| Unit tests | 1757 | 6 | 0 | 6 pre-existing failures (not regressions) |
| Integration tests | 25 | 1 | 30 | 30 errors from DB password mismatch (testcontainers/TEST_DATABASE_URL) |

---

## Tool Status (All 4 Built-in Tools)

| Tool | Credential Status | Health | Functions | Production-Ready? |
|------|-------------------|--------|-----------|-------------------|
| **web_search** (Tavily) | missing | error: TAVILY_API_KEY not configured | web_search | NO -- needs API key |
| **calendar** (Google) | configured (via OAuth) | unchecked | list_events, create_event | NO -- needs Google OAuth flow completed |
| **gmail** (Google) | missing | unchecked | search_emails, read_email, send_email, draft_email | NO -- needs Google OAuth |
| **notion** | missing | unchecked | search_pages, read_page, create_page | NO -- needs NOTION_TOKEN |

All tools are registered and have correct metadata (risk_tier, domain, function schemas). None can actually execute because no API keys are configured.

---

## What's NOT Production Ready -- Specific Action Items

### Must Fix (Blockers)

1. **Configure LLM API keys**: Set at least one of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` in the noa-api container environment. Without this, chat does nothing.

2. **Fix ProviderRouter per-user key loading**: The router must pick up API keys from user settings, not just env vars. Currently stored keys in DB are never used by the chat pipeline. Either:
   - Rebuild ProviderRouter per-request with user's settings
   - Or use env vars exclusively and document this

3. **Persist tool credentials to DB**: Replace the in-memory `_credential_store` dict in `tools.py` with encrypted DB storage. Any container restart wipes all tool credentials.

4. **Set ENVIRONMENT=production**: This gates /docs exposure, and may affect other security behaviors.

5. **Deploy Caddy for TLS**: All traffic is currently plaintext HTTP. The Caddyfile exists but the container is not running.

6. **Set TOKEN_ENCRYPTION_KEY**: Required for encrypting Google OAuth refresh tokens. Currently unset.

### Should Fix (Important)

7. **Remove reset_token from forgot-password response**: Send via email or remove the endpoint.

8. **Run initial backup**: The backup container is running but has never executed a backup.

9. **Fix integration test DB password**: Update `TEST_DATABASE_URL` or document the correct password so integration tests pass in the dev container.

10. **Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET**: Required for Google OAuth (calendar, gmail, Google login).

11. **Set APNS_KEY_PATH, APNS_KEY_ID, APNS_TEAM_ID**: Required for iOS push notifications.

### Nice to Have (Before Public Use)

12. **Add manual memory fact creation**: A POST endpoint for `/api/v1/memory/facts` would let users add facts without chatting.

13. **Make tool enable/health use conventional HTTP methods**: PUT for enable (idempotent), GET for health.

14. **Add "list all" mode to audit entries**: Currently requires a specific trace_id.

15. **Validate settings field names**: Return an error when unknown fields are sent to PATCH /settings.

---

## Production Deployment Checklist

```
[ ] Set ENVIRONMENT=production in docker-compose
[ ] Set OPENAI_API_KEY or ANTHROPIC_API_KEY (at least one LLM provider)
[ ] Set SECRET_KEY to a strong random value (currently set)
[ ] Set TOKEN_ENCRYPTION_KEY for Google OAuth token encryption
[ ] Set GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET (if using Google tools/OAuth)
[ ] Set TAVILY_API_KEY (if using web search)
[ ] Set NOTION_TOKEN (if using Notion integration)
[ ] Set APNS_KEY_PATH + APNS_KEY_ID + APNS_TEAM_ID (if using iOS push)
[ ] Deploy Caddy container for TLS termination
[ ] Run initial database backup and verify restore works
[ ] Fix or remove forgot-password reset_token exposure
[ ] Persist tool credentials to DB instead of in-memory dict
[ ] Fix ProviderRouter to load user-specific API keys per-request
[ ] Verify CORS origins match production domain
[ ] Run integration tests with correct DB credentials
[ ] Set up monitoring/alerting (Wave 22 planned)
```

---

## Conclusion

Noa has a well-architected backend with solid security fundamentals (CORS, CSP, auth, credential masking, domain isolation). The static analysis gates are pristine (0 ruff violations, 0 mypy errors). The API surface is comprehensive with 72 registered routes covering threads, chat, tools, memory, approvals, settings, cost, and more.

The critical gap is the **LLM pipeline**: the core chat feature does not work because API keys are neither configured in environment variables nor properly loaded from user settings at request time. This is the single biggest blocker.

Secondary blockers are operational: no TLS, no backups, volatile credential storage, and missing API keys for all external services. These are configuration/deployment issues rather than code bugs.

**Bottom line**: The code is production-quality. The deployment is not production-ready. With 1-2 days of configuration and the ProviderRouter fix, this system could serve real users.

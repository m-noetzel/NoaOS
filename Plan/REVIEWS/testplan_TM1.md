# Test Plan: Phase TM1

**Date:** 2026-03-11
**Planner:** qa-review agent (test-plan mode)
**Spec Sections:** SPEC.md 11.1 (Secret Categories), 11.2 (Provisioning Rules), 12.1-12.4 (MVP Tool Definitions)

## Summary

TM1 adds three new capabilities to the tools subsystem: (1) credential status checking (configured vs missing per tool), (2) health probing (lightweight API call per tool with timeout), and (3) credential store/retrieve endpoints. The key testing risks are: secrets leaking in responses, probes hanging without timeout, health status being faked by mocks that never exercise real timeout/error paths, and the new endpoints not being wired into the running app.

## Test Specifications

### MUST-HAVE Tests

#### T1: test_list_tools_includes_credential_status
- **Spec ref:** PLAN Phase TM1 (Tool list enrichment)
- **Category:** Behavioral
- **Setup:** Register one tool with credentials configured (env var set) and one without.
- **Action:** `GET /api/v1/tools` as authenticated user.
- **Expected:** Each tool object in `data` contains `credential_status` field. Tool with env var set has `"configured"`, tool without has `"missing"`. Field is always present (never omitted).
- **Why:** Without this, the UI cannot show which tools need setup vs are ready.

#### T2: test_list_tools_includes_health_field
- **Spec ref:** PLAN Phase TM1 (Tool list enrichment)
- **Category:** Behavioral
- **Setup:** Authenticated user, tools registered.
- **Action:** `GET /api/v1/tools`
- **Expected:** Each tool object contains `health` field with value `"unchecked"` (default before any probe has run). Valid values are `"ok"`, `"error"`, `"unchecked"`.
- **Why:** If health field is absent, the frontend will crash or show undefined.

#### T3: test_health_probe_success_returns_ok
- **Spec ref:** PLAN Phase TM1 (Health probe)
- **Category:** Behavioral
- **Setup:** Tool `web_search` registered with valid credentials. Mock the external API call (Tavily) to return a successful response.
- **Action:** `POST /api/v1/tools/web_search/health` as authenticated user.
- **Expected:** Response `data.status == "ok"`, `data.latency_ms` is a positive number, HTTP 200.
- **Why:** Core functionality -- if probe success is not tested, we don't know the happy path works.

#### T4: test_health_probe_failure_returns_error_with_message
- **Spec ref:** PLAN Phase TM1 (Health probe)
- **Category:** Behavioral / Negative
- **Setup:** Tool `web_search` registered. Mock external API to raise an HTTP 401 error.
- **Action:** `POST /api/v1/tools/web_search/health`
- **Expected:** Response `data.status == "error"`, `data.error_message` is a non-empty string describing the failure (e.g., "Authentication failed" or "401 Unauthorized"). HTTP 200 (probe result, not probe crash).
- **Why:** Users need to know WHY a tool is unhealthy, not just that it is.

#### T5: test_health_probe_timeout_returns_error
- **Spec ref:** PLAN Phase TM1 (Health probe -- 5s timeout)
- **Category:** Behavioral / Edge
- **Setup:** Tool registered. Mock external API to hang indefinitely (asyncio.sleep or similar).
- **Action:** `POST /api/v1/tools/{name}/health`
- **Expected:** Response returns within ~6s (5s timeout + buffer). `data.status == "error"`, `data.error_message` mentions timeout. Does NOT hang the server.
- **Why:** Without timeout enforcement, a dead external API blocks the health endpoint forever. This is the most dangerous failure mode for health checks.

#### T6: test_health_probe_unknown_tool_returns_404
- **Spec ref:** PLAN Phase TM1 (Health endpoint)
- **Category:** Negative
- **Setup:** Authenticated user.
- **Action:** `POST /api/v1/tools/nonexistent_tool/health`
- **Expected:** HTTP 404 with error detail "Unknown tool: nonexistent_tool".
- **Why:** Prevents confusion and potential injection via arbitrary tool names.

#### T7: test_credential_store_post_stores_and_returns_masked
- **Spec ref:** PLAN Phase TM1 (Credential store endpoint), SPEC.md 11.1
- **Category:** Behavioral
- **Setup:** Authenticated user. Tool `web_search` exists in TOOL_SCHEMAS.
- **Action:** `POST /api/v1/tools/web_search/credentials` with body `{"api_key": "tvly-abc123secretkey"}`.
- **Expected:** HTTP 200. Response `data.api_key == "****tkey"` (masked, last 4 chars). The key is actually stored (retrievable by the system for probes). The raw key NEVER appears in the response body.
- **Why:** This is the core credential storage flow. If masking is broken, secrets leak to the frontend.

#### T8: test_credential_get_returns_only_masked
- **Spec ref:** PLAN Phase TM1 (Credential store endpoint), SPEC.md 11.2
- **Category:** Security
- **Setup:** Credential previously stored for tool `web_search`.
- **Action:** `GET /api/v1/tools/web_search/credentials` (or whatever the GET path is).
- **Expected:** Response contains ONLY the masked value (e.g., `"****tkey"`). The full key is NEVER returned. Response does NOT contain fields like `raw_key`, `plaintext`, `value`.
- **Why:** L11 (no plaintext token storage/exposure). If GET returns the raw key, any XSS or log capture leaks all credentials.

#### T9: test_credential_store_missing_tool_returns_404
- **Spec ref:** PLAN Phase TM1
- **Category:** Negative
- **Setup:** Authenticated user.
- **Action:** `POST /api/v1/tools/fake_tool/credentials` with body `{"api_key": "test"}`.
- **Expected:** HTTP 404.
- **Why:** Prevents storing credentials for nonexistent tools.

#### T10: test_all_endpoints_require_auth
- **Spec ref:** SPEC.md 5.1, L11 (default-deny)
- **Category:** Security
- **Setup:** No auth token / invalid auth token.
- **Action:** Call each new endpoint without authentication:
  - `POST /api/v1/tools/{name}/health`
  - `POST /api/v1/tools/{name}/credentials`
  - `GET /api/v1/tools/{name}/credentials`
- **Expected:** All return HTTP 401 (not 403, not 200, not 500).
- **Why:** Unauthenticated access to credential store or health probes is a critical security boundary.

#### T11: test_credential_status_checks_keychain_env_vars
- **Spec ref:** PLAN Phase TM1 (Credential status from Keychain), SPEC.md 11.1
- **Category:** Behavioral
- **Setup:** Set `TAVILY_API_KEY` env var. Do NOT set `NOTION_TOKEN`.
- **Action:** Call credential status check for `web_search` and `notion`.
- **Expected:** `web_search` returns `"configured"`. `notion` returns `"missing"`.
- **Why:** Credential status must reflect actual env var / Keychain state, not just database rows.

#### T12: test_health_probe_per_tool_type
- **Spec ref:** PLAN Phase TM1 (per-tool probes)
- **Category:** Behavioral
- **Setup:** Mock appropriate external API for each tool type.
- **Action:** Run health probe for each tool: `web_search`, `calendar`, `gmail`, `notion`.
- **Expected:** Each tool uses its specific probe method:
  - web_search: Tavily search "test"
  - calendar: Google Calendar list 0 events
  - gmail: Gmail list 1 email
  - notion: Notion search empty query
  Each returns `"ok"` on mock success.
- **Why:** A generic probe that doesn't actually call the tool's API is useless. Each tool has different auth and endpoints.

#### T13: test_no_plaintext_secrets_in_any_response
- **Spec ref:** SPEC.md 11.2 ("Secrets are never logged"), L6 (never log secrets), L11
- **Category:** Security / Invariant
- **Setup:** Store a credential `"sk-secret-test-key-12345678"` for a tool.
- **Action:** Call ALL tool endpoints: `GET /api/v1/tools`, `GET /api/v1/tools/{name}/credentials`, `POST /api/v1/tools/{name}/health`.
- **Expected:** The string `"sk-secret-test-key-12345678"` does NOT appear in any response body. Only masked form appears.
- **Why:** This is a defense-in-depth check. Even if individual masking tests pass, a different endpoint might leak the raw value through a different code path.

#### T14: test_credential_store_invalid_body_returns_422
- **Spec ref:** PLAN Phase TM1
- **Category:** Negative
- **Setup:** Authenticated user.
- **Action:** `POST /api/v1/tools/web_search/credentials` with empty body `{}` or missing required field.
- **Expected:** HTTP 422 (validation error). NOT HTTP 500.
- **Why:** Invalid input must be rejected cleanly, not crash the server.

#### T15: test_health_probe_updates_tool_list_health_field
- **Spec ref:** PLAN Phase TM1 (Tool list enrichment)
- **Category:** Integration
- **Setup:** Mock external API for success. Run health probe.
- **Action:** `POST /api/v1/tools/web_search/health` (succeeds), then `GET /api/v1/tools`.
- **Expected:** The tool list now shows `health: "ok"` for `web_search` (not `"unchecked"`).
- **Why:** If health probe results aren't persisted/cached and reflected in the list endpoint, the two endpoints are disconnected.

### NICE-TO-HAVE Tests

#### T16: test_health_probe_concurrent_requests
- **Spec ref:** PLAN Phase TM1
- **Category:** Edge
- **Setup:** Two simultaneous health probe requests for the same tool.
- **Action:** Fire two `POST /api/v1/tools/web_search/health` concurrently.
- **Expected:** Both return valid results. No race condition, no crash.
- **Why:** Multiple users or UI refresh can trigger concurrent probes.

#### T17: test_credential_store_overwrites_existing
- **Spec ref:** PLAN Phase TM1
- **Category:** Behavioral
- **Setup:** Store credential once. Store again with different value.
- **Action:** Two sequential `POST /api/v1/tools/web_search/credentials` with different keys.
- **Expected:** Second call succeeds. GET returns masked version of the NEW key. Old key is no longer accessible.
- **Why:** Credential rotation must replace, not append.

#### T18: test_credential_delete_clears_credential
- **Spec ref:** PLAN Phase TM1
- **Category:** Behavioral
- **Setup:** Store credential for a tool.
- **Action:** `DELETE /api/v1/tools/web_search/credentials` (if endpoint exists) or clear via POST with empty value.
- **Expected:** Subsequent GET shows credential_status as `"missing"`.
- **Why:** Users must be able to disconnect a tool by removing credentials.

#### T19: test_mask_key_edge_cases
- **Spec ref:** PLAN Phase TM1
- **Category:** Edge
- **Setup:** Various key lengths.
- **Action:** Mask keys of length 0, 1, 4, 5, 100.
- **Expected:** Empty/None returns None. 1-4 char keys return `"****"`. 5+ char keys return `"****" + last 4 chars`.
- **Why:** Short API keys should never leak full content.

#### T20: test_health_probe_with_missing_credentials
- **Spec ref:** PLAN Phase TM1
- **Category:** Negative
- **Setup:** Tool exists in TOOL_SCHEMAS but no credentials configured (env var unset).
- **Action:** `POST /api/v1/tools/web_search/health`
- **Expected:** Returns `data.status == "error"` with message indicating credentials are not configured. Does NOT attempt to call external API with empty/None key.
- **Why:** Probing without credentials wastes time and may produce confusing auth errors.

## Security Test Requirements

1. **No plaintext secrets in responses** (T7, T8, T13): Every endpoint that touches credentials must be verified to return only masked values. Search response bodies for the raw key string.

2. **Auth required on all new endpoints** (T10): credential store/retrieve and health probe endpoints must reject unauthenticated requests with 401.

3. **No `or ""` fallbacks on credential reads** (L11): When reading credentials from env/Keychain, the code must NOT use `or ""` or `or "default"` patterns that would silently provide empty credentials. It should return `None` / `"missing"` status.

4. **Credential storage mechanism**: Verify credentials are stored via the Keychain/env var pattern established in `settings/service.py` (env var priority, then DB). Credentials must NOT be stored in plaintext in a DB column without encryption.

5. **Health probe error messages must NOT leak credentials**: If a probe fails with a 401, the error message must not include the API key in the error details.

## Integration Test Requirements

1. **T15 (health probe -> tool list):** This is the key integration test. It verifies that the health probe endpoint and the tool list endpoint share state correctly. Must be tested without mocking the state-sharing mechanism (mock only the external API call).

2. **Wiring check:** The new endpoints (`POST /health`, `POST /credentials`, `GET /credentials`) must be reachable from the FastAPI router. Test via actual HTTP calls through TestClient, not by calling handler functions directly.

3. **Credential status must read from the same source as `registration.py`:** The credential status check must use the same env var names (`TAVILY_API_KEY`, `NOTION_TOKEN`, etc.) as `registration.py` uses to decide whether to register tools. If they diverge, the UI shows "configured" but the tool isn't actually registered.

## Anti-Patterns to Watch For

1. **"Health probe that probes nothing" (RC1 from retro):** A health probe that constructs a mock client or skips the actual API call and just returns `"ok"` is useless. The probe MUST attempt a real (but lightweight) API call. Tests must mock at the HTTP layer (httpx), not at the probe logic layer.

2. **"Wired in class, not in app" pattern (QC5/QC8 recurrence):** New health service or credential service classes may be implemented but never instantiated in `app.py` lifespan or connected to the router. Verify new classes appear in `app.py`.

3. **"Credential status from definitions, not from env" pattern:** If credential status is derived from `TOOL_SCHEMAS` keys (which are always present) instead of checking actual env vars / Keychain, every tool will show `"configured"`. Must check `os.environ.get()` or equivalent.

4. **"except Exception: pass" in probe code:** Health probes are exactly the kind of code where developers swallow exceptions. Every exception in probe code must be caught, logged, and returned as error status -- never silently swallowed.

5. **"Health probe stores raw key in response":** Watch for debug/error paths that include the API key in the health probe response (e.g., `{"error": "401 Unauthorized for key sk-abc..."}`).

6. **"Credential status hardcoded to tool names in TOOL_SCHEMAS":** The credential requirements per tool differ (Tavily needs 1 env var, Google needs 3). If the code checks only one generic env var per tool, Google tools will show "configured" when only `GOOGLE_CLIENT_ID` is set but `GOOGLE_CLIENT_SECRET` and `GOOGLE_REFRESH_TOKEN` are missing.

7. **"Timeout not enforced in probe":** If the probe uses `httpx.AsyncClient` without an explicit `timeout=5.0`, it inherits the default (which may be much longer or infinite). Verify the 5s timeout is explicit in the code.

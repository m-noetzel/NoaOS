# Test Plan: Phase TM2

**Date:** 2026-03-11
**Planner:** qa-review agent (test-plan mode)
**Spec Sections:** SPEC.md 12.1-12.4 (MVP Tool Definitions), 22.1 (risk_tier), ARCH_INVARIANTS L9/L10/L11

## Summary

TM2 enriches the Tools API to expose per-function metadata (risk_tier, domain, parameters) and per-function capability grants. The key testing risks are: (1) backward compatibility -- existing tool-level grants (NULL function_name) must continue working; (2) risk_tier values must match SPEC.md exactly (not hardcoded "medium" for everything); (3) new endpoints must enforce auth; (4) the DB model migration must be non-destructive.

## Spec-Derived Risk Tiers (Ground Truth)

These are the SPEC-mandated risk tiers that the implementation MUST match. Tests should assert against these exact values:

| Tool | Function | Risk Tier (SPEC) |
|------|----------|-----------------|
| calendar | list_events | low |
| calendar | create_event | medium |
| gmail | search_emails | low |
| gmail | read_email | low |
| gmail | send_email | medium |
| gmail | draft_email | low |
| notion | search_pages | low |
| notion | read_page | low |
| notion | create_page | medium |
| web_search | web_search | low |

Note: SPEC 12.3 says "Medium (create/update), Low (search/read)" for Notion. `update_event` and `update_page` are in SPEC but NOT in current TOOL_SCHEMAS. TM2 may or may not add them. Tests must verify what IS present matches SPEC.

## Test Specifications

### MUST-HAVE Tests

#### T1: test_tool_schemas_have_risk_tier_per_function
- **Spec ref:** SPEC.md 12.1-12.4
- **Category:** Behavioral
- **Setup:** Import TOOL_SCHEMAS from definitions.py
- **Action:** Iterate all tools and all functions within each tool
- **Expected:** Every function dict contains a `risk_tier` key with value in {"low", "medium", "high"}
- **Why:** The current code hardcodes `risk_tier: "medium"` in the API response for all tools. This test ensures the schema itself carries the correct per-function tier.

#### T2: test_risk_tiers_match_spec
- **Spec ref:** SPEC.md 12.1-12.4
- **Category:** Invariant
- **Setup:** Import TOOL_SCHEMAS
- **Action:** Check each function's risk_tier against the SPEC ground truth table above
- **Expected:** `gmail.send_email` = "medium", `gmail.search_emails` = "low", `gmail.read_email` = "low", `gmail.draft_email` = "low", `calendar.list_events` = "low", `calendar.create_event` = "medium", `notion.search_pages` = "low", `notion.read_page` = "low", `notion.create_page` = "medium", `web_search.web_search` = "low"
- **Why:** SPEC mandates specific risk tiers. A blanket "medium" violates the spec and causes unnecessary approval prompts for low-risk operations.

#### T3: test_tool_schemas_have_domain_per_function
- **Spec ref:** SPEC.md 12.1-12.4
- **Category:** Behavioral
- **Setup:** Import TOOL_SCHEMAS
- **Action:** Check every function for a `domain` key
- **Expected:** All current tools have domain "external" (per SPEC: calendar, gmail, notion, web_search are all external domain). Memory tool (if added) would be "private".
- **Why:** Domain assignment drives which worker processes a tool call. Wrong domain = data leak.

#### T4: test_list_tools_returns_nested_functions
- **Spec ref:** PLAN TM2 "API response" row
- **Category:** Behavioral
- **Setup:** Authenticated user, mock DB session with tool-level capability granted
- **Action:** GET /api/v1/tools
- **Expected:** Response contains tools with `functions` array. Each function object has: `name` (str), `description` (str), `parameters` (dict with JSON Schema), `risk_tier` (str), `enabled` (bool), `domain` (str)
- **Why:** The current API returns a flat list with no function details. TM2's primary deliverable is the nested structure.

#### T5: test_list_tools_function_enabled_reflects_capability
- **Spec ref:** PLAN TM2 "Per-function capabilities"
- **Category:** Behavioral
- **Setup:** User has capability granted for `gmail__send_email` but NOT `gmail__read_email`
- **Action:** GET /api/v1/tools
- **Expected:** In the gmail tool's functions array, `send_email` has `enabled: true`, `read_email` has `enabled: false`
- **Why:** Per-function granularity is the core feature. If all functions show the same enabled state, the feature is broken.

#### T6: test_grant_function_capability
- **Spec ref:** PLAN TM2 "Grant/revoke per function"
- **Category:** Behavioral
- **Setup:** Authenticated user, empty capabilities
- **Action:** POST /api/v1/tools/gmail/send_email/enable
- **Expected:** 200 OK, response indicates granted. Subsequent GET /api/v1/tools shows gmail.send_email as enabled.
- **Why:** Core CRUD operation for per-function permissions.

#### T7: test_revoke_function_capability
- **Spec ref:** PLAN TM2 "Grant/revoke per function"
- **Category:** Behavioral
- **Setup:** User has gmail__send_email capability
- **Action:** DELETE /api/v1/tools/gmail/send_email
- **Expected:** 200 OK, response indicates revoked. Subsequent GET shows gmail.send_email as disabled.
- **Why:** Users must be able to revoke individual function access.

#### T8: test_grant_unknown_tool_returns_404
- **Spec ref:** PLAN TM2 / L11 default-deny
- **Category:** Negative
- **Setup:** Authenticated user
- **Action:** POST /api/v1/tools/nonexistent/somefunc/enable
- **Expected:** 404 with detail "Unknown tool: nonexistent"
- **Why:** Prevents capability grants for tools that don't exist. Default-deny (L11).

#### T9: test_grant_unknown_function_returns_404
- **Spec ref:** PLAN TM2 / L11 default-deny
- **Category:** Negative
- **Setup:** Authenticated user
- **Action:** POST /api/v1/tools/gmail/nonexistent_function/enable
- **Expected:** 404 with detail indicating unknown function
- **Why:** Must validate function name against TOOL_SCHEMAS, not just tool name. Otherwise attackers can create arbitrary capability strings.

#### T10: test_db_model_function_name_column
- **Spec ref:** PLAN TM2 "DB model"
- **Category:** Behavioral
- **Setup:** Inspect ToolCapability model
- **Action:** Check model has `function_name` column
- **Expected:** Column exists, is nullable (String type), allows NULL for backward compat
- **Why:** The migration must add this column without breaking existing rows.

#### T11: test_backward_compat_null_function_grants_all
- **Spec ref:** PLAN TM2 "NULL function_name means all functions"
- **Category:** Invariant
- **Setup:** User has a ToolCapability row with `tool_name="gmail"`, `function_name=NULL`
- **Action:** Check capability for `gmail__send_email`, `gmail__read_email`, `gmail__search_emails`, `gmail__draft_email`
- **Expected:** All return True (NULL = wildcard grant for all functions of that tool)
- **Why:** This is the backward compatibility contract. Existing data has NULL function_name. If this breaks, all existing tool permissions silently stop working.

#### T12: test_function_grant_does_not_grant_sibling_functions
- **Spec ref:** PLAN TM2 per-function isolation
- **Category:** Security / Invariant
- **Setup:** Grant capability for `gmail__send_email` only (function_name="send_email")
- **Action:** Check capability for `gmail__read_email`
- **Expected:** Returns False
- **Why:** Per-function grants must be isolated. A send_email grant must not implicitly enable read_email.

#### T13: test_all_endpoints_require_auth
- **Spec ref:** M3 security boundaries
- **Category:** Security
- **Setup:** No auth token
- **Action:** Call each new endpoint: POST /tools/{name}/{func}/enable, DELETE /tools/{name}/{func}
- **Expected:** 401 or 403 for each
- **Why:** Unauthenticated tool permission changes = privilege escalation.

#### T14: test_revoke_function_does_not_revoke_tool_wildcard
- **Spec ref:** PLAN TM2 backward compat
- **Category:** Invariant
- **Setup:** User has BOTH a wildcard grant (function_name=NULL, tool_name="gmail") AND a specific grant (function_name="send_email", tool_name="gmail")
- **Action:** DELETE /api/v1/tools/gmail/send_email (revoke function-level)
- **Expected:** The wildcard grant (NULL) is NOT deleted. Only the function-specific row is removed.
- **Why:** Revoking a single function must not destroy the broader tool-level grant. This is the most dangerous backward-compat edge case.

#### T15: test_capabilities_function_level_entries
- **Spec ref:** PLAN TM2 "Extend TOOL_CAPABILITIES to function-level"
- **Category:** Behavioral
- **Setup:** Import TOOL_CAPABILITIES
- **Action:** Check for function-level entries like "gmail__send_email", "gmail__read_email"
- **Expected:** Function-level keys exist in TOOL_CAPABILITIES dict (e.g., `gmail__send_email: "gmail.send"`)
- **Why:** The capability checker needs function-level mappings to do per-function permission checks.

### NICE-TO-HAVE Tests

#### T16: test_get_anthropic_tools_respects_function_capabilities
- **Spec ref:** definitions.py get_anthropic_tools
- **Category:** Integration
- **Setup:** User has only `gmail__send_email` enabled
- **Action:** Call get_anthropic_tools with capability-filtered function list
- **Expected:** Only `gmail__send_email` tool entry is returned, not `gmail__search_emails` etc.
- **Why:** The LLM should only see tools the user has enabled. If filtering happens at API level but not at LLM tool-building level, the orchestrator will still try to use disabled functions.

#### T17: test_risk_tier_in_api_response_matches_schema
- **Spec ref:** PLAN TM2 API response
- **Category:** Integration
- **Setup:** Authenticated user
- **Action:** GET /api/v1/tools, extract risk_tier from each function
- **Expected:** Each function's risk_tier matches TOOL_SCHEMAS value, NOT the old hardcoded "medium"
- **Why:** Catches the case where TOOL_SCHEMAS is updated but the API response still reads from a different source.

#### T18: test_empty_tool_no_functions
- **Spec ref:** Edge case
- **Category:** Behavioral
- **Setup:** A tool name in TOOL_CAPABILITIES but NOT in TOOL_SCHEMAS (or with empty functions)
- **Action:** GET /api/v1/tools
- **Expected:** Tool appears with empty functions array, not a crash
- **Why:** Defensive against schema/capabilities map desync.

#### T19: test_duplicate_function_grant_is_idempotent
- **Spec ref:** Robustness
- **Category:** Behavioral
- **Setup:** User already has gmail__send_email capability
- **Action:** POST /api/v1/tools/gmail/send_email/enable again
- **Expected:** 200 OK (idempotent), no duplicate rows in DB
- **Why:** Double-click protection. Without idempotency, duplicate rows could cause confusing revoke behavior.

#### T20: test_revoke_nonexistent_function_returns_success
- **Spec ref:** Robustness
- **Category:** Behavioral
- **Setup:** User has no gmail__send_email capability
- **Action:** DELETE /api/v1/tools/gmail/send_email
- **Expected:** 200 OK with revoked count = 0
- **Why:** Idempotent delete is standard REST pattern. Should not error.

## Security Test Requirements

1. **Auth required on all new endpoints** (T13) -- both the function-level enable and disable endpoints must reject unauthenticated requests
2. **Function name validation** (T9) -- arbitrary function names must be rejected to prevent capability string injection
3. **Grant isolation** (T12) -- per-function grants must not leak to sibling functions
4. **Revoke isolation** (T14) -- function revoke must not destroy wildcard grants
5. **Default deny** -- unknown tools and unknown functions must be denied, not silently allowed

## Integration Test Requirements

1. **At least one test must use a real DB session** (not mocked) to verify the function_name column query logic works with SQLAlchemy -- specifically the NULL wildcard behavior (T11). This is the most dangerous place for ORM query bugs.
2. **At least one test must call the endpoint through the FastAPI test client** (not just the handler function) to verify routing works for the new `/{name}/{function}/enable` and `/{name}/{function}` URL patterns.

## Anti-Patterns to Watch For

### From past retros and audit findings:

1. **Hardcoded risk_tier "medium" not replaced** -- The current `list_tools` endpoint hardcodes `"risk_tier": "medium"` (line 148 of tools.py). If TM2 only adds risk_tier to TOOL_SCHEMAS but does not update the API response builder to read from TOOL_SCHEMAS, the API will still return "medium" for everything. T17 catches this.

2. **"Wired in class, not in app" pattern** -- If new endpoints are added to the router but the router is already registered, this is fine. But if new helper functions/classes are created (e.g., a FunctionCapabilityChecker), verify they are actually called from the endpoints, not just defined.

3. **Source inspection tests instead of behavioral tests** -- Tests must actually call functions and check return values, not just `inspect.getsource()` for keywords. (RC1 from project audit: "Tests Validated Shape, Not Behavior")

4. **except Exception in new code** -- TM1 already has one `except Exception` in tools.py:139. New code must not add more without logging (L9).

5. **NULL handling in SQLAlchemy queries** -- `WHERE function_name = 'send_email' OR function_name IS NULL` is tricky in SQLAlchemy. A naive `== None` comparison works but `is None` does not. The backward-compat wildcard logic (T11) is the most likely place for a subtle bug.

6. **Capability map divergence** -- TOOL_CAPABILITIES and TOOL_SCHEMAS can diverge. If a function exists in TOOL_SCHEMAS but not TOOL_CAPABILITIES, the capability check will deny it (good, per L11). But if a function exists in TOOL_CAPABILITIES but not TOOL_SCHEMAS, grants will succeed but the function won't appear in the API response. Tests should verify both maps cover the same functions.

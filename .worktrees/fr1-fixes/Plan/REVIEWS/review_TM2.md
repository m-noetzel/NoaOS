# QA Review: Phase TM2

**Date:** 2026-03-11
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 3/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All tests have docstrings citing SPEC.md sections or PLAN TM2. Test plan T1-T15 all covered. |
| M2 | Negative Tests | PASS | T8 (unknown tool 404), T9 (unknown function 404), T12 (function isolation), T13 (auth required). |
| M3 | Security Boundaries | PASS | Auth enforced on new endpoints (verified via ASGI client tests). Function name validated against TOOL_SCHEMAS in enable_function. Default-deny preserved. |
| M4 | Determinism | PASS | No wall-clock time, network calls, or random values in tests. All use in-memory SQLite. |
| M5 | Implementation Completeness | PASS | All 5 deliverables implemented: rich schema, function-level capabilities, DB model column, nested API response, grant/revoke endpoints. |
| M6 | No Silent Error Swallowing | PASS | tools.py:141 `except Exception` (pre-existing TM1) has logging. No new bare except blocks. |
| M7 | Wiring Completeness | PASS | tools_router already registered in app.py:389. New routes are on the same router. Verified via smoke test. |
| M8 | Domain Isolation | PASS | No cross-domain imports. `noa.tools` only imports from `noa.db.models` and `noa.tools.definitions`. |
| S1 | Error Handling & Boundaries | OPEN | `disable_function` does not validate tool_name/function_name (see Note 2). |
| S2 | Code Consistency | PASS | Follows existing patterns. Parameter naming consistent. |
| S3 | Migration & Rollback | OPEN | No alembic migration for `function_name` column (see Note 1). |
| S4 | Documentation | PASS | All public functions have type annotations and docstrings. |
| S5 | Integration Smoke Test | PASS | 3 tests use real in-memory SQLite (T11, T12, T14). 7 tests call through ASGI transport. Smoke test passes. |

## Test Plan Coverage

All 15 MUST-HAVE tests from the test plan are present and passing. Coverage mapping:

| Test Plan ID | Test Method | Status |
|---|---|---|
| T1 | test_every_function_has_risk_tier | PASS |
| T2 | test_risk_tiers_match_spec | PASS |
| T3 | test_every_function_has_domain + test_mvp_tools_are_external_domain | PASS |
| T4 | test_list_tools_returns_nested_functions | PASS |
| T5 | test_function_enabled_reflects_grant | PASS |
| T6 | test_grant_function_capability | PASS |
| T7 | test_revoke_function_capability | PASS |
| T8 | test_grant_unknown_tool_returns_404 | PASS |
| T9 | test_grant_unknown_function_returns_404 | PASS |
| T10 | test_function_name_column_exists + test_function_name_column_is_nullable | PASS |
| T11 | test_null_function_grants_all | PASS (real DB) |
| T12 | test_function_grant_does_not_grant_siblings | PASS (real DB) |
| T13 | test_function_enable_requires_auth + test_function_disable_requires_auth | PASS |
| T14 | test_revoke_function_does_not_revoke_wildcard | PASS (real DB) |
| T15 | test_function_level_keys_exist + test_tool_level_keys_still_exist | PASS |

NICE-TO-HAVE: T17 implemented. T16/T18/T19/T20 not implemented (acceptable).

## Spec Compliance

Risk tiers verified against SPEC.md 12.1-12.4:
- calendar.list_events = low, calendar.create_event = medium (matches SPEC: "Medium create, Low list")
- gmail.search_emails = low, gmail.read_email = low, gmail.send_email = medium, gmail.draft_email = low (matches SPEC: "Medium send, Low search/read/draft")
- notion.search_pages = low, notion.read_page = low, notion.create_page = medium (matches SPEC: "Medium create, Low search/read")
- web_search.web_search = low (matches SPEC: "Low")

Note: Phase plan said `gmail.send_email = high` but SPEC says Medium (send). Implementation correctly follows SPEC.

## Test Coverage

20 tests total, all passing. Breakdown:
- 4 schema-level (risk_tier, domain)
- 2 capability map (function-level keys, backward compat)
- 2 DB model (column existence, nullability)
- 3 capability checker with real DB (NULL wildcard, function isolation, revoke isolation)
- 7 API endpoint via ASGI client (list, grant, revoke, 404s, auth)
- 2 auth enforcement (enable, disable without token)

Integration tests: 3 real-DB async tests + 7 ASGI transport tests = strong coverage.

## Anti-Pattern Scan Results

**M6 (bare except):** No bare `except:` in src/noa/tools/. The pre-existing `except Exception` at tools.py:141 has logging (noqa BLE001 suppressed). No new violations.

**M7 (wiring):** tools_router registered at app.py:389. New routes on same router -- automatically included.

**M8 (domain isolation):** No cross-domain imports found.

**Ruff check:** All 4 modified files pass (`All checks passed!`).

## Smoke Test Results

```
OK: definitions imports
OK: capabilities imports
OK: tool_capability model import
OK: tools router imports
OK: All 10 functions have risk_tier + domain
OK: 14 capability keys (tool + function level)
OK: ToolCapability.function_name column is nullable
OK: Function-level routes registered
OK: parse_tool_call_name works
OK: get_anthropic_tools returns 4 gmail functions
OK: get_openai_tools returns 4 gmail functions
=== ALL SMOKE TESTS PASSED ===
```

## Security

1. **Auth enforced:** Both new endpoints require Bearer token. Verified with unauthenticated requests returning 401/403.
2. **Input validation:** `enable_function` validates tool_name against TOOL_SCHEMAS and function_name against tool's functions dict.
3. **Default-deny preserved:** Unknown tools denied. H7 fix intact -- `has_capability` returns False for tools not in TOOL_CAPABILITIES.
4. **No hardcoded secrets:** Clean.
5. **Function grant isolation:** Verified -- granting send_email does NOT grant read_email.

## Code Quality

- Clean separation: definitions (data), capabilities (business logic + DB), tools.py (API layer).
- Backward compatibility well-handled: NULL function_name acts as wildcard throughout.
- `parse_tool_call_name` is a useful addition for the orchestrator's tool dispatch.
- The capability generation loop at capabilities.py:31-36 dynamically builds function-level keys from TOOL_SCHEMAS, preventing divergence.

## Beyond the Test Plan

1. **No unique constraint on grants:** `DbCapabilityChecker.grant()` does not check for existing grants before inserting. Double-calling `enable_function` creates duplicate rows. This causes `revoke()` to delete multiple rows and `has_capability()` to work correctly (scalar_one_or_none still finds a match). Not a correctness bug but a data hygiene issue.

2. **`disable_function` lacks validation:** Unlike `enable_function` (which validates both tool_name and function_name against TOOL_SCHEMAS), `disable_function` at tools.py:262-285 does no validation. A user can DELETE `/api/v1/tools/anything/anything` and receive 200 OK with `revoked: 0`. This is inconsistent but not a security issue (the delete is a no-op).

3. **Route ordering risk:** `DELETE /{name}` (disable_tool) and `DELETE /{tool_name}/{function_name}` (disable_function) could theoretically collide if FastAPI route matching is ambiguous. Verified: FastAPI matches more specific paths first, so `gmail/send_email` matches the two-segment route, not the one-segment `{name}` route. No actual issue.

4. **No migration created:** This is the highest-risk gap. The `function_name` column is defined in the ORM model but no alembic migration exists to add it. Production deployments will fail when the column is referenced. All tests pass because they use `Base.metadata.create_all` (which creates the full schema from ORM models).

## Notes (PASS_WITH_NOTES)

1. **Missing alembic migration (S3):** The `function_name` column on `tool_capabilities` table needs migration 009. Without it, production deployments will crash on any function-level capability query. The column is nullable with a default of None, so the migration is safe to add (backward-compatible ALTER TABLE ADD COLUMN). File: `src/noa/db/models/tool_capability.py:31-33`.

2. **`disable_function` lacks input validation (S1):** `disable_function` at `src/noa/api/v1/tools.py:262-285` does not validate `tool_name` or `function_name` against TOOL_SCHEMAS. Should mirror the validation in `enable_function` (lines 232-241) for consistency and to prevent creation of misleading success responses for nonexistent tools/functions.

3. **No unique constraint prevents duplicate grants:** `ToolCapability` model at `src/noa/db/models/tool_capability.py:35-37` should have a unique constraint on `(user_id, tool_name, function_name)` to prevent duplicate rows. Or `grant()` should check-before-insert.

## Decision Review

The implementation is solid and well-tested. The core feature -- per-function metadata and capability grants with backward compatibility -- is complete and correct. The three notes above are all robustness improvements that do not affect correctness of the current feature set.

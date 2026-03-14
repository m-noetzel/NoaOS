# QA Review: Phase FR6

**Date:** 2026-03-14
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 13/13 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All tests cite SPEC.md §11, §19, §2.1 and PLAN phase IDs (UX-M2/M3/M4/M10/H6/L10) |
| M2 | Negative Tests | PASS | Not-found (404), empty title (422), ownership isolation (rename other user's thread = 404), unknown scope (404) |
| M2b | Write-Path Test Fidelity | PASS | Uses real SQLite in-memory DB + ASGI test client — no mock-both-read-and-write vacuous pattern |
| M3 | Security Boundaries | PASS | All endpoints require auth. Thread rename enforces user_id ownership at query level. Scope overrides are user-keyed by uid. Auto-grant uses real DB session. No hardcoded secrets. |
| M3b | Write-Path User Scoping | PASS | `update_thread` filters by `Conversation.user_id == user.user_id` at write time. `_auto_grant_capability` extracts user_id from payload before writing. `_scope_overrides` keyed by uid. |
| M4 | Determinism | PASS | No wall-clock assertions. No network calls in tests. Tests use in-memory SQLite. |
| M4b | Mock Interface Accuracy | PASS | Tests use real ASGI client and real DB — no mock interface issues |
| M5 | Implementation Completeness | PASS | All planned files present: threads.py (PATCH endpoint), settings.py (PATCH + new fields), tools.py (scopes endpoints + _auto_grant_capability), migration 016, Settings.tsx (Governance + Agent Limits), Tools.tsx (All/Usable toggle + search + scope panel), Chat.tsx (rename), AppSidebar.tsx (flex-shrink-0), SettingsViewModel.swift (BackendConnectionStatus), SettingsView.swift (backend section) |
| M5b | Findings Currency | PASS | FINDINGS.md updated: UX-M2, UX-M3, UX-M4, UX-M8, UX-M9, UX-M10, UX-L1, UX-H6, iOS-H5 all marked Resolved by FR6 |
| M5c | Related-Issue Scope Completeness | PASS | Pattern (governance fields) consistently applied across ORM model, migration, service, and API layer |
| M6 | No Silent Error Swallowing | PASS | Three `except Exception: # noqa: BLE001` blocks all have `logger.warning/debug + exc_info=True`. None return success on error. |
| M7 | Wiring Completeness | PASS | threads_router, settings_router, tools_router all registered in app.py (lines 465, 467, 472). PATCH /threads/{thread_id} confirmed present. New scope endpoints appended to existing tools_router — no separate registration needed. |
| M8 | Domain Isolation | PASS | No cross-domain imports. `settings.py` imports `noa.external_worker.llm.router` — correct direction (api→worker). No private_worker references in external-facing code. |
| M8b | Cross-Language Field Optionality | PASS | `UpdateSettingsRequest` has all new fields as `Optional` (default None). `UserSettings` type in types.ts uses `?` for new fields. |
| M2c | Source-Inspection Test Gate | PASS | UX-L1 test does source text scan with behavioral fallback. L10 function row test executes actual render code path. |
| S1 | Error Handling & Boundaries | OPEN | `max_tool_calls`, `max_retries`, `timeout_seconds` accept negative and zero values — no Pydantic `Field(ge=1)` or `ge=0` constraints. A user can set `max_tool_calls=-99` and it persists to DB without error. Low-risk for single-user deployment but semantically incorrect. |
| S2 | Code Consistency | PASS | Follows existing naming conventions. Layering: API endpoint → SettingsService → SettingsRepository. No duplicate abstractions. |
| S3 | Migration & Rollback | PASS | Migration 016 has `upgrade()` and `downgrade()`. Chains to `down_revision="015"`. Uses `batch_alter_table(recreate="always")` for SQLite compatibility. |
| S4 | Documentation | PASS | All public functions have type annotations and docstrings. Inline comments cite spec requirement IDs (UX-M2, UX-M4, UX-H6, UX-M10, BE-H8). |
| S5 | Integration Smoke Test | PASS | 19 backend tests use real ASGI + in-memory SQLite — no mocks of DB or services. Cross-module paths tested (API → SettingsService → SettingsRepository → SQLite). |

---

## Spec Compliance

All spec requirements from the phase plan verified:

- **UX-M3** (thread rename): `PATCH /api/v1/threads/{thread_id}` implemented in `threads.py:179-232`. Ownership enforced via `Conversation.user_id == user.user_id`. Empty title → 422. Title > 256 chars → 422. Tests cover: rename, not-found, empty title, cross-user ownership, persistence to list endpoint.
- **UX-M2** (approvals toggle): `approvals_enabled: bool | None = None` in `UpdateSettingsRequest`. ORM field with `server_default="1"`. Service default `True`. Tests cover: default read, disable, re-enable.
- **UX-M4** (agent limits): `max_tool_calls`, `max_retries`, `timeout_seconds` fields added to ORM, service, and API. Tests cover: defaults, save, partial update.
- **UX-M10** (tool scopes): `GET /api/v1/tools/scopes` + `PATCH /api/v1/tools/scopes/{scope_name}`. Backed by `ToolScopeRegistry` + in-memory per-user override map. Tests cover: list predefined, update, unknown scope 404.
- **UX-H6** (Notion auto-grant): `_auto_grant_capability()` in `store_credentials` endpoint. Uses `DbCapabilityChecker.grant()` which is idempotent (checks for existing grant before inserting). Tests cover: Notion and web_search credential saves grant capabilities.
- **UX-M8** (Tools All/Usable toggle): Frontend filter with `data-testid="filter-all"` and `data-testid="filter-usable"`. Usable = `health.status === "healthy"` AND `credentials.configured !== false`. Tests cover: default shows all, usable filters, empty state.
- **UX-M9** (Tools search): `data-testid="tools-search"`. Case-insensitive search on name + description. Tests cover: basic filter, case-insensitive, name-match.
- **UX-L1** (logo flex-shrink-0): `AppSidebar.tsx:73` — `className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl gradient-primary shadow-md glow-sm"`.
- **iOS-H5** (backend health): `BackendConnectionStatus` enum (unknown/checking/reachable/unreachable), `HealthCheckProviding` protocol, `URLSessionHealthChecker` implementation, `checkBackendHealth()` async method. 8 Swift tests cover all state transitions.

---

## Test Coverage

| Spec Req | Test Class | Tests | Notes |
|----------|-----------|-------|-------|
| UX-M3 | TestThreadRename | 5 | Positive, 404, empty, ownership, persistence |
| UX-M2 | TestApprovalsToggle | 3 | Default, disable, re-enable |
| UX-M4 | TestAgentLimits | 3 | Defaults, save, partial update |
| UX-H6 | TestNotionCapabilityAutoGrant | 2 | Notion + web_search credential saves |
| UX-M10 | TestToolScopes | 3 | List, update, unknown-404 |
| Migration | TestSettingsSchema | 3 | ORM fields, _ALL_FIELDS, _DEFAULTS |
| UX-M8 | Frontend (vitest) | 4 | All, toggle, usable-only, empty state |
| UX-M9 | Frontend (vitest) | 3 | Render, name filter, case-insensitive |
| UX-M10 | Frontend (vitest) | 3 | Hidden default, toggle exists, toggle shows panel |
| UX-M2 | Frontend (vitest) | 2 | Governance section render, checked state |
| UX-M4 | Frontend (vitest) | 4 | Section render, default values for 3 fields |
| UX-L1 | Frontend (vitest) | 1 | Source text or import without error |
| L10 | Frontend (vitest) | 1 | Function rows with enable/disable switches |
| iOS-H5 | Swift (FR6SettingsTests) | 8 | All BackendConnectionStatus cases |

**Gaps:**
- No negative test for `max_tool_calls < 0` being stored and later causing orchestrator errors (S1-level concern)
- No test verifying that `_scope_overrides` survives (or doesn't survive) across app restarts — in-memory limitation is implicit
- iOS T-FR6-04 (checking transition) has a soft assertion: `if case .reachable = vm.backendStatus { } else if case .unreachable = vm.backendStatus { }` — accepts either outcome for the `.checking` transition test

---

## Anti-Pattern Scan Results

**M6 — Bare exception blocks:**
```
src/noa/api/v1/tools.py:199  except Exception:  # noqa: BLE001  → logger.warning + exc_info — OK
src/noa/api/v1/tools.py:214  except Exception:  # noqa: BLE001  → logger.warning + exc_info — OK
src/noa/api/v1/tools.py:477  except Exception:  # noqa: BLE001  → logger.warning + exc_info — OK
src/noa/api/v1/settings.py:120 except Exception: # noqa: BLE001 → logger.debug + exc_info — OK
src/noa/api/v1/settings.py:127 except Exception: # noqa: BLE001 → logger.warning + exc_info — OK
```
All BLE001 blocks log with exc_info=True and none return HTTP 200 on error. No new bare `except:` violations.

**M7 — Wiring completeness:**
```
app.py:465: app.include_router(threads_router)  ✓
app.py:467: app.include_router(settings_router)  ✓
app.py:472: app.include_router(tools_router)  ✓
```
Scope endpoints are on the existing tools_router — no separate registration needed. PATCH `/threads/{thread_id}` confirmed wired (verified by route enumeration).

**M8 — Domain isolation:**
```
No 'from noa.private_worker' in src/noa/api/v1/
No 'from noa.external_worker' in src/noa/private_worker/
settings.py imports noa.external_worker.llm.router — correct direction (API → worker)
```

---

## Smoke Test Results

```
python3 /tmp/qa_smoke_fr6_v2.py

OK: PATCH /api/v1/threads/{thread_id} confirmed
OK: PATCH /api/v1/settings confirmed
OK: GET /api/v1/tools/scopes confirmed
OK: PATCH /api/v1/tools/scopes/{scope_name} confirmed
WARN: No validation for negative/zero values: ['max_tool_calls=-5', 'max_retries=-1', 'timeout_seconds=0']
WARN: UpdateThreadRequest accepts >256 char title at model level (handler must check)
OK: TOOL_CAPABILITIES has 18 tools
WARN: _scope_overrides is in-memory only — not persisted across restarts
OK: Migration 016 has upgrade + downgrade, chains to 015
All smoke checks PASSED

pytest tests/unit/test_fr6_tools_settings.py -v
19 passed, 1 warning in 0.92s

vitest run fr6
18 tests passed (296ms)

ruff check src/noa/api/v1/threads.py src/noa/api/v1/tools.py src/noa/api/v1/settings.py src/noa/settings/
All checks passed!

mypy src/noa/api/v1/threads.py src/noa/api/v1/settings.py src/noa/settings/
Success: no issues found in 6 source files
```

---

## Security

**No new vulnerabilities introduced.**

1. **Thread ownership**: `update_thread` queries `WHERE Conversation.id == thread_id AND Conversation.user_id == user.user_id` — IDOR impossible. Test `test_patch_thread_cannot_rename_other_users_thread` explicitly verifies this.

2. **Scope isolation**: `_scope_overrides` is a `dict[str, dict[str, list[str]]]` keyed by `uid` (string). User A cannot read User B's scope overrides. No cross-user data leakage.

3. **Auto-grant idempotency**: `DbCapabilityChecker.grant()` checks for existing grant before inserting (lines 119-130 in capabilities.py). No race-window duplicate grants possible within a single await call.

4. **Credential body**: `store_credentials` accepts `body: dict[str, Any]` — arbitrary keys stored in-memory. Pre-existing pattern (TM1), not introduced by FR6. Not a blocker.

5. **Settings fallback defaults**: `approvals_enabled` defaults to `True` (secure — approvals on by default). No unsafe fallback pattern (`or ""` on secrets).

6. **Input size**: Thread title bounded to 256 chars in handler (line 213-217). Settings fields have no explicit bounds on integer values (see Notes).

---

## Code Quality

- `update_thread` handler does manual validation (`.strip()`, `len(title) > 256`) rather than Pydantic `Field(max_length=256, min_length=1)`. Functionally correct but inconsistent with Pydantic-first approach used elsewhere.
- `UpdateSettingsRequest` fields `max_tool_calls`, `max_retries`, `timeout_seconds` have no `ge=1` or `ge=0` constraints. Negative values are accepted and persisted to DB. The orchestrator would then run with a negative tool call limit (unclear behavior).
- `_scope_overrides` is in-memory. Documented as a known limitation. On restart, all scope customizations are lost. This degrades UX but is not a security issue.
- `test_patch_thread_empty_title_rejected` triggers FastAPI deprecation warning: `'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead`. Non-blocking cosmetic issue.
- iOS T-FR6-04 transition test has a soft assertion that accepts both `.reachable` and `.unreachable` — effectively the test doesn't verify the `.checking` intermediate state, only the final settled state.

---

## Deep Dive

**Issue 1: Settings frontend uses PUT, not PATCH (behavior difference)**
`Settings.tsx:388-390` sends `PUT /api/v1/settings` (not PATCH). The phase description says "4 new fields: approvals_enabled, max_tool_calls, max_retries, timeout_seconds (UX-M2, UX-M4)". Both PUT and PATCH are implemented on the backend (`settings.py:180` and `:200`). PUT sends the full body so this works correctly — but it means ALL settings are resent on every save (potentially overwriting fields edited elsewhere). This is pre-existing behavior, not introduced by FR6.

**Issue 2: Scope overrides lost on restart**
`_scope_overrides` is module-level in-memory dict. Any scope configuration the user sets via `PATCH /tools/scopes/{scope_name}` is lost when the server restarts. The test `test_patch_scope_updates_tools` even manually cleans up: `tools_mod._scope_overrides.pop(str(user_id), None)`. This is explicitly documented as a known limitation in the spec section and does not block FR6, but should be tracked.

**Issue 3: Auto-grant on ANY tool with a capability entry**
`store_credentials` auto-grants capability for ANY tool in `TOOL_CAPABILITIES` when credentials are saved (line 514: `if name in TOOL_CAPABILITIES`). This means storing credentials for `gmail` would also auto-grant the `gmail` capability, including high-risk functions like `delete_email` if they exist. The design intent (UX-H6) appears to be Notion-specific, but the implementation is tool-generic. Given capability defaults are deny-first and users must explicitly save credentials, this is acceptable but worth noting.

**Issue 4: `_auto_grant_capability` uses a separate DB session**
The function opens a new session via `get_session_factory()` rather than reusing the request's session. This means the grant is committed independently from the credential storage. If the credential store call succeeds but the session factory is None, the grant is silently skipped (with a debug log). This is intentional ("best-effort") and documented in the docstring. Acceptable.

**Issue 5: No test for `max_tool_calls` orchestrator integration**
The settings are saved and loaded correctly, but there is no test that passes `max_tool_calls=5` through to the orchestrator and verifies it uses that value as a limit. The new fields are persisted but their effect on agent behavior is untested. This is a cross-phase concern (orchestrator would need to read from settings), not a blocker for FR6's stated scope.

---

## Notes (PASS_WITH_NOTES)

1. **S1 — Missing integer bounds on agent limit fields**: `UpdateSettingsRequest.max_tool_calls`, `max_retries`, `timeout_seconds` have no Pydantic `Field(ge=1)` (or `ge=0` for retries). A user can persist `max_tool_calls=-99`. Add `Field(ge=1, le=1000)`, `Field(ge=0, le=20)`, `Field(ge=10, le=3600)` respectively.

2. **S1 — UpdateThreadRequest title not model-level validated**: Title length (>256) and emptiness are enforced in the handler at lines 207-217, not at the Pydantic model. This means the model-level error message differs from the handler-level message, creating inconsistent error shapes (handler returns 422 HTTPException, not Pydantic ValidationError). Consider `Field(min_length=1, max_length=256, strip_whitespace=True)`.

3. **S2 — Scope overrides not persisted to DB**: `_scope_overrides` is in-memory. A future phase should persist scope overrides to a user settings table column (e.g., JSON column on `UserSettings`). Add a FINDINGS entry.

4. **S1 — iOS T-FR6-04 weak assertion**: `testCheckBackendHealthSettlesToReachable` accepts both `.reachable` and `.unreachable` as valid outcomes after a mock 200 response. The test intent is to verify `.checking` transitions to `.reachable`, but the assertion accepts failure. Should assert `if case .reachable = vm.backendStatus` without the fallback.

5. **Cosmetic — FastAPI deprecation warning**: `HTTP_422_UNPROCESSABLE_ENTITY` deprecated in favour of `HTTP_422_UNPROCESSABLE_CONTENT`. Update `threads.py:209,215` to use `status.HTTP_422_UNPROCESSABLE_CONTENT` when upgrading FastAPI.

---

## Findings Sync

FR6 resolves the following findings (already reflected in FINDINGS.md):
- `UX-H6` → Resolved (auto-grant on credential save)
- `iOS-H5` → Resolved (BackendConnectionStatus + checkBackendHealth)
- `UX-M2` → Resolved (approvals_enabled governance toggle)
- `UX-M3` → Resolved (PATCH /threads/{thread_id} rename)
- `UX-M4` → Resolved (max_tool_calls, max_retries, timeout_seconds)
- `UX-M8` → Resolved (All/Usable toggle)
- `UX-M9` → Resolved (Tools search)
- `UX-M10` → Resolved (scope settings panel)
- `UX-L1` → Resolved (flex-shrink-0 logo)

**New finding to add:**
- `FR6-L1` (Low): Scope overrides (`_scope_overrides` in tools.py) are in-memory only — lost on server restart. User scope configurations are not persisted to DB. A future phase should add a JSON column to `UserSettings` or a separate `user_scope_overrides` table.

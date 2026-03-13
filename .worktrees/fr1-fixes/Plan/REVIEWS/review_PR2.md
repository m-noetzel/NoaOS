# QA Review: Phase PR2

**Date:** 2026-03-11
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | Tests cite SPEC.md SS11.1, SS24; all 3 findings covered |
| M2 | Negative Tests | PASS | test_patch_settings_creates_row_if_not_exists tests missing-row path; null-guard test for thread creation |
| M3 | Security Boundaries | PASS | No hardcoded secrets, auth required on PATCH, no localStorage |
| M4 | Determinism | PASS | No wall-clock, no network, no randomness in test assertions |
| M5 | Implementation Completeness | PASS | All 3 findings addressed: PATCH endpoint, mutateAsync race fix, type cast removal |
| M6 | No Silent Error Swallowing | PASS | No bare except blocks in changed files |
| M7 | Wiring Completeness | PASS | settings router already registered in app.py (line 384) |
| M8 | Domain Isolation | PASS | No cross-domain imports |
| S1 | Error Handling & Boundaries | PASS | Chat.tsx has try/catch with toast for thread creation failures |
| S2 | Code Consistency | OPEN | 4 ruff violations in test file: unused import `ast`, unused import `SettingsRepository`, camelCase function name, E501 line too long |
| S3 | Migration & Rollback | PASS | No DB schema changes |
| S4 | Documentation | PASS | Docstrings on all test classes and PATCH handler |
| S5 | Integration Smoke Test | OPEN | Tests mock the DB session; no non-mocked integration test exists for the PATCH endpoint (all tests inject mocked AsyncSession). Frontend tests read source files but don't call real endpoints. |

## Test Plan Coverage
No separate test plan was written for PR2. The implementation addresses 3 specific audit findings (BE-H3, FE-C1, FE-H1, FE-H2).

## Spec Compliance
- **SPEC.md SS11.1 (Settings):** PATCH endpoint now exists alongside PUT. Both use `exclude_unset=True` on `UpdateSettingsRequest.model_dump()`, which correctly implements partial update semantics. The PrivacyToggle's PATCH request will now succeed.
- **SPEC.md SS24 (Frontend):** Thread creation race fixed -- `mutateAsync` is awaited before SSE connection. Type safety restored in RunDetail (no unsafe casts).

## Test Coverage

| Test | Spec Ref | Type |
|------|----------|------|
| test_patch_handler_is_registered | BE-H3 / FE-C1 | Behavioral |
| test_patch_settings_privacy_mode_only | BE-H3 | Behavioral |
| test_patch_settings_preserves_unspecified_fields | BE-H3 | Behavioral (key test) |
| test_patch_settings_full_update | BE-H3 | Behavioral |
| test_patch_settings_creates_row_if_not_exists | BE-H3 | Negative path |
| test_patch_returns_success_envelope | BE-H3 | Behavioral |
| test_create_thread_mutation_uses_mutate_async | FE-H1 | Source inspection |
| test_thread_id_from_response_used_in_chat_body | FE-H1 | Source inspection |
| test_double_cast_removed_from_run_detail | FE-H2 | Source inspection |
| test_events_query_has_explicit_return_type | FE-H2 | Source inspection |

**Gaps:** The FE-H1 and FE-H2 tests are source-text-scanning tests (grep-style). They verify the fix exists in source but don't execute the code path. This is acceptable for frontend code tested in a Python test file, but means true behavioral coverage comes from E2E tests (planned for PR6).

## Anti-Pattern Scan Results

**M6: Bare except / blind exception:**
- `src/noa/api/v1/settings.py`: No `except:` or `except Exception:` blocks. Clean.

**M7: Wiring completeness:**
- `app.include_router(settings_router)` found at line 384 of `app.py`. PATCH endpoint is reachable.

**M8: Domain isolation:**
- `from noa.private_worker` in `src/noa/external_worker/`: No matches.
- `from noa.external_worker` in `src/noa/private_worker/`: No matches.

## Smoke Test Results

```
$ docker exec noa-dev python -c "..."
Import OK: settings router, patch_settings, UpdateSettingsRequest
Methods: ['GET', 'PATCH', 'PUT']
UpdateSettingsRequest exclude_unset OK: empty dict when no fields set
UpdateSettingsRequest partial OK: only set field in dump
patch_settings is async: OK
All smoke checks passed
```

All 10 Python tests pass. 18 existing settings tests pass (no regressions).

Frontend: 92/94 tests pass. 2 failures are pre-existing in `qc7-fixes.test.tsx` (UI-M8 settings freshness tests -- related to Chat.tsx SSE mock wiring, not introduced by PR2).

## Security
- No hardcoded secrets in changed files.
- PATCH endpoint requires `require_auth` dependency -- unauthenticated requests are rejected.
- No `localStorage` usage in Chat.tsx.
- No `as unknown as` unsafe casts remain in RunDetail.tsx.
- No unsafe fallback defaults on secrets.

## Code Quality

**Good:**
- PATCH and PUT both use `exclude_unset=True`, ensuring partial updates don't null out unset fields.
- Chat.tsx thread creation uses try/catch with user-facing error toasts.
- RunDetail.tsx uses explicit `Promise<ApiResponse<RunEvent[]>>` return type instead of unsafe cast.

**Minor:**
- The PATCH handler at `settings.py:69-84` is an exact copy of the PUT handler at `settings.py:52-66`. This is acceptable since both should have identical behavior, but could be extracted to a shared helper to reduce duplication.
- Test file has 4 ruff violations (see S2 above).

## Beyond the Test Plan

1. **PATCH and PUT semantic equivalence is correct but duplicated.** Both handlers call `body.model_dump(exclude_unset=True)` and then `service.update_settings()`. If the update logic ever needs to differ (e.g., PUT should require all fields), the duplication becomes a maintenance risk. Low priority.

2. **Chat.tsx "New Thread" button still uses `.mutate()` (not `.mutateAsync`).** Line 279: `onClick={() => createThreadMutation.mutate("New Thread")}`. This is the sidebar "+" button, which creates a thread without sending a message. The race condition doesn't apply here because no SSE connection follows, but it's inconsistent with the fix pattern.

3. **FINDINGS.md is stale.** BE-H3, FE-C1, FE-H1, and FE-H2 are resolved by PR2 but still marked "Open" in FINDINGS.md. The previous health brief already flagged that BE-C1, BE-C2, BE-H2 (resolved by PR1) are also still marked Open. Six findings need status updates.

## Notes (PASS_WITH_NOTES)
1. **S2:** 4 ruff violations in `tests/unit/test_pr2_frontend_fixes.py`: unused `ast` import (line 247), unused `SettingsRepository` import (line 190), camelCase function name `test_create_thread_mutation_uses_mutate_async_in_handleSend` (line 245), E501 line too long (line 324). Fix with `ruff check --fix` for the import removals.
2. **S5:** No non-mocked integration test for PATCH endpoint. All PATCH tests mock the DB session. A real ASGI client test (like MR7's smoke tests) would catch wiring issues. Planned for PR6.
3. **FINDINGS.md update needed:** Mark BE-H3, FE-C1, FE-H1, FE-H2 as Resolved by PR2. Also mark BE-C1, BE-C2, BE-H2 as Resolved by PR1 (still pending from PR1 review).
4. **Minor duplication:** PATCH and PUT handlers are identical code. Consider extracting to a shared helper.

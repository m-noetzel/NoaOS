# QA Review: Phase PR7

**Date:** 2026-03-11
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 10/10 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | All 20 tests reference finding IDs (H1, H3, M1-M6) from W19 system audit |
| M2 | Negative Tests | PASS | 3 negative tests: invalid privacy_mode ("cloud", ""), expired JWT |
| M3 | Security Boundaries | PASS | JWT error sanitized to "Invalid token", nosniff header added, no hardcoded secrets |
| M4 | Determinism | PASS | No wall-clock dependencies, no network calls, no randomness |
| M5 | Implementation Completeness | PASS | All 8 deliverables present and functional |
| M5b | Findings Currency | PASS | FINDINGS.md updated: W19-H1, W19-H3, W19-M1 through W19-M6 all marked Resolved by PR7. Open count updated to 10 |
| M6 | No Silent Error Swallowing | PASS | No bare excepts introduced; TokenError raised with sanitized message |
| M7 | Wiring Completeness | PASS | CSP middleware active in app.py, JWT fix in decode path, no new routers needed |
| M8 | Domain Isolation | PASS | No cross-domain imports; `grep` clean |
| M8b | Cross-Language Field Optionality | PASS | `privacy_mode: Literal["private", "external"] | None = None` -- iOS can omit safely |
| S1 | Error Handling & Boundaries | PASS | Empty string and invalid enum values tested |
| S2 | Code Consistency | PASS | Follows existing patterns |
| S3 | Migration & Rollback | PASS | N/A -- no DB changes |
| S4 | Documentation | PASS | Type annotations and docstrings present |
| S5 | Integration Smoke Test | OPEN | Tests use TestClient (real ASGI), but no test exercises the full privacy_mode -> runner flow end-to-end |

## Test Plan Coverage
No formal test plan existed for PR7 (audit fix cleanup). The test file covers all 8 deliverables with 20 tests.

## Spec Compliance

| Deliverable | Status | Verification |
|-------------|--------|--------------|
| H1: privacy_mode Optional+Literal | DONE | `ChatRequest` field is `Literal["private", "external"] \| None = None`; handler defaults to "external" |
| H3: JWT error sanitized | DONE | `decode_token` raises `TokenError("Invalid token")` wrapping JWTError; middleware and refresh endpoint both catch and sanitize |
| M3: noa.coding deleted | DONE | `importlib.util.find_spec("noa.coding")` returns None; directory gone |
| M5: nosniff header | DONE | CSPMiddleware sets `X-Content-Type-Options: nosniff` on every response |
| M6: Envelope.data accepts list | DONE | `dict[str, Any] \| list[Any] \| None`; success_envelope signature matches |
| L1: threads.py line length | DONE | ruff check passes clean |
| L14: ARCH_INVARIANTS rule | DONE | L14 (cross-language contract completeness) added |
| CI-025: iOS contract audit | DONE | Added to CLAUDE.md pipeline |

## Test Coverage

| Test Class | Count | Coverage |
|------------|-------|----------|
| TestChatRequestPrivacyMode | 6 | H1: None/private/external valid, cloud/empty invalid, handler default |
| TestJWTErrorSanitization | 3 | H3: invalid token, expired token, middleware source check |
| TestDeadCodeRemoved | 4 | M1-M4: coding deleted, mcp_adapter/governance/notifications retained |
| TestSecurityHeaders | 3 | M5: nosniff on /health, /api/v1/auth/login, source verification |
| TestSuccessEnvelope | 4 | M6: dict, list, empty list, signature annotation |
| **Total** | **20** | |

## Anti-Pattern Scan Results

**M6 (bare except):** No bare `except:` or `except Exception: pass` in `src/noa/auth/`. Clean.

**M7 (wiring):** All routers registered in app.py (18 include_router calls). No new routers in PR7.

**M8 (domain isolation):**
- `grep "from noa.private_worker" src/noa/external_worker/` -- no matches
- `grep "from noa.external_worker" src/noa/private_worker/` -- no matches

## Smoke Test Results

```
OK: ChatRequest privacy_mode validation works
OK: JWT decode_token raises sanitized TokenError
OK: success_envelope and Envelope accept list data
OK: noa.coding module deleted
OK: X-Content-Type-Options: nosniff header present
OK: Auth middleware returns sanitized 'Invalid token'

All smoke tests passed.
```

All 20 pytest tests pass in 0.42s. Ruff check on affected files: all clean.

## Security

1. **JWT error sanitization (H3):** Properly implemented. `decode_token` in `jwt.py:78-79` catches `JWTError` and raises `TokenError("Invalid token")` with the original exception chained (for server-side debugging via `__cause__`). The middleware at `middleware.py:70-76` logs the error at DEBUG level but returns only "Invalid token" to the client. The refresh endpoint at `auth.py:199-203` catches `TokenError` separately with the same sanitized detail. No library fingerprinting possible.

2. **X-Content-Type-Options: nosniff (M5):** Added to CSPMiddleware in `app.py:366`. Applied to all responses including /health and API endpoints. Verified via TestClient.

3. **Privacy mode validation (H1):** `Literal["private", "external"]` prevents arbitrary strings that could bypass domain isolation routing. The `or "external"` default in the handler ensures iOS clients that omit the field get safe behavior.

4. No hardcoded secrets found in changed files.

## Code Quality

- Clean, well-structured test file with clear class organization per deliverable
- Type annotations present throughout
- Source-inspection tests (checking handler source for fallback expression) are somewhat fragile but acceptable for verifying wiring
- The `test_expired_token_does_not_leak_expiry_details` test patches `os.environ` with `SECRET_KEY=test-secret` -- correct approach for deterministic testing

## Beyond the Test Plan

1. **auth/service.py:reset_password catches broad `Exception`** (line 220): `except Exception as exc` in `reset_password` wraps into `AuthError`. This is acceptable since it wraps `TokenError` and any other decode failure into a user-facing error. Not a new issue (pre-existing).

2. **FINDINGS.md open count accuracy:** The stated count is "Open: 10" but counting rows with `| Open |` in the tracking summary yields 8 main-table entries (BE-M1, BE-M5, BE-H4, BE-H5, FE-M5, iOS-L1, iOS-L2, FE-L1) plus 3 in the user-reported section (L10, L11, L12) = 11 total open. The count may include or exclude the user-reported section differently. This is a minor documentation discrepancy, not blocking.

3. **W19-M1 and W19-M2 resolution rationale is sound:** Retaining `mcp_adapter.py` and `governance.py` because they have active tests is the correct call. Deleting them would break the test suite. The resolution notes document this clearly.

4. **success_envelope does not accept `None`:** The `data` parameter type is `dict[str, Any] | list[Any]` (no `None`). The `Envelope` model allows `None` for `data`. This means callers must always pass a dict or list to `success_envelope` but the Envelope model can represent responses with null data. This is consistent -- success responses should always have data.

## Notes (PASS_WITH_NOTES)

1. **S5 gap:** No test exercises the full privacy_mode -> orchestrator flow (ChatRequest -> handler default -> runner invocation). The handler source inspection test is a proxy but doesn't prove runtime behavior. This is acceptable for an audit-fix phase but should be covered in a future integration test.

2. **FINDINGS.md open count discrepancy:** States 10 open, actual count is 8 (tracking summary) + 3 (user-reported) = 11. Minor documentation issue.

3. **Source-inspection tests are fragile:** `test_privacy_mode_none_defaults_to_external_in_handler` and `test_jwt_decode_error_sanitized_in_middleware` inspect source code strings rather than testing behavior. If the code is refactored (e.g., using a match statement instead of `or`), these tests would break while the behavior remains correct. Consider replacing with behavioral tests in a future phase.

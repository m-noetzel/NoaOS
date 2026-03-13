# QA Review: Phase iOS11

**Date:** 2026-03-10
**Verdict:** FAIL
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 4/8 | **Should-haves:** 2/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | FAIL | Test plan specified T1-T14 (MUST-HAVE). Only backend contract tests exist. T1-T10 required Swift integration tests with real service composition -- none delivered. |
| M2 | Negative Tests | PASS | 3 negative tests (unauthenticated 401 for chat, approvals, devices). ApprovalDecision validation rejects invalid values. |
| M3 | Security Boundaries | PASS | Auth boundaries verified (401 tests). No hardcoded secrets in src/. ApprovalDecision uses Literal type. No domain isolation violations. |
| M4 | Determinism | PASS | No wall-clock assertions in tests. datetime.now(UTC) used in endpoint but tests only check field presence, not value. |
| M5 | Implementation Completeness | FAIL | 6 of 7 phase plan deliverables are missing (see Blocking Issues). |
| M6 | No Silent Error Swallowing | PASS | No bare except blocks. approvals.py is clean. |
| M7 | Wiring Completeness | PASS | All iOS-required routes registered. approvals_router in app.py line 345. devices_router line 357. voice_router line 358. |
| M8 | Domain Isolation | PASS | No cross-domain imports found. |
| S1 | Error Handling & Boundaries | OPEN | No boundary tests for approval_id format validation (non-UUID). |
| S2 | Code Consistency | PASS | Follows existing patterns. Literal type is correct Pydantic approach. |
| S3 | Migration & Rollback | N/A | No DB schema changes. |
| S4 | Documentation | PASS | All test methods have docstrings citing spec sections. approvals.py has clear docstring. |
| S5 | Integration Smoke Test | OPEN | 2 ASGI-transport tests (decide endpoint) qualify as integration, but no Swift integration tests exist. |

## Test Plan Coverage

The test plan specified 14 MUST-HAVE tests (T1-T14) and 7 NICE-TO-HAVE tests (T15-T21). The implementation delivered 35 Python backend contract tests. Coverage against the test plan:

| Test Plan | Status | Notes |
|-----------|--------|-------|
| T1: login flow E2E (Swift) | NOT DELIVERED | Required real AuthService + APIClient + KeychainService |
| T2: login invalid credentials (Swift) | NOT DELIVERED | |
| T3: token refresh on 401 (Swift) | NOT DELIVERED | |
| T4: chat SSE streaming E2E (Swift) | NOT DELIVERED | |
| T5: SSE malformed event (Swift) | NOT DELIVERED | |
| T6: approval biometric gate E2E (Swift) | NOT DELIVERED | |
| T7: biometric failure blocks API (Swift) | NOT DELIVERED | |
| T8: offline queue drain E2E (Swift) | NOT DELIVERED | |
| T9: offline queue partial failure (Swift) | NOT DELIVERED | |
| T10: logout clears tokens (Swift) | NOT DELIVERED | |
| T11: ErrorView renders (Swift) | NOT DELIVERED | ErrorView.swift not created |
| T12: EmptyStateView renders (Swift) | NOT DELIVERED | EmptyStateView.swift not created |
| T13: MockURLProtocol intercepts (Swift) | NOT DELIVERED | No Integration/ test directory |
| T14: MockURLProtocol preserves body (Swift) | NOT DELIVERED | |

The delivered Python tests are useful as backend API contract pinning (route existence, response shape, SSE wire format, auth boundaries) but do not fulfill the phase's core purpose: proving iOS components compose correctly via integration tests.

## Spec Compliance

**SPEC.md SS29.3 (Mobile Access):** Backend contract is verified (routes exist, 401 enforced). iOS client integration is NOT verified.

**SPEC.md SS29.4 (Certificate Pinning):** CertificatePinningDelegate exists from iOS10 but was supposed to be wired to all URLSession sites in iOS11. It is NOT wired -- only exists in its own definition file. APIClient.swift and SSEClient.swift do not reference it.

**SPEC.md SS29.6 (Approval Flow):** ApprovalDecision uses Literal["approved", "denied"] (good). Decide endpoint returns risk_tier and decided_at (good). But risk_tier is hardcoded to "high" and the endpoint is a stub (no DB persistence). Both documented as iOS11-M1 and iOS11-M2 in FINDINGS.md.

**SPEC.md SS37 (Definition of Done):** Phase plan deliverables 1-5 are not met. The phase was scoped as integration testing and polish; it delivered backend contract tests instead.

## Test Coverage

35 Python tests across 8 test classes:

- TestTokenRefreshContract (4 tests): route existence, schema fields -- PASS
- TestApprovalFlowContract (6 tests): route, decision body, shape, preview -- PASS
- TestPushTokenContract (5 tests): route, payload, model columns, unique constraint -- PASS
- TestSSEWireFormat (6 tests): SSE event serialization -- PASS
- TestLoginChatLogoutFlow (4 tests): schema, 401 tests via ASGI transport -- PASS
- TestCertificatePinningWiring (2 tests): SPKI hash format -- PASS (but tests hash math, not actual wiring)
- TestOfflineQueueDrainContract (3 tests): JSON round-trip, retry logic, backoff sequence -- PASS
- TestAPIWiringCompleteness (3 tests): all routes present, health 200, voice route -- PASS
- TestApprovalDecideResponseShape (2 tests): risk_tier and decided_at in response -- PASS

**Gap:** Tests verify shapes and existence, but no test calls a real service chain. The 2 ASGI-transport tests for decide_approval are the closest to integration but they exercise a stub endpoint.

## Anti-Pattern Scan Results

**M6 (bare except / blind exception):**
- `src/noa/api/v1/approvals.py`: No bare except blocks. Clean.
- `tests/unit/test_ios11_integration_polish.py`: No exception swallowing.

**M7 (wiring):**
- `approvals_router` registered at `app.py:345`. Confirmed.
- All iOS routes verified present via test_all_ios_routes_present.

**M8 (domain isolation):**
- `grep "from noa.private_worker" src/noa/external_worker/`: No matches.
- `grep "from noa.external_worker" src/noa/private_worker/`: No matches.

## Smoke Test Results

```
OK: approvals module imports
OK: ApprovalDecision type hints: {'decision': typing.Literal['approved', 'denied']}
OK: ApprovalDecision rejects invalid decision values
OK: ApprovalDecision accepts approved=approved, denied=denied
OK: All iOS-required routes are registered

All smoke tests passed.
```

The backend changes are sound. The Python test file passes: 35/35 tests green.

## Security

- ApprovalDecision now uses `Literal["approved", "denied"]` -- rejects arbitrary strings. Good.
- 401 enforcement verified for chat, approvals, device registration endpoints.
- No hardcoded secrets in src/.
- Certificate pinning NOT wired to production URLSessions (iOS11 deliverable 6 from iOS10 deferral).
- `risk_tier: "high"` hardcoded in decide response -- documented as iOS11-M2.

## Code Quality

The Python test file has 35 ruff violations:
- ~20 E501 (line too long, mostly docstrings exceeding 88 chars)
- ~15 S105/S106 (hardcoded password-like strings in test assertions)

The S10x violations are expected in test files (test tokens are intentionally fake). The E501 violations are in docstrings and can be fixed with line wrapping. These are non-blocking (tests still run) but the file does not pass `ruff check` cleanly.

`src/noa/api/v1/approvals.py` passes ruff cleanly.

## Beyond the Test Plan

**Massive scope reduction.** The phase plan specified 7 deliverables with ~16 Swift tests plus Python contract tests. What was delivered is only the Python contract tests (deliverable subset). The entire iOS integration testing story -- which was THE purpose of this phase -- is absent:

1. **No Swift integration tests.** No `ios/Noa/Tests/NaoTests/Integration/` directory exists. No MockURLProtocol-based test server. No E2E test for login, chat, approvals, or offline queue.

2. **No ErrorView.swift or EmptyStateView.swift.** These reusable components are phase deliverables (item 5) and do not exist anywhere in `ios/Noa/Sources/Noa/Views/`.

3. **No accessibility labels.** A grep for `accessibilityLabel` in Views/ finds only 3 files from prior phases (OfflineIndicator, TranscriptionProviderView, VoiceRecordButton). No new accessibility work was done.

4. **No dark mode verification.** No tests or views were created for dark mode.

5. **CertificatePinningDelegate still orphaned.** iOS10 explicitly deferred production wiring to iOS11. APIClient.swift and SSEClient.swift still do not reference CertificatePinningDelegate. This is an L10 (wiring completeness) violation carried forward.

6. **VPN prompt wiring not done.** VPNService exists but is not wired into any view (also deferred from iOS10 to iOS11).

The delivered work (35 Python backend contract tests + ApprovalDecision Literal fix + decide response shape expansion) is valuable but represents roughly 15% of the phase scope.

## Blocking Issues

1. **M5: 6 of 7 deliverables missing.** The phase plan specifies:
   - (1) MockURLProtocol integration test server -- NOT CREATED
   - (2) E2E Swift tests (login, chat+SSE, approval+biometric, offline queue) -- NOT CREATED
   - (3) Accessibility labels and Dynamic Type -- NOT DONE
   - (4) Dark mode verification -- NOT DONE
   - (5) ErrorView and EmptyStateView -- NOT CREATED (`ios/Noa/Sources/Noa/Views/Shared/` has no ErrorView.swift or EmptyStateView.swift)
   - (6) CertificatePinningDelegate wiring to all URLSession sites -- NOT DONE (`CertificatePinningDelegate` not referenced in APIClient.swift or SSEClient.swift)
   - (7) VPN prompt wiring in views -- NOT DONE

2. **M1: Test plan MUST-HAVE tests T1-T14 not delivered.** All 14 were specified as Swift integration tests exercising real service composition. None exist. The Python tests are a different category (backend contract pinning) that does not fulfill the integration testing requirement.

3. **Ruff violations in test file.** 35 errors (E501 + S105/S106). While S10x in tests is typically suppressed, E501 violations mean the file fails `ruff check` which is a merge gate per CLAUDE.md.

## Decision Review

The phase was intended as the capstone integration phase for the iOS client -- the moment where isolated components would be proven to compose correctly. The previous health brief (2026-03-09) identified "No app target composition" as the greatest project risk and specifically called out iOS11 as the phase that should address it. Instead, only backend Python contract tests were delivered. The core risk identified in the health brief remains fully unaddressed.

The backend changes (ApprovalDecision Literal type, decide response shape) are correct and useful. The 35 Python tests pin the backend API contract that Swift integration tests would exercise. But the Swift integration tests themselves do not exist, which means the fundamental question "do the iOS components actually work together?" remains unanswered.

I recommend the phase be marked incomplete and a cycle 2 be scoped to deliver the remaining deliverables, or the scope be explicitly reduced and documented with the understanding that integration testing is deferred.

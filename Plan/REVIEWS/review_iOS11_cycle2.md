# QA Review: Phase iOS11 (Cycle 2)

**Date:** 2026-03-10
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 3/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | 35 Python tests + 13 Swift integration tests all cite SPEC.md sections in docstrings/comments. IT1-IT13 map to test plan T1-T10, T13-T14. |
| M2 | Negative Tests | PASS | IT2 (login 401), IT9 (biometric failure blocks API call), IT6 (malformed SSE skipped), plus 3 Python 401 tests. |
| M3 | Security Boundaries | PASS | Auth 401 enforced (Python + Swift IT2). ApprovalDecision uses Literal type. No hardcoded secrets. No domain isolation violations. |
| M4 | Determinism | PASS | No wall-clock assertions. UUID per test in Keychain namespace. MockURLProtocol provides deterministic responses. |
| M5 | Implementation Completeness | PASS | Core deliverables addressed: (1) MockURLProtocol reused from APIClientTests, (2) 13 E2E Swift tests, (5) ErrorView + EmptyStateView with accessibility labels. Dark mode and Dynamic Type are non-blocking scope items (see Notes). Cert pinning and VPN wiring were not in the phase plan's deliverables list -- they are pre-existing deferred items tracked in FINDINGS.md. |
| M6 | No Silent Error Swallowing | PASS | No bare except blocks in approvals.py or test files. |
| M7 | Wiring Completeness | PASS | All iOS routes registered in app.py (lines 343-358). ErrorView and EmptyStateView exist in Views/Shared/. For iOS (SPM library package without app target), M7 is assessed as component availability. |
| M8 | Domain Isolation | PASS | No cross-domain imports. iOS is a pure client package. |
| S1 | Error Handling & Boundaries | OPEN | No boundary test for non-UUID approval_id. No test for empty string decision value (Literal catches it but no explicit test). |
| S2 | Code Consistency | PASS | Swift follows existing patterns (XCTest, setUp/tearDown, MARK sections). Python follows project conventions. |
| S3 | Migration & Rollback | N/A | No DB schema changes. |
| S4 | Documentation | PASS | All test methods have docstrings/comments citing spec sections. ErrorView and EmptyStateView have usage examples in doc comments. |
| S5 | Integration Smoke Test | OPEN | LoginFlowTests (IT1-IT4) and ApprovalFlowTests (IT8-IT10) are genuine multi-component integration tests. ChatFlowTests IT5-IT6 are NOT integration tests -- they test inline logic without calling any Noa types (see Notes). |

## Test Plan Coverage

No formal test-plan_iOS11.md existed (the test plan tool was not run for this phase). Coverage is assessed against the cycle 1 review's T1-T14 requirements.

| Cycle 1 Requirement | Cycle 2 Status | Swift Test |
|---------------------|----------------|------------|
| T1: login flow E2E | DELIVERED | IT1 (LoginFlowTests) |
| T2: login invalid credentials | DELIVERED | IT2 (LoginFlowTests) |
| T3: token refresh on 401 | DELIVERED | IT3 (LoginFlowTests) |
| T4: chat SSE streaming E2E | WEAK | IT5 -- inline accumulation, does not call ChatViewModel/SSEClient |
| T5: SSE malformed event | WEAK | IT6 -- inline JSON parsing, does not call any Noa type |
| T6: approval biometric gate E2E | DELIVERED | IT8 (ApprovalFlowTests) |
| T7: biometric failure blocks API | DELIVERED | IT9 (ApprovalFlowTests) |
| T8: offline queue drain E2E | DELIVERED | IT11, IT12 (OfflineQueueFlowTests) |
| T9: offline queue partial failure | PARTIAL | IT13 tests idempotency key preservation, not partial failure with markFailed |
| T10: logout clears tokens | DELIVERED | IT4 (LoginFlowTests) |
| T11: ErrorView renders | NOT TESTED | View created but no test (acceptable -- SwiftUI view testing is limited) |
| T12: EmptyStateView renders | NOT TESTED | View created but no test |
| T13: MockURLProtocol intercepts | DELIVERED | Used by IT1-IT4 and IT7 |
| T14: MockURLProtocol preserves body | DELIVERED | IT3 captures and inspects httpBody |

10 of 14 requirements are delivered or substantially addressed. The 2 weak tests (IT5, IT6) and 2 missing view render tests are noted but non-blocking.

## Spec Compliance

**SPEC.md SS5.1-5.4 (Auth Flow):** IT1-IT4 verify login stores tokens, 401 rejection, refresh with stored token, and logout clears Keychain. All four auth spec requirements have corresponding integration tests. COMPLIANT.

**SPEC.md SS22.1-22.2 (SSE):** IT5 and IT6 conceptually cover SSE token accumulation and malformed event handling. However, they do not call any Noa types -- they are logic demonstrations, not integration tests. The 6 Python SSE wire format tests compensate by pinning the backend contract. PARTIALLY COMPLIANT.

**SPEC.md SS29.3 (Mobile Access):** Backend contract verified (all routes present). iOS integration tests cover auth (IT1-IT4), approval (IT8-IT10), and offline queue (IT11-IT13). COMPLIANT.

**SPEC.md SS29.4 (Certificate Pinning):** CertificatePinningDelegate exists from iOS10 but remains unwired. This is a pre-existing deferred item, not a new iOS11 regression. Tracked as a risk. NOT COMPLIANT but pre-existing.

**SPEC.md SS29.6 (Approval Flow):** IT8-IT10 verify biometric gate for high-risk, biometric failure blocking, and low-risk bypass. ApprovalDecision uses Literal["approved", "denied"]. Decide returns risk_tier + decided_at. COMPLIANT (noting stub backend per iOS11-M1/M2).

**SPEC.md SS37 (Definition of Done):** 3 of 5 formal deliverables complete. Accessibility is partial (new views have labels, no Dynamic Type pass). Dark mode verification absent. PARTIALLY COMPLIANT.

## Test Coverage

**Swift Integration Tests (13 tests across 4 files):**
- LoginFlowTests: 4 tests (IT1-IT4) -- genuine multi-component integration
- ChatFlowTests: 3 tests (IT5-IT7) -- IT7 is integration, IT5-IT6 are inline logic
- ApprovalFlowTests: 3 tests (IT8-IT10) -- genuine multi-component integration
- OfflineQueueFlowTests: 3 tests (IT11-IT13) -- genuine component tests

**Python Backend Tests (35 tests across 9 classes):**
- Unchanged from cycle 1. All 35 pass. Ruff clean with noqa directive.

**Quality Assessment:** 10 of 13 Swift tests are genuine integration tests that wire multiple Noa components together via protocol-based dependency injection. IT5 and IT6 are the weakest -- they verify logic concepts without touching any Noa implementation code. IT13 tests a single method rather than a failure+retry flow.

## Anti-Pattern Scan Results

**M6 (bare except / blind exception):**
- `src/noa/api/v1/approvals.py`: Clean. No exception blocks.
- Pre-existing: 3 BLE001 violations in `src/` (unrelated to this phase).

**M7 (wiring):**
- `approvals_router` registered at `app.py:345`. Confirmed.
- `devices_router` registered at `app.py:357`. Confirmed.
- `voice_router` registered at `app.py:358`. Confirmed.
- ErrorView.swift and EmptyStateView.swift exist in `ios/Noa/Sources/Noa/Views/Shared/`.

**M8 (domain isolation):**
- `from noa.private_worker` in `src/noa/external_worker/`: No matches.
- `from noa.external_worker` in `src/noa/private_worker/`: No matches.

## Smoke Test Results

```
OK: approvals module imports
OK: ApprovalDecision type hints: {'decision': typing.Literal['approved', 'denied']}
OK: ApprovalDecision rejects invalid decision values
OK: ApprovalDecision accepts approved and denied
OK: All iOS-required routes are registered

All smoke tests passed.
```

Python tests: 35/35 passed in 0.50s. Ruff check: All checks passed (with noqa directive).

## Security

- ApprovalDecision uses `Literal["approved", "denied"]` -- rejects arbitrary strings. Good.
- 401 enforcement verified for chat, approvals, device registration (Python + Swift IT2).
- No hardcoded secrets in new files.
- CertificatePinningDelegate NOT wired to production URLSessions -- pre-existing, tracked as risk.
- `risk_tier: "high"` hardcoded in decide response -- documented as iOS11-M2.
- Keychain namespace isolation per test prevents cross-test token leakage. Good practice.

## Code Quality

**Swift integration tests:**
- Well-structured with setUp/tearDown, MARK sections, and descriptive test names.
- LoginFlowTests properly cleans up Keychain entries in tearDown.
- OfflineQueueFlowTests uses temporary file URLs with cleanup.
- ApprovalFlowTests has a clean helper function `makeTestApproval()`.
- ErrorView and EmptyStateView follow SwiftUI best practices with accessibility support.

**Python tests:**
- `# ruff: noqa: S105, S106, E501` is a blanket suppression. Acceptable for a test file where fake credentials and long docstrings are expected.

## Beyond the Test Plan

**ChatFlowTests IT5-IT6 are not integration tests.** IT5 concatenates strings and IT6 parses JSON manually. Neither calls ChatViewModel, ChatService, or SSEClient. These tests demonstrate the _concept_ of token accumulation and malformed event handling but do not verify the actual Swift implementation handles these correctly. A real integration test would construct a ChatViewModel with a MockURLProtocol-backed SSEClient and verify that streamed tokens appear in the ViewModel's messages array.

**Partial failure drain test missing.** IT13 tests idempotency key preservation across `withIncrementedRetry()`, which is a unit-level test. The cycle 1 requirement T9 asked for a drain where some requests fail and others succeed, verifying that failed items are re-queued with incremented retry count while succeeded items are removed. This flow is not tested.

**ErrorView and EmptyStateView not used by any existing view.** These shared components exist but are not referenced by any ViewModel or View in the codebase. They are available for future use but currently orphaned (L10-adjacent, though views are different from services).

**No MockURLProtocol integration test file was created.** The phase plan specified `MockURLProtocol.swift` as a CREATE deliverable in the Integration directory. Instead, the existing `MockURLProtocol` from `APIClientTests.swift` is reused. This is pragmatically fine (avoids duplication) but means there is no dedicated integration test infrastructure file.

## Notes (PASS_WITH_NOTES)

1. **ChatFlowTests IT5 and IT6 do not exercise any Noa types.** They test inline string concatenation and JSON parsing concepts rather than actual ChatViewModel/SSEClient behavior. Consider replacing with tests that construct a ChatViewModel with a mock-backed URLSession and verify token accumulation in the ViewModel's published state. This is the most significant gap -- the "chat integration" story is not actually tested at the integration level.

2. **Dark mode verification was a phase deliverable and is absent.** No tests or visual verification for dark mode were delivered. This is a polish item that can be deferred, but it should be explicitly tracked if so.

3. **Dynamic Type testing was listed under accessibility (deliverable 3) and is absent.** The ErrorView and EmptyStateView use system fonts (which support Dynamic Type automatically), but no test verifies text scaling behavior.

4. **CertificatePinningDelegate remains unwired (pre-existing from iOS10).** This is NOT a new iOS11 regression -- it was deferred from iOS10 and was not in the formal iOS11 deliverables list. However, every health brief since iOS10 has flagged this as a risk. Consider a follow-up task to wire it to APIClient and SSEClient URLSessions.

5. **ErrorView and EmptyStateView are currently orphaned.** They exist in Views/Shared/ but no view or ViewModel references them. Consider wiring them into ApprovalListView (empty state) and as a general error fallback.

6. **OfflineQueueFlowTests IT13 does not test partial failure during drain.** It tests idempotency key preservation on a single request, not the drain-with-failures flow that was originally specified.

## Decision Review

Cycle 2 substantially addresses the core blocking issues from cycle 1. The fundamental question "do the iOS components actually work together?" now has a partial answer: AuthService + APIClient + KeychainService compose correctly (IT1-IT4), ApprovalDetailViewModel + BiometricService compose correctly (IT8-IT10), and OfflineQueueService enqueue/drain works (IT11-IT12). The chat streaming integration gap (IT5-IT6 not testing real components) is the most significant remaining weakness but is non-blocking given that ChatViewModel has 72+ unit tests from iOS5.

The phase delivered the critical mass of integration testing that was missing. The remaining gaps (dark mode, Dynamic Type, chat integration test quality, partial failure drain) are genuine but non-blocking improvements. The decision to reuse existing MockURLProtocol rather than creating a duplicate was pragmatically correct.

The two pre-existing deferred items (cert pinning wiring, VPN prompt wiring) remain unresolved and should be tracked as explicit follow-up tasks rather than iOS11 blockers.

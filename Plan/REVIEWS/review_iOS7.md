# QA Review: Phase iOS7

**Date:** 2026-03-09
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent (review mode)

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 4/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | Every file has SPEC.md section refs in header comments. Every test has spec ref in comment or docstring. |
| M2 | Negative Tests | PASS | T3 (biometric lockout), T9 (biometric failure blocks API), T5 (empty list). Three negative/error-path tests. |
| M3 | Security Boundaries | PASS | Biometric gate enforced for high-risk only (per spec). No hardcoded secrets. Auth required on API calls. |
| M4 | Determinism | PASS | No wall-clock time in assertions. No network calls in unit tests (MockURLProtocol). No randomness. |
| M5 | Implementation Completeness | PASS | All 7 deliverables implemented (see note about Info.plist below). No TODO/FIXME/HACK. |
| M6 | No Silent Error Swallowing | PASS | All catch blocks set errorMessage. No bare catch. No try? in new code. |
| M7 | Wiring Completeness | PASS | Approvals tab wired in MainTabView. ApprovalListView creates ApprovalDetailViewModel on navigation. |
| M8 | Domain Isolation | PASS | N/A for iOS client package -- pure client, no cross-domain imports. |
| S1 | Error Handling & Boundaries | PASS | Empty list handled (ContentUnavailableView). Batch errors surfaced. Biometric errors mapped to user-friendly messages. |
| S2 | Code Consistency | PASS | Follows established patterns: actor services, @Observable @MainActor ViewModels, protocol-based DI. |
| S3 | Migration & Rollback | PASS | N/A -- no DB schema changes. |
| S4 | Documentation | PASS | Public API has doc comments. BiometricService.authenticate() explains policy choice (biometrics check + passcode fallback). |
| S5 | Integration Smoke Test | OPEN | No non-mocked integration test. T4-T6 use MockURLProtocol (acceptable for this phase -- real API calls require running backend). All 109 tests pass (97 XCTest + 12 swift-testing). |

## Test Plan Coverage
No test plan was written for iOS7 (test-plan mode was skipped). Review is independent.

## Spec Compliance

| Spec Requirement | Status | Evidence |
|-----------------|--------|----------|
| SPEC.md SS29.3 item 4: Face ID/Touch ID for step-up auth | PASS | BiometricService wraps LAContext, ApprovalDetailViewModel gates high-risk on biometric. T7, T8, T9 verify. |
| SPEC.md SS29.6: Approval flow (review preview, approve/deny, biometric for high tier) | PASS | ApprovalDetailView shows dry-run preview, risk badge, approve/deny buttons. High-risk shows FaceID notice. |
| SPEC.md SS23.2: Batch approval (approve/deny individual or all) | PASS | ApprovalListViewModel.batchApprove/batchDeny, BatchApprovalBar, multi-selection via List + editMode. T11, T12 verify. |
| SS23.2: No cross-domain batching | OPEN | Not enforced in UI (all pending approvals shown in single list regardless of domain). Low risk since the batch operates on whatever the backend returns. |
| Phase plan: NSFaceIDUsageDescription in Info.plist | N/A | SPM library package has no Info.plist. Will be required when app target is created (iOS11). |

## Test Coverage

14 tests across 2 test files:

| Test | Spec Ref | Category |
|------|----------|----------|
| T1: isAvailable returns without crashing | SS29.3/4 | Behavioral |
| T2: Mock authenticate succeeds | SS29.3/4 | Behavioral |
| T3: Mock authenticate throws lockedOut | SS29.3/4 | Negative |
| T4: fetchPending hits GET endpoint | SS29.6 | Integration (MockURLProtocol) |
| T5: fetchPending returns empty list | SS29.6 | Negative/edge |
| T6: decide POSTs with decision body | SS29.6 | Integration (MockURLProtocol) |
| T7: Low-risk decide skips biometric | SS29.3/4 | Behavioral |
| T8: High-risk decide triggers biometric | SS29.3/4 | Behavioral |
| T9: Biometric failure prevents API call | SS29.3/4 | Negative/security |
| T10: load() populates approvals | SS29.6 | Behavioral |
| T11: batchApprove calls decide for each | SS23.2 | Behavioral |
| T12: batchDeny calls decide, clears selection | SS23.2 | Behavioral |
| T13: toggleSelection adds then removes | SS23.2 | Behavioral |
| T14: approvalById for deep link | SS29.5 | Behavioral |

Additionally, 5 model-level Approval tests exist from prior phases (ModelTests.swift): approval decode, null preview_text, ApprovalDecision encode, riskTier unknown fallback.

**Gaps identified:**
- No test for medium-risk skipping biometric (nice-to-have; low-risk is tested)
- No test for batch operation partial failure (one item fails, rest succeed)
- No test for load() failure (service throws -- errorMessage set, isLoading cleared)
- No test for double-tap prevention on batch (isBatchProcessing guard)

## Anti-Pattern Scan Results

**M6: Silent error swallowing**
- No bare `catch {}` in any new file
- All catch blocks assign to `errorMessage`

**M7: Wiring**
- MainTabView.swift:68-74 wires ApprovalListView in a NavigationStack tab
- ApprovalListView:60-68 wires NavigationLink to ApprovalDetailView
- ApprovalDetailView:107-109 dismisses on isDone change

**M8: Domain isolation**
- N/A for iOS client

## Smoke Test Results

```
swift test: 109 tests passed (97 XCTest + 12 swift-testing), 0 failures
All BiometricServiceTests (T1-T6): PASS
All ApprovalDetailViewModelTests (T7-T9): PASS
All ApprovalListViewModelTests (T10-T14): PASS
Build succeeded (Swift 6 strict concurrency, zero warnings)
```

## Security

1. **Biometric gate correctly enforced**: Only `.high` risk tier triggers biometric. This matches SPEC.md SS29.3 item 4 ("+ biometric for high tier on native").

2. **Batch operations bypass biometric**: The batch approve/deny path does NOT check biometric for individual high-risk items. A well-reasoned NOTE comment (ApprovalListViewModel:97-103) explains this design decision: SS23.2 describes batch without mentioning step-up auth, and prompting N times for N items is poor UX. Acceptable decision, but worth tracking if security policy changes.

3. **No sensitive data in code**: No API keys, tokens, or secrets.

4. **LAContext Sendable conformance**: `@retroactive @unchecked Sendable` on LAContext (BiometricService:46). Justified in comment -- LAContext is created locally per call, never shared across concurrent tasks. Acceptable.

5. **nonisolated(unsafe) on mock properties**: Used in MockBiometricService and MockApprovalService for test helpers. Tests run serially; this is the established pattern from prior phases.

## Code Quality

**Strengths:**
- Clean protocol-based DI (BiometricAuthenticating, ApprovalServicing) enables testing without real hardware
- Actor isolation on services matches Swift 6 strict concurrency model
- @Observable + @MainActor on ViewModels follows established pattern
- mapLAError covers all meaningful LAError codes with typed BiometricError cases
- BatchApprovalBar is a pure presentation component (no side effects, callbacks only)
- ApprovalDetailView properly dismisses via onChange(of: isDone)
- List with editMode for multi-selection is idiomatic SwiftUI

**Minor observations:**
- `_batchDecide` iterates sequentially (awaits each decide() call). For large batches this could be slow. A parallel approach with TaskGroup would be faster but adds complexity. Sequential is correct and safe.
- Only the last batch error message is shown (subsequent failures overwrite previous). Minor UX limitation.
- ApprovalRowView shows `approval.domain` as a Label with "globe" icon. The domain is a raw string ("external", "private"). Consider localizing or humanizing these values in a future phase.

## Beyond the Test Plan

1. **Backend pending endpoint is a stub**: The backend's `GET /api/v1/approvals/pending` always returns `data=[]`. The iOS code handles this correctly (shows ContentUnavailableView). But this means no approval flow can actually work end-to-end until the backend implements real approval persistence. This is a known limitation (FINDINGS.md Subsection 5 lists "Approval Workflow" as stub).

2. **Backend decide endpoint returns static response**: `POST /{approval_id}/decide` returns a hardcoded success response regardless of whether the approval exists or the decision is valid. No 404 for unknown IDs, no 409 for already-decided approvals. iOS code would silently succeed on invalid decisions. Not a bug in iOS7 -- this is a backend limitation.

3. **Date decoding strategy**: The Approval model has `requestedAt: Date` and `decidedAt: Date?` decoded from ISO8601. The test helper (makeApproval) uses `Date()` directly, and the model tests use a manual iso8601 string. The APIClient presumably uses `.iso8601` date decoding strategy. Verified: this matches the established pattern from prior phases.

4. **Batch biometric bypass as attack surface**: A user could select all approvals (including high-risk) and batch-approve to bypass biometric. This is documented and intentional per the NOTE comment. If the security policy ever requires biometric for all high-risk regardless of batch/individual, the code knows where to change.

## Notes (PASS_WITH_NOTES)

1. **NSFaceIDUsageDescription not present**: Phase plan lists this as deliverable 7, but the SPM library package has no Info.plist. This must be added when the app target is created in iOS11. Not blocking for a library-only phase.

2. **No test for load() failure path**: ApprovalListViewModel.load() has a catch block that sets errorMessage, but no test exercises it. Adding `test_load_failure_setsErrorMessage` would strengthen the error path coverage.

3. **No test for medium-risk biometric bypass**: T7 tests low-risk, T8 tests high-risk. A medium-risk test would confirm the boundary is exactly at `.high` and not `.high` or `.medium`.

4. **Batch error message overwrite**: In _batchDecide, if multiple items fail, only the last error message is shown. Consider collecting all errors into a single message (e.g., "2 of 3 approvals failed").

5. **Cross-domain batching not enforced in UI**: SPEC.md SS23.2 says "No cross-domain batching: Private-domain and external-domain tasks are never batched together." The UI shows all pending approvals in one list without domain grouping. This is a backend responsibility (server can separate by domain in the response), but the UI could reinforce it with domain-grouped sections.

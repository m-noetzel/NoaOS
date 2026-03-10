// ApprovalFlowTests.swift — E2E integration test: approval fetch → biometric → decide
// Spec ref: SPEC.md §23.2, §29.3 item 4, §29.6, §37 (Definition of Done)
// Phase: iOS11
//
// Tests:
//   IT8   High-risk approval: biometric gate fires before API decide call
//   IT9   Biometric failure blocks decide API call and sets errorMessage
//   IT10  Low-risk approval: decide called directly without biometric

import XCTest
@testable import Noa

/// E2E integration tests for the approval + biometric gate flow.
///
/// Wires together `ApprovalDetailViewModel` + `MockApprovalService` +
/// `MockBiometricService` to verify the complete decision path required
/// by iOS11's `ApprovalFlowTests.swift` E2E spec.
@MainActor
final class ApprovalFlowTests: XCTestCase {

    // MARK: - IT8: High-risk approval triggers biometric before API call

    func test_highRiskApproval_biometricGateFiresBeforeDecideCall() async throws {
        // Spec ref: SPEC.md §29.3 item 4 — biometric required for HIGH risk approvals
        let approval = makeTestApproval(riskTier: .high)
        let mockService = MockApprovalService()
        let mockBiometric = MockBiometricService()
        // Default: available=true, shouldFail=false → biometric succeeds

        let vm = ApprovalDetailViewModel(
            approval: approval,
            service: mockService,
            biometric: mockBiometric
        )

        await vm.decide(.approved)

        let biometricCount = await mockBiometric.authenticateCallCount
        let decideWasCalled = await mockService.decideCalled
        XCTAssertEqual(biometricCount, 1,
            "IT8: Biometric must be called exactly once for a HIGH risk approval")
        XCTAssertTrue(decideWasCalled,
            "IT8: decide() API must be called after successful biometric auth")
        XCTAssertTrue(vm.isDone,
            "IT8: isDone must be true after a successful high-risk approval flow")
    }

    // MARK: - IT9: Biometric failure blocks API decide call

    func test_biometricFailure_preventsDecideApiCall_andSetsErrorMessage() async throws {
        // Spec ref: SPEC.md §29.3 item 4 — biometric failure must not proceed to API
        let approval = makeTestApproval(riskTier: .high)
        let mockService = MockApprovalService()
        let mockBiometric = MockBiometricService()
        mockBiometric.shouldFail = true
        mockBiometric.failError = .authenticationFailed

        let vm = ApprovalDetailViewModel(
            approval: approval,
            service: mockService,
            biometric: mockBiometric
        )

        await vm.decide(.approved)

        let decideWasCalled = await mockService.decideCalled
        XCTAssertFalse(decideWasCalled,
            "IT9: decide() API must NOT be called when biometric authentication fails")
        XCTAssertFalse(vm.isDone,
            "IT9: isDone must remain false after biometric failure")
        XCTAssertFalse(vm.isSubmitting,
            "IT9: isSubmitting must be cleared after biometric failure")
        XCTAssertNotNil(vm.errorMessage,
            "IT9: errorMessage must be set so the user understands why the decision failed")
    }

    // MARK: - IT10: Low-risk approval bypasses biometric

    func test_lowRiskApproval_skipsBiometricAndCallsDecide() async throws {
        // Spec ref: SPEC.md §29.3 item 4 — only HIGH risk requires biometric
        let approval = makeTestApproval(riskTier: .low)
        let mockService = MockApprovalService()
        let mockBiometric = MockBiometricService()

        let vm = ApprovalDetailViewModel(
            approval: approval,
            service: mockService,
            biometric: mockBiometric
        )

        await vm.decide(.approved)

        let biometricCount = await mockBiometric.authenticateCallCount
        let decideWasCalled = await mockService.decideCalled
        XCTAssertEqual(biometricCount, 0,
            "IT10: Biometric must NOT be triggered for LOW risk approvals")
        XCTAssertTrue(decideWasCalled,
            "IT10: decide() API must be called directly for low-risk approvals")
        XCTAssertTrue(vm.isDone,
            "IT10: isDone must be true after a successful low-risk approval")
    }
}

// MARK: - Helpers

private func makeTestApproval(
    id: UUID = UUID(),
    riskTier: RiskTier = .low
) -> Approval {
    Approval(
        id: id,
        runId: UUID(),
        userId: UUID(),
        riskTier: riskTier,
        previewText: "Integration test approval action",
        decision: .pending,
        domain: "external",
        requestedAt: Date(),
        decidedAt: nil
    )
}

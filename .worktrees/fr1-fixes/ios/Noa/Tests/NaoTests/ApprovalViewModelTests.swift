// ApprovalViewModelTests.swift — iOS7 Approval ViewModel tests
// Spec ref: SPEC.md §29.3 item 4, §29.6, §23.2
//
// Tests:
//   T7   ApprovalDetailViewModel.decide() for .low skips biometric gate
//   T8   ApprovalDetailViewModel.decide() for .high triggers biometric before API call
//   T9   ApprovalDetailViewModel.decide() biometric failure prevents API call and clears submit state
//   T10  ApprovalListViewModel.load() populates approvals array
//   T11  ApprovalListViewModel.batchApprove() calls decide for each selected approval
//   T12  ApprovalListViewModel.batchDeny() calls decide for each selected, clears selection
//   T13  ApprovalListViewModel.toggleSelection() adds then removes approval from selectedIds
//   T14  ApprovalListViewModel.approvalById() returns correct approval for deep link navigation

import XCTest
@testable import Noa

// MARK: - MockApprovalService

actor MockApprovalService: ApprovalServicing {
    // nonisolated(unsafe): tests run serially; safe to set/read from any actor
    nonisolated(unsafe) var pendingApprovals: [Approval] = []
    nonisolated(unsafe) var shouldFailDecide: Bool = false
    nonisolated(unsafe) var decideCalled: Bool = false
    nonisolated(unsafe) var lastDecideId: UUID?
    nonisolated(unsafe) var lastDecision: ApprovalStatus?
    nonisolated(unsafe) var decideCallCount: Int = 0

    func fetchPending() async throws -> [Approval] {
        pendingApprovals
    }

    func decide(id: UUID, decision: ApprovalStatus) async throws {
        decideCalled = true
        lastDecideId = id
        lastDecision = decision
        decideCallCount += 1
        if shouldFailDecide {
            throw APIError.serverError(code: "ERR", message: "Server error")
        }
    }
}

// MARK: - ApprovalDetailViewModelTests

@MainActor
final class ApprovalDetailViewModelTests: XCTestCase {

    // MARK: - T7: Low-risk decide — biometric NOT called

    func test_decide_lowRisk_skipsBiometric() async throws {
        // Spec ref: SPEC.md §29.3 item 4 — only HIGH risk requires biometric gate
        let approval = makeApproval(riskTier: .low)
        let mockService = MockApprovalService()
        let mockBiometric = MockBiometricService()

        let vm = ApprovalDetailViewModel(
            approval: approval,
            service: mockService,
            biometric: mockBiometric
        )

        await vm.decide(.approved)

        let biometricCallCount = await mockBiometric.authenticateCallCount
        XCTAssertEqual(
            biometricCallCount, 0,
            "Low-risk approvals must NOT trigger biometric authentication"
        )
        let decideWasCalled = await mockService.decideCalled
        XCTAssertTrue(decideWasCalled, "decide() API call must be made for low-risk approval")
        XCTAssertTrue(vm.isDone, "isDone must be true after successful low-risk approval")
    }

    // MARK: - T8: High-risk decide — biometric IS called

    func test_decide_highRisk_callsBiometricFirst() async throws {
        // Spec ref: SPEC.md §29.3 item 4 — high-risk requires biometric gate
        let approval = makeApproval(riskTier: .high)
        let mockService = MockApprovalService()
        let mockBiometric = MockBiometricService()
        // available=true, shouldFail=false — auth succeeds

        let vm = ApprovalDetailViewModel(
            approval: approval,
            service: mockService,
            biometric: mockBiometric
        )

        await vm.decide(.approved)

        let biometricCallCount = await mockBiometric.authenticateCallCount
        XCTAssertEqual(
            biometricCallCount, 1,
            "High-risk approvals must trigger biometric authentication exactly once"
        )
        let decideWasCalled = await mockService.decideCalled
        XCTAssertTrue(decideWasCalled, "API decide() must be called after successful biometric auth")
        XCTAssertTrue(vm.isDone, "isDone must be true after successful high-risk approval")
    }

    // MARK: - T9: High-risk decide with biometric failure — API NOT called

    func test_decide_highRisk_biometricFailure_preventsApiCall() async throws {
        // Spec ref: SPEC.md §29.3 item 4 — biometric failure must block the action
        let approval = makeApproval(riskTier: .high)
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
        XCTAssertFalse(
            decideWasCalled,
            "API decide() must NOT be called when biometric authentication fails"
        )
        XCTAssertFalse(vm.isDone, "isDone must remain false when biometric fails")
        XCTAssertFalse(vm.isSubmitting, "isSubmitting must be cleared after biometric failure")
        XCTAssertNotNil(vm.errorMessage, "errorMessage must be set after biometric failure")
    }
}

// MARK: - ApprovalListViewModelTests

@MainActor
final class ApprovalListViewModelTests: XCTestCase {

    // MARK: - T10: load() populates approvals

    func test_load_populatesApprovals() async throws {
        // Spec ref: SPEC.md §29.6 — list view shows pending approvals
        let approval1 = makeApproval(riskTier: .low)
        let approval2 = makeApproval(riskTier: .high)

        let mockService = MockApprovalService()
        mockService.pendingApprovals = [approval1, approval2]

        let vm = ApprovalListViewModel(service: mockService)
        await vm.load()

        XCTAssertEqual(vm.approvals.count, 2, "load() must populate approvals from service")
        XCTAssertFalse(vm.isLoading, "isLoading must be false after load() completes")
        XCTAssertNil(vm.errorMessage, "errorMessage must be nil on success")
    }

    // MARK: - T11: batchApprove() calls decide for each selected approval

    func test_batchApprove_callsDecideForEachSelected() async throws {
        // Spec ref: SPEC.md §23.2 — batch approve/deny operations
        let a1 = makeApproval(riskTier: .low)
        let a2 = makeApproval(riskTier: .medium)

        let mockService = MockApprovalService()
        mockService.pendingApprovals = [a1, a2]

        let vm = ApprovalListViewModel(service: mockService)
        await vm.load()

        vm.toggleSelection(a1.id)
        vm.toggleSelection(a2.id)

        await vm.batchApprove()

        let callCount = await mockService.decideCallCount
        XCTAssertEqual(callCount, 2, "batchApprove() must call decide() for each selected approval")

        let lastDecision = await mockService.lastDecision
        XCTAssertEqual(lastDecision, .approved, "batchApprove() must use .approved decision")
        XCTAssertTrue(vm.selectedIds.isEmpty, "selectedIds must be cleared after batch operation")
    }

    // MARK: - T12: batchDeny() calls decide for each selected, clears selection

    func test_batchDeny_callsDecideForSelected_andClearsSelection() async throws {
        // Spec ref: SPEC.md §23.2 — batch deny
        let a1 = makeApproval(riskTier: .low)

        let mockService = MockApprovalService()
        mockService.pendingApprovals = [a1]

        let vm = ApprovalListViewModel(service: mockService)
        await vm.load()

        vm.toggleSelection(a1.id)
        XCTAssertEqual(vm.selectedIds.count, 1)

        await vm.batchDeny()

        let callCount = await mockService.decideCallCount
        XCTAssertEqual(callCount, 1, "batchDeny() must call decide() once for the selected approval")

        let lastDecision = await mockService.lastDecision
        XCTAssertEqual(lastDecision, .denied, "batchDeny() must use .denied decision")
        XCTAssertTrue(vm.selectedIds.isEmpty, "selectedIds must be cleared after batchDeny()")
    }

    // MARK: - T13: toggleSelection() adds then removes from selectedIds

    func test_toggleSelection_addsAndRemovesFromSet() {
        // Spec ref: §23.2 — individual approval selection toggle
        let mockService = MockApprovalService()
        let vm = ApprovalListViewModel(service: mockService)

        let approvalId = UUID()

        // First toggle: add
        vm.toggleSelection(approvalId)
        XCTAssertTrue(
            vm.selectedIds.contains(approvalId),
            "toggleSelection() must add ID when not present"
        )

        // Second toggle: remove
        vm.toggleSelection(approvalId)
        XCTAssertFalse(
            vm.selectedIds.contains(approvalId),
            "toggleSelection() must remove ID when already present"
        )
    }

    // MARK: - T14: approvalById() finds approval for deep link navigation

    func test_approvalById_returnsCorrectApprovalForDeepLink() async throws {
        // Spec ref: §29.5 — deep link from push notification navigates to specific approval
        let target = makeApproval(riskTier: .high)
        let other = makeApproval(riskTier: .low)

        let mockService = MockApprovalService()
        mockService.pendingApprovals = [target, other]

        let vm = ApprovalListViewModel(service: mockService)
        await vm.load()

        let found = vm.approvalById(target.id)
        XCTAssertNotNil(found, "approvalById() must find the approval matching the deep link ID")
        XCTAssertEqual(found?.id, target.id)

        let notFound = vm.approvalById(UUID())
        XCTAssertNil(notFound, "approvalById() must return nil for unknown IDs")
    }
}

// MARK: - Helpers

private func makeApproval(
    id: UUID = UUID(),
    riskTier: RiskTier = .low,
    decision: ApprovalStatus = .pending
) -> Approval {
    Approval(
        id: id,
        runId: UUID(),
        userId: UUID(),
        riskTier: riskTier,
        previewText: "Send an email to test@example.com",
        decision: decision,
        domain: "external",
        requestedAt: Date(),
        decidedAt: nil
    )
}

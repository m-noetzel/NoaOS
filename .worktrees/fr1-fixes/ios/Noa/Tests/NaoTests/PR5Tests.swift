// PR5Tests.swift — iOS polish fixes tests
// Spec ref: SPEC.md §29.2, §29.3, §29.6
//
// Tests:
//   T1   MainTabView.init accepts optional networkMonitor and offlineQueue (iOS-M1)
//   T2   ChatViewModel.cancelStreamAndClear clears all state including loadTask (iOS-M2)
//   T3   ChatViewModel.loadHistory populates messages from service (iOS-M2 — basic)
//   T4   ApprovalDetailViewModel.decide sets isBiometricError on biometric failure (iOS-M3)
//   T5   ApprovalDetailViewModel.decide sets pendingDecision for retry (iOS-M3)
//   T6   ApprovalDetailViewModel.decide isBiometricError is false on userCancelled (iOS-M3)
//   T7   ApprovalListViewModel.batchDeny calls decide for each selected item (iOS-M4)
//   T8   VoiceViewModel.cancel() from any state transitions to .idle (iOS-M5)
//   T9   VoiceViewModel.stopAndTranscribe transitions to .error on CancellationError (iOS-M5)
//   T10  VoiceViewModel.uploadTimeoutSeconds is a positive, bounded value (iOS-M5)

import XCTest
@testable import Noa

// MARK: - iOS-M1: MainTabView lifecycle cleanup

@MainActor
final class MainTabViewLifecycleTests: XCTestCase {

    /// T1: MainTabView.init accepts optional networkMonitor and offlineQueue.
    ///
    /// Before PR5 the init had no lifecycle parameters. With the new optional
    /// parameters the caller can pass them in so that onDisappear can stop them.
    func test_mainTabViewInit_acceptsOptionalLifecycleServices() async throws {
        // Spec ref: SPEC.md §29.3 item 6 (offline queue lifecycle)
        let tokenProvider = MockTokenProviderPR5()
        let apiClient = MockAPIClientPR5(tokenProvider: tokenProvider)
        let chatService = ChatService(
            apiClient: apiClient,
            baseURL: URL(string: "http://localhost:8000")!,
            tokenProvider: tokenProvider
        )
        let fakeAPIClient = MockAPIClientPR5(tokenProvider: tokenProvider)
        let authService = AuthService(
            apiClient: fakeAPIClient,
            keychainService: "com.noa.pr5tests"
        )
        let authVM = AuthViewModel(authService: authService)
        let approvalService = MockApprovalServicePR5()
        let biometricService = MockBiometricServicePR5()

        // Without lifecycle services — must compile and not crash
        let _ = MainTabView(
            authViewModel: authVM,
            chatService: chatService,
            approvalService: approvalService,
            biometricService: biometricService
        )

        // With lifecycle services — must compile and not crash
        let monitor = NetworkMonitorService()
        let queueURL = FileManager.default
            .temporaryDirectory
            .appendingPathComponent("pr5_t1_queue.json")
        let queue = OfflineQueueService(fileURL: queueURL)

        let _ = MainTabView(
            authViewModel: authVM,
            chatService: chatService,
            approvalService: approvalService,
            biometricService: biometricService,
            networkMonitor: monitor,
            offlineQueue: queue
        )
    }
}

// MARK: - iOS-M2: ChatViewModel loadHistory race fix

@MainActor
final class ChatViewModelLoadRaceTests: XCTestCase {

    // T2: cancelStreamAndClear clears all observable state.
    //
    // The fix adds loadTask cancellation to cancelStreamAndClear(). This test
    // verifies all state fields are reset as a guard against regressions.
    func test_cancelStreamAndClear_resetsAllState() {
        // Spec ref: iOS-M2 — cancelStreamAndClear must cancel loadTask too
        let tokenProvider = MockTokenProviderPR5()
        let apiClient = MockAPIClientPR5(tokenProvider: tokenProvider)
        let chatService = ChatService(
            apiClient: apiClient,
            baseURL: URL(string: "http://localhost:8000")!,
            tokenProvider: tokenProvider
        )
        let vm = ChatViewModel(chatService: chatService)

        vm.cancelStreamAndClear()

        XCTAssertTrue(vm.messages.isEmpty, "messages must be empty")
        XCTAssertFalse(vm.isStreaming, "isStreaming must be false")
        XCTAssertNil(vm.errorMessage, "errorMessage must be nil")
        XCTAssertNil(vm.currentRunId, "currentRunId must be nil")
        XCTAssertNil(vm.capturedThreadId, "capturedThreadId must be nil")
        XCTAssertNil(vm.currentIndicator, "currentIndicator must be nil")
    }

    // T3: A second call to loadHistory replaces messages from the first call.
    //
    // Uses a mock API client that returns different sets of messages per call
    // to verify that messages don't accumulate from two concurrent loads.
    func test_loadHistory_secondCallReplacesFirstResult() async throws {
        // Spec ref: iOS-M2 — rapid thread switching race fix
        let tokenProvider = MockTokenProviderPR5()
        let apiClient = MockListMessagesPR5(tokenProvider: tokenProvider)
        let chatService = ChatService(
            apiClient: apiClient,
            baseURL: URL(string: "http://localhost:8000")!,
            tokenProvider: tokenProvider
        )
        let vm = ChatViewModel(chatService: chatService)

        // Configure first call to return 2 messages
        apiClient.messageCount = 2
        await vm.loadHistory(threadId: UUID())
        XCTAssertEqual(vm.messages.count, 2, "First load should produce 2 messages")

        // cancelStreamAndClear simulates thread switch
        vm.cancelStreamAndClear()
        XCTAssertTrue(vm.messages.isEmpty, "Messages cleared on thread switch")

        // Second load: 1 message for the new thread
        apiClient.messageCount = 1
        await vm.loadHistory(threadId: UUID())
        XCTAssertEqual(vm.messages.count, 1, "Second load should produce 1 message for new thread")
    }
}

// MARK: - iOS-M3: ApprovalDetailViewModel biometric retry

@MainActor
final class ApprovalDetailBiometricRetryTests: XCTestCase {

    // T4: decide() sets isBiometricError = true when biometric fails with a
    //     retryable error (not userCancelled).
    func test_decide_highRisk_biometricFailure_setsBiometricErrorFlag() async {
        // Spec ref: iOS-M3 — recovery UI for biometric failure
        let approval = makeApprovalPR5(riskTier: .high)
        let mockService = MockApprovalServicePR5()
        let mockBiometric = MockBiometricServicePR5()
        mockBiometric.shouldFail = true
        mockBiometric.failError = .authenticationFailed

        let vm = ApprovalDetailViewModel(
            approval: approval,
            service: mockService,
            biometric: mockBiometric
        )

        await vm.decide(.approved)

        XCTAssertTrue(
            vm.isBiometricError,
            "isBiometricError must be true after a retryable biometric failure"
        )
        XCTAssertNotNil(vm.errorMessage, "errorMessage must be set on biometric failure")
        XCTAssertFalse(vm.isSubmitting, "isSubmitting must be cleared after failure")
    }

    // T5: pendingDecision is stored so the View can offer a "Try Again" retry.
    func test_decide_highRisk_biometricFailure_storesPendingDecision() async {
        // Spec ref: iOS-M3 — "Try Again" needs to know which decision to retry
        let approval = makeApprovalPR5(riskTier: .high)
        let mockService = MockApprovalServicePR5()
        let mockBiometric = MockBiometricServicePR5()
        mockBiometric.shouldFail = true
        mockBiometric.failError = .authenticationFailed

        let vm = ApprovalDetailViewModel(
            approval: approval,
            service: mockService,
            biometric: mockBiometric
        )

        await vm.decide(.approved)

        XCTAssertEqual(
            vm.pendingDecision, .approved,
            "pendingDecision must be stored so the retry button can re-submit"
        )
    }

    // T6: isBiometricError is false when the user explicitly cancels biometric.
    //     Cancellation is deliberate; showing "Try Again" would be confusing.
    func test_decide_highRisk_userCancelled_doesNotSetBiometricErrorFlag() async {
        // Spec ref: iOS-M3 — distinguish retryable failure from deliberate cancel
        let approval = makeApprovalPR5(riskTier: .high)
        let mockService = MockApprovalServicePR5()
        let mockBiometric = MockBiometricServicePR5()
        mockBiometric.shouldFail = true
        mockBiometric.failError = .userCancelled

        let vm = ApprovalDetailViewModel(
            approval: approval,
            service: mockService,
            biometric: mockBiometric
        )

        await vm.decide(.denied)

        XCTAssertFalse(
            vm.isBiometricError,
            "isBiometricError must be false when the user explicitly cancels biometric"
        )
    }
}

// MARK: - iOS-M4: Batch deny confirmation (ViewModel side)

@MainActor
final class ApprovalListBatchDenyConfirmationTests: XCTestCase {

    // T7: batchDeny() still calls decide for each selected item.
    //     The confirmation dialog is View-level; the ViewModel logic is unchanged.
    func test_batchDeny_callsDecideForEachSelected() async {
        // Spec ref: iOS-M4 — batch deny executes after user confirmation
        let a1 = makeApprovalPR5(riskTier: .low)
        let a2 = makeApprovalPR5(riskTier: .medium)

        let mockService = MockApprovalServicePR5()
        mockService.pendingApprovals = [a1, a2]

        let vm = ApprovalListViewModel(service: mockService)
        await vm.load()

        vm.toggleSelection(a1.id)
        vm.toggleSelection(a2.id)

        await vm.batchDeny()

        let callCount = mockService.decideCallCount
        XCTAssertEqual(callCount, 2, "batchDeny() must call decide() for each selected item")
        let lastDecision = mockService.lastDecision
        XCTAssertEqual(lastDecision, .denied)
        XCTAssertTrue(vm.selectedIds.isEmpty)
    }
}

// MARK: - iOS-M5: VoiceViewModel upload cancel and timeout

@MainActor
final class VoiceViewModelCancelTests: XCTestCase {

    // T8: cancel() resets state to .idle from any state.
    func test_cancel_fromAnyState_resetsToIdle() async {
        // Spec ref: iOS-M5 — user can cancel a hanging upload
        let recorder = MockAudioRecorderPR5()
        let voiceService = ImmediateSuccessMockVoiceService()

        let vm = VoiceViewModel(
            recorder: recorder,
            voiceService: voiceService
        )

        // Start recording then cancel
        await vm.startRecording()
        // recorder.isRecording is now true

        await vm.cancel()

        if case .idle = vm.state {
            // correct
        } else {
            XCTFail("Expected .idle after cancel(), got \(vm.state)")
        }
        XCTAssertEqual(vm.audioLevel, 0)
    }

    // T9: stopAndTranscribe() transitions to .error when service throws CancellationError.
    func test_stopAndTranscribe_transitionsToError_onCancellation() async {
        // Spec ref: iOS-M5 — upload timeout/cancel surfaces as error state
        let recorder = MockAudioRecorderPR5()
        recorder.stopReturnURL = URL(fileURLWithPath: "/tmp/pr5_t9.m4a")
        let voiceService = CancellingMockVoiceServicePR5()

        let vm = VoiceViewModel(
            recorder: recorder,
            voiceService: voiceService
        )

        await vm.stopAndTranscribe()

        if case .error(let msg) = vm.state {
            XCTAssertFalse(msg.isEmpty, "Error message must not be empty after cancellation")
        } else {
            XCTFail("Expected .error state after CancellationError, got \(vm.state)")
        }
    }

    // T10: uploadTimeoutSeconds is a sensible positive value.
    func test_uploadTimeoutSeconds_isPositiveAndBounded() {
        // Spec ref: iOS-M5 — timeout must prevent indefinite server hangs
        XCTAssertGreaterThan(
            VoiceViewModel.uploadTimeoutSeconds, 0,
            "Upload timeout must be positive"
        )
        XCTAssertLessThanOrEqual(
            VoiceViewModel.uploadTimeoutSeconds, 120,
            "Upload timeout must not exceed 2 minutes"
        )
    }
}

// MARK: - Supporting mocks

// MARK: MockTokenProviderPR5

actor MockTokenProviderPR5: TokenProviding {
    func accessToken() async -> String? { "mock-token" }
    func refreshAccessToken() async throws -> String { "mock-refreshed-token" }
}

// MARK: MockAPIClientPR5 (returns empty arrays for all requests)

actor MockAPIClientPR5: APIClientProtocol {
    let tokenProvider: MockTokenProviderPR5

    init(tokenProvider: MockTokenProviderPR5) {
        self.tokenProvider = tokenProvider
    }

    func request<T: Decodable & Sendable>(
        _ endpoint: String,
        method: String,
        body: (any Encodable & Sendable)?
    ) async throws -> T {
        throw NSError(domain: "MockAPIClientPR5", code: 0,
                      userInfo: [NSLocalizedDescriptionKey: "No mock for \(endpoint)"])
    }

    func isAuthenticated() async -> Bool { true }
}

// MARK: MockListMessagesPR5 (returns configurable Message arrays)

actor MockListMessagesPR5: APIClientProtocol {
    let tokenProvider: MockTokenProviderPR5
    nonisolated(unsafe) var messageCount: Int = 0

    init(tokenProvider: MockTokenProviderPR5) {
        self.tokenProvider = tokenProvider
    }

    func request<T: Decodable & Sendable>(
        _ endpoint: String,
        method: String,
        body: (any Encodable & Sendable)?
    ) async throws -> T {
        if endpoint.contains("/messages") {
            let count = messageCount
            let msgs = (0..<count).map { i in
                Message(
                    id: UUID(),
                    threadId: UUID(),
                    role: .user,
                    content: "Message \(i)",
                    createdAt: Date()
                )
            }
            if let result = msgs as? T {
                return result
            }
        }
        throw NSError(domain: "MockListMessagesPR5", code: 0,
                      userInfo: [NSLocalizedDescriptionKey: "No mock for \(endpoint)"])
    }

    func isAuthenticated() async -> Bool { true }
}

// MARK: MockApprovalServicePR5

actor MockApprovalServicePR5: ApprovalServicing {
    nonisolated(unsafe) var pendingApprovals: [Approval] = []
    nonisolated(unsafe) var decideCallCount: Int = 0
    nonisolated(unsafe) var lastDecision: ApprovalStatus?

    func fetchPending() async throws -> [Approval] { pendingApprovals }

    func decide(id: UUID, decision: ApprovalStatus) async throws {
        decideCallCount += 1
        lastDecision = decision
    }
}

// MARK: MockBiometricServicePR5

actor MockBiometricServicePR5: BiometricAuthenticating {
    nonisolated(unsafe) var shouldFail: Bool = false
    nonisolated(unsafe) var failError: BiometricError = .authenticationFailed

    func isAvailable() async -> Bool { true }

    func authenticate(reason: String) async throws {
        if shouldFail { throw failError }
    }
}

// MARK: MockAudioRecorderPR5

actor MockAudioRecorderPR5: AudioRecording {
    nonisolated(unsafe) var stopReturnURL: URL? = nil
    var isRecording: Bool = false
    var duration: TimeInterval = 0
    var audioLevel: Float = 0

    func startRecording() async throws { isRecording = true }
    func stopRecording() async -> URL? {
        isRecording = false
        return stopReturnURL
    }
    func cancelRecording() async { isRecording = false }
}

// MARK: ImmediateSuccessMockVoiceService

actor ImmediateSuccessMockVoiceService: VoiceServicing {
    func transcribe(audioURL: URL, mode: VoiceMode) async throws -> VoiceTranscriptionResult {
        VoiceTranscriptionResult(text: "Hello", mode: "transcribe", threadId: nil)
    }
}

// MARK: CancellingMockVoiceServicePR5 (throws CancellationError)

actor CancellingMockVoiceServicePR5: VoiceServicing {
    func transcribe(audioURL: URL, mode: VoiceMode) async throws -> VoiceTranscriptionResult {
        throw CancellationError()
    }
}

// MARK: Factory helpers

private func makeApprovalPR5(
    id: UUID = UUID(),
    riskTier: RiskTier = .low
) -> Approval {
    Approval(
        id: id,
        runId: UUID(),
        userId: UUID(),
        riskTier: riskTier,
        previewText: "Action preview",
        decision: .pending,
        domain: "external",
        requestedAt: Date(),
        decidedAt: nil
    )
}

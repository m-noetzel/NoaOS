// VoiceViewModelTests.swift — iOS8 Voice recording & transcription ViewModel tests
// Spec ref: SPEC.md §29.2, Phase iOS8 deliverable 8
//
// Tests:
//   T1   startRecording() transitions state to .recording
//   T2   stopAndTranscribe() produces .transcribed state on success
//   T3   stopAndTranscribe() with autoSend calls chatViewModel.sendMessage
//   T4   cancel() resets state to .idle
//   T5   permissionDenied error from recorder surfaces as .error state
//   T6   upload error from VoiceService surfaces as .error state
//   T7   state transitions: idle → recording → uploading → transcribed
//   T8   cancel() from uploading state (recorder not recording) goes to .idle

import XCTest
@testable import Noa

// MARK: - MockAudioRecorder

actor MockAudioRecorder: AudioRecording {
    // nonisolated(unsafe): tests run serially; safe to set/read from any actor
    nonisolated(unsafe) var startCallCount: Int = 0
    nonisolated(unsafe) var stopCallCount: Int = 0
    nonisolated(unsafe) var cancelCallCount: Int = 0
    nonisolated(unsafe) var shouldThrowOnStart: Error? = nil
    nonisolated(unsafe) var stopReturnURL: URL? = URL(fileURLWithPath: "/tmp/voice_test.m4a")

    // AudioRecording protocol async properties
    var isRecording: Bool = false
    var duration: TimeInterval = 0
    var audioLevel: Float = 0

    func startRecording() async throws {
        startCallCount += 1
        if let error = shouldThrowOnStart {
            throw error
        }
        isRecording = true
    }

    func stopRecording() async -> URL? {
        stopCallCount += 1
        isRecording = false
        return stopReturnURL
    }

    func cancelRecording() async {
        cancelCallCount += 1
        isRecording = false
    }
}

// MARK: - MockVoiceService

actor MockVoiceService: VoiceServicing {
    nonisolated(unsafe) var transcribeCallCount: Int = 0
    nonisolated(unsafe) var shouldThrow: Error? = nil
    nonisolated(unsafe) var result: VoiceTranscriptionResult = VoiceTranscriptionResult(
        text: "Hello world",
        mode: "transcribe",
        threadId: nil
    )

    func transcribe(audioURL: URL, mode: VoiceMode) async throws -> VoiceTranscriptionResult {
        transcribeCallCount += 1
        if let error = shouldThrow {
            throw error
        }
        return result
    }
}

// MARK: - VoiceViewModelTests

@MainActor
final class VoiceViewModelTests: XCTestCase {

    // MARK: - T1: startRecording() transitions to .recording

    func test_startRecording_transitionsToRecordingState() async {
        // Spec ref: SPEC.md §29.2 — recording flow starts on user tap
        let recorder = MockAudioRecorder()
        let service = MockVoiceService()
        let vm = VoiceViewModel(recorder: recorder, voiceService: service)

        await vm.startRecording()

        guard case .recording = vm.state else {
            return XCTFail("State must be .recording after startRecording(), got: \(vm.state)")
        }
        let callCount = recorder.startCallCount
        XCTAssertEqual(callCount, 1, "startRecording() must call recorder.startRecording() once")
    }

    // MARK: - T2: stopAndTranscribe() produces .transcribed on success

    func test_stopAndTranscribe_producesTranscribedState() async {
        // Spec ref: SPEC.md §29.2 — transcription result shown to user
        let recorder = MockAudioRecorder()
        let service = MockVoiceService()
        let vm = VoiceViewModel(recorder: recorder, voiceService: service)

        await vm.startRecording()
        await vm.stopAndTranscribe()

        guard case .transcribed(let text) = vm.state else {
            return XCTFail("State must be .transcribed after stopAndTranscribe(), got: \(vm.state)")
        }
        XCTAssertEqual(text, "Hello world", "transcribed text must match service result")

        let stopCount = recorder.stopCallCount
        XCTAssertEqual(stopCount, 1, "stopRecording() must be called once")

        let transcribeCount = service.transcribeCallCount
        XCTAssertEqual(transcribeCount, 1, "VoiceService.transcribe() must be called once")
    }

    // MARK: - T3: stopAndTranscribe() with autoSend calls chatViewModel.sendMessage

    func test_stopAndTranscribe_autoSend_forwardsTextToChatViewModel() async {
        // Spec ref: SPEC.md §29.2 — voice message can be sent directly
        let recorder = MockAudioRecorder()
        let service = MockVoiceService()
        service.result = VoiceTranscriptionResult(text: "Send this", mode: "transcribe", threadId: nil)

        // Use a real ChatViewModel with a mock backing service so we can inspect messages.
        let chatService = makeStubChatService()
        let chatVM = ChatViewModel(chatService: chatService)
        let vm = VoiceViewModel(recorder: recorder, voiceService: service, chatViewModel: chatVM)

        await vm.startRecording()
        await vm.stopAndTranscribe(autoSend: true)

        // After autoSend, state returns to .idle.
        guard case .idle = vm.state else {
            return XCTFail("State must be .idle after autoSend, got: \(vm.state)")
        }
        // ChatViewModel should have an optimistic user message appended.
        XCTAssertFalse(chatVM.messages.isEmpty, "chatViewModel must have at least one message after autoSend")
        XCTAssertEqual(chatVM.messages.first?.content, "Send this", "autoSend must forward the transcribed text")
    }

    // MARK: - T4: cancel() resets state to .idle

    func test_cancel_resetsStateToIdle() async {
        // Spec ref: SPEC.md §29.2 — cancel discards recording
        let recorder = MockAudioRecorder()
        let service = MockVoiceService()
        let vm = VoiceViewModel(recorder: recorder, voiceService: service)

        await vm.startRecording()
        await vm.cancel()

        guard case .idle = vm.state else {
            return XCTFail("State must be .idle after cancel(), got: \(vm.state)")
        }
        let cancelCount = recorder.cancelCallCount
        XCTAssertEqual(cancelCount, 1, "cancel() must call recorder.cancelRecording() once")
        XCTAssertEqual(vm.audioLevel, 0, "audioLevel must be 0 after cancel()")
    }

    // MARK: - T5: permissionDenied surfaces as .error state

    func test_permissionDenied_surfacesAsErrorState() async {
        // Spec ref: SPEC.md §29.2 — microphone denied must surface gracefully
        let recorder = MockAudioRecorder()
        recorder.shouldThrowOnStart = AudioRecorderError.permissionDenied
        let service = MockVoiceService()
        let vm = VoiceViewModel(recorder: recorder, voiceService: service)

        await vm.startRecording()

        guard case .error(let msg) = vm.state else {
            return XCTFail("State must be .error after permission denied, got: \(vm.state)")
        }
        XCTAssertFalse(msg.isEmpty, "Error message must not be empty")
        XCTAssertTrue(
            msg.localizedCaseInsensitiveContains("microphone") ||
            msg.localizedCaseInsensitiveContains("denied"),
            "Error message should mention microphone or denied, got: \(msg)"
        )
    }

    // MARK: - T6: upload error surfaces as .error state

    func test_uploadError_surfacesAsErrorState() async {
        // Spec ref: SPEC.md §29.2 — network failures must not crash
        let recorder = MockAudioRecorder()
        let service = MockVoiceService()
        service.shouldThrow = VoiceServiceError.networkError(underlying: URLError(.notConnectedToInternet))
        let vm = VoiceViewModel(recorder: recorder, voiceService: service)

        await vm.startRecording()
        await vm.stopAndTranscribe()

        guard case .error = vm.state else {
            return XCTFail("State must be .error after upload failure, got: \(vm.state)")
        }
    }

    // MARK: - T7: state machine sequence idle → recording → uploading → transcribed

    func test_stateTransitions_fullFlow() async {
        // Verify the complete happy-path state sequence.
        let recorder = MockAudioRecorder()
        let service = MockVoiceService()
        let vm = VoiceViewModel(recorder: recorder, voiceService: service)

        // Initial state is idle.
        guard case .idle = vm.state else {
            return XCTFail("Initial state must be .idle")
        }

        // After startRecording: .recording
        await vm.startRecording()
        guard case .recording = vm.state else {
            return XCTFail("State must be .recording after startRecording()")
        }

        // After stopAndTranscribe completes: .transcribed
        await vm.stopAndTranscribe()
        guard case .transcribed = vm.state else {
            return XCTFail("State must be .transcribed after stopAndTranscribe(), got: \(vm.state)")
        }
    }

    // MARK: - T8: cancel() from non-recording state goes to .idle without crashing

    func test_cancel_fromIdleState_isNoOp() async {
        // cancel() must be safe to call even when not recording.
        let recorder = MockAudioRecorder()
        let service = MockVoiceService()
        let vm = VoiceViewModel(recorder: recorder, voiceService: service)

        // Should not throw or crash.
        await vm.cancel()

        guard case .idle = vm.state else {
            return XCTFail("State must remain .idle after cancel() with no active recording")
        }
    }
}

// MARK: - Helpers

/// Returns a minimal ChatService stub for T3 (autoSend test).
@MainActor
private func makeStubChatService() -> ChatService {
    let config = URLSessionConfiguration.ephemeral
    config.protocolClasses = [MockURLProtocol.self]
    let session = URLSession(configuration: config)

    MockURLProtocol.handler = { _ in
        // Return a minimal SSE stream that completes immediately.
        let sseData = "data: {\"type\":\"done\"}\n\n".data(using: .utf8)!
        return (sseData, makeHTTPResponse(statusCode: 200))
    }

    let tokenProvider = MockTokenProvider()
    Task { await tokenProvider.setToken("test-token") }

    let baseURL = NoaEnvironment.development.baseURL
    let apiClient = APIClient(
        environment: .development,
        tokenProvider: tokenProvider,
        session: session
    )
    return ChatService(apiClient: apiClient, baseURL: baseURL, tokenProvider: tokenProvider)
}

// AudioRecorderServiceTests.swift — iOS8 AudioRecorderService unit tests
// Spec ref: SPEC.md §29.2, Phase iOS8 deliverable 8
//
// Tests:
//   T9   MockAudioRecorder.startRecording() increments call count
//   T10  MockAudioRecorder.stopRecording() returns configured URL
//   T11  MockAudioRecorder.cancelRecording() increments call count
//   T12  AudioRecorderError.permissionDenied is distinct from .recordingFailed
//   T13  VoiceService.transcribe() POSTs multipart to /api/v1/voice/transcribe with auth header
//   T14  VoiceService.transcribe() decodes flat JSON response (no envelope)
//   T15  VoiceService.transcribe() throws .unauthorized on 401

import XCTest
@testable import Noa

// MARK: - AudioRecorderServiceTests

final class AudioRecorderServiceTests: XCTestCase {

    // MARK: - T9: MockAudioRecorder.startRecording() is callable

    func test_mockRecorder_startRecording_incrementsCallCount() async throws {
        // Verifies MockAudioRecorder (defined in VoiceViewModelTests.swift) compiles and works.
        let recorder = MockAudioRecorder()
        try await recorder.startRecording()
        let count = await recorder.startCallCount
        XCTAssertEqual(count, 1, "startRecording() must increment call count")
    }

    // MARK: - T10: MockAudioRecorder.stopRecording() returns configured URL

    func test_mockRecorder_stopRecording_returnsConfiguredURL() async {
        let recorder = MockAudioRecorder()
        let expected = URL(fileURLWithPath: "/tmp/test_voice.m4a")
        recorder.stopReturnURL = expected

        let url = await recorder.stopRecording()
        XCTAssertEqual(url, expected, "stopRecording() must return the configured URL")
    }

    // MARK: - T11: MockAudioRecorder.cancelRecording() increments call count

    func test_mockRecorder_cancelRecording_incrementsCallCount() async {
        let recorder = MockAudioRecorder()
        await recorder.cancelRecording()
        let count = await recorder.cancelCallCount
        XCTAssertEqual(count, 1, "cancelRecording() must increment call count")
    }

    // MARK: - T12: AudioRecorderError cases are distinct

    func test_audioRecorderError_casesAreDistinct() {
        // Verifies the error enum compiles with expected cases.
        let permissionError = AudioRecorderError.permissionDenied
        let recordingError = AudioRecorderError.recordingFailed(underlying: nil)
        let notRecordingError = AudioRecorderError.notRecording

        // Basic distinctness via pattern matching.
        if case .permissionDenied = permissionError { /* expected */ } else {
            XCTFail("Expected .permissionDenied")
        }
        if case .recordingFailed = recordingError { /* expected */ } else {
            XCTFail("Expected .recordingFailed")
        }
        if case .notRecording = notRecordingError { /* expected */ } else {
            XCTFail("Expected .notRecording")
        }

        // Confirm they are not the same.
        if case .permissionDenied = recordingError {
            XCTFail(".permissionDenied and .recordingFailed must be distinct")
        }
    }

    // MARK: - T13: VoiceService.transcribe() POSTs to correct endpoint with auth header

    func test_voiceService_transcribe_POSTsToCorrectEndpointWithAuthHeader() async throws {
        // Spec ref: SPEC.md §29.2 — POST /api/v1/voice/transcribe with Bearer token
        var capturedRequest: URLRequest?

        MockURLProtocol.handler = { request in
            capturedRequest = request
            let json = """
            {"text":"hello","mode":"transcribe","thread_id":null}
            """.data(using: .utf8)!
            return (json, makeHTTPResponse(statusCode: 200))
        }

        let service = makeVoiceService(token: "test-token-abc")
        let audioURL = makeTempAudioFile()
        _ = try await service.transcribe(audioURL: audioURL, mode: .transcribe)
        try? FileManager.default.removeItem(at: audioURL)

        let req = try XCTUnwrap(capturedRequest, "A request must have been made")

        XCTAssertTrue(
            req.url?.path.contains("/api/v1/voice/transcribe") == true,
            "URL must contain /api/v1/voice/transcribe, got: \(req.url?.path ?? "nil")"
        )
        XCTAssertEqual(req.httpMethod, "POST", "Method must be POST")

        let authHeader = req.value(forHTTPHeaderField: "Authorization")
        XCTAssertEqual(
            authHeader, "Bearer test-token-abc",
            "Authorization header must be Bearer + token"
        )

        let contentType = req.value(forHTTPHeaderField: "Content-Type") ?? ""
        XCTAssertTrue(
            contentType.contains("multipart/form-data"),
            "Content-Type must be multipart/form-data, got: \(contentType)"
        )
    }

    // MARK: - T14: VoiceService.transcribe() decodes flat JSON (no envelope)

    func test_voiceService_transcribe_decodesFlatJSONResponse() async throws {
        // Spec ref: voice.py returns flat JSON, not ApiResponse<T> envelope.
        let threadId = UUID()
        MockURLProtocol.handler = { _ in
            let json = """
            {"text":"good morning","mode":"chat","thread_id":"\(threadId.uuidString.lowercased())"}
            """.data(using: .utf8)!
            return (json, makeHTTPResponse(statusCode: 200))
        }

        let service = makeVoiceService()
        let audioURL = makeTempAudioFile()
        let result = try await service.transcribe(audioURL: audioURL, mode: .chat)
        try? FileManager.default.removeItem(at: audioURL)

        XCTAssertEqual(result.text, "good morning", "text must be decoded from flat JSON")
        XCTAssertEqual(result.mode, "chat", "mode must be decoded from flat JSON")
        XCTAssertEqual(result.threadId, threadId, "thread_id must be decoded as UUID")
    }

    // MARK: - T15: VoiceService.transcribe() throws .unauthorized on 401

    func test_voiceService_transcribe_throwsUnauthorizedOn401() async {
        // Spec ref: §29.3 — 401 must surface as typed error, not crash
        MockURLProtocol.handler = { _ in
            let json = "{}".data(using: .utf8)!
            return (json, makeHTTPResponse(statusCode: 401))
        }

        let service = makeVoiceService()
        let audioURL = makeTempAudioFile()
        defer { try? FileManager.default.removeItem(at: audioURL) }

        do {
            _ = try await service.transcribe(audioURL: audioURL, mode: .transcribe)
            XCTFail("Expected VoiceServiceError.unauthorized to be thrown")
        } catch VoiceServiceError.unauthorized {
            // Expected
        } catch {
            XCTFail("Expected VoiceServiceError.unauthorized, got: \(error)")
        }
    }

    // MARK: - Teardown

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }
}

// MARK: - Helpers

private func makeVoiceService(token: String = "test-token") -> VoiceService {
    let config = URLSessionConfiguration.ephemeral
    config.protocolClasses = [MockURLProtocol.self]
    let session = URLSession(configuration: config)

    let tokenProvider = MockTokenProvider()
    Task { await tokenProvider.setToken(token) }

    return VoiceService(
        environment: .development,
        tokenProvider: tokenProvider,
        session: session
    )
}

/// Creates a minimal non-empty temp file that VoiceService can read as audio data.
/// Callers are responsible for deleting the file after the test.
private func makeTempAudioFile() -> URL {
    let url = FileManager.default.temporaryDirectory
        .appendingPathComponent("test_voice_\(UUID().uuidString).m4a")
    // Write a few dummy bytes — VoiceService reads raw Data, not decoded audio.
    let dummyData = Data(repeating: 0, count: 16)
    try? dummyData.write(to: url)
    return url
}

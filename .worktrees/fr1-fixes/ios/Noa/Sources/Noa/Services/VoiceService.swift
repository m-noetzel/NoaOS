// VoiceService.swift — Voice transcription via raw multipart/form-data upload
// Spec ref: SPEC.md §29.2, Phase iOS8 deliverable 3
//
// Endpoint:
//   POST /api/v1/voice/transcribe   (multipart/form-data)
//
// Request fields:
//   "file"  — M4A audio data
//   "mode"  — "transcribe" or "chat"
//
// Response: flat JSON {"text": "...", "mode": "...", "thread_id": "..."|null}
// NOT wrapped in ApiResponse envelope — use raw URLSession decode.
//
// Auth: reads access token directly from TokenProviding (same as AuthService).
// 401 is surfaced as VoiceServiceError.unauthorized; no auto-refresh here
// (VoiceService is a one-shot upload, not a long-lived session).

import Foundation

// MARK: - VoiceMode

/// The transcription mode to request from the voice endpoint.
public enum VoiceMode: String, Sendable {
    /// Plain speech-to-text — no chat continuation.
    case transcribe
    /// Speech-to-text followed by a chat completion round-trip.
    case chat
}

// MARK: - VoiceTranscriptionResult

/// Decoded result from the `/api/v1/voice/transcribe` endpoint.
public struct VoiceTranscriptionResult: Sendable {
    /// The transcribed (and optionally processed) text.
    public let text: String
    /// The mode string echoed back by the server.
    public let mode: String
    /// The thread ID associated with a chat-mode response, if any.
    public let threadId: UUID?

    public init(text: String, mode: String, threadId: UUID?) {
        self.text = text
        self.mode = mode
        self.threadId = threadId
    }
}

// MARK: - VoiceServiceError

/// Typed errors from voice transcription operations.
public enum VoiceServiceError: Error, Sendable {
    /// The audio file at the given URL could not be read.
    case fileReadFailed(underlying: Error?)
    /// The request was rejected because the user is not authenticated.
    case unauthorized
    /// A network-level error occurred.
    case networkError(underlying: Error?)
    /// The server returned a non-2xx status code.
    case serverError(statusCode: Int)
    /// The server response could not be decoded.
    case decodingError(underlying: Error?)
}

// MARK: - VoiceServicing

/// Protocol for dependency injection in tests.
public protocol VoiceServicing: Sendable {
    /// Uploads the audio file and returns the transcription result.
    func transcribe(audioURL: URL, mode: VoiceMode) async throws -> VoiceTranscriptionResult
}

// MARK: - Private response type

/// Decodable model for the flat JSON voice response.
/// The server does NOT use the `ApiResponse<T>` envelope here.
private struct _VoiceResponse: Decodable, Sendable {
    let text: String
    let mode: String
    let threadId: String?

    enum CodingKeys: String, CodingKey {
        case text
        case mode
        case threadId = "thread_id"
    }
}

// MARK: - VoiceService

/// Actor-isolated service for voice transcription uploads.
/// Uses raw `URLSession` multipart/form-data because the voice endpoint
/// returns a flat JSON body (not the `ApiResponse<T>` envelope that `APIClient` expects).
/// Spec ref: SPEC.md §29.2
public actor VoiceService: VoiceServicing {

    // MARK: - Properties

    private let baseURL: URL
    private let session: URLSession
    private let tokenProvider: any TokenProviding

    private static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }()

    // MARK: - Init

    public init(
        environment: NoaEnvironment = .current,
        tokenProvider: any TokenProviding,
        session: URLSession? = nil
    ) {
        self.baseURL = environment.baseURL
        self.tokenProvider = tokenProvider
        if let session {
            self.session = session
        } else {
            let config = URLSessionConfiguration.default
            config.timeoutIntervalForRequest = 120   // transcription may take up to 2 min
            config.timeoutIntervalForResource = 150  // > backend timeout so server-side 504 surfaces first
            self.session = URLSession(configuration: config)
        }
    }

    // MARK: - VoiceServicing

    /// Uploads the audio file at `audioURL` and returns the transcription result.
    ///
    /// - Parameters:
    ///   - audioURL: Local file URL of the `.m4a` recording.
    ///   - mode: `.transcribe` for plain STT, `.chat` for chat continuation.
    /// - Returns: `VoiceTranscriptionResult` decoded from the flat JSON response.
    /// - Throws: `VoiceServiceError` on any failure.
    public func transcribe(audioURL: URL, mode: VoiceMode) async throws -> VoiceTranscriptionResult {
        // Read audio file data.
        let audioData: Data
        do {
            audioData = try Data(contentsOf: audioURL)
        } catch {
            throw VoiceServiceError.fileReadFailed(underlying: error)
        }

        // Build the multipart request.
        let token = await tokenProvider.accessToken()
        let boundary = "Boundary-\(UUID().uuidString)"
        let url = baseURL.appendingPathComponent("/api/v1/voice/transcribe")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        // Idempotency-Key on POST — SPEC §25.4.
        request.setValue(UUID().uuidString, forHTTPHeaderField: "Idempotency-Key")

        request.httpBody = buildMultipartBody(
            audioData: audioData,
            mode: mode.rawValue,
            boundary: boundary
        )

        // Perform the upload.
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request)
        } catch let urlError as URLError {
            throw VoiceServiceError.networkError(underlying: urlError)
        } catch {
            throw VoiceServiceError.networkError(underlying: error)
        }

        guard let http = response as? HTTPURLResponse else {
            throw VoiceServiceError.networkError(underlying: URLError(.badServerResponse))
        }

        if http.statusCode == 401 {
            throw VoiceServiceError.unauthorized
        }
        guard (200...299).contains(http.statusCode) else {
            throw VoiceServiceError.serverError(statusCode: http.statusCode)
        }

        // Decode the flat JSON response.
        let voiceResponse: _VoiceResponse
        do {
            voiceResponse = try Self.decoder.decode(_VoiceResponse.self, from: data)
        } catch {
            throw VoiceServiceError.decodingError(underlying: error)
        }

        let threadId = voiceResponse.threadId.flatMap { UUID(uuidString: $0) }
        return VoiceTranscriptionResult(
            text: voiceResponse.text,
            mode: voiceResponse.mode,
            threadId: threadId
        )
    }

    // MARK: - Multipart body builder

    /// Constructs a `multipart/form-data` body with an audio "file" field and a "mode" field.
    private func buildMultipartBody(audioData: Data, mode: String, boundary: String) -> Data {
        var body = Data()
        let crlf = "\r\n"

        // "file" field — the M4A audio data.
        body.append("--\(boundary)\(crlf)")
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"voice.m4a\"\(crlf)")
        body.append("Content-Type: audio/m4a\(crlf)")
        body.append(crlf)
        body.append(audioData)
        body.append(crlf)

        // "mode" field — plain text value.
        body.append("--\(boundary)\(crlf)")
        body.append("Content-Disposition: form-data; name=\"mode\"\(crlf)")
        body.append(crlf)
        body.append(mode)
        body.append(crlf)

        // Closing boundary.
        body.append("--\(boundary)--\(crlf)")

        return body
    }
}

// MARK: - Data append helper

private extension Data {
    /// Appends a UTF-8 encoded string. No-ops if encoding fails (prevents silent data corruption).
    mutating func append(_ string: String) {
        if let data = string.data(using: .utf8) {
            append(data)
        }
    }
}

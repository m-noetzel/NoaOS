// SSEClient.swift — Server-Sent Events streaming client
// Spec ref: SPEC.md §22.2, §29.1, PLAN Phase iOS3
//
// Responsibilities:
//   - URLSession.bytes(for:) streaming
//   - SSE line parser: "data:" prefix, multi-line concatenation, comment/empty line handling
//   - Emits SSEEvent values via AsyncThrowingStream
//   - Reconnection backoff [1s, 2s, 5s, 10s]
//   - Last-Event-ID header on reconnect
//   - Captures run_id and thread_id from the first "meta" event

import Foundation

/// Server-Sent Events streaming client.
/// Uses `URLSession.bytes(for:)` for true streaming without loading the full response.
/// Actor isolation protects mutable state (capturedRunId, capturedThreadId, lastEventId)
/// from data races under Swift 6 strict concurrency.
public actor SSEClient {

    // MARK: - Properties

    /// Backoff schedule in seconds: [1, 2, 5, 10]. §PLAN Phase iOS3.
    public nonisolated static let backoffSchedule: [TimeInterval] = [1, 2, 5, 10]

    private let baseURL: URL
    private let session: URLSession
    private let tokenProvider: any TokenProviding
    private let endpoint: String

    /// run_id captured from the `meta` SSE event.
    public private(set) var capturedRunId: String?
    /// thread_id captured from the `meta` SSE event.
    public private(set) var capturedThreadId: String?
    /// Last received event ID, sent as `Last-Event-ID` header on reconnect.
    private var lastEventId: String?

    // MARK: - Init

    public init(
        baseURL: URL,
        endpoint: String,
        tokenProvider: any TokenProviding,
        session: URLSession? = nil
    ) {
        self.baseURL = baseURL
        self.endpoint = endpoint
        self.tokenProvider = tokenProvider
        if let session {
            self.session = session
        } else {
            let config = URLSessionConfiguration.default
            config.timeoutIntervalForRequest = 0  // No timeout on streaming
            self.session = URLSession(configuration: config)
        }
    }

    // MARK: - Public streaming API

    /// Begins streaming SSE events. Reconnects with backoff on disconnect.
    /// Yields `SSEEvent` values until the stream ends or `maxReconnects` is reached.
    ///
    /// - Parameter maxReconnects: Maximum reconnection attempts (default: backoffSchedule.count).
    /// - Returns: An `AsyncThrowingStream` of `SSEEvent` values.
    public func stream(
        maxReconnects: Int = SSEClient.backoffSchedule.count
    ) -> AsyncThrowingStream<SSEEvent, Error> {
        AsyncThrowingStream { continuation in
            Task {
                var reconnectCount = 0
                while true {
                    do {
                        let request = try await self.buildRequest()
                        let (bytes, response) = try await self.session.bytes(for: request)
                        guard let httpResponse = response as? HTTPURLResponse,
                            (200...299).contains(httpResponse.statusCode)
                        else {
                            throw SSEError.badResponse
                        }
                        try await self.parseStream(bytes: bytes, continuation: continuation)
                        // Stream ended gracefully
                        break
                    } catch is CancellationError {
                        continuation.finish()
                        return
                    } catch {
                        if reconnectCount >= maxReconnects {
                            continuation.finish(throwing: SSEError.maxReconnectsExceeded)
                            return
                        }
                        // Reconnect with backoff
                        let delay = SSEClient.backoffSchedule[
                            min(reconnectCount, SSEClient.backoffSchedule.count - 1)
                        ]
                        reconnectCount += 1
                        try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                    }
                }
                continuation.finish()
            }
        }
    }

    // MARK: - SSE Line Parser

    /// Parses an SSE byte stream line by line, emitting events to the continuation.
    /// Handles: `data:` fields, multi-line data accumulation, `id:` fields, comment lines.
    /// Spec ref: SSE specification (RFC-compliant), SPEC.md §22.2
    func parseStream(
        bytes: URLSession.AsyncBytes,
        continuation: AsyncThrowingStream<SSEEvent, Error>.Continuation
    ) async throws {
        var dataBuffer: [String] = []
        var currentEventId: String?

        for try await line in bytes.lines {
            // Empty line: dispatch the event
            if line.isEmpty {
                if !dataBuffer.isEmpty {
                    let jsonString = dataBuffer.joined(separator: "\n")
                    dataBuffer.removeAll()
                    if let event = parseEvent(from: jsonString) {
                        // Capture run_id and thread_id from the meta event
                        if event.eventType == "meta" {
                            extractMeta(from: event)
                        }
                        if let eid = currentEventId {
                            lastEventId = eid
                            currentEventId = nil
                        }
                        continuation.yield(event)
                    }
                }
                continue
            }

            // Comment line (starts with ':'): ignore per SSE spec
            if line.hasPrefix(":") {
                continue
            }

            // Field: value parsing
            if let colonIndex = line.firstIndex(of: ":") {
                let field = String(line[line.startIndex..<colonIndex])
                let afterColon = line.index(after: colonIndex)
                // SSE spec: strip a single leading space after the colon
                let rawValue = String(line[afterColon...])
                let value = rawValue.hasPrefix(" ") ? String(rawValue.dropFirst()) : rawValue

                switch field {
                case "data":
                    dataBuffer.append(value)
                case "id":
                    currentEventId = value
                case "event":
                    // `event:` field is ignored here; we use `event_type` from the JSON payload
                    break
                case "retry":
                    // `retry:` field: ignored (we use fixed backoff schedule)
                    break
                default:
                    // Unknown field: ignore per SSE spec
                    break
                }
            }
            // Lines without ':' are field names with empty values — ignore per spec
        }
    }

    // MARK: - Private helpers

    private func buildRequest() async throws -> URLRequest {
        let url = baseURL.appendingPathComponent(endpoint)
        var request = URLRequest(url: url)
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.setValue("no-cache", forHTTPHeaderField: "Cache-Control")

        if let token = await tokenProvider.accessToken() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let lastId = lastEventId {
            request.setValue(lastId, forHTTPHeaderField: "Last-Event-ID")
        }

        return request
    }

    private func parseEvent(from jsonString: String) -> SSEEvent? {
        guard let data = jsonString.data(using: .utf8) else { return nil }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try? decoder.decode(SSEEvent.self, from: data)
    }

    private func extractMeta(from event: SSEEvent) {
        if let payload = event.payload {
            if case let runId as String = payload["run_id"]?.value {
                capturedRunId = runId
            }
            if case let threadId as String = payload["thread_id"]?.value {
                capturedThreadId = threadId
            }
        }
    }
}

// MARK: - SSE-specific errors

public enum SSEError: Error, Sendable {
    case badResponse
    case maxReconnectsExceeded
}

// MARK: - SSELineParser (pure, testable)

/// Stateless SSE line parser. Exposed for unit testing without networking.
/// Spec ref: PLAN Phase iOS3 — "SSE parser tested with messy input"
public struct SSELineParser: Sendable {

    /// Parses a raw SSE text block (one or more data: lines separated by blank lines)
    /// into an array of `SSEEvent` values.
    public static func parse(text: String) -> [SSEEvent] {
        var events: [SSEEvent] = []
        var dataBuffer: [String] = []
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let lines = text.components(separatedBy: "\n")
        for line in lines {
            if line.isEmpty {
                if !dataBuffer.isEmpty {
                    let jsonString = dataBuffer.joined(separator: "\n")
                    dataBuffer.removeAll()
                    if let data = jsonString.data(using: .utf8),
                        let event = try? decoder.decode(SSEEvent.self, from: data)
                    {
                        events.append(event)
                    }
                }
                continue
            }

            if line.hasPrefix(":") {
                // Comment — skip
                continue
            }

            if let colonIndex = line.firstIndex(of: ":") {
                let field = String(line[line.startIndex..<colonIndex])
                let afterColon = line.index(after: colonIndex)
                let rawValue = String(line[afterColon...])
                let value = rawValue.hasPrefix(" ") ? String(rawValue.dropFirst()) : rawValue

                if field == "data" {
                    dataBuffer.append(value)
                }
                // id/event/retry fields: not needed for pure parsing
            }
            // Malformed lines (no colon): skip gracefully — do not crash
        }

        // Flush any trailing data without trailing blank line
        if !dataBuffer.isEmpty {
            let jsonString = dataBuffer.joined(separator: "\n")
            if let data = jsonString.data(using: .utf8),
                let event = try? JSONDecoder().decode(SSEEvent.self, from: data)
            {
                events.append(event)
            }
        }

        return events
    }
}

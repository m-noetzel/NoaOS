// ChatService.swift — Chat API + SSE streaming service
// Spec ref: SPEC.md §22.2, §29.2
//
// Responsibilities:
//   - POST /api/v1/chat → returns an AsyncThrowingStream<SSEEvent, Error>
//   - GET  /api/v1/threads → [Thread]
//   - POST /api/v1/threads → Thread
//   - GET  /api/v1/threads/{id}/messages → [Message]
//   - DELETE /api/v1/threads/{id} → void

import Foundation

// MARK: - ChatService

/// Actor-isolated chat service. Manages SSE streaming and thread CRUD.
public actor ChatService {

    // MARK: - Properties

    private let apiClient: any APIClientProtocol
    private let baseURL: URL
    private let tokenProvider: any TokenProviding

    // MARK: - Init

    public init(
        apiClient: any APIClientProtocol,
        baseURL: URL,
        tokenProvider: any TokenProviding
    ) {
        self.apiClient = apiClient
        self.baseURL = baseURL
        self.tokenProvider = tokenProvider
    }

    // MARK: - Chat (SSE)

    /// Sends a message and returns a stream of SSE events.
    /// The caller must iterate the stream and handle each event type.
    public func sendMessage(_ request: ChatRequest) -> AsyncThrowingStream<SSEEvent, Error> {
        // Encode body to JSON for POST
        let body: Data
        do {
            let encoder = JSONEncoder()
            encoder.keyEncodingStrategy = .convertToSnakeCase
            body = try encoder.encode(request)
        } catch {
            return AsyncThrowingStream { continuation in
                continuation.finish(throwing: error)
            }
        }

        let baseURL = self.baseURL
        let tokenProvider = self.tokenProvider

        return AsyncThrowingStream { continuation in
            Task {
                var urlRequest = URLRequest(url: baseURL.appendingPathComponent("/api/v1/chat"))
                urlRequest.httpMethod = "POST"
                urlRequest.httpBody = body
                urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
                urlRequest.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                urlRequest.setValue(UUID().uuidString, forHTTPHeaderField: "Idempotency-Key")

                if let token = await tokenProvider.accessToken() {
                    urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
                }

                let config = URLSessionConfiguration.default
                config.timeoutIntervalForRequest = 0  // No timeout on streaming
                let session = URLSession(configuration: config)

                do {
                    let (bytes, response) = try await session.bytes(for: urlRequest)
                    guard let http = response as? HTTPURLResponse,
                          (200...299).contains(http.statusCode)
                    else {
                        continuation.finish(throwing: ChatServiceError.badResponse)
                        return
                    }

                    // Parse SSE line-by-line
                    var dataBuffer: [String] = []
                    let decoder = JSONDecoder()
                    decoder.dateDecodingStrategy = .iso8601

                    for try await line in bytes.lines {
                        if line.isEmpty {
                            if !dataBuffer.isEmpty {
                                let jsonString = dataBuffer.joined(separator: "\n")
                                dataBuffer.removeAll()
                                if let data = jsonString.data(using: .utf8) {
                                    do {
                                        let event = try decoder.decode(SSEEvent.self, from: data)
                                        continuation.yield(event)
                                    } catch {
                                        // Surface malformed SSE frames as stream errors
                                        continuation.finish(throwing: error)
                                        return
                                    }
                                }
                            }
                            continue
                        }
                        if line.hasPrefix(":") { continue }
                        if let colonIdx = line.firstIndex(of: ":") {
                            let field = String(line[line.startIndex..<colonIdx])
                            let afterColon = line.index(after: colonIdx)
                            let raw = String(line[afterColon...])
                            let value = raw.hasPrefix(" ") ? String(raw.dropFirst()) : raw
                            if field == "data" {
                                dataBuffer.append(value)
                            }
                        }
                    }
                    continuation.finish()
                } catch is CancellationError {
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    // MARK: - Thread CRUD

    /// Loads all threads for the authenticated user.
    public func listThreads() async throws -> [Thread] {
        try await apiClient.get("/api/v1/threads")
    }

    /// Creates a new thread with the given title.
    public func createThread(title: String) async throws -> Thread {
        let body = CreateThreadBody(title: title)
        return try await apiClient.post("/api/v1/threads", body: body)
    }

    /// Loads messages for the given thread.
    public func listMessages(threadId: UUID) async throws -> [Message] {
        try await apiClient.get("/api/v1/threads/\(threadId)/messages")
    }

    /// Deletes the given thread (swipe-to-delete from ThreadListView).
    public func deleteThread(threadId: UUID) async throws {
        let _: DeletedResponse = try await apiClient.request(
            "/api/v1/threads/\(threadId)",
            method: "DELETE",
            body: nil as String?
        )
    }
}

// MARK: - Supporting types

private struct CreateThreadBody: Encodable, Sendable {
    let title: String
}

private struct DeletedResponse: Decodable, Sendable {
    let deleted: String
}

public enum ChatServiceError: Error, Sendable {
    case badResponse
    case encodingFailed
}

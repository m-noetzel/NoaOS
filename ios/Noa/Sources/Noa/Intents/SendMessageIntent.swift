// SendMessageIntent.swift — Siri Shortcut / App Intent to send a message to Noa
// Spec ref: SPEC.md §13.1, Phase IS1
//
// Responsibilities:
//   - Expose a "Send Message to Noa" App Intent with a `message` parameter
//   - Call the Noa SSE chat endpoint and collect the final response
//   - Return a string result (the assistant's response) to Siri / Shortcuts
//
// Auth note: The intent reads the access token from the shared Keychain via
// KeychainService and constructs a URLSession directly. It cannot rely on the
// main app's actor-isolated state since intents run in a separate process.
//
// Privacy note: Intents always route to "private" domain (local Ollama) because
// the intent process has no access to the user's privacy_mode preference. This
// is a deliberate safe default — external providers require explicit user choice
// in the main app per the Transparency Principle.

#if canImport(AppIntents)
import AppIntents
import Foundation

// MARK: - SendMessageIntent

/// Sends a message to Noa and returns the assistant's response.
///
/// Available as: "Send message to Noa" in Siri and the Shortcuts app.
/// The `message` parameter is provided by the user at shortcut setup time
/// or spoken to Siri at runtime.
///
/// Uses the SSE `/api/v1/chat` endpoint and collects `result_ready` or
/// `message` events to build the response text.
@available(iOS 16.0, *)
public struct SendMessageIntent: AppIntent {

    public static let title: LocalizedStringResource = "Send Message to Noa"
    public static let description = IntentDescription(
        "Send a message to Noa and get a response."
    )

    // MARK: - Parameters

    /// The message text to send. Siri will prompt for this if not provided.
    @Parameter(title: "Message", description: "The message to send to Noa.")
    public var message: String

    // MARK: - Init

    public init() {}

    public init(message: String) {
        self.message = message
    }

    // MARK: - Perform

    public func perform() async throws -> some IntentResult & ReturnsValue<String> {
        let trimmed = message.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            throw IntentError.emptyMessage
        }

        let tokenProvider = SharedIntentTokenProvider()
        guard let accessToken = await tokenProvider.accessToken() else {
            throw IntentError.notAuthenticated
        }

        let environment = NoaEnvironment.current
        let baseURL = environment.baseURL

        // Build the SSE request to POST /api/v1/chat
        let url = baseURL.appendingPathComponent("api/v1/chat")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 120 // LLM responses can be slow

        let body = ChatRequestBody(
            message: trimmed,
            threadId: nil,
            privacyMode: "private"
        )
        request.httpBody = try JSONEncoder().encode(body)

        // Collect SSE events and extract the assistant's response
        let responseText = try await collectSSEResponse(request: request)

        if responseText.isEmpty {
            return .result(value: "Noa processed your message but returned no text response.")
        }
        return .result(value: responseText)
    }

    // MARK: - SSE Collection

    /// Sends the request and reads the SSE stream, collecting assistant text
    /// from `token` and `result_ready` events.
    private func collectSSEResponse(request: URLRequest) async throws -> String {
        let (bytes, response) = try await URLSession.shared.bytes(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw IntentError.networkError
        }

        guard httpResponse.statusCode == 200 else {
            if httpResponse.statusCode == 401 {
                throw IntentError.notAuthenticated
            }
            throw IntentError.networkError
        }

        var accumulated = ""

        for try await line in bytes.lines {
            // SSE format: "data: {json}" or "data: [DONE]"
            guard line.hasPrefix("data: ") else { continue }
            let payload = String(line.dropFirst(6))
            if payload == "[DONE]" { break }

            guard let data = payload.data(using: .utf8),
                  let event = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let eventType = event["event_type"] as? String
            else { continue }

            let eventPayload = event["payload"] as? [String: Any]

            switch eventType {
            case "token_stream":
                // Incremental token — append to accumulated text
                if let token = eventPayload?["token"] as? String {
                    accumulated += token
                }
            case "result_ready":
                // Final result — use the full response text if available
                if let response = eventPayload?["response"] as? String, !response.isEmpty {
                    accumulated = response
                }
            case "error":
                if let message = eventPayload?["message"] as? String {
                    throw IntentError.serverError(message)
                }
            case "done":
                break
            default:
                continue
            }
        }

        return accumulated
    }
}

// MARK: - Supporting types

@available(iOS 16.0, *)
private enum IntentError: Error, LocalizedError {
    case emptyMessage
    case notAuthenticated
    case networkError
    case serverError(String)

    var errorDescription: String? {
        switch self {
        case .emptyMessage:
            return "Please provide a message to send to Noa."
        case .notAuthenticated:
            return "You must be signed in to Noa to use this shortcut."
        case .networkError:
            return "Could not connect to Noa. Please check your network."
        case .serverError(let msg):
            return "Noa encountered an error: \(msg)"
        }
    }
}

/// Request body matching the backend `ChatRequest` schema.
private struct ChatRequestBody: Encodable, Sendable {
    let message: String
    let threadId: UUID?
    let privacyMode: String

    enum CodingKeys: String, CodingKey {
        case message
        case threadId = "thread_id"
        case privacyMode = "privacy_mode"
    }
}
#endif

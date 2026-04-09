// ChatModels.swift — Thread, Message, ChatRequest, SSEEvent
// Spec ref: SPEC.md §10.1, §22.2, §29.1

import Foundation

// MARK: - Thread

/// A conversation thread. Mirrors backend Conversation schema.
public struct Thread: Codable, Sendable, Identifiable {
    public let id: UUID
    public let userId: UUID?
    /// Optional title; may be null until the backend derives one from the first message.
    public let title: String?
    public let createdAt: Date?
    public let updatedAt: Date?

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case title
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }

    public init(id: UUID, userId: UUID? = nil, title: String?, createdAt: Date? = nil, updatedAt: Date? = nil) {
        self.id = id
        self.userId = userId
        self.title = title
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
}

// MARK: - Message

/// Role of a chat message participant.
public enum MessageRole: String, Codable, Sendable {
    case user
    case assistant
    case system
    case tool
}

/// A single message within a thread.
public struct Message: Codable, Sendable, Identifiable {
    public let id: UUID
    public let threadId: UUID
    public let role: MessageRole
    public let content: String
    public let createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case threadId = "thread_id"
        case role
        case content
        case createdAt = "created_at"
    }

    public init(id: UUID, threadId: UUID, role: MessageRole, content: String, createdAt: Date) {
        self.id = id
        self.threadId = threadId
        self.role = role
        self.content = content
        self.createdAt = createdAt
    }
}

// MARK: - ChatRequest

/// Request body for POST /api/v1/chat.
/// Spec ref: SPEC.md §22.2, §6.2 — privacy_mode and provider are required by the backend.
public struct ChatRequest: Codable, Sendable {
    public let message: String
    /// Optional existing thread to continue; nil creates a new thread.
    public let threadId: UUID?
    /// Domain routing: "private" (Ollama, stays on-device) or "external" (cloud LLM).
    public let privacyMode: String
    /// LLM provider to use (e.g. "anthropic", "openai", "google_ai", "ollama").
    public let provider: String?
    /// Specific model override (optional; backend uses defaults if nil).
    public let model: String?
    /// LLM sampling temperature (0.0–1.0). Optional — backend uses its default if nil.
    public let temperature: Float?
    /// Maximum output token budget. Optional — backend uses its default if nil.
    public let maxTokens: Int?

    enum CodingKeys: String, CodingKey {
        case message
        case threadId = "thread_id"
        case privacyMode = "privacy_mode"
        case provider
        case model
        case temperature
        case maxTokens = "max_tokens"
    }

    public init(
        message: String,
        threadId: UUID? = nil,
        privacyMode: String = "private",
        provider: String? = nil,
        model: String? = nil,
        temperature: Float? = nil,
        maxTokens: Int? = nil
    ) {
        self.message = message
        self.threadId = threadId
        self.privacyMode = privacyMode
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.maxTokens = maxTokens
    }
}

// MARK: - SSEEventType

/// All backend SSE stream event types.
/// Spec ref: SPEC.md §22.2, VALID_EVENT_TYPES in noa/runs/schemas.py
public enum SSEEventType: String, Codable, Sendable {
    case messageReceived = "message_received"
    case classificationDone = "classification_done"
    case stepStarted = "step_started"
    case tokenStream = "token_stream"
    case toolCalled = "tool_called"
    case toolResult = "tool_result"
    case approvalRequested = "approval_requested"
    case approvalReceived = "approval_received"
    case artifactCreated = "artifact_created"
    case resultReady = "result_ready"
    case error
    case meta
    // OV8: ask_user interrupt
    case askUser = "ask_user"
    // OV10: tool lifecycle events (UX-H10)
    case toolStart = "tool_start"
    case toolEnd = "tool_end"
    case queued
    case compaction
}

// MARK: - SSEEvent

/// A parsed Server-Sent Event from the chat stream.
/// The backend emits: `data: {"event_type": "...", "payload": {...}}\n\n`
/// Spec ref: SPEC.md §22.2
public struct SSEEvent: Codable, Sendable {
    public let eventType: String
    /// Free-form payload dictionary. Contents vary by event type.
    public let payload: [String: AnyCodable]?

    enum CodingKeys: String, CodingKey {
        case eventType = "event_type"
        case payload
    }

    public init(eventType: String, payload: [String: AnyCodable]? = nil) {
        self.eventType = eventType
        self.payload = payload
    }

    /// The parsed event type, or nil if the backend sent an unknown value.
    public var type: SSEEventType? {
        SSEEventType(rawValue: eventType)
    }
}

// MARK: - AnyCodable

/// Type-erasing Codable wrapper for JSON values of unknown type.
/// Used for SSE `payload` dictionaries.
public struct AnyCodable: Codable, Sendable {
    public let value: any Sendable

    public init(_ value: any Sendable) {
        self.value = value
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            value = Optional<Int>.none as any Sendable
        } else if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            value = dict
        } else {
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "AnyCodable: unsupported value type"
            )
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case let bool as Bool:
            try container.encode(bool)
        case let int as Int:
            try container.encode(int)
        case let double as Double:
            try container.encode(double)
        case let string as String:
            try container.encode(string)
        case let array as [AnyCodable]:
            try container.encode(array)
        case let dict as [String: AnyCodable]:
            try container.encode(dict)
        default:
            try container.encodeNil()
        }
    }
}

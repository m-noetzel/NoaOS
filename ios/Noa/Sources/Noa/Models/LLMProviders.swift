// LLMProviders.swift — Compile-time catalogue of available LLM providers and models
// Spec ref: SPEC.md §6.2, §22.2
// Phase: PR3 (iOS-H4)
//
// These lists mirror the backend's PROVIDER_MODELS in web/src/pages/Settings.tsx.
// "nil" provider/model means "use the server default" — no override is sent.

import Foundation

// MARK: - LLMProvider

/// A known LLM provider that can be requested per-message.
public struct LLMProvider: Identifiable, Sendable {
    public let id: String          // e.g. "anthropic"
    public let displayName: String // e.g. "Anthropic"
    public let models: [LLMModel]

    public init(id: String, displayName: String, models: [LLMModel]) {
        self.id = id
        self.displayName = displayName
        self.models = models
    }
}

// MARK: - LLMModel

public struct LLMModel: Identifiable, Sendable {
    public let id: String          // e.g. "gpt-4.1"
    public let displayName: String // e.g. "GPT-4.1"

    public init(id: String, displayName: String) {
        self.id = id
        self.displayName = displayName
    }
}

// MARK: - Available providers

/// The full catalogue of providers available through the Noa backend.
/// Matches web/src/pages/Settings.tsx PROVIDER_MODELS.
public enum LLMProviders {

    public static let all: [LLMProvider] = [
        LLMProvider(id: "anthropic", displayName: "Anthropic", models: [
            LLMModel(id: "claude-sonnet-4-5",  displayName: "Claude Sonnet 4.5"),
            LLMModel(id: "claude-opus-4-5",    displayName: "Claude Opus 4.5"),
        ]),
        LLMProvider(id: "openai", displayName: "OpenAI", models: [
            LLMModel(id: "gpt-4.1",      displayName: "GPT-4.1"),
            LLMModel(id: "gpt-4.1-mini", displayName: "GPT-4.1 Mini"),
            LLMModel(id: "gpt-4o",       displayName: "GPT-4o"),
        ]),
        LLMProvider(id: "google_ai", displayName: "Google AI", models: [
            LLMModel(id: "gemini-2.5-pro", displayName: "Gemini 2.5 Pro"),
        ]),
        LLMProvider(id: "ollama", displayName: "Ollama (Local)", models: [
            LLMModel(id: "llama-3.1-70b", displayName: "Llama 3.1 70B (Local)"),
        ]),
    ]

    /// Returns the `LLMProvider` matching the given id, or `nil` if unknown.
    public static func provider(id: String) -> LLMProvider? {
        all.first { $0.id == id }
    }

    /// Returns the models for the given provider id.
    /// Returns an empty array for unknown provider ids.
    public static func models(for providerId: String) -> [LLMModel] {
        provider(id: providerId)?.models ?? []
    }
}

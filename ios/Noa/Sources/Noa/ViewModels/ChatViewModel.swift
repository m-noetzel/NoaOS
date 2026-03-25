// ChatViewModel.swift — SSE lifecycle and token accumulation
// Spec ref: SPEC.md §22.2, §29.2, Phase iOS5 deliverable 2
//
// Responsibilities:
//   - Manages the active SSE stream (one at a time — no duplicate sends)
//   - Accumulates token_stream events into the assistant reply
//   - Appends optimistic user message; rolls back on failure
//   - Surfaces inline indicators: tool_called, approval_requested,
//     classification_done, step_started
//   - Captures run_id and thread_id from the meta event

import Foundation
import Observation

// MARK: - InlineIndicator

/// Transient inline status shown during a streaming response.
public enum InlineIndicator: Sendable {
    case classificationDone(domain: String)
    case stepStarted(step: String)
    case toolCalled(toolName: String)
    case approvalRequested(toolName: String)
}

// MARK: - ChatMessage (display model)

/// A message shown in the ChatView bubble list.
public struct ChatMessage: Identifiable, Sendable {
    public let id: UUID
    public let role: MessageRole
    /// Accumulated text content (may grow token by token during streaming).
    public var content: String
    public let isOptimistic: Bool  // True for the user bubble appended before server ack

    public init(id: UUID = UUID(), role: MessageRole, content: String, isOptimistic: Bool = false) {
        self.id = id
        self.role = role
        self.content = content
        self.isOptimistic = isOptimistic
    }
}

// MARK: - ChatViewModel

@Observable
@MainActor
public final class ChatViewModel {

    // MARK: - Published state

    public var messages: [ChatMessage] = []
    public var isStreaming: Bool = false
    public var errorMessage: String?
    public var currentIndicator: InlineIndicator?

    /// run_id from the most recent meta event.
    public var currentRunId: String?
    /// thread_id from the meta event (may differ from the selected thread if a new one was created).
    public var capturedThreadId: String?

    // MARK: - Composer state

    public var privacyMode: String = "private"
    public var selectedProvider: String? = nil
    public var selectedModel: String? = nil

    // MARK: - Private

    private let chatService: ChatService
    private let sharedDataManager: SharedDataManager
    private var streamTask: Task<Void, Never>?
    /// iOS-M2: Active history-load task. Cancelled before starting a new load
    /// so that rapid thread switching cannot deliver stale messages.
    private var loadTask: Task<Void, Never>?
    /// Index of the optimistic user message (for rollback on failure).
    private var optimisticIndex: Int?
    /// The title of the currently loaded thread (used to update the widget).
    public var currentThreadTitle: String?

    // MARK: - Init

    public init(chatService: ChatService, sharedDataManager: SharedDataManager = SharedDataManager()) {
        self.chatService = chatService
        self.sharedDataManager = sharedDataManager
    }

    // MARK: - Actions

    /// Sends a message. No-ops while a stream is already active.
    public func sendMessage(text: String, threadId: UUID?) {
        guard !isStreaming, !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        // Optimistic append
        let userMsg = ChatMessage(role: .user, content: text, isOptimistic: true)
        messages.append(userMsg)
        optimisticIndex = messages.count - 1

        // Placeholder for the streaming assistant response
        let assistantMsg = ChatMessage(role: .assistant, content: "")
        messages.append(assistantMsg)
        let assistantIndex = messages.count - 1

        isStreaming = true
        errorMessage = nil
        currentIndicator = nil

        let request = ChatRequest(
            message: text,
            threadId: threadId,
            privacyMode: privacyMode,
            provider: selectedProvider,
            model: selectedModel
        )

        streamTask = Task { [weak self] in
            guard let self else { return }
            do {
                let stream = await chatService.sendMessage(request)
                for try await event in stream {
                    guard !Task.isCancelled else { break }
                    self.handleEvent(event, assistantIndex: assistantIndex)
                }
            } catch {
                self.handleStreamError(error, assistantIndex: assistantIndex)
            }
            self.finishStream()
        }
    }

    /// Loads message history for the given thread.
    ///
    /// iOS-M2: Cancels any in-flight load before starting a new one, so that
    /// rapid thread switching cannot deliver stale messages from the old thread.
    public func loadHistory(threadId: UUID) async {
        // Cancel any previous load task before starting
        loadTask?.cancel()
        loadTask = Task { [weak self] in
            guard let self else { return }
            do {
                let history = try await chatService.listMessages(threadId: threadId)
                guard !Task.isCancelled else { return }
                self.messages = history.map { msg in
                    ChatMessage(id: msg.id, role: msg.role, content: msg.content)
                }
            } catch {
                guard !Task.isCancelled else { return }
                self.errorMessage = error.localizedDescription
            }
        }
        await loadTask?.value
    }

    /// Cancels the active SSE stream and clears the current message list.
    ///
    /// Call this before switching to a different thread so that:
    /// 1. The old SSE connection is terminated (no duplicate deliveries).
    /// 2. The message list is empty when the new thread starts loading.
    /// 3. Any in-flight history load is cancelled (iOS-M2 race fix).
    ///
    /// iOS-H2: previously only `cancelStream()` existed but `clearMessages()` was
    /// separate; callers had to remember both. This combined method is the single
    /// correct call site for thread switching.
    public func cancelStreamAndClear() {
        streamTask?.cancel()
        streamTask = nil
        loadTask?.cancel()
        loadTask = nil
        isStreaming = false
        messages = []
        currentIndicator = nil
        errorMessage = nil
        currentRunId = nil
        capturedThreadId = nil
        optimisticIndex = nil
    }

    /// Cancels the active SSE stream.
    public func cancelStream() {
        streamTask?.cancel()
        streamTask = nil
        isStreaming = false
    }

    // MARK: - SSE event handling

    private func handleEvent(_ event: SSEEvent, assistantIndex: Int) {
        guard let type = event.type else { return }

        switch type {
        case .meta:
            currentRunId = event.payload?["run_id"]?.value as? String
            capturedThreadId = event.payload?["thread_id"]?.value as? String

        case .classificationDone:
            // Backend sends "privacy_mode" (e.g. "private" or "external") — SPEC §22.2
            let domain = event.payload?["privacy_mode"]?.value as? String ?? "unknown"
            currentIndicator = .classificationDone(domain: domain)

        case .stepStarted:
            let step = event.payload?["step"]?.value as? String ?? ""
            currentIndicator = .stepStarted(step: step)

        case .toolCalled:
            let toolName = event.payload?["tool_name"]?.value as? String ?? "tool"
            currentIndicator = .toolCalled(toolName: toolName)

        case .approvalRequested:
            let toolName = event.payload?["tool_name"]?.value as? String ?? "tool"
            currentIndicator = .approvalRequested(toolName: toolName)

        case .tokenStream:
            let token = event.payload?["token"]?.value as? String ?? ""
            if assistantIndex < messages.count {
                messages[assistantIndex].content += token
            }

        case .resultReady:
            // Backend sends "response" as the final canonical text — SPEC §22.2
            let text = event.payload?["response"]?.value as? String ?? ""
            if assistantIndex < messages.count && !text.isEmpty {
                messages[assistantIndex].content = text
            }
            currentIndicator = nil
            // Update the widget shared storage with the latest assistant response
            // so the home screen widget shows fresh content after each conversation.
            if !text.isEmpty {
                sharedDataManager.saveLastThreadSnapshot(
                    threadTitle: currentThreadTitle,
                    lastMessagePreview: text,
                    lastMessageDate: .now
                )
            }

        case .error:
            let msg = event.payload?["message"]?.value as? String ?? "Unknown error"
            errorMessage = msg
            // Remove the empty assistant placeholder
            if assistantIndex < messages.count {
                messages.remove(at: assistantIndex)
            }
            rollbackOptimistic()

        default:
            break
        }
    }

    private func handleStreamError(_ error: Error, assistantIndex: Int) {
        errorMessage = error.localizedDescription
        // Remove empty assistant placeholder
        if assistantIndex < messages.count {
            messages.remove(at: assistantIndex)
        }
        rollbackOptimistic()
    }

    private func finishStream() {
        isStreaming = false
        streamTask = nil
        optimisticIndex = nil
    }

    private func rollbackOptimistic() {
        if let idx = optimisticIndex, idx < messages.count {
            messages.remove(at: idx)
        }
        optimisticIndex = nil
    }
}

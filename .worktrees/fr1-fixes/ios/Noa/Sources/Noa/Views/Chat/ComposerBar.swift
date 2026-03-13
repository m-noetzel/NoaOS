// ComposerBar.swift — Text input, send button, voice button, and privacy/model selectors
// Spec ref: SPEC.md §29.2, Phase iOS5 deliverable 1, Phase iOS8 deliverable 7
// Phase PR3: iOS-H4 — inline provider/model selector added

import SwiftUI

/// Composer bar at the bottom of ChatView.
/// Binds to `ChatViewModel` for text, privacy mode, provider, and model state.
/// Optionally embeds a `VoiceRecordButton` when a `VoiceViewModel` is provided (iOS8).
///
/// iOS-H4: the provider and model selectors that were previously only in Settings are
/// now also available inline in the composer, so the user can change the LLM per-message
/// without leaving the chat screen.
public struct ComposerBar: View {

    @Bindable var viewModel: ChatViewModel
    /// Optional voice view model injected by the parent ChatView (iOS8).
    var voiceViewModel: VoiceViewModel?
    @State private var text: String = ""
    /// Controls whether the provider/model row is expanded.
    @State private var showModelPicker: Bool = false
    let onSend: (String) -> Void

    // MARK: - Init

    /// Full init: supports both text and voice input.
    public init(
        viewModel: ChatViewModel,
        voiceViewModel: VoiceViewModel? = nil,
        onSend: @escaping (String) -> Void
    ) {
        self.viewModel = viewModel
        self.voiceViewModel = voiceViewModel
        self.onSend = onSend
    }

    // MARK: - Derived state

    /// Available models for the currently-selected provider.
    /// Empty when no provider is selected (uses server default).
    private var availableModels: [LLMModel] {
        guard let providerId = viewModel.selectedProvider else { return [] }
        return LLMProviders.models(for: providerId)
    }

    /// Display label for the current provider + model selection.
    private var modelLabel: String {
        let providerName = viewModel.selectedProvider
            .flatMap { LLMProviders.provider(id: $0)?.displayName } ?? "Default"
        let modelName = viewModel.selectedModel
            .flatMap { id in availableModels.first { $0.id == id }?.displayName } ?? nil
        if let modelName {
            return "\(providerName) · \(modelName)"
        }
        return providerName
    }

    public var body: some View {
        VStack(spacing: 0) {
            Divider()

            // MARK: Provider/model picker row (collapsible)
            if showModelPicker {
                modelPickerRow
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }

            // MARK: Main composer row
            HStack(alignment: .bottom, spacing: 8) {
                // Privacy mode picker
                Picker("Privacy", selection: $viewModel.privacyMode) {
                    Label("Private", systemImage: "lock").tag("private")
                    Label("External", systemImage: "globe").tag("external")
                }
                .pickerStyle(.menu)
                .font(.footnote)
                .frame(maxWidth: 120)

                // Text input
                TextField("Message", text: $text, axis: .vertical)
                    .lineLimit(1...6)
                    .textFieldStyle(.plain)
                    .padding(.vertical, 8)

                // Model picker toggle (iOS-H4)
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        showModelPicker.toggle()
                    }
                } label: {
                    Image(systemName: "cpu")
                        .font(.system(size: 18))
                        .foregroundStyle(viewModel.selectedProvider != nil ? Color.accentColor : Color.secondary)
                }
                .accessibilityLabel("Select AI model — \(modelLabel)")

                // Voice record button (iOS8) — shown when voiceViewModel is available.
                if let voiceVM = voiceViewModel {
                    VoiceRecordButton(viewModel: voiceVM) { transcribedText in
                        // Transcription result populates the text field.
                        text = transcribedText
                    }
                }

                // Send button — disabled while streaming or text is empty
                Button {
                    let msg = text.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !msg.isEmpty else { return }
                    text = ""
                    onSend(msg)
                } label: {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.system(size: 28))
                        .foregroundStyle(
                            (viewModel.isStreaming || text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                                ? Color.secondary
                                : Color.accentColor
                        )
                }
                .disabled(viewModel.isStreaming || text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
        }
        .background(.regularMaterial)
    }

    // MARK: - Model picker row

    @ViewBuilder
    private var modelPickerRow: some View {
        VStack(spacing: 0) {
            Divider()
            HStack(spacing: 12) {
                // Provider picker
                Picker("Provider", selection: providerBinding) {
                    Text("Default").tag(String?.none)
                    ForEach(LLMProviders.all) { provider in
                        Text(provider.displayName).tag(Optional(provider.id))
                    }
                }
                .pickerStyle(.menu)
                .font(.footnote)

                // Model picker — shown only when a provider is selected
                if viewModel.selectedProvider != nil && !availableModels.isEmpty {
                    Picker("Model", selection: modelBinding) {
                        Text("Default model").tag(String?.none)
                        ForEach(availableModels) { model in
                            Text(model.displayName).tag(Optional(model.id))
                        }
                    }
                    .pickerStyle(.menu)
                    .font(.footnote)
                }

                Spacer()

                // Clear selection
                if viewModel.selectedProvider != nil {
                    Button("Reset") {
                        viewModel.selectedProvider = nil
                        viewModel.selectedModel = nil
                    }
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
        }
    }

    // MARK: - Bindings

    private var providerBinding: Binding<String?> {
        Binding(
            get: { viewModel.selectedProvider },
            set: { newProvider in
                viewModel.selectedProvider = newProvider
                // Reset model when provider changes — the old model may not be valid.
                viewModel.selectedModel = nil
            }
        )
    }

    private var modelBinding: Binding<String?> {
        Binding(
            get: { viewModel.selectedModel },
            set: { viewModel.selectedModel = $0 }
        )
    }
}

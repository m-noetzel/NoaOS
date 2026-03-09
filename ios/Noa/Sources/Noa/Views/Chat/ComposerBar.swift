// ComposerBar.swift — Text input, send button, voice button, and privacy/model selectors
// Spec ref: SPEC.md §29.2, Phase iOS5 deliverable 1, Phase iOS8 deliverable 7

import SwiftUI

/// Composer bar at the bottom of ChatView.
/// Binds to `ChatViewModel` for text, privacy mode, and provider state.
/// Optionally embeds a `VoiceRecordButton` when a `VoiceViewModel` is provided (iOS8).
public struct ComposerBar: View {

    @Bindable var viewModel: ChatViewModel
    /// Optional voice view model injected by the parent ChatView (iOS8).
    var voiceViewModel: VoiceViewModel?
    @State private var text: String = ""
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

    public var body: some View {
        VStack(spacing: 0) {
            Divider()
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
}

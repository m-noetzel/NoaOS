// ComposerBar.swift — Text input, send button, and privacy/model selectors
// Spec ref: SPEC.md §29.2, Phase iOS5 deliverable 1

import SwiftUI

/// Composer bar at the bottom of ChatView.
/// Binds to `ChatViewModel` for text, privacy mode, and provider state.
public struct ComposerBar: View {

    @Bindable var viewModel: ChatViewModel
    @State private var text: String = ""
    let onSend: (String) -> Void

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

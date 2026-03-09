// ChatView.swift — Primary chat screen with SSE streaming
// Spec ref: SPEC.md §22.2, §29.2, Phase iOS5 deliverable 1
//
// Layout: scrollable message list + inline indicator row + ComposerBar

import SwiftUI

public struct ChatView: View {

    @Bindable var viewModel: ChatViewModel
    let threadId: UUID?

    public init(viewModel: ChatViewModel, threadId: UUID? = nil) {
        self.viewModel = viewModel
        self.threadId = threadId
    }

    public var body: some View {
        VStack(spacing: 0) {
            // Message list
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(viewModel.messages) { message in
                            MessageBubble(message: message)
                                .id(message.id)
                        }
                        // Inline indicator (tool call / approval / classification)
                        if let indicator = viewModel.currentIndicator {
                            ToolCallCard(indicator: indicator)
                        }
                        // Anchor for auto-scroll
                        Color.clear
                            .frame(height: 1)
                            .id("bottom")
                    }
                    .padding(.top, 8)
                }
                .onChange(of: viewModel.messages.count) { _, _ in
                    withAnimation { proxy.scrollTo("bottom", anchor: .bottom) }
                }
                .onChange(of: viewModel.currentIndicator != nil) { _, _ in
                    withAnimation { proxy.scrollTo("bottom", anchor: .bottom) }
                }
            }

            // Error banner
            if let error = viewModel.errorMessage {
                HStack {
                    Image(systemName: "exclamationmark.triangle")
                    Text(error)
                        .font(.footnote)
                    Spacer()
                    Button("Dismiss") { viewModel.errorMessage = nil }
                        .font(.footnote)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color(.systemOrange).opacity(0.15))
                .foregroundStyle(.orange)
            }

            ComposerBar(viewModel: viewModel) { text in
                viewModel.sendMessage(text: text, threadId: threadId)
            }
        }
        .navigationTitle("Chat")
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .task {
            if let threadId {
                await viewModel.loadHistory(threadId: threadId)
            }
        }
    }
}

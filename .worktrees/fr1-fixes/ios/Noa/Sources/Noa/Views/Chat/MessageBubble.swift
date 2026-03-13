// MessageBubble.swift — Individual message rendering
// Spec ref: SPEC.md §29.2, Phase iOS5 deliverable 1
//
// Shows user messages right-aligned and assistant messages left-aligned.
// Supports in-progress streaming state (trailing ellipsis on empty content).

import SwiftUI

public struct MessageBubble: View {

    let message: ChatMessage

    private var isUser: Bool { message.role == .user }

    public var body: some View {
        HStack {
            if isUser { Spacer(minLength: 60) }
            VStack(alignment: isUser ? .trailing : .leading, spacing: 4) {
                if message.content.isEmpty && !isUser {
                    // In-progress streaming indicator
                    ProgressView()
                        .scaleEffect(0.7)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(Color.secondary.opacity(0.15))
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                } else {
                    Text(message.content)
                        .textSelection(.enabled)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(isUser ? Color.accentColor : Color.secondary.opacity(0.15))
                        .foregroundStyle(isUser ? .white : .primary)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                }
            }
            if !isUser { Spacer(minLength: 60) }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 2)
    }
}

// EmptyStateView.swift — Reusable empty state view
// Spec ref: SPEC.md §37 (Definition of Done — polish pass)
// Phase: iOS11

import SwiftUI

/// A reusable empty state view with an icon, title, and optional action button.
///
/// Usage:
/// ```swift
/// if viewModel.approvals.isEmpty {
///     EmptyStateView(
///         icon: "checkmark.seal",
///         title: "No Pending Approvals",
///         message: "You're all caught up!"
///     )
/// }
/// ```
public struct EmptyStateView: View {

    // MARK: - Properties

    public let icon: String
    public let title: String
    public let message: String?
    public let actionLabel: String?
    public let onAction: (() -> Void)?

    // MARK: - Init

    public init(
        icon: String = "tray",
        title: String,
        message: String? = nil,
        actionLabel: String? = nil,
        onAction: (() -> Void)? = nil
    ) {
        self.icon = icon
        self.title = title
        self.message = message
        self.actionLabel = actionLabel
        self.onAction = onAction
    }

    // MARK: - Body

    public var body: some View {
        VStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 48))
                .foregroundStyle(.quaternary)
                .accessibilityHidden(true)

            Text(title)
                .font(.headline)
                .foregroundStyle(.primary)
                .multilineTextAlignment(.center)
                .accessibilityAddTraits(.isHeader)

            if let message {
                Text(message)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }

            if let actionLabel, let onAction {
                Button(actionLabel, action: onAction)
                    .buttonStyle(.bordered)
                    .padding(.top, 4)
                    .accessibilityLabel(actionLabel)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .accessibilityElement(children: .contain)
        .accessibilityLabel(accessibilityDescription)
    }

    // MARK: - Private

    private var accessibilityDescription: String {
        var parts = [title]
        if let msg = message { parts.append(msg) }
        return parts.joined(separator: ". ")
    }
}

#if DEBUG
#Preview("Approvals empty") {
    EmptyStateView(
        icon: "checkmark.seal",
        title: "No Pending Approvals",
        message: "You're all caught up! New approvals will appear here.",
        actionLabel: "Refresh",
        onAction: {}
    )
}

#Preview("Threads empty") {
    EmptyStateView(
        icon: "bubble.left.and.bubble.right",
        title: "No Conversations Yet",
        message: "Start chatting with Noa to see your threads here."
    )
}
#endif

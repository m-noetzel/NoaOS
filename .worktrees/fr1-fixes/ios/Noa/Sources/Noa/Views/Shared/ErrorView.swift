// ErrorView.swift — Reusable error state view
// Spec ref: SPEC.md §37 (Definition of Done — polish pass)
// Phase: iOS11

import SwiftUI

/// A reusable full-screen error state view with an optional retry action.
///
/// Usage:
/// ```swift
/// if let error = viewModel.errorMessage {
///     ErrorView(
///         message: error,
///         retryLabel: "Try Again",
///         onRetry: { await viewModel.load() }
///     )
/// }
/// ```
public struct ErrorView: View {

    // MARK: - Properties

    public let message: String
    public let retryLabel: String
    public let onRetry: (() -> Void)?

    // MARK: - Init

    public init(
        message: String,
        retryLabel: String = "Retry",
        onRetry: (() -> Void)? = nil
    ) {
        self.message = message
        self.retryLabel = retryLabel
        self.onRetry = onRetry
    }

    // MARK: - Body

    public var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 44))
                .foregroundStyle(.secondary)
                .accessibilityHidden(true)

            Text(message)
                .font(.body)
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 32)
                .accessibilityLabel("Error: \(message)")

            if let onRetry {
                Button(retryLabel, action: onRetry)
                    .buttonStyle(.bordered)
                    .accessibilityLabel(retryLabel)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .accessibilityElement(children: .contain)
    }
}

#if DEBUG
#Preview("With retry") {
    ErrorView(
        message: "Could not load approvals. Check your connection and try again.",
        retryLabel: "Try Again",
        onRetry: {}
    )
}

#Preview("Without retry") {
    ErrorView(message: "Something went wrong.")
}
#endif

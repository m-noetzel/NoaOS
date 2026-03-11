// BatchApprovalBar.swift — Sticky bottom bar for batch approve/deny
// Spec ref: SPEC.md §23.2, Phase iOS7 deliverable 7

import SwiftUI

/// A compact toolbar shown at the bottom of the approvals list when one or
/// more approvals are selected, allowing the user to approve or deny all at once.
public struct BatchApprovalBar: View {

    let count: Int
    let isProcessing: Bool
    let onApprove: () -> Void
    let onDeny: () -> Void

    public init(
        count: Int,
        isProcessing: Bool = false,
        onApprove: @escaping () -> Void,
        onDeny: @escaping () -> Void
    ) {
        self.count = count
        self.isProcessing = isProcessing
        self.onApprove = onApprove
        self.onDeny = onDeny
    }

    public var body: some View {
        HStack(spacing: 12) {
            if isProcessing {
                ProgressView()
                    .controlSize(.small)
            }
            Text("\(count) selected")
                .font(.subheadline.bold())
                .foregroundStyle(.primary)

            Spacer()

            Button(role: .destructive, action: onDeny) {
                Label("Deny All", systemImage: "xmark.circle.fill")
            }
            .buttonStyle(.bordered)
            .disabled(isProcessing)

            Button(action: onApprove) {
                Label("Approve All", systemImage: "checkmark.circle.fill")
            }
            .buttonStyle(.borderedProminent)
            .tint(.green)
            .disabled(isProcessing)
        }
        .padding(.horizontal)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial)
    }
}

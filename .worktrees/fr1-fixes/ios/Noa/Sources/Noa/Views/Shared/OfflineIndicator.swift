// OfflineIndicator.swift — Offline banner with queue count badge
// Spec ref: SPEC.md §29.3 item 6
// Phase: iOS9

import SwiftUI

/// A compact banner that appears when the device is offline.
/// Displays a queue count badge so the user knows how many requests are pending.
///
/// Usage:
/// ```swift
/// VStack(spacing: 0) {
///     if !isConnected {
///         OfflineIndicator(queueCount: pendingCount)
///     }
///     // rest of content
/// }
/// ```
public struct OfflineIndicator: View {

    public let queueCount: Int

    public init(queueCount: Int = 0) {
        self.queueCount = queueCount
    }

    public var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "wifi.slash")
                .font(.caption.weight(.semibold))

            Text("Offline")
                .font(.caption.weight(.semibold))

            Spacer()

            if queueCount > 0 {
                Text("\(queueCount) pending")
                    .font(.caption2)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Color.white.opacity(0.25), in: Capsule())
            }
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Color.orange, in: Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityText)
    }

    private var accessibilityText: String {
        if queueCount > 0 {
            return "Offline. \(queueCount) request\(queueCount == 1 ? "" : "s") pending."
        }
        return "Offline."
    }
}

#if DEBUG
#Preview("Offline with pending") {
    VStack(spacing: 0) {
        OfflineIndicator(queueCount: 3)
        Color.gray.opacity(0.1)
    }
}

#Preview("Offline no pending") {
    OfflineIndicator(queueCount: 0)
}
#endif

// ToolCallCard.swift — Inline tool call display
// Spec ref: SPEC.md §22.2, Phase iOS5 deliverable 5

import SwiftUI

/// Compact card shown inline in the message list when a tool is called
/// or an approval is required during a streaming response.
public struct ToolCallCard: View {

    let indicator: InlineIndicator

    public var body: some View {
        HStack(spacing: 8) {
            Image(systemName: iconName)
                .foregroundStyle(iconColor)
                .font(.system(size: 14, weight: .semibold))
            Text(label)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(Color.secondary.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .padding(.horizontal, 12)
        .padding(.vertical, 2)
    }

    private var iconName: String {
        switch indicator {
        case .toolCalled:          return "wrench.and.screwdriver"
        case .approvalRequested:   return "hand.raised"
        case .classificationDone:  return "shield.lefthalf.filled"
        case .stepStarted:         return "arrow.trianglehead.forward"
        }
    }

    private var iconColor: Color {
        switch indicator {
        case .approvalRequested:   return .orange
        case .toolCalled:          return .accentColor
        case .classificationDone:  return .green
        case .stepStarted:         return .secondary
        }
    }

    private var label: String {
        switch indicator {
        case .toolCalled(let name):          return "Calling \(name)…"
        case .approvalRequested(let name):   return "Approval needed: \(name)"
        case .classificationDone(let domain): return "Routed to \(domain)"
        case .stepStarted(let step):         return step
        }
    }
}

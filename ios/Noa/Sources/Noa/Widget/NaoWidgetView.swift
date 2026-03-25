// NaoWidgetView.swift — SwiftUI view for the Noa home screen widget
// Spec ref: SPEC.md §13.1, Phase IS1
//
// Responsibilities:
//   - Render thread title, last message preview, and relative timestamp
//   - Support small and medium widget families
//   - Show an empty-state prompt when no thread data is available

#if canImport(WidgetKit)
import WidgetKit
import SwiftUI

// MARK: - NaoWidgetView

public struct NaoWidgetView: View {
    let entry: NaoWidgetEntry

    @Environment(\.widgetFamily) private var family

    public init(entry: NaoWidgetEntry) {
        self.entry = entry
    }

    public var body: some View {
        switch family {
        case .systemSmall:
            smallWidget
        case .systemMedium:
            mediumWidget
        default:
            smallWidget
        }
    }

    // MARK: - Small widget (2x2)

    private var smallWidget: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: "bubble.left.and.bubble.right.fill")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Spacer()
                if let msgDate = entry.lastMessageDate {
                    Text(msgDate, style: .relative)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            if let title = entry.threadTitle {
                Text(title)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .lineLimit(2)
                    .foregroundStyle(.primary)
            } else {
                Text("No threads yet")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if let preview = entry.lastMessagePreview {
                Text(preview)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            } else if entry.threadTitle == nil {
                Text("Open Noa to start chatting")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        .containerBackground(Color(.systemBackground), for: .widget)
    }

    // MARK: - Medium widget (4x2)

    private var mediumWidget: some View {
        HStack(spacing: 12) {
            // Left: Icon column
            VStack {
                Image(systemName: "sparkles")
                    .font(.title2)
                    .foregroundStyle(.blue)
                Spacer()
            }

            // Right: Content column
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("Noa")
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundStyle(.primary)
                    Spacer()
                    if let msgDate = entry.lastMessageDate {
                        Text(msgDate, style: .relative)
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }

                if let title = entry.threadTitle {
                    Text(title)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .lineLimit(1)
                        .foregroundStyle(.primary)

                    if let preview = entry.lastMessagePreview {
                        Text(preview)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(3)
                    }
                } else {
                    Text("No threads yet")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Text("Open Noa to start chatting")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        .containerBackground(Color(.systemBackground), for: .widget)
    }
}
#endif

// NaoWidget.swift — Main WidgetKit widget definition for Noa
// Spec ref: SPEC.md §13.1, Phase IS1
//
// Responsibilities:
//   - Define the StaticConfiguration for the Noa home screen widget
//   - Wire NaoWidgetProvider → NaoWidgetEntry → NaoWidgetView
//   - Declare supported widget families

#if canImport(WidgetKit)
import WidgetKit
import SwiftUI

// MARK: - NaoWidget

/// The Noa home screen widget.
///
/// Displays the title and most recent message preview from the user's latest
/// thread. Data is sourced from the App Group shared UserDefaults written by
/// the main app whenever threads are loaded or a new message arrives.
///
/// Widget cannot make network calls — all data comes from SharedDataManager.
public struct NaoWidget: Widget {
    public static let kind: String = "NaoWidget"

    public init() {}

    public var body: some WidgetConfiguration {
        StaticConfiguration(
            kind: NaoWidget.kind,
            provider: NaoWidgetProvider()
        ) { entry in
            NaoWidgetView(entry: entry)
        }
        .configurationDisplayName("Noa")
        .description("See your latest conversation at a glance.")
        .supportedFamilies([.systemSmall, .systemMedium])
        .contentMarginsDisabled()
    }
}
#endif

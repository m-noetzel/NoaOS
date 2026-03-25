// NaoShortcuts.swift — AppShortcutsProvider that exposes Noa's intents to Siri
// Spec ref: SPEC.md §13.1, Phase IS1
//
// Responsibilities:
//   - Register SendMessageIntent and ListThreadsIntent as App Shortcuts
//   - Provide Siri-pronounceable phrases that trigger each shortcut
//
// The AppShortcutsProvider makes the shortcuts available immediately without
// the user needing to add them manually in the Shortcuts app. Siri learns
// the phrases listed in `appShortcuts`.

#if canImport(AppIntents)
import AppIntents

// MARK: - NaoShortcuts

/// Exposes Noa's App Intents as built-in Siri shortcuts.
///
/// Phrases listed here become the spoken triggers for each shortcut.
/// Apple requires at least one phrase per shortcut and recommends 2–3
/// natural variations.
@available(iOS 16.4, *)
public struct NaoShortcuts: AppShortcutsProvider {

    public static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: SendMessageIntent(),
            phrases: [
                "Send a message to \(.applicationName)",
                "Ask \(.applicationName) something",
                "Message \(.applicationName)",
            ],
            shortTitle: "Send Message",
            systemImageName: "bubble.left.and.bubble.right.fill"
        )

        AppShortcut(
            intent: ListThreadsIntent(),
            phrases: [
                "List my \(.applicationName) threads",
                "Show my \(.applicationName) conversations",
                "What are my recent \(.applicationName) threads",
            ],
            shortTitle: "List Threads",
            systemImageName: "list.bullet.rectangle"
        )
    }
}
#endif

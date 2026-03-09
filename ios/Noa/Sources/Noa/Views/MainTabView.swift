// MainTabView.swift — Root tab navigation (Chat, Runs, Settings)
// Spec ref: SPEC.md §29.2, Phase iOS5 deliverable 4
//
// Uses NavigationSplitView on iPad/large screen and a TabView on iPhone.
// The Chat tab embeds ThreadListView in the sidebar and ChatView in the detail.

import SwiftUI

@MainActor
public struct MainTabView: View {

    // MARK: - Dependencies

    let authViewModel: AuthViewModel
    let chatService: ChatService

    // MARK: - State

    @State private var chatViewModel: ChatViewModel
    @State private var threadListViewModel: ThreadListViewModel
    @State private var selectedThreadId: UUID? = nil

    // MARK: - Init

    public init(authViewModel: AuthViewModel, chatService: ChatService) {
        self.authViewModel = authViewModel
        self.chatService = chatService
        _chatViewModel = State(wrappedValue: ChatViewModel(chatService: chatService))
        _threadListViewModel = State(wrappedValue: ThreadListViewModel(chatService: chatService))
    }

    public var body: some View {
        TabView {
            // MARK: Chat tab
            NavigationSplitView {
                ThreadListView(
                    viewModel: threadListViewModel,
                    selectedThreadId: $selectedThreadId
                )
            } detail: {
                if let threadId = selectedThreadId {
                    ChatView(viewModel: chatViewModel, threadId: threadId)
                } else {
                    ContentUnavailableView(
                        "Select a Thread",
                        systemImage: "bubble.left",
                        description: Text("Pick a thread or start a new one.")
                    )
                }
            }
            .tabItem {
                Label("Chat", systemImage: "bubble.left.and.bubble.right")
            }
            .tag(0)

            // MARK: Settings tab (placeholder — wired in a later phase)
            NavigationStack {
                Text("Settings")
                    .navigationTitle("Settings")
                    .toolbar {
                        ToolbarItem(placement: .primaryAction) {
                            Button("Sign Out") {
                                Task { try? await authViewModel.logout() }
                            }
                        }
                    }
            }
            .tabItem {
                Label("Settings", systemImage: "gearshape")
            }
            .tag(1)
        }
    }
}

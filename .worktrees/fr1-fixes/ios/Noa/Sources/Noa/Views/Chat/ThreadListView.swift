// ThreadListView.swift — Thread sidebar
// Spec ref: SPEC.md §13.1, §29.2, Phase iOS5 deliverable 4

import SwiftUI

public struct ThreadListView: View {

    @Bindable var viewModel: ThreadListViewModel
    @Binding var selectedThreadId: UUID?

    public init(viewModel: ThreadListViewModel, selectedThreadId: Binding<UUID?>) {
        self.viewModel = viewModel
        self._selectedThreadId = selectedThreadId
    }

    public var body: some View {
        Group {
            if viewModel.isLoading && viewModel.threads.isEmpty {
                ProgressView("Loading threads…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if viewModel.threads.isEmpty {
                ContentUnavailableView(
                    "No Threads",
                    systemImage: "bubble.left.and.bubble.right",
                    description: Text("Start a new conversation.")
                )
            } else {
                List(selection: $selectedThreadId) {
                    ForEach(viewModel.threads) { thread in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(thread.title ?? "Untitled")
                                .font(.body)
                                .lineLimit(1)
                            Text(thread.createdAt ?? Date(), style: .relative)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .tag(thread.id)
                    }
                    .onDelete { offsets in
                        Task { await viewModel.deleteThreads(at: offsets) }
                    }
                }
                .listStyle(.sidebar)
            }
        }
        .navigationTitle("Threads")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    Task {
                        let thread = await viewModel.createThread()
                        if let thread {
                            selectedThreadId = thread.id
                        }
                    }
                } label: {
                    Image(systemName: "square.and.pencil")
                }
            }
        }
        .refreshable {
            await viewModel.loadThreads()
        }
        .task {
            await viewModel.loadThreads()
        }
        .alert("Error", isPresented: Binding(
            get: { viewModel.errorMessage != nil },
            set: { if !$0 { viewModel.errorMessage = nil } }
        )) {
            Button("OK", role: .cancel) { viewModel.errorMessage = nil }
        } message: {
            Text(viewModel.errorMessage ?? "")
        }
    }
}

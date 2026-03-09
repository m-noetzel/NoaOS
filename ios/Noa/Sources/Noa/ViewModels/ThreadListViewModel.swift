// ThreadListViewModel.swift — Thread list loading and creation
// Spec ref: SPEC.md §13.1, §29.2, Phase iOS5 deliverable 3
//
// Responsibilities:
//   - Load thread list on appear
//   - Create new thread
//   - Delete thread (swipe-to-delete)
//   - Surface loading and error states to ThreadListView

import Foundation
import Observation

@Observable
@MainActor
public final class ThreadListViewModel {

    // MARK: - Published state

    public var threads: [Thread] = []
    public var isLoading: Bool = false
    public var errorMessage: String?

    // MARK: - Private

    private let chatService: ChatService

    // MARK: - Init

    public init(chatService: ChatService) {
        self.chatService = chatService
    }

    // MARK: - Actions

    /// Loads the thread list. Called on view appear and after create/delete.
    public func loadThreads() async {
        isLoading = true
        errorMessage = nil
        do {
            threads = try await chatService.listThreads()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    /// Creates a new thread with the given title and reloads the list.
    @discardableResult
    public func createThread(title: String = "New thread") async -> Thread? {
        do {
            let thread = try await chatService.createThread(title: title)
            threads.insert(thread, at: 0)
            return thread
        } catch {
            errorMessage = error.localizedDescription
            return nil
        }
    }

    /// Deletes the thread at the given offsets (for swipe-to-delete from onDelete).
    public func deleteThreads(at offsets: IndexSet) async {
        let toDelete = offsets.map { threads[$0] }
        // Optimistic removal
        threads.remove(atOffsets: offsets)
        for thread in toDelete {
            do {
                try await chatService.deleteThread(threadId: thread.id)
            } catch {
                errorMessage = error.localizedDescription
                // Reload to restore the list on failure
                await loadThreads()
                return
            }
        }
    }
}

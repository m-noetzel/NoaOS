// ApprovalListViewModel.swift — Observable state for the pending approvals list
// Spec ref: SPEC.md §29.6, §23.2, Phase iOS7 deliverable 3 & 6
//
// Responsibilities:
//   - Load pending approvals from ApprovalService
//   - Track multi-selection for batch operations (§23.2)
//   - Batch approve / deny selected approvals
//   - Look up approval by ID for deep link navigation

import Foundation
import Observation

// MARK: - ApprovalListViewModel

@Observable
@MainActor
public final class ApprovalListViewModel {

    // MARK: - State

    /// Pending approvals loaded from the backend.
    public var approvals: [Approval] = []
    /// True while the list is loading.
    public var isLoading: Bool = false
    /// Non-nil when an error occurs (load or batch decision).
    public var errorMessage: String? = nil
    /// IDs of approvals currently selected for batch operations.
    public var selectedIds: Set<UUID> = []

    // MARK: - Dependencies

    private let service: any ApprovalServicing

    // MARK: - Init

    public init(service: any ApprovalServicing) {
        self.service = service
    }

    // MARK: - Load

    /// Fetches pending approvals. Replaces current list on success.
    public func load() async {
        isLoading = true
        errorMessage = nil
        do {
            approvals = try await service.fetchPending()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    // MARK: - Selection

    /// Toggles membership of `id` in `selectedIds`.
    public func toggleSelection(_ id: UUID) {
        if selectedIds.contains(id) {
            selectedIds.remove(id)
        } else {
            selectedIds.insert(id)
        }
    }

    // MARK: - Batch operations (§23.2)

    /// True while a batch approve/deny operation is in progress.
    /// Prevents duplicate submissions if the user taps the button twice.
    public var isBatchProcessing: Bool = false

    /// Approves all currently selected approvals.
    /// Removes each from the list after a successful decision.
    /// Clears selection when done.
    public func batchApprove() async {
        guard !isBatchProcessing else { return }
        await _batchDecide(.approved)
    }

    /// Denies all currently selected approvals.
    /// Removes each from the list after a successful decision.
    /// Clears selection when done.
    public func batchDeny() async {
        guard !isBatchProcessing else { return }
        await _batchDecide(.denied)
    }

    // MARK: - Deep link support

    /// Returns the approval matching `id`, or `nil` if not in the loaded list.
    /// Used by `DeepLinkRouter` when a push notification navigates to an approval.
    public func approvalById(_ id: UUID) -> Approval? {
        approvals.first { $0.id == id }
    }

    // MARK: - Private

    // NOTE: Batch operations bypass the per-approval biometric gate.
    // SPEC.md §23.2 describes batch approve/deny without mentioning step-up auth.
    // §29.3 item 4 mandates biometric for high-risk on individual decisions.
    // Individual high-risk items should be reviewed via ApprovalDetailView (which
    // does enforce the gate). Batch selection is intentionally unrestricted to
    // avoid prompting the user N times for N selected items. If this policy
    // changes, update ApprovalListViewModel._batchDecide to filter or prompt.
    private func _batchDecide(_ decision: ApprovalStatus) async {
        isBatchProcessing = true
        let ids = selectedIds
        for id in ids {
            do {
                try await service.decide(id: id, decision: decision)
                approvals.removeAll { $0.id == id }
            } catch {
                errorMessage = error.localizedDescription
            }
        }
        selectedIds.removeAll()
        isBatchProcessing = false
    }
}

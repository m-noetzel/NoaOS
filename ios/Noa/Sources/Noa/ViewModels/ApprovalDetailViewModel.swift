// ApprovalDetailViewModel.swift — Observable state for a single approval detail
// Spec ref: SPEC.md §29.3 item 4, §29.6, Phase iOS7 deliverable 4 & 5
//
// Responsibilities:
//   - Present a single approval with its dry-run preview
//   - Gate high-risk approvals behind biometric authentication
//   - Submit approve/deny decision via ApprovalService

import Foundation
import Observation

// MARK: - ApprovalDetailViewModel

@Observable
@MainActor
public final class ApprovalDetailViewModel {

    // MARK: - State

    /// True while an API call or biometric prompt is in progress.
    public var isSubmitting: Bool = false
    /// Non-nil when an error occurs (biometric failure or API error).
    public var errorMessage: String? = nil
    /// True after a successful decide() call; triggers navigation back.
    public var isDone: Bool = false
    /// iOS-M3: True when the last error was a retryable biometric failure.
    /// Used to show a "Try Again" action in the error alert.
    public var isBiometricError: Bool = false
    /// iOS-M3: The pending decision to retry after biometric prompt.
    public var pendingDecision: ApprovalStatus? = nil

    // MARK: - Data

    /// The approval to be reviewed.
    public let approval: Approval

    // MARK: - Dependencies

    private let service: any ApprovalServicing
    private let biometric: any BiometricAuthenticating

    // MARK: - Init

    public init(
        approval: Approval,
        service: any ApprovalServicing,
        biometric: any BiometricAuthenticating
    ) {
        self.approval = approval
        self.service = service
        self.biometric = biometric
    }

    // MARK: - Actions

    /// Submits an approval decision.
    ///
    /// High-risk approvals (`.high`) require successful biometric authentication
    /// before the API call is made (SPEC.md §29.3 item 4).
    /// On failure — biometric or network — sets `errorMessage` and returns.
    ///
    /// - Parameter decision: `.approved` or `.denied`.
    public func decide(_ decision: ApprovalStatus) async {
        isSubmitting = true
        errorMessage = nil
        isBiometricError = false
        pendingDecision = nil

        // Biometric gate: only for high-risk approvals (§29.3 item 4)
        if approval.riskTier == .high {
            do {
                try await biometric.authenticate(
                    reason: "Authenticate to confirm this high-risk action"
                )
            } catch {
                let isCancelled: Bool = {
                    if case .userCancelled = error as? BiometricError { return true }
                    return false
                }()
                errorMessage = biometricErrorMessage(error)
                // iOS-M3: mark as biometric error so View can offer "Try Again",
                // unless the user explicitly cancelled.
                if !isCancelled {
                    isBiometricError = true
                    pendingDecision = decision
                }
                isSubmitting = false
                return
            }
        }

        // Submit the decision
        do {
            try await service.decide(id: approval.id, decision: decision)
            isDone = true
        } catch {
            errorMessage = error.localizedDescription
        }
        isSubmitting = false
    }

    // MARK: - Private

    private func biometricErrorMessage(_ error: Error) -> String {
        if let bio = error as? BiometricError {
            switch bio {
            case .lockedOut:
                return "Biometric locked. Try again later or use your passcode."
            case .userCancelled:
                return "Authentication cancelled."
            case .notAvailable:
                return "Biometric authentication is not available."
            case .passcodeNotSet:
                return "Set a device passcode to use this feature."
            case .authenticationFailed:
                return "Authentication failed. Try again."
            case .unknown:
                return "An authentication error occurred."
            }
        }
        return error.localizedDescription
    }
}

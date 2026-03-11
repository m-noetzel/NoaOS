// BiometricService.swift — Biometric authentication wrapping LocalAuthentication
// Spec ref: SPEC.md §29.3 item 4, Phase iOS7 deliverable 1
//
// Responsibilities:
//   - isAvailable(): reports whether biometric auth is possible on this device
//   - authenticate(reason:): prompts Face ID / Touch ID with passcode fallback
//   - Maps LAError to typed BiometricError cases

import Foundation
import LocalAuthentication

// MARK: - BiometricError

/// Typed errors from biometric authentication.
public enum BiometricError: Error, Sendable {
    /// No biometric hardware present, or biometrics not enrolled.
    case notAvailable
    /// Authentication was attempted but failed (wrong fingerprint / face).
    case authenticationFailed
    /// Biometrics are locked out after too many failures.
    case lockedOut
    /// User cancelled the prompt or chose fallback.
    case userCancelled
    /// Device has no passcode configured (required for passcode fallback).
    case passcodeNotSet
    /// Unexpected error from LocalAuthentication.
    case unknown(underlying: Error?)
}

// MARK: - BiometricAuthenticating

/// Protocol for dependency injection in tests. Allows `ApprovalDetailViewModel`
/// to work with a mock in unit tests without real biometric hardware.
public protocol BiometricAuthenticating: Sendable {
    /// `true` if the device can evaluate biometrics (has Face ID / Touch ID enrolled).
    func isAvailable() async -> Bool
    /// Presents the biometric prompt. Throws `BiometricError` on failure.
    func authenticate(reason: String) async throws
}

// MARK: - LAContext Sendability

// LAContext is an NSObject subclass designed for single-use evaluation on any
// thread. Conforming it to @unchecked Sendable is safe when the instance is
// never shared across concurrent tasks (created locally per call site).
extension LAContext: @retroactive @unchecked Sendable {}

// MARK: - BiometricService

/// Actor-isolated biometric authentication service.
/// Wraps `LAContext` for testability via `BiometricAuthenticating`.
/// Spec ref: SPEC.md §29.3 item 4
public actor BiometricService: BiometricAuthenticating {

    public init() {}

    // MARK: - BiometricAuthenticating

    /// Returns `true` if biometric authentication is available and enrolled.
    /// Returns `false` on simulator, CI, or if biometrics are not enrolled.
    public nonisolated func isAvailable() async -> Bool {
        let context = LAContext()
        var error: NSError?
        return context.canEvaluatePolicy(
            .deviceOwnerAuthenticationWithBiometrics,
            error: &error
        )
    }

    /// Presents a biometric prompt with passcode fallback.
    ///
    /// Only called when biometrics are available (guarded by `isAvailable()`).
    /// Uses `.deviceOwnerAuthentication` (biometrics + passcode) to allow
    /// passcode fallback when biometry is temporarily unavailable.
    ///
    /// - Parameter reason: Localized description of why auth is needed.
    /// - Throws: `BiometricError` mapped from `LAError`.
    public nonisolated func authenticate(reason: String) async throws {
        let context = LAContext()
        var canError: NSError?
        guard context.canEvaluatePolicy(
            .deviceOwnerAuthenticationWithBiometrics,
            error: &canError
        ) else {
            throw BiometricError.notAvailable
        }

        let success: Bool = try await withCheckedThrowingContinuation { continuation in
            // .deviceOwnerAuthentication: biometrics with passcode fallback.
            // The policy check above uses .deviceOwnerAuthenticationWithBiometrics so that
            // isAvailable() only reports true when biometrics are enrolled; evaluatePolicy
            // uses the broader .deviceOwnerAuthentication to allow passcode fallback once the
            // biometric prompt is already shown (intentional UX — passcode as fallback).
            context.evaluatePolicy(
                .deviceOwnerAuthentication,
                localizedReason: reason
            ) { ok, error in
                if let error {
                    // Map raw LAError to typed BiometricError so callers can discriminate
                    // lock-out, cancellation, and hardware failures without depending on LAError.
                    let mapped = (error as? LAError).map(BiometricService.mapLAError) ?? .unknown(underlying: error)
                    continuation.resume(throwing: mapped)
                } else {
                    continuation.resume(returning: ok)
                }
            }
        }

        if !success {
            throw BiometricError.authenticationFailed
        }
    }
}

// MARK: - LAError mapping

extension BiometricService {
    /// Maps an `LAError` to a typed `BiometricError`.
    static func mapLAError(_ error: LAError) -> BiometricError {
        switch error.code {
        case .biometryLockout:
            return .lockedOut
        case .userCancel, .userFallback, .systemCancel, .appCancel:
            return .userCancelled
        case .biometryNotAvailable, .biometryNotEnrolled:
            return .notAvailable
        case .passcodeNotSet:
            return .passcodeNotSet
        default:
            return .unknown(underlying: error)
        }
    }
}

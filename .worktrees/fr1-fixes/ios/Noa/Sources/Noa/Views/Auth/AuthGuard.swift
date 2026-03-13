// AuthGuard.swift — Auth check view modifier
// Spec ref: SPEC.md §5.1–5.4, Phase iOS4 deliverable 6

import SwiftUI

/// Redirects to `LoginView` when the user is not authenticated.
/// Usage: `.authGuard(viewModel: authViewModel)`
public struct AuthGuard<Protected: View>: View {

    @Bindable var viewModel: AuthViewModel
    let protected: Protected

    public init(viewModel: AuthViewModel, @ViewBuilder protected: () -> Protected) {
        self.viewModel = viewModel
        self.protected = protected()
    }

    public var body: some View {
        if viewModel.isAuthenticated {
            protected
        } else {
            LoginView(viewModel: viewModel)
        }
    }
}

public extension View {
    /// Wraps this view in an `AuthGuard`, showing `LoginView` when unauthenticated.
    func authGuard(viewModel: AuthViewModel) -> some View {
        AuthGuard(viewModel: viewModel) {
            self
        }
    }
}

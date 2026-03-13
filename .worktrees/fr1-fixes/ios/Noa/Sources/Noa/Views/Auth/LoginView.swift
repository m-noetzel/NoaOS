// LoginView.swift — Email/password login screen
// Spec ref: SPEC.md §5.1, Phase iOS4 deliverable 5

import SwiftUI

/// Email and password login form.
/// Binds to `AuthViewModel` for state and actions.
public struct LoginView: View {

    @Bindable var viewModel: AuthViewModel

    @State private var username: String = ""
    @State private var password: String = ""
    @State private var isLoading: Bool = false

    public init(viewModel: AuthViewModel) {
        self.viewModel = viewModel
    }

    public var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                Spacer()

                Text("Noa")
                    .font(.largeTitle.bold())

                VStack(spacing: 12) {
                    TextField("Email", text: $username)
                        .textContentType(.emailAddress)
                        .autocorrectionDisabled()
                        #if os(iOS)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        #endif
                        .padding()
                        .background(.quaternary, in: RoundedRectangle(cornerRadius: 10))

                    SecureField("Password", text: $password)
                        .textContentType(.password)
                        .padding()
                        .background(.quaternary, in: RoundedRectangle(cornerRadius: 10))
                }
                .padding(.horizontal)

                if let error = viewModel.errorMessage {
                    Text(error)
                        .foregroundStyle(.red)
                        .font(.caption)
                        .padding(.horizontal)
                }

                Button {
                    Task {
                        isLoading = true
                        await viewModel.loginAttempt(username: username, password: password)
                        isLoading = false
                    }
                } label: {
                    Group {
                        if isLoading {
                            ProgressView()
                        } else {
                            Text("Sign In")
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.accentColor)
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }
                .disabled(username.isEmpty || password.isEmpty || isLoading)
                .padding(.horizontal)

                Spacer()
            }
            .navigationTitle("Sign In")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
        }
    }
}

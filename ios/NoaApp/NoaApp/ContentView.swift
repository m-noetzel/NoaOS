import SwiftUI
import Noa

struct ContentView: View {
    let authViewModel: AuthViewModel
    let chatService: ChatService
    let approvalService: ApprovalService
    let biometricService: BiometricService

    var body: some View {
        AuthGuard(viewModel: authViewModel) {
            MainTabView(
                authViewModel: authViewModel,
                chatService: chatService,
                approvalService: approvalService,
                biometricService: biometricService
            )
        }
    }
}

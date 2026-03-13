// TranscriptionProviderView.swift — Transcription provider selection in Settings
// Spec ref: SPEC.md §29.2, Phase iOS8 deliverable 6
//
// Lets the user choose between OpenAI Whisper (cloud) and whisper.cpp (local).
// Reads/writes UserDefaults keys:
//   "transcription_provider"  — "openai" | "local"
//   "whisper_cpp_url"         — service URL for the local whisper.cpp server
//
// No external dependencies.

import SwiftUI

// MARK: - TranscriptionProvider

/// The two supported transcription backends.
enum TranscriptionProvider: String, CaseIterable, Identifiable {
    case openai = "openai"
    case local  = "local"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .openai: return "OpenAI Whisper"
        case .local:  return "Local (whisper.cpp)"
        }
    }
}

// MARK: - TranscriptionProviderView

/// Settings screen for choosing the transcription backend and configuring its credentials/URL.
public struct TranscriptionProviderView: View {

    // MARK: - UserDefaults keys

    private static let providerKey    = "transcription_provider"
    private static let whisperCPPKey  = "whisper_cpp_url"
    private static let defaultCPPURL  = "http://host.docker.internal:8001"

    // MARK: - State

    @AppStorage("transcription_provider") private var rawProvider: String = "openai"
    @AppStorage("whisper_cpp_url")        private var whisperCPPURL: String = ""

    /// Derived binding from AppStorage string to enum.
    private var selectedProvider: TranscriptionProvider {
        get { TranscriptionProvider(rawValue: rawProvider) ?? .openai }
        set { rawProvider = newValue.rawValue }
    }

    /// Whether the API key field is shown in plain text.
    @State private var showAPIKey: Bool = false
    @State private var apiKey: String = ""

    // MARK: - Body

    public init() {}

    public var body: some View {
        Form {
            // MARK: Provider picker
            Section(header: Text("Transcription Backend")) {
                Picker("Provider", selection: Binding(
                    get: { selectedProvider },
                    set: { rawProvider = $0.rawValue }
                )) {
                    ForEach(TranscriptionProvider.allCases) { provider in
                        Text(provider.displayName).tag(provider)
                    }
                }
                .pickerStyle(.inline)
                .labelsHidden()
            }

            // MARK: Provider-specific configuration
            switch selectedProvider {
            case .openai:
                openAISection
            case .local:
                localSection
            }
        }
        .navigationTitle("Transcription")
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .onAppear {
            // Load stored API key from UserDefaults (not Keychain — per-spec simplicity for now).
            apiKey = UserDefaults.standard.string(forKey: "openai_whisper_api_key") ?? ""
            if whisperCPPURL.isEmpty {
                whisperCPPURL = Self.defaultCPPURL
            }
        }
    }

    // MARK: - OpenAI section

    private var openAISection: some View {
        Section(
            header: Text("OpenAI API Key"),
            footer: Text("Used for Whisper speech-to-text. Stored in UserDefaults.")
        ) {
            HStack {
                if showAPIKey {
                    TextField("sk-...", text: $apiKey)
                        .autocorrectionDisabled()
                        #if os(iOS)
                        .textInputAutocapitalization(.never)
                        #endif
                        .onChange(of: apiKey) { _, value in
                            UserDefaults.standard.set(value, forKey: "openai_whisper_api_key")
                        }
                } else {
                    SecureField("API key", text: $apiKey)
                        .onChange(of: apiKey) { _, value in
                            UserDefaults.standard.set(value, forKey: "openai_whisper_api_key")
                        }
                }

                Button {
                    showAPIKey.toggle()
                } label: {
                    Image(systemName: showAPIKey ? "eye.slash" : "eye")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(showAPIKey ? "Hide API key" : "Show API key")
            }
        }
    }

    // MARK: - Local (whisper.cpp) section

    private var localSection: some View {
        Section(
            header: Text("Service URL"),
            footer: Text("URL of your running whisper.cpp HTTP server. Default: \(Self.defaultCPPURL)")
        ) {
            TextField(Self.defaultCPPURL, text: $whisperCPPURL)
                .autocorrectionDisabled()
                #if os(iOS)
                .textInputAutocapitalization(.never)
                .keyboardType(.URL)
                #endif
        }
    }
}

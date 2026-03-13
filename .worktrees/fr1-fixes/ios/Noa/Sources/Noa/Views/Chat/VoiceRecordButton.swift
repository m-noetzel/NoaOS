// VoiceRecordButton.swift — Tap-to-toggle microphone recording button
// Spec ref: SPEC.md §29.2, Phase iOS8 deliverable 5
//
// Tap to start recording; tap again to stop and transcribe.
// While recording: pulsing red circle + elapsed duration timer + audioLevel-driven waveform.

import SwiftUI

// MARK: - VoiceRecordButton

/// A self-contained microphone toggle button that drives `VoiceViewModel`.
///
/// - `viewModel`: The `VoiceViewModel` managing recording state.
/// - `onTranscribed`: Called with the transcribed text when a result arrives.
public struct VoiceRecordButton: View {

    @Bindable var viewModel: VoiceViewModel
    var onTranscribed: (String) -> Void

    // MARK: - Init

    public init(viewModel: VoiceViewModel, onTranscribed: @escaping (String) -> Void) {
        self.viewModel = viewModel
        self.onTranscribed = onTranscribed
    }

    // MARK: - Body

    public var body: some View {
        VStack(spacing: 6) {
            switch viewModel.state {
            case .idle:
                idleButton

            case .recording(let duration):
                recordingView(duration: duration)

            case .uploading:
                uploadingView

            case .transcribed(let text):
                // Bubble the result up and return to idle immediately.
                Color.clear
                    .frame(width: 0, height: 0)
                    .onAppear {
                        onTranscribed(text)
                        Task { await viewModel.cancel() }
                    }

            case .error(let message):
                errorView(message: message)
            }
        }
        .animation(.easeInOut(duration: 0.2), value: stateTag)
    }

    // MARK: - Sub-views

    /// Idle state: plain microphone button.
    private var idleButton: some View {
        Button {
            Task { await viewModel.startRecording() }
        } label: {
            Image(systemName: "mic.circle.fill")
                .font(.system(size: 28))
                .foregroundStyle(Color.secondary)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Start voice recording")
    }

    /// Recording state: pulsing red circle + duration + waveform + stop button.
    private func recordingView(duration: TimeInterval) -> some View {
        VStack(spacing: 4) {
            // Waveform + stop button row.
            HStack(spacing: 8) {
                // Mini waveform driven by audioLevel.
                WaveformView(level: viewModel.audioLevel)
                    .frame(width: 48, height: 20)

                // Stop button (pulsing red).
                Button {
                    Task { await viewModel.stopAndTranscribe() }
                } label: {
                    Image(systemName: "stop.circle.fill")
                        .font(.system(size: 28))
                        .foregroundStyle(Color.red)
                        .scaleEffect(pulseScale)
                        .animation(
                            .easeInOut(duration: 0.8).repeatForever(autoreverses: true),
                            value: pulseScale
                        )
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Stop recording and transcribe")
            }

            // Elapsed duration label.
            Text(Self.formatDuration(duration))
                .font(.caption.monospacedDigit())
                .foregroundStyle(Color.red)
        }
        .onAppear { pulseScale = 1.15 }
        .onDisappear { pulseScale = 1.0 }
    }

    /// Uploading state: spinner + cancel button (iOS-M5).
    ///
    /// Allowing the user to cancel is critical when the server hangs — without a
    /// cancel affordance the UI appears frozen and the user has no recovery path.
    private var uploadingView: some View {
        HStack(spacing: 8) {
            ProgressView()
                .controlSize(.small)
                .accessibilityLabel("Transcribing voice message")

            Button {
                Task { await viewModel.cancel() }
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .font(.system(size: 20))
                    .foregroundStyle(Color.secondary)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Cancel transcription upload")
        }
    }

    /// Error state: warning icon; tap to dismiss.
    private func errorView(message: String) -> some View {
        Button {
            Task { await viewModel.cancel() }
        } label: {
            Image(systemName: "exclamationmark.circle.fill")
                .font(.system(size: 28))
                .foregroundStyle(Color.orange)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Voice error: \(message). Tap to dismiss.")
    }

    // MARK: - Animation state

    @State private var pulseScale: CGFloat = 1.0

    // MARK: - Helpers

    /// An integer tag used to drive animation transitions between states.
    private var stateTag: Int {
        switch viewModel.state {
        case .idle: return 0
        case .recording: return 1
        case .uploading: return 2
        case .transcribed: return 3
        case .error: return 4
        }
    }

    /// Formats seconds as `M:SS`.
    private static func formatDuration(_ seconds: TimeInterval) -> String {
        let totalSeconds = Int(seconds)
        let m = totalSeconds / 60
        let s = totalSeconds % 60
        return String(format: "%d:%02d", m, s)
    }
}

// MARK: - WaveformView

/// Five vertical bars whose height is proportional to the audio level (0–1).
private struct WaveformView: View {

    let level: Float

    private static let barCount = 5
    /// Heights follow a bell-curve shape to suggest a natural waveform.
    private static let relativeHeights: [CGFloat] = [0.4, 0.7, 1.0, 0.7, 0.4]

    var body: some View {
        HStack(alignment: .center, spacing: 2) {
            ForEach(0..<Self.barCount, id: \.self) { i in
                Capsule()
                    .fill(Color.red.opacity(0.85))
                    .frame(
                        width: 4,
                        height: max(4, Self.relativeHeights[i] * CGFloat(level) * 20)
                    )
                    .animation(.linear(duration: 0.1), value: level)
            }
        }
    }
}

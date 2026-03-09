// VoiceViewModel.swift — Observable state for voice recording and transcription
// Spec ref: SPEC.md §29.2, Phase iOS8 deliverable 4
//
// Responsibilities:
//   - Drive startRecording / stopAndTranscribe / cancel lifecycle
//   - Expose VoiceState for UI rendering
//   - Optionally forward transcribed text to ChatViewModel (autoSend)
//   - Respect max recording duration from AudioRecorderService

import Foundation
import Observation

// MARK: - VoiceState

/// State machine for the voice recording and transcription flow.
public enum VoiceState: Sendable {
    /// No recording in progress.
    case idle
    /// Recording is active; `duration` is the elapsed time in seconds.
    case recording(duration: TimeInterval)
    /// Recording has stopped and the audio is being uploaded for transcription.
    case uploading
    /// Transcription succeeded; `text` contains the result.
    case transcribed(text: String)
    /// An error occurred at any phase.
    case error(String)
}

// MARK: - VoiceViewModel

@Observable
@MainActor
public final class VoiceViewModel {

    // MARK: - Published state

    /// Current state of the voice flow.
    public var state: VoiceState = .idle
    /// Normalised audio level (0–1) for waveform display while recording.
    public var audioLevel: Float = 0

    // MARK: - Dependencies

    private let recorder: any AudioRecording
    private let voiceService: any VoiceServicing
    /// Optional ChatViewModel — when non-nil and `autoSend` is true,
    /// the transcribed text is forwarded as a new message.
    private weak var chatViewModel: ChatViewModel?

    // MARK: - Internal state

    /// Background task polling recorder state for UI updates.
    private var pollingTask: Task<Void, Never>?

    // MARK: - Init

    public init(
        recorder: any AudioRecording,
        voiceService: any VoiceServicing,
        chatViewModel: ChatViewModel? = nil
    ) {
        self.recorder = recorder
        self.voiceService = voiceService
        self.chatViewModel = chatViewModel
    }

    // MARK: - Actions

    /// Begins a recording session.
    ///
    /// Transitions: idle → recording(0)
    /// On permission denied or hardware failure: idle → error(message)
    public func startRecording() async {
        do {
            try await recorder.startRecording()
            state = .recording(duration: 0)
            audioLevel = 0
            startPolling()
        } catch AudioRecorderError.permissionDenied {
            state = .error("Microphone access denied. Please enable it in Settings.")
        } catch {
            state = .error(error.localizedDescription)
        }
    }

    /// Stops the recording, uploads the audio, and optionally sends the transcription to chat.
    ///
    /// Transitions: recording → uploading → transcribed(text)
    ///                                    → error(message) on failure
    ///
    /// - Parameter autoSend: If `true` and `chatViewModel` is set, calls `sendMessage` with the result.
    public func stopAndTranscribe(autoSend: Bool = false) async {
        stopPolling()
        let url = await recorder.stopRecording()
        guard let url else {
            state = .idle
            return
        }

        state = .uploading

        do {
            let result = try await voiceService.transcribe(audioURL: url, mode: .transcribe)
            state = .transcribed(text: result.text)
            if autoSend, let chatVM = chatViewModel {
                chatVM.sendMessage(text: result.text, threadId: result.threadId)
                // Reset back to idle after auto-sending.
                state = .idle
            }
        } catch VoiceServiceError.unauthorized {
            state = .error("Session expired. Please log in again.")
        } catch {
            state = .error(error.localizedDescription)
        }
    }

    /// Cancels the active recording and resets state to idle.
    public func cancel() async {
        stopPolling()
        await recorder.cancelRecording()
        state = .idle
        audioLevel = 0
    }

    // MARK: - Private

    /// Polls recorder for duration and audio level updates every 100 ms.
    private func startPolling() {
        pollingTask?.cancel()
        pollingTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 s
                guard let self, !Task.isCancelled else { break }
                await self.refreshRecorderState()
            }
        }
    }

    private func stopPolling() {
        pollingTask?.cancel()
        pollingTask = nil
    }

    /// Reads current duration and audioLevel from the recorder actor.
    private func refreshRecorderState() async {
        let dur = await recorder.duration
        let lvl = await recorder.audioLevel
        let rec = await recorder.isRecording

        if rec {
            state = .recording(duration: dur)
            audioLevel = lvl
        } else {
            // Recorder stopped itself (max duration reached) — trigger transcription.
            if case .recording = state {
                stopPolling()
                await stopAndTranscribe(autoSend: false)
            }
        }
    }
}

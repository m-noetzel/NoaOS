// AudioRecorderService.swift — AVAudioRecorder-based voice capture
// Spec ref: SPEC.md §29.2, Phase iOS8 deliverable 1
//
// Responsibilities:
//   - Start/stop/cancel M4A recording to a temp file
//   - Enforce 10-minute maximum duration via Timer
//   - Request microphone permission; throw .permissionDenied if denied
//   - Publish isRecording, duration (elapsed seconds), audioLevel (0–1)

import Foundation
import AVFoundation

// MARK: - AudioRecorderError

/// Typed errors from audio recording operations.
public enum AudioRecorderError: Error, Sendable {
    /// Microphone permission was denied or restricted.
    case permissionDenied
    /// Recording could not be started (hardware or configuration issue).
    case recordingFailed(underlying: Error?)
    /// Attempted to stop a recording that was not active.
    case notRecording
}

// MARK: - AudioRecording

/// Protocol for dependency injection in tests.
public protocol AudioRecording: Sendable {
    /// Starts a new recording session. Throws if permission is denied or recording fails.
    func startRecording() async throws
    /// Stops the active recording and returns the URL of the recorded file.
    /// Returns `nil` if no recording was active.
    func stopRecording() async -> URL?
    /// Cancels the active recording and discards the file.
    func cancelRecording() async

    /// True while a recording session is active.
    var isRecording: Bool { get async }
    /// Elapsed recording time in seconds.
    var duration: TimeInterval { get async }
    /// Normalised audio power (0–1) for waveform display.
    var audioLevel: Float { get async }
}

// MARK: - AudioRecorderService

/// Actor-isolated audio recording service backed by `AVAudioRecorder`.
/// Spec ref: SPEC.md §29.2
public actor AudioRecorderService: AudioRecording {

    // MARK: - Constants

    /// Maximum recording duration: 10 minutes per SPEC §29.2.
    public static let maxDuration: TimeInterval = 600

    /// Polling interval for duration + level metering updates (seconds).
    private static let meterInterval: TimeInterval = 0.1

    // MARK: - Published-like state
    // Stored on the actor; callers read via `isRecording`, `duration`, `audioLevel`.

    /// True while a recording session is active.
    public private(set) var isRecording: Bool = false
    /// Elapsed recording time in seconds.
    public private(set) var duration: TimeInterval = 0
    /// Normalised audio power (0–1) derived from AVAudioRecorder metering.
    public private(set) var audioLevel: Float = 0

    // MARK: - Private

    private var recorder: AVAudioRecorder?
    private var outputURL: URL?
    private var meterTimer: Task<Void, Never>?
    private var durationTimer: Task<Void, Never>?

    // MARK: - Init

    public init() {}

    // MARK: - AudioRecording

    /// Requests microphone permission, configures the audio session, and starts recording.
    ///
    /// - Throws: `AudioRecorderError.permissionDenied` if the user has not granted access.
    ///           `AudioRecorderError.recordingFailed` on any AVFoundation error.
    public func startRecording() async throws {
        // Request permission (async bridge for AVAudioApplication).
        let granted = await requestMicrophonePermission()
        guard granted else {
            throw AudioRecorderError.permissionDenied
        }

        // Tear down any previous session before starting a new one.
        await _cancelInternal()

        // Configure audio session for recording.
        // Calls platform helper — AVAudioSession on iOS, no-op on macOS.
        do {
            try configureRecordingSession()
        } catch {
            throw AudioRecorderError.recordingFailed(underlying: error)
        }

        // Build recording settings (AAC in .m4a container).
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16_000,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue,
        ]

        let url = Self.makeTempURL()
        let avRecorder: AVAudioRecorder
        do {
            avRecorder = try AVAudioRecorder(url: url, settings: settings)
        } catch {
            throw AudioRecorderError.recordingFailed(underlying: error)
        }

        avRecorder.isMeteringEnabled = true
        guard avRecorder.record() else {
            throw AudioRecorderError.recordingFailed(underlying: nil)
        }

        recorder = avRecorder
        outputURL = url
        isRecording = true
        duration = 0
        audioLevel = 0

        // Start background tasks for metering and max-duration enforcement.
        startMeterTask()
        startDurationTask()
    }

    /// Stops the active recording.
    ///
    /// - Returns: The URL of the recorded `.m4a` file, or `nil` if not recording.
    public func stopRecording() async -> URL? {
        guard isRecording, let rec = recorder else { return nil }
        rec.stop()
        _deactivateSession()
        cancelTimers()
        isRecording = false
        let url = outputURL
        recorder = nil
        outputURL = nil
        duration = 0
        audioLevel = 0
        return url
    }

    /// Cancels the active recording and deletes the temp file.
    public func cancelRecording() async {
        await _cancelInternal()
    }

    // MARK: - Private helpers

    private func _cancelInternal() async {
        guard let rec = recorder else { return }
        rec.stop()
        // Remove the temp file — discard result.
        if let url = outputURL {
            try? FileManager.default.removeItem(at: url)
        }
        _deactivateSession()
        cancelTimers()
        isRecording = false
        recorder = nil
        outputURL = nil
        duration = 0
        audioLevel = 0
    }

    private func _deactivateSession() {
        deactivateAudioSession()
    }

    /// Polls the recorder every `meterInterval` seconds to update `duration` and `audioLevel`.
    private func startMeterTask() {
        meterTimer = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: UInt64(AudioRecorderService.meterInterval * 1_000_000_000))
                guard let self, !Task.isCancelled else { break }
                await self.updateMetering()
            }
        }
    }

    /// Updates `duration` and `audioLevel` from the current recorder state.
    /// Must be called from within an actor-isolated context.
    private func updateMetering() {
        guard let rec = recorder, isRecording else { return }
        rec.updateMeters()
        duration = rec.currentTime
        // AVAudioRecorder reports average power in dBFS (roughly -160 to 0).
        // Map to 0–1 using a simple floor of -60 dB.
        let dB = rec.averagePower(forChannel: 0)
        let minDB: Float = -60
        audioLevel = max(0, min(1, (dB - minDB) / (-minDB)))
    }

    /// Stops recording automatically when `maxDuration` is reached.
    private func startDurationTask() {
        durationTimer = Task { [weak self] in
            // Sleep for maxDuration then stop if still recording.
            let nanoseconds = UInt64(AudioRecorderService.maxDuration * 1_000_000_000)
            try? await Task.sleep(nanoseconds: nanoseconds)
            guard let self, !Task.isCancelled else { return }
            // Auto-stop; discard returned URL (caller polls state).
            _ = await self.stopRecording()
        }
    }

    private func cancelTimers() {
        meterTimer?.cancel()
        meterTimer = nil
        durationTimer?.cancel()
        durationTimer = nil
    }

    /// Creates a unique `.m4a` URL in the system temp directory.
    private static func makeTempURL() -> URL {
        let filename = "noa_voice_\(UUID().uuidString).m4a"
        return FileManager.default.temporaryDirectory.appendingPathComponent(filename)
    }

    /// Requests microphone permission using `AVAudioApplication` on iOS 17+.
    private func requestMicrophonePermission() async -> Bool {
        await withCheckedContinuation { continuation in
            #if os(iOS)
            AVAudioApplication.requestRecordPermission { granted in
                continuation.resume(returning: granted)
            }
            #else
            // macOS / simulator: assume granted for unit tests.
            continuation.resume(returning: true)
            #endif
        }
    }
}

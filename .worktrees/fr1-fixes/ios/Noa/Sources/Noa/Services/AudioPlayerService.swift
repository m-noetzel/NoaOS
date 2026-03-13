// AudioPlayerService.swift — AVAudioPlayer-based voice playback
// Spec ref: SPEC.md §29.2, Phase iOS8 deliverable 2
//
// Responsibilities:
//   - Play an audio file from a local URL
//   - Stop playback on demand
//   - Publish isPlaying state

import Foundation
import AVFoundation

// MARK: - AudioPlayerError

/// Typed errors from audio playback operations.
public enum AudioPlayerError: Error, Sendable {
    /// The file at the given URL could not be loaded for playback.
    case loadFailed(underlying: Error?)
    /// Playback failed to start.
    case playbackFailed
}

// MARK: - AudioPlaying

/// Protocol for dependency injection in tests.
public protocol AudioPlaying: Sendable {
    /// Plays the audio file at the given URL. Throws if the file cannot be loaded.
    func play(url: URL) async throws
    /// Stops any active playback.
    func stop() async
}

// MARK: - AVAudioPlayer Sendability

// AVAudioPlayer is an NSObject designed for use on any thread when accessed serially.
// The actor's serial execution makes this safe.
extension AVAudioPlayer: @retroactive @unchecked Sendable {}

// MARK: - AudioPlayerService

/// Actor-isolated audio playback service backed by `AVAudioPlayer`.
/// Spec ref: SPEC.md §29.2
public actor AudioPlayerService: AudioPlaying {

    // MARK: - Published-like state

    /// True while audio is actively playing.
    public private(set) var isPlaying: Bool = false

    // MARK: - Private

    private var player: AVAudioPlayer?

    // MARK: - Init

    public init() {}

    // MARK: - AudioPlaying

    /// Loads and plays the audio file at `url`.
    ///
    /// Stops any currently playing audio before starting the new one.
    ///
    /// - Parameter url: Local file URL of an `.m4a` (or any AVFoundation-supported format).
    /// - Throws: `AudioPlayerError.loadFailed` if the file cannot be loaded.
    ///           `AudioPlayerError.playbackFailed` if `play()` returns false.
    public func play(url: URL) async throws {
        // Stop previous playback first.
        await stop()

        // Configure audio session for playback.
        // Calls platform helper — AVAudioSession on iOS, no-op on macOS.
        try? configurePlaybackSession()

        let avPlayer: AVAudioPlayer
        do {
            avPlayer = try AVAudioPlayer(contentsOf: url)
        } catch {
            throw AudioPlayerError.loadFailed(underlying: error)
        }

        avPlayer.prepareToPlay()
        guard avPlayer.play() else {
            throw AudioPlayerError.playbackFailed
        }

        player = avPlayer
        isPlaying = true

        // Monitor completion asynchronously.
        startCompletionTask(duration: avPlayer.duration)
    }

    /// Stops the current playback session.
    public func stop() async {
        player?.stop()
        player = nil
        isPlaying = false
        completionTask?.cancel()
        completionTask = nil
        deactivateAudioSession()
    }

    // MARK: - Private

    private var completionTask: Task<Void, Never>?

    /// Waits for `duration` seconds then marks `isPlaying = false`.
    private func startCompletionTask(duration: TimeInterval) {
        completionTask?.cancel()
        completionTask = Task { [weak self] in
            let nanoseconds = UInt64(max(0, duration) * 1_000_000_000)
            try? await Task.sleep(nanoseconds: nanoseconds)
            guard let self, !Task.isCancelled else { return }
            await self._markFinished()
        }
    }

    private func _markFinished() {
        isPlaying = false
        player = nil
        completionTask = nil
    }
}

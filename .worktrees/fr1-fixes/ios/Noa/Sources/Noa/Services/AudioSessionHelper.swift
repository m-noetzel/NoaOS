// AudioSessionHelper.swift — AVAudioSession configuration helpers (iOS only)
// Extracted so SourceKit does not attempt to resolve AVAudioSession on macOS.
// Both platforms get the same function signatures; the macOS stubs are no-ops.

#if os(iOS)
import AVFoundation

/// Configure the shared audio session for microphone recording.
func configureRecordingSession() throws {
    let session = AVAudioSession.sharedInstance()
    try session.setCategory(.record, mode: .default)
    try session.setActive(true)
}

/// Configure the shared audio session for audio playback.
func configurePlaybackSession() throws {
    let session = AVAudioSession.sharedInstance()
    try session.setCategory(.playback, mode: .default)
    try session.setActive(true)
}

/// Deactivate the shared audio session and notify other apps.
func deactivateAudioSession() {
    let session = AVAudioSession.sharedInstance()
    try? session.setActive(false, options: .notifyOthersOnDeactivation)
}
#else
// macOS stubs — AVAudioSession is not available; no-ops keep tests green.
func configureRecordingSession() throws {}
func configurePlaybackSession() throws {}
func deactivateAudioSession() {}
#endif

/**
 * useVoiceRecorder — VX1: Voice UX Refinement
 *
 * Manages MediaRecorder lifecycle for in-browser audio recording.
 * On stop, POSTs to /api/v1/voice/transcribe and returns the transcription.
 *
 * States:
 *   idle      — no recording in progress
 *   requesting — waiting for microphone permission
 *   recording  — actively recording
 *   processing — uploaded, awaiting transcription response
 *   error      — permission denied or transcription failed
 */

import { useState, useRef, useCallback } from "react";
import { getAccessToken } from "@/auth/tokens";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export type RecordingState = "idle" | "requesting" | "recording" | "processing" | "error";

export interface UseVoiceRecorderReturn {
  state: RecordingState;
  /** Elapsed recording seconds (only meaningful in "recording" state) */
  elapsedSeconds: number;
  /** Human-readable error message when state === "error" */
  errorMessage: string | null;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  cancelRecording: () => void;
}

/** POST multipart audio to /api/v1/voice/transcribe, return transcription text. */
async function transcribeAudio(blob: Blob, filename: string): Promise<string> {
  const formData = new FormData();
  formData.append("file", blob, filename);
  formData.append("mode", "transcribe");

  const token = getAccessToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}/api/v1/voice/transcribe`, {
    method: "POST",
    headers,
    body: formData,
    credentials: "include",
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      (body?.detail as string | undefined) ||
        (body?.error?.message as string | undefined) ||
        `Transcription failed: ${response.status}`
    );
  }

  const envelope = await response.json() as {
    ok: boolean;
    data?: { text?: string };
    error?: { message?: string } | null;
  };

  if (!envelope.ok || envelope.error) {
    throw new Error(envelope.error?.message || "Transcription returned an error");
  }

  return envelope.data?.text ?? "";
}

/** Choose a file extension based on the chosen MIME type. */
function extensionForMime(mimeType: string): string {
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("mp4") || mimeType.includes("m4a")) return "m4a";
  if (mimeType.includes("webm")) return "webm";
  return "webm";
}

/** Pick a MediaRecorder MIME type the browser supports. */
function chooseMimeType(): string {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  for (const mime of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(mime)) {
      return mime;
    }
  }
  return "audio/webm";
}

export function useVoiceRecorder(
  onTranscription: (text: string) => void
): UseVoiceRecorderReturn {
  const [state, setState] = useState<RecordingState>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const releaseStream = useCallback(() => {
    if (streamRef.current) {
      for (const track of streamRef.current.getTracks()) {
        track.stop();
      }
      streamRef.current = null;
    }
  }, []);

  const startRecording = useCallback(async () => {
    setErrorMessage(null);
    setState("requesting");
    setElapsedSeconds(0);

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      const msg =
        (err instanceof Error || err instanceof DOMException) && (err as { name?: string }).name === "NotAllowedError"
          ? "Microphone access denied. Please allow mic access in your browser settings."
          : "Could not access microphone.";
      setErrorMessage(msg);
      setState("error");
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];

    const mimeType = chooseMimeType();
    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream, { mimeType });
    } catch {
      // Fall back to no options
      recorder = new MediaRecorder(stream);
    }

    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        chunksRef.current.push(e.data);
      }
    };

    recorder.onstop = async () => {
      stopTimer();
      releaseStream();

      const chunks = chunksRef.current;
      if (chunks.length === 0) {
        setState("idle");
        return;
      }

      const actualMime = recorder.mimeType || mimeType;
      const blob = new Blob(chunks, { type: actualMime });
      const ext = extensionForMime(actualMime);
      const filename = `recording.${ext}`;

      setState("processing");
      try {
        const text = await transcribeAudio(blob, filename);
        onTranscription(text);
        setState("idle");
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "Transcription failed";
        setErrorMessage(msg);
        setState("error");
      }
    };

    recorder.start(250); // collect data every 250 ms
    setState("recording");

    // Elapsed seconds counter
    timerRef.current = setInterval(() => {
      setElapsedSeconds((s) => s + 1);
    }, 1000);
  }, [onTranscription, stopTimer, releaseStream]);

  const stopRecording = useCallback(() => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      mediaRecorderRef.current.stop();
    }
    stopTimer();
    // onstop handler will set state to "processing" or "idle"
  }, [stopTimer]);

  const cancelRecording = useCallback(() => {
    stopTimer();
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      // Override onstop so no transcription is sent
      mediaRecorderRef.current.onstop = null;
      mediaRecorderRef.current.stop();
    }
    releaseStream();
    chunksRef.current = [];
    mediaRecorderRef.current = null;
    setElapsedSeconds(0);
    setErrorMessage(null);
    setState("idle");
  }, [stopTimer, releaseStream]);

  return {
    state,
    elapsedSeconds,
    errorMessage,
    startRecording,
    stopRecording,
    cancelRecording,
  };
}

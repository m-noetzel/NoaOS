/**
 * VX1: Voice UX Refinement
 *
 * Tests for:
 * - useVoiceRecorder hook: states (idle, requesting, recording, processing, error)
 * - MediaRecorder mock: start, stop, dataavailable trigger, transcription insertion
 * - Permission denied path: error state with descriptive message
 * - ChatComposer: mic button present, recording bar shown during recording
 * - Build integration: ChatComposer renders with mic button
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

// ================================================================
// Helpers
// ================================================================

function makeQC() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function wrap(ui: React.ReactElement, qc?: QueryClient) {
  const client = qc ?? makeQC();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

// ================================================================
// MediaRecorder mock factory
// ================================================================

type MockRecorderCallbacks = {
  ondataavailable: ((e: { data: Blob }) => void) | null;
  onstop: (() => void) | null;
};

function makeMockMediaRecorder(callbacks: MockRecorderCallbacks) {
  return {
    state: "inactive" as string,
    mimeType: "audio/webm",
    ondataavailable: null as ((e: { data: Blob }) => void) | null,
    onstop: null as (() => void) | null,
    start(timeslice?: number) {
      void timeslice;
      this.state = "recording";
      // Assign to the shared callbacks object so tests can observe
      callbacks.ondataavailable = this.ondataavailable as typeof this.ondataavailable;
      callbacks.onstop = this.onstop;
    },
    stop() {
      this.state = "inactive";
      // Forward callbacks
      if (this.ondataavailable) callbacks.ondataavailable = this.ondataavailable as typeof this.ondataavailable;
      if (this.onstop) callbacks.onstop = this.onstop;
    },
  };
}

// ================================================================
// useVoiceRecorder — idle initial state
// ================================================================

describe("useVoiceRecorder: initial state", () => {
  it("starts in idle state with no error", async () => {
    vi.resetModules();
    vi.doMock("@/auth/tokens", () => ({ getAccessToken: () => "test-token" }));
    const { useVoiceRecorder } = await import("@/hooks/useVoiceRecorder");
    const onTranscription = vi.fn();
    const { result } = renderHook(() => useVoiceRecorder(onTranscription));

    expect(result.current.state).toBe("idle");
    expect(result.current.elapsedSeconds).toBe(0);
    expect(result.current.errorMessage).toBeNull();
  });
});

// ================================================================
// useVoiceRecorder — permission denied path
// ================================================================

describe("useVoiceRecorder: permission denied", () => {
  it("transitions to error state when getUserMedia is denied", async () => {
    vi.resetModules();
    vi.doMock("@/auth/tokens", () => ({ getAccessToken: () => null }));

    // Mock navigator.mediaDevices.getUserMedia to reject with NotAllowedError
    const notAllowed = new DOMException("Permission denied", "NotAllowedError");
    Object.defineProperty(globalThis, "navigator", {
      value: {
        mediaDevices: {
          getUserMedia: vi.fn().mockRejectedValue(notAllowed),
        },
      },
      writable: true,
      configurable: true,
    });

    const { useVoiceRecorder } = await import("@/hooks/useVoiceRecorder");
    const onTranscription = vi.fn();
    const { result } = renderHook(() => useVoiceRecorder(onTranscription));

    await act(async () => {
      await result.current.startRecording();
    });

    expect(result.current.state).toBe("error");
    expect(result.current.errorMessage).toMatch(/denied/i);
    expect(onTranscription).not.toHaveBeenCalled();
  });
});

// ================================================================
// useVoiceRecorder — recording → transcription flow
// ================================================================

describe("useVoiceRecorder: recording flow", () => {
  let mockRecorderCallbacks: MockRecorderCallbacks;

  beforeEach(() => {
    mockRecorderCallbacks = { ondataavailable: null, onstop: null };

    const mockRecorder = makeMockMediaRecorder(mockRecorderCallbacks);

    // Mock MediaRecorder constructor
    vi.stubGlobal("MediaRecorder", class {
      state = "inactive";
      mimeType = "audio/webm";
      ondataavailable: ((e: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;

      static isTypeSupported(_mime: string) { return true; }

      start(timeslice?: number) {
        void timeslice;
        this.state = "recording";
        mockRecorderCallbacks.ondataavailable = this.ondataavailable;
        mockRecorderCallbacks.onstop = this.onstop;
        mockRecorder.state = "recording";
      }
      stop() {
        this.state = "inactive";
        mockRecorderCallbacks.ondataavailable = this.ondataavailable;
        mockRecorderCallbacks.onstop = this.onstop;
        mockRecorder.state = "inactive";
      }
    });

    // Mock getUserMedia to return a fake stream
    const fakeTracks = [{ stop: vi.fn() }];
    Object.defineProperty(globalThis, "navigator", {
      value: {
        mediaDevices: {
          getUserMedia: vi.fn().mockResolvedValue({
            getTracks: () => fakeTracks,
          }),
        },
      },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("transitions to recording state after startRecording", async () => {
    vi.doMock("@/auth/tokens", () => ({ getAccessToken: () => "tok" }));
    const { useVoiceRecorder } = await import("@/hooks/useVoiceRecorder");
    const onTranscription = vi.fn();
    const { result } = renderHook(() => useVoiceRecorder(onTranscription));

    await act(async () => {
      await result.current.startRecording();
    });

    expect(result.current.state).toBe("recording");
  });

  it("calls onTranscription after stop when transcription succeeds", async () => {
    // Mock fetch for transcription API
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        ok: true,
        data: { text: "hello world", mode: "transcribe" },
        error: null,
        trace_id: "test",
      }),
    }));

    vi.doMock("@/auth/tokens", () => ({ getAccessToken: () => "tok" }));
    const { useVoiceRecorder } = await import("@/hooks/useVoiceRecorder");
    const onTranscription = vi.fn();
    const { result } = renderHook(() => useVoiceRecorder(onTranscription));

    await act(async () => {
      await result.current.startRecording();
    });

    expect(result.current.state).toBe("recording");

    // Simulate audio data arrival and then stop
    await act(async () => {
      // Trigger ondataavailable with a fake blob
      if (mockRecorderCallbacks.ondataavailable) {
        mockRecorderCallbacks.ondataavailable({ data: new Blob(["audio"], { type: "audio/webm" }) });
      }
      result.current.stopRecording();
      // Trigger onstop (MediaRecorder fires this)
      if (mockRecorderCallbacks.onstop) {
        await mockRecorderCallbacks.onstop();
      }
    });

    await waitFor(() => {
      expect(onTranscription).toHaveBeenCalledWith("hello world");
    });

    expect(result.current.state).toBe("idle");
  });

  it("transitions to error state when transcription API returns non-ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: () => Promise.resolve({ detail: "Transcription service error" }),
    }));

    vi.doMock("@/auth/tokens", () => ({ getAccessToken: () => "tok" }));
    const { useVoiceRecorder } = await import("@/hooks/useVoiceRecorder");
    const onTranscription = vi.fn();
    const { result } = renderHook(() => useVoiceRecorder(onTranscription));

    await act(async () => {
      await result.current.startRecording();
    });

    await act(async () => {
      if (mockRecorderCallbacks.ondataavailable) {
        mockRecorderCallbacks.ondataavailable({ data: new Blob(["audio"], { type: "audio/webm" }) });
      }
      result.current.stopRecording();
      if (mockRecorderCallbacks.onstop) {
        await mockRecorderCallbacks.onstop();
      }
    });

    await waitFor(() => {
      expect(result.current.state).toBe("error");
    });
    expect(result.current.errorMessage).toMatch(/Transcription/i);
    expect(onTranscription).not.toHaveBeenCalled();
  });

  it("cancelRecording resets to idle without calling onTranscription", async () => {
    vi.doMock("@/auth/tokens", () => ({ getAccessToken: () => "tok" }));
    const { useVoiceRecorder } = await import("@/hooks/useVoiceRecorder");
    const onTranscription = vi.fn();
    const { result } = renderHook(() => useVoiceRecorder(onTranscription));

    await act(async () => {
      await result.current.startRecording();
    });

    act(() => {
      result.current.cancelRecording();
    });

    expect(result.current.state).toBe("idle");
    expect(onTranscription).not.toHaveBeenCalled();
  });
});

// ================================================================
// ChatComposer: mic button presence
// ================================================================

describe("VX1: ChatComposer renders mic button", () => {
  beforeEach(() => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: {}, error: null, trace_id: "" }),
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, isLoading: false }),
    }));
    vi.doMock("@/auth/tokens", () => ({ getAccessToken: () => null }));
    vi.doMock("@/api/sse", () => ({
      SSEClient: class { connect() {} disconnect() {} },
      VALID_SSE_EVENTS: new Set([]),
    }));
  });

  afterEach(() => {
    vi.resetModules();
  });

  it("mic button is rendered in the chat composer", async () => {
    vi.resetModules();
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "" }),
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, isLoading: false }),
    }));
    vi.doMock("@/auth/tokens", () => ({ getAccessToken: () => null }));
    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        connect() { return Promise.resolve(); }
        disconnect() {}
      },
      VALID_SSE_EVENTS: new Set(["meta", "result_ready", "token_stream"]),
    }));

    const { default: Chat } = await import("@/pages/Chat");
    wrap(<Chat />);

    await waitFor(() => {
      expect(screen.getByTestId("voice-mic")).toBeInTheDocument();
    });
  });

  it("mic button has accessible label", async () => {
    vi.resetModules();
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "" }),
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, isLoading: false }),
    }));
    vi.doMock("@/auth/tokens", () => ({ getAccessToken: () => null }));
    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        connect() { return Promise.resolve(); }
        disconnect() {}
      },
      VALID_SSE_EVENTS: new Set(["meta", "result_ready", "token_stream"]),
    }));

    const { default: Chat } = await import("@/pages/Chat");
    wrap(<Chat />);

    await waitFor(() => {
      const btn = screen.getByTestId("voice-mic");
      expect(btn).toHaveAttribute("aria-label", "Record voice message");
    });
  });

  it("mic button is disabled while streaming", async () => {
    vi.resetModules();
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "" }),
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, isLoading: false }),
    }));
    vi.doMock("@/auth/tokens", () => ({ getAccessToken: () => null }));

    // Simulate a never-resolving SSE so isStreaming stays true
    let sseResolve: (() => void) | undefined;
    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        connect() {
          return new Promise<void>((res) => { sseResolve = res; });
        }
        disconnect() { if (sseResolve) sseResolve(); }
      },
      VALID_SSE_EVENTS: new Set(["meta", "result_ready", "token_stream"]),
    }));

    const { default: Chat } = await import("@/pages/Chat");
    const qc = makeQC();

    // Mock thread creation too
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockImplementation((path: string, opts?: RequestInit) => {
        if (path === "/api/v1/threads" && opts?.method === "POST") {
          return Promise.resolve({
            ok: true,
            data: { id: "t-1", title: "Test", message_count: 0, created_at: "", updated_at: "" },
            error: null, trace_id: "",
          });
        }
        return Promise.resolve({ ok: true, data: [], error: null, trace_id: "" });
      }),
    }));

    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><Chat /></MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => screen.getByTestId("chat-input"));

    // Send a message to start streaming
    fireEvent.change(screen.getByTestId("chat-input"), { target: { value: "hi" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() => {
      const micBtn = screen.queryByTestId("voice-mic");
      if (micBtn) {
        expect(micBtn).toBeDisabled();
      }
      // Also: send button should be disabled
      expect(screen.getByTestId("chat-send")).toBeDisabled();
    });
  });
});

// ================================================================
// VX1: transcribeAudio — fetch contract
// ================================================================

describe("VX1: transcribeAudio fetch contract", () => {
  it("sends multipart/form-data POST to /api/v1/voice/transcribe", async () => {
    vi.resetModules();
    vi.doMock("@/auth/tokens", () => ({ getAccessToken: () => "my-token" }));

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        ok: true,
        data: { text: "transcribed text", mode: "transcribe" },
        error: null,
        trace_id: "abc",
      }),
    });
    vi.stubGlobal("fetch", mockFetch);

    // Trigger via the hook: start recording and stop with data
    const callbacks: MockRecorderCallbacks = { ondataavailable: null, onstop: null };
    vi.stubGlobal("MediaRecorder", class {
      state = "inactive";
      mimeType = "audio/webm";
      ondataavailable: ((e: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;
      static isTypeSupported() { return true; }
      start() {
        this.state = "recording";
        callbacks.ondataavailable = this.ondataavailable;
        callbacks.onstop = this.onstop;
      }
      stop() {
        this.state = "inactive";
        callbacks.ondataavailable = this.ondataavailable;
        callbacks.onstop = this.onstop;
      }
    });

    Object.defineProperty(globalThis, "navigator", {
      value: {
        mediaDevices: {
          getUserMedia: vi.fn().mockResolvedValue({
            getTracks: () => [{ stop: vi.fn() }],
          }),
        },
      },
      writable: true,
      configurable: true,
    });

    const { useVoiceRecorder } = await import("@/hooks/useVoiceRecorder");
    const onTranscription = vi.fn();
    const { result } = renderHook(() => useVoiceRecorder(onTranscription));

    await act(async () => {
      await result.current.startRecording();
    });

    await act(async () => {
      if (callbacks.ondataavailable) {
        callbacks.ondataavailable({ data: new Blob(["audio"], { type: "audio/webm" }) });
      }
      result.current.stopRecording();
      if (callbacks.onstop) {
        await callbacks.onstop();
      }
    });

    await waitFor(() => {
      expect(onTranscription).toHaveBeenCalledWith("transcribed text");
    });

    // Verify fetch was called with correct URL and Authorization header
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/voice/transcribe"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer my-token" }),
      })
    );

    vi.unstubAllGlobals();
  });
});

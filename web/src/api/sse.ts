import type { SSEEvent, SSEEventType } from "./types";
import { getAccessToken } from "@/auth/tokens";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export type SSECallback = (event: SSEEvent) => void;

interface SSEClientOptions {
  onEvent: SSECallback;
  onError?: (error: Error) => void;
  onClose?: () => void;
}

const BACKOFF_SCHEDULE = [1000, 2000, 5000, 10000];

export class SSEClient {
  private controller: AbortController | null = null;
  private retryCount = 0;
  private runId: string | null = null;
  private options: SSEClientOptions;
  private closed = false;

  constructor(options: SSEClientOptions) {
    this.options = options;
  }

  async connect(path: string, body?: unknown): Promise<void> {
    this.closed = false;
    this.retryCount = 0;
    await this.startStream(path, body);
  }

  private async startStream(path: string, body?: unknown): Promise<void> {
    if (this.closed) return;

    this.controller = new AbortController();
    const token = getAccessToken();

    try {
      const headers: Record<string, string> = {
        Accept: "text/event-stream",
      };

      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      let response: Response;

      if (body) {
        headers["Content-Type"] = "application/json";
        response = await fetch(`${BASE_URL}${path}`, {
          method: "POST",
          headers,
          body: JSON.stringify(body),
          signal: this.controller.signal,
        });
      } else {
        response = await fetch(`${BASE_URL}${path}`, {
          method: "GET",
          headers,
          signal: this.controller.signal,
        });
      }

      if (!response.ok) {
        throw new Error(`SSE connection failed: ${response.status}`);
      }

      if (!response.body) {
        throw new Error("No response body for SSE stream");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      this.retryCount = 0; // reset on successful connection

      while (!this.closed) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let currentEvent: string | null = null;
        let currentData = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            currentData += line.slice(6);
          } else if (line === "" && currentData) {
            try {
              const parsed = JSON.parse(currentData);

              // Capture run_id for reconnection
              if (parsed.run_id && !this.runId) {
                this.runId = parsed.run_id;
              }

              // Use explicit event: line if present, otherwise extract
              // event_type from the JSON payload (backend sends data-only)
              const eventName = currentEvent
                || parsed.event_type
                || "unknown";

              this.options.onEvent({
                event: eventName as SSEEventType,
                data: parsed.payload ?? parsed,
              });
            } catch {
              // skip malformed events
            }
            currentEvent = null;
            currentData = "";
          }
        }
      }

      this.options.onClose?.();
    } catch (error) {
      if (this.closed) return;

      if (error instanceof DOMException && error.name === "AbortError") return;

      this.options.onError?.(error as Error);
      await this.tryReconnect();
    }
  }

  private async tryReconnect(): Promise<void> {
    if (this.closed || !this.runId) return;

    const delay = BACKOFF_SCHEDULE[Math.min(this.retryCount, BACKOFF_SCHEDULE.length - 1)];
    this.retryCount++;

    await new Promise((r) => setTimeout(r, delay));

    if (!this.closed) {
      await this.startStream(`/api/v1/runs/${this.runId}/events`);
    }
  }

  disconnect(): void {
    this.closed = true;
    this.controller?.abort();
    this.controller = null;
  }
}

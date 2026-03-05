/**
 * SSE hook for streaming run events — SPEC.md §22.4.
 * Connects to /api/v1/runs/{runId}/events and parses typed events.
 */

import { useEffect, useRef, useState } from "react";

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
}

export interface UseSSEResult {
  tokens: string;
  events: SSEEvent[];
  isConnected: boolean;
  isComplete: boolean;
  error: string | null;
}

export function useSSE(runId: string, token: string): UseSSEResult {
  const [tokens, setTokens] = useState("");
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const url = `/api/v1/runs/${runId}/events?token=${token}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    es.onerror = () => {
      setError("Connection error");
      setIsConnected(false);
    };

    const handleEvent = (type: string) => (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [...prev, { type, data }]);

      if (type === "token_stream" && data.token) {
        setTokens((prev) => prev + data.token);
      }

      if (type === "result_ready") {
        setIsComplete(true);
      }
    };

    es.addEventListener("token_stream", handleEvent("token_stream"));
    es.addEventListener("tool_called", handleEvent("tool_called"));
    es.addEventListener("tool_result", handleEvent("tool_result"));
    es.addEventListener("approval_requested", handleEvent("approval_requested"));
    es.addEventListener("result_ready", handleEvent("result_ready"));
    es.addEventListener("error", handleEvent("error"));

    return () => {
      es.close();
    };
  }, [runId, token]);

  return { tokens, events, isConnected, isComplete, error };
}

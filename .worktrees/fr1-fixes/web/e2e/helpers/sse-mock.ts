import type { Page } from "@playwright/test";

interface SSEEvent {
  id?: string;
  event?: string;
  data: Record<string, unknown>;
}

/**
 * Build an SSE-formatted response body string from an array of events.
 * Each event follows the Server-Sent Events spec:
 *   id: <id>\nevent: <type>\ndata: <json>\n\n
 */
function formatSSEBody(events: SSEEvent[]): string {
  return events
    .map((evt) => {
      const lines: string[] = [];
      if (evt.id) lines.push(`id: ${evt.id}`);
      if (evt.event) lines.push(`event: ${evt.event}`);
      lines.push(`data: ${JSON.stringify(evt.data)}`);
      lines.push(""); // empty line terminates event
      return lines.join("\n");
    })
    .join("\n") + "\n"; // trailing \n ensures the last event's blank line terminates it
}

/**
 * Intercept POST /api/v1/chat and respond with a controlled SSE stream.
 * The stream delivers the provided events with optional delay between them.
 */
export async function mockSSEChat(
  page: Page,
  events: SSEEvent[],
) {
  await page.route("**/api/v1/chat", async (route) => {
    const body = formatSSEBody(events);

    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
      body,
    });
  });
}

/** Convenience: build a standard successful chat SSE sequence with token streaming. */
export function buildChatSSEEvents(tokens: string[], finalContent: string): SSEEvent[] {
  const runId = "r_test_1";
  const events: SSEEvent[] = [
    {
      id: "1",
      event: "meta",
      data: { run_id: runId, event_type: "meta" },
    },
  ];

  tokens.forEach((token, i) => {
    events.push({
      id: String(i + 2),
      event: "token_stream",
      data: { token, event_type: "token_stream" },
    });
  });

  events.push({
    id: String(tokens.length + 2),
    event: "result_ready",
    data: {
      content: finalContent,
      event_type: "result_ready",
    },
  });

  return events;
}

/** Build an SSE error event sequence. */
export function buildChatSSEError(message: string): SSEEvent[] {
  return [
    {
      id: "1",
      event: "meta",
      data: { run_id: "r_err_1", event_type: "meta" },
    },
    {
      id: "2",
      event: "error",
      data: { message, event_type: "error" },
    },
  ];
}

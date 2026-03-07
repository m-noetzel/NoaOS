import { test, expect, setupApiMocks, loginViaUI } from "./fixtures";
import { mockSSEChat, buildChatSSEEvents, buildChatSSEError } from "./helpers/sse-mock";

/**
 * Set up mocks with a pre-existing thread so activeThread is set,
 * and messages endpoint returns user+assistant messages after SSE completes.
 */
async function setupChatMocks(
  page: import("@playwright/test").Page,
  opts?: { messagesAfterSend?: Array<{ id: string; role: string; content: string }> },
) {
  const threadId = "t_test_1";
  const thread = { id: threadId, title: "Test Thread", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", message_count: 0 };

  // Override threads to return one pre-existing thread
  await page.route("**/api/v1/threads", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, data: thread, error: null, trace_id: "test" }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, data: [thread], error: null, trace_id: "test" }),
    });
  });

  // Messages: empty initially, return provided messages on subsequent fetches
  let fetchCount = 0;
  await page.route("**/api/v1/threads/*/messages", async (route) => {
    fetchCount++;
    const messages = fetchCount > 1 && opts?.messagesAfterSend
      ? opts.messagesAfterSend.map((m) => ({ ...m, thread_id: threadId, created_at: new Date().toISOString() }))
      : [];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, data: messages, error: null, trace_id: "test" }),
    });
  });
}

test.describe("Chat", () => {
  test("authenticated user sees chat input and send button", async ({ authenticatedPage: page }) => {
    await expect(page.getByTestId("chat-input")).toBeVisible();
    await expect(page.getByTestId("chat-send")).toBeVisible();
  });

  test("send message — input clears and assistant responds", async ({ page }) => {
    await setupApiMocks(page);
    await setupChatMocks(page);
    await mockSSEChat(page, buildChatSSEEvents(["Hello!"], "Hello!"));
    await loginViaUI(page);

    // Wait for thread to load
    await expect(page.getByText("Test Thread")).toBeVisible({ timeout: 5000 });

    await page.getByTestId("chat-input").fill("Hi Noa");
    await page.getByTestId("chat-send").click();

    // Input should clear after send
    await expect(page.getByTestId("chat-input")).toHaveValue("");

    // Optimistic assistant message appears after SSE completes
    await expect(page.getByTestId("message-list").getByText("Hello!")).toBeVisible({ timeout: 5000 });
  });

  test("send message — SSE tokens accumulate and become optimistic message", async ({ page }) => {
    // route.fulfill delivers all events at once, so token_stream events are
    // accumulated then result_ready immediately promotes them to an optimistic message.
    await setupApiMocks(page);
    await setupChatMocks(page);
    const tokens = ["Hello", " from", " Noa", "!"];
    await mockSSEChat(page, buildChatSSEEvents(tokens, "Hello from Noa!"));
    await loginViaUI(page);

    await page.getByTestId("chat-input").fill("Test streaming");
    await page.getByTestId("chat-send").click();

    // Accumulated tokens become an optimistic assistant message after result_ready
    await expect(page.getByTestId("message-list").getByText("Hello from Noa!")).toBeVisible({ timeout: 5000 });
  });

  test("send message — stream completes — final message visible", async ({ page }) => {
    await setupApiMocks(page);
    await setupChatMocks(page);
    await mockSSEChat(page, buildChatSSEEvents(["Stream", " done!"], "Stream done!"));
    await loginViaUI(page);

    await page.getByTestId("chat-input").fill("Complete test");
    await page.getByTestId("chat-send").click();

    // After stream completes, optimistic assistant message should be visible
    await expect(page.getByTestId("message-list").getByText("Stream done!")).toBeVisible({ timeout: 5000 });
    // Streaming should be done — input re-enabled
    await expect(page.getByTestId("chat-input")).toBeEnabled();
  });

  test("SSE error — error state shown, input re-enabled", async ({ page }) => {
    await setupApiMocks(page);
    await setupChatMocks(page);
    await mockSSEChat(page, buildChatSSEError("Something went wrong"));
    await loginViaUI(page);

    await page.getByTestId("chat-input").fill("Trigger error");
    await page.getByTestId("chat-send").click();

    // Input should be re-enabled after error (not stuck in streaming state)
    await expect(page.getByTestId("chat-input")).toBeEnabled({ timeout: 5000 });
    await expect(page.getByTestId("chat-send")).toBeVisible();
  });

  test("send button disabled while streaming", async ({ page }) => {
    await setupApiMocks(page);
    await setupChatMocks(page);

    // Respond with token_stream but no result_ready — stream stays "open"
    await page.route("**/api/v1/chat", async (route) => {
      await route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
        },
        body: 'id: 1\nevent: meta\ndata: {"run_id":"r_test","event_type":"meta"}\n\nid: 2\nevent: token_stream\ndata: {"token":"thinking...","event_type":"token_stream"}\n\n',
      });
    });
    await loginViaUI(page);

    await page.getByTestId("chat-input").fill("Long task");
    await page.getByTestId("chat-send").click();

    // While streaming, the send button should be disabled
    await expect(page.getByTestId("streaming-content")).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId("chat-send")).toBeDisabled();
  });
});

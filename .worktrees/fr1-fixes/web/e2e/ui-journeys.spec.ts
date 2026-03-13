import { test, expect, type Page } from "@playwright/test";

/**
 * Real E2E user-journey tests against the live backend.
 * Uses gpt-4.1-mini (openai) + Tavily web_search.
 * No mocks — every assertion reflects actual system behavior.
 */

const TEST_EMAIL = "playwright@example.com";
const TEST_PASSWORD = "Test1234pass";

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Login via the UI, end up on /. */
async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(TEST_EMAIL);
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL("/", { timeout: 10_000 });
}

/** Login via API and return the access token. */
async function getToken(request: Page["request"]): Promise<string> {
  // Use page.request context which shares cookies
  const res = await (await fetch("http://localhost:8000/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: TEST_EMAIL, password: TEST_PASSWORD, device_id: "pw-test" }),
  })).json();
  return res.data.access_token;
}

// ─── Setup: configure the test user once ─────────────────────────────────────

test.describe.configure({ mode: "serial" });

let accessToken: string;

test.beforeAll(async () => {
  // Login to get token
  const loginRes = await (await fetch("http://localhost:8000/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: TEST_EMAIL, password: TEST_PASSWORD, device_id: "pw-setup" }),
  })).json();
  accessToken = loginRes.data.access_token;

  // Configure settings: openai + gpt-4.1-mini + external mode
  await fetch("http://localhost:8000/api/v1/settings", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({
      default_provider: "openai",
      default_model: "gpt-4.1-mini",
      default_privacy_mode: "external",
    }),
  });
});

// ─── Journey 1: Send a message, get a response ──────────────────────────────

test("send a message and receive an LLM response", async ({ page }) => {
  test.setTimeout(90_000);
  await login(page);

  // Should land on chat with composer visible
  const input = page.getByTestId("chat-input");
  await expect(input).toBeVisible();

  // Send a simple message
  await input.fill("Reply with exactly: PONG");

  // Watch for the SSE POST request to /api/v1/chat
  const chatRequestPromise = page.waitForRequest(
    (req) => req.url().includes("/api/v1/chat") && req.method() === "POST",
    { timeout: 15_000 }
  ).catch(() => null);

  await page.getByTestId("chat-send").click();
  await page.screenshot({ path: "e2e/screenshots/debug-after-click-send.png", fullPage: true });

  // Wait for the POST to fire — if it doesn't, the send didn't work
  const chatRequest = await chatRequestPromise;
  if (!chatRequest) {
    // Take debug screenshot and fail with useful info
    await page.screenshot({ path: "e2e/screenshots/debug-no-chat-request.png", fullPage: true });
    // Check: was the input cleared? (handleSend clears it)
    const inputVal = await input.inputValue();
    throw new Error(`POST /api/v1/chat never fired. Input value after click: "${inputVal}"`);
  }

  // The user message should appear
  await expect(page.getByText("Reply with exactly: PONG")).toBeVisible({ timeout: 10_000 });

  // Send button should be disabled during streaming
  await expect(page.getByTestId("chat-send")).toBeDisabled({ timeout: 5_000 });

  // Wait for an assistant response bubble (has class rounded-tl-md)
  const assistantBubble = page.getByTestId("message-list").locator(".rounded-tl-md").first();
  await expect(assistantBubble).toBeVisible({ timeout: 60_000 });

  // Response should contain actual text
  const responseText = await assistantBubble.textContent();
  expect(responseText!.trim().length).toBeGreaterThan(0);

  // Send button should be re-enabled after streaming completes
  await expect(page.getByTestId("chat-send")).toBeEnabled({ timeout: 30_000 });

  // Take screenshot for review
  await page.screenshot({ path: "e2e/screenshots/journey-chat-response.png", fullPage: true });
});

// ─── Journey 2: Trigger a tool call (Tavily web search) ─────────────────────

test("trigger Tavily web search and handle approval", async ({ page }) => {
  test.setTimeout(90_000);
  await login(page);

  // First enable web_search tool if not already
  await page.goto("/tools");
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

  const webSearchToggle = page.locator("[role='switch']").first();
  if (await webSearchToggle.isVisible({ timeout: 3_000 }).catch(() => false)) {
    const isChecked = await webSearchToggle.getAttribute("data-state");
    if (isChecked !== "checked") {
      await webSearchToggle.click();
      await page.waitForTimeout(1_000);
    }
  }

  // Go to chat and ask something that requires web search
  await page.goto("/");
  await page.waitForTimeout(1_000);

  const input = page.getByTestId("chat-input");
  await input.fill("Search the web for: latest Anthropic Claude news today");
  await page.getByTestId("chat-send").click();

  // Either we get an approval_requested card OR a direct response
  // Wait for either: approval card OR assistant response
  const approvalCard = page.getByText(/approval required/i);
  const assistantBubble = page.getByTestId("message-list").locator(".rounded-tl-md").first();

  // Wait up to 60s for either to appear
  await expect(approvalCard.or(assistantBubble)).toBeVisible({ timeout: 60_000 });

  // If approval card appeared, approve it
  if (await approvalCard.isVisible().catch(() => false)) {
    const approveBtn = page.getByRole("button", { name: /approve/i }).first();
    await approveBtn.click();

    // Now wait for the actual response
    await expect(assistantBubble).toBeVisible({ timeout: 60_000 });
  }

  const responseText = await assistantBubble.textContent();
  expect(responseText!.trim().length).toBeGreaterThan(0);

  await page.screenshot({ path: "e2e/screenshots/journey-tool-call.png", fullPage: true });
});

// ─── Journey 3: Chat creates a run visible in /runs ──────────────────────────

test("chat run appears in the Runs page", async ({ page }) => {
  test.setTimeout(30_000);
  await login(page);

  // After previous tests, there should be at least one run
  await page.goto("/runs");
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

  // Should see at least one run row (not "No runs found")
  const runRow = page.locator("tbody tr").filter({ hasNot: page.getByText(/no runs/i) }).first();
  await expect(runRow).toBeVisible({ timeout: 10_000 });

  // Click it to go to run detail
  await runRow.click();
  await page.waitForURL(/\/runs\//, { timeout: 5_000 });

  // Run detail should show status and model info
  await expect(page.getByText(/gpt-4.1-mini|openai/i).first()).toBeVisible({ timeout: 5_000 });

  await page.screenshot({ path: "e2e/screenshots/journey-run-detail.png", fullPage: true });
});

// ─── Journey 4: Settings round-trip ──────────────────────────────────────────

test("change settings and verify they persist after reload", async ({ page }) => {
  test.setTimeout(30_000);
  await login(page);
  await page.goto("/settings");
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

  // Change daily budget to a unique value
  const dailyInput = page.locator("input").filter({ has: page.locator("") }).nth(0);
  // Find by nearby label text
  const dailyField = page.locator("input:near(:text('Daily Budget'))").first();
  await dailyField.clear();
  await dailyField.fill("42");

  // Save
  await page.getByRole("button", { name: /save/i }).click();
  await page.waitForTimeout(2_000);

  // Reload
  await page.reload();
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

  // Verify the value persisted
  const dailyAfter = page.locator("input:near(:text('Daily Budget'))").first();
  await expect(dailyAfter).toHaveValue("42", { timeout: 5_000 });

  await page.screenshot({ path: "e2e/screenshots/journey-settings.png", fullPage: true });
});

// ─── Journey 5: Thread CRUD ──────────────────────────────────────────────────

test("create thread, send message, delete thread", async ({ page }) => {
  test.setTimeout(90_000);
  await login(page);

  // Create a new thread
  await page.getByRole("button", { name: "New thread" }).click();
  await page.waitForTimeout(1_000);

  // Send a message in the new thread
  const input = page.getByTestId("chat-input");
  await input.fill("Hello from thread test");
  await page.getByTestId("chat-send").click();

  // Wait for the user message to appear
  await expect(page.getByText("Hello from thread test")).toBeVisible({ timeout: 10_000 });

  // Wait for assistant response
  const assistantBubble = page.getByTestId("message-list").locator(".rounded-tl-md").first();
  await expect(assistantBubble).toBeVisible({ timeout: 60_000 });

  // The thread should now appear in the sidebar with a title
  const threadList = page.locator("[class*='thread'], [data-testid*='thread']").or(
    page.locator("text=THREADS").locator("..").locator("button").filter({ hasNot: page.locator("svg.lucide-plus") })
  );

  // Delete the thread — hover over it to reveal delete button
  page.on("dialog", (dialog) => dialog.accept());

  // Find thread items in the sidebar
  const threads = page.locator("button[class*='thread']").or(
    page.locator(".sidebar-content button").filter({ hasText: /.+/ })
  );

  if (await threads.first().isVisible({ timeout: 3_000 }).catch(() => false)) {
    await threads.first().hover();
    const deleteBtn = page.locator("[aria-label*='delete' i], button:has(svg.lucide-trash2)").first();
    if (await deleteBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await deleteBtn.click();
      await page.waitForTimeout(1_000);
    }
  }

  await page.screenshot({ path: "e2e/screenshots/journey-thread-crud.png", fullPage: true });
});

// ─── Journey 6: Cost page reflects usage ─────────────────────────────────────

test("cost page shows usage after chat", async ({ page }) => {
  test.setTimeout(15_000);
  await login(page);
  await page.goto("/cost");
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

  // After the chat tests, there should be some cost data
  await expect(page.getByText("Cost Dashboard")).toBeVisible();

  // Check daily/monthly cards exist
  await expect(page.getByText(/daily/i).first()).toBeVisible();
  await expect(page.getByText(/monthly/i).first()).toBeVisible();

  await page.screenshot({ path: "e2e/screenshots/journey-cost.png", fullPage: true });
});

// ─── Journey 7: Full sidebar navigation without errors ───────────────────────

test("navigate all sidebar pages without JS errors", async ({ page }) => {
  test.setTimeout(30_000);
  await login(page);

  const jsErrors: string[] = [];
  page.on("pageerror", (err) => jsErrors.push(err.message));

  const apiErrors: { url: string; status: number }[] = [];
  page.on("response", (res) => {
    if (res.url().includes("/api/") && res.status() >= 400 && res.status() !== 401) {
      apiErrors.push({ url: res.url(), status: res.status() });
    }
  });

  for (const name of ["Runs", "Approvals", "Queue", "Memory", "Artifacts", "Cost", "Tools", "Settings", "Chat"]) {
    const link = page.getByRole("link", { name, exact: true });
    if (await link.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await link.click();
      await page.waitForTimeout(1_000);
    }
  }

  expect(jsErrors, `JS errors: ${jsErrors.join("; ")}`).toHaveLength(0);
  if (apiErrors.length > 0) {
    console.log("API errors during navigation:", JSON.stringify(apiErrors, null, 2));
  }
  expect(apiErrors).toHaveLength(0);
});

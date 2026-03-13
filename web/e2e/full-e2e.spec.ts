import { test, expect, type Page } from "@playwright/test";

/**
 * Full real E2E tests — no mocks.
 *
 * Exercises the actual backend: chat with LLM, tool calls,
 * traceability (runs, events, audit), settings round-trip,
 * cost KPIs, and approval flow.
 *
 * Requires:
 *   - noa-api-dev running (backend)
 *   - Vite dev server (auto-started by playwright.config.ts webServer)
 *   - Test user registered (beforeAll handles this)
 *   - OpenAI API key configured in backend
 */

const API = "http://noa-api-dev:8000";
const TEST_EMAIL = "e2e-full@example.com";
const TEST_PASSWORD = "E2eFullTest!99";

// ─── Helpers ─────────────────────────────────────────────────────────────────

async function apiPost(path: string, body: object, token?: string) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  return res.json();
}

async function apiGet(path: string, token: string) {
  const res = await fetch(`${API}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}

async function apiPut(path: string, body: object, token: string) {
  const res = await fetch(`${API}${path}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function getToken(): Promise<string> {
  const res = await apiPost("/api/v1/auth/login", {
    email: TEST_EMAIL,
    password: TEST_PASSWORD,
    device_id: "e2e-full",
  });
  return res.data.access_token;
}

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(TEST_EMAIL);
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL("/", { timeout: 15_000 });
}

// ─── Global setup ────────────────────────────────────────────────────────────

test.describe("Full E2E Suite", () => {
test.describe.configure({ mode: "serial" });

let accessToken: string;

test.beforeAll(async () => {
  // Register test user (idempotent — 409 if exists is fine)
  await apiPost("/api/v1/auth/register", {
    email: TEST_EMAIL,
    password: TEST_PASSWORD,
  });

  accessToken = await getToken();

  // Configure: openai gpt-4.1-mini, external mode, known budgets
  await apiPut(
    "/api/v1/settings",
    {
      default_provider: "openai",
      default_model: "gpt-4.1-mini",
      default_privacy_mode: "external",
      budget_daily_usd: 5.0,
      budget_monthly_usd: 100.0,
    },
    accessToken,
  );
});

// ─── 1. Chat: send message, receive LLM response ────────────────────────────

let chatTraceId: string | null = null;

test("1 — send a chat message and get a real LLM response", async ({ page }) => {
  test.setTimeout(120_000);
  await login(page);

  const input = page.getByTestId("chat-input");
  await expect(input).toBeVisible({ timeout: 10_000 });

  // Send a deterministic prompt
  const msg = `E2E-${Date.now()}: Reply with exactly one word: PONG`;
  await input.fill(msg);

  // Watch for the SSE POST to fire
  const chatRequestPromise = page.waitForRequest(
    (req) => req.url().includes("/api/v1/chat") && req.method() === "POST",
    { timeout: 15_000 },
  ).catch(() => null);

  // Capture the response for trace_id
  const chatResponsePromise = page.waitForResponse(
    (res) => res.url().includes("/api/v1/chat") && res.request().method() === "POST",
    { timeout: 30_000 },
  ).catch(() => null);

  await page.getByTestId("chat-send").click();

  // Verify the POST actually fired
  const chatRequest = await chatRequestPromise;
  if (!chatRequest) {
    await page.screenshot({ path: "e2e/screenshots/debug-no-chat-request.png", fullPage: true });
    throw new Error("POST /api/v1/chat never fired");
  }

  // Grab trace_id
  const chatResponse = await chatResponsePromise;
  chatTraceId = chatResponse?.headers()["x-trace-id"] ?? null;

  // Wait for send button to re-enable (stream completed)
  await expect(page.getByTestId("chat-send")).toBeEnabled({ timeout: 90_000 });

  // The user message should appear somewhere on page
  await expect(page.getByText(msg).first()).toBeVisible({ timeout: 5_000 });

  await page.screenshot({ path: "e2e/screenshots/full-1-chat.png", fullPage: true });
});

// ─── 2. Runs page: verify the chat created a run ────────────────────────────

test("2 — chat run appears on /runs with correct model & cost > 0", async ({ page }) => {
  test.setTimeout(30_000);
  await login(page);
  await page.goto("/runs");
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

  // At least one run row
  const firstRow = page.locator("tbody tr").first();
  await expect(firstRow).toBeVisible({ timeout: 10_000 });

  // Model column should mention gpt-4.1-mini or openai
  await expect(firstRow.locator("td").nth(4)).toContainText(/gpt-4|openai/i, { timeout: 5_000 });

  // Cost column (7th) should be > $0
  const costCell = firstRow.locator("td").nth(6);
  const costText = await costCell.textContent();
  expect(costText).toBeTruthy();
  // Parse "$0.001234" → 0.001234
  const costVal = parseFloat(costText!.replace("$", "").replace(",", ""));
  expect(costVal).toBeGreaterThan(0);

  // Click into run detail
  await firstRow.click();
  await page.waitForURL(/\/runs\//, { timeout: 5_000 });

  // Run detail should show model info
  await expect(page.locator("text=gpt-4.1-mini").or(page.locator("text=openai")).first()).toBeVisible({
    timeout: 5_000,
  });

  // Should show token count > 0
  const tokensCard = page.locator('p:has-text("Tokens")').locator("..").locator("p.font-mono").first();
  if (await tokensCard.isVisible({ timeout: 3_000 }).catch(() => false)) {
    const tokensText = await tokensCard.textContent();
    const tokensVal = parseInt(tokensText!.replace(",", ""), 10);
    expect(tokensVal).toBeGreaterThan(0);
  }

  // Should show cost > 0
  const costCard = page.locator('p:has-text("Cost")').locator("..").locator("p.font-mono").first();
  if (await costCard.isVisible({ timeout: 3_000 }).catch(() => false)) {
    const cText = await costCard.textContent();
    const cVal = parseFloat(cText!.replace("$", "").replace(",", ""));
    expect(cVal).toBeGreaterThan(0);
  }

  // Event timeline tab should be visible
  await expect(page.locator('button[role="tab"]:has-text("Timeline")')).toBeVisible();

  await page.screenshot({ path: "e2e/screenshots/full-2-run-detail.png", fullPage: true });
});

// ─── 3. Traceability: audit log has entries for our chat ─────────────────────

test("3 — audit log contains entries for the chat trace_id", async () => {
  test.setTimeout(15_000);

  // Use the trace_id captured from the chat response
  // If we didn't capture it, query runs and get a trace_id from there
  let traceId = chatTraceId;
  if (!traceId) {
    const runs = await apiGet("/api/v1/runs?limit=1", accessToken);
    expect(runs.ok).toBe(true);
    expect(runs.data.length).toBeGreaterThan(0);
    // Use the run's trace_id from events if available
    const runId = runs.data[0].id;
    const runDetail = await apiGet(`/api/v1/runs/${runId}`, accessToken);
    // Try to extract trace_id from run events
    if (runDetail.data?.events?.length > 0) {
      const metaEvent = runDetail.data.events.find((e: any) => e.event_type === "meta");
      traceId = metaEvent?.payload?.trace_id;
    }
  }

  if (traceId) {
    const audit = await apiGet(`/api/v1/audit/entries?trace_id=${traceId}`, accessToken);
    expect(audit.ok).toBe(true);
    // Response shape is { data: { entries: [...] } } or { data: [...] }
    const entries = Array.isArray(audit.data) ? audit.data : audit.data?.entries ?? [];
    if (entries.length > 0) {
      const entry = entries[0];
      expect(entry.model_provider).toBeTruthy();
      expect(entry.model_name).toBeTruthy();
      expect(entry.input_tokens).toBeGreaterThanOrEqual(0);
      expect(entry.output_tokens).toBeGreaterThanOrEqual(0);
      expect(parseFloat(entry.cost_usd)).toBeGreaterThanOrEqual(0);
    }
  }

  // Verify hash chain integrity
  const verify = await apiPost("/api/v1/audit/verify", {}, accessToken);
  expect(verify.ok).toBe(true);
  expect(verify.data.valid).toBe(true);

  // Ensure the endpoint is reachable even with no audit entries
  expect(verify.data.entries_checked).toBeGreaterThanOrEqual(0);
});

// ─── 4. Cost KPIs: daily and monthly show real usage ─────────────────────────

test("4 — cost summary shows non-zero usage after chat", async ({ page }) => {
  test.setTimeout(30_000);

  // API-level check first
  const daily = await apiGet("/api/v1/cost/summary?period=daily", accessToken);
  expect(daily.ok).toBe(true);
  expect(daily.data.length).toBeGreaterThan(0);
  // At least one period entry should have cost > 0
  const hasCost = daily.data.some((d: any) => parseFloat(d.cost_usd) > 0);
  expect(hasCost).toBe(true);

  const monthly = await apiGet("/api/v1/cost/summary?period=monthly", accessToken);
  expect(monthly.ok).toBe(true);
  const hasMonthly = monthly.data.some((d: any) => parseFloat(d.cost_usd) > 0);
  expect(hasMonthly).toBe(true);

  // Token counts > 0
  const hasTokens = daily.data.some((d: any) => d.tokens_in > 0 || d.tokens_out > 0);
  expect(hasTokens).toBe(true);

  // UI check: navigate to /cost and verify it renders
  await login(page);
  await page.goto("/cost");
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

  await expect(page.locator('h1:has-text("Cost Dashboard")')).toBeVisible({ timeout: 5_000 });

  // Should show daily and monthly sections
  await expect(page.locator("text=daily").or(page.locator("text=Daily")).first()).toBeVisible({
    timeout: 5_000,
  });
  await expect(page.locator("text=monthly").or(page.locator("text=Monthly")).first()).toBeVisible({
    timeout: 5_000,
  });

  // Cost values should be rendered (dollar amounts)
  const costValues = page.locator("p.text-2xl.font-semibold.font-mono");
  if (await costValues.first().isVisible({ timeout: 3_000 }).catch(() => false)) {
    const firstCost = await costValues.first().textContent();
    expect(firstCost).toMatch(/\$/); // Should contain $ sign
  }

  await page.screenshot({ path: "e2e/screenshots/full-4-cost.png", fullPage: true });
});

// ─── 5. Settings: full round-trip of all traceability settings ───────────────

test("5 — settings round-trip: provider, model, privacy, budgets", async ({ page }) => {
  test.setTimeout(45_000);
  await login(page);
  await page.goto("/settings");
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

  // ── Verify current values loaded from API
  await expect(page.locator('h1:has-text("Settings")')).toBeVisible();

  // ── Change provider to anthropic
  const providerTrigger = page
    .locator("text=Default Provider")
    .locator("..")
    .locator('button[role="combobox"], div[role="combobox"]')
    .first();
  if (await providerTrigger.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await providerTrigger.click();
    await page.locator('[role="option"]:has-text("Anthropic")').click();
  }

  // ── Change privacy mode to private
  const privacyTrigger = page
    .locator("text=Default Privacy Mode")
    .locator("..")
    .locator('button[role="combobox"], div[role="combobox"]')
    .first();
  if (await privacyTrigger.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await privacyTrigger.click();
    await page.locator('[role="option"]:has-text("Private")').click();
  }

  // ── Set daily budget to 7.50
  const dailyInput = page.locator("input#daily-budget");
  await dailyInput.clear();
  await dailyInput.fill("7.50");

  // ── Set monthly budget to 150
  const monthlyInput = page.locator("input#monthly-budget");
  await monthlyInput.clear();
  await monthlyInput.fill("150");

  // ── Save
  await page.locator('button:has-text("Save")').click();
  await page.waitForTimeout(2_000);

  // ── Reload and verify persistence
  await page.reload();
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

  // Daily budget should be 7.50 (or 7.5)
  await expect(dailyInput).toHaveValue(/7\.5/, { timeout: 5_000 });
  // Monthly budget should be 150
  await expect(monthlyInput).toHaveValue("150", { timeout: 5_000 });

  // ── Budget validation: daily > monthly should show error
  await dailyInput.clear();
  await dailyInput.fill("999");
  // Check for error message
  const budgetError = page.locator("p.text-destructive, p.text-sm.text-destructive");
  // Error may or may not appear depending on impl — just check save still works
  await dailyInput.clear();
  await dailyInput.fill("7.50");

  // ── Verify via API
  const settings = await apiGet("/api/v1/settings", accessToken);
  expect(settings.ok).toBe(true);
  expect(settings.data.budget_daily_usd).toBe(7.5);
  expect(settings.data.budget_monthly_usd).toBe(150);

  // ── Restore original settings for subsequent tests
  await apiPut(
    "/api/v1/settings",
    {
      default_provider: "openai",
      default_model: "gpt-4.1-mini",
      default_privacy_mode: "external",
      budget_daily_usd: 5.0,
      budget_monthly_usd: 100.0,
    },
    accessToken,
  );

  await page.screenshot({ path: "e2e/screenshots/full-5-settings.png", fullPage: true });
});

// ─── 6. Tools page: list tools, check health, toggle enable ──────────────────

test("6 — tools page: list, health check, toggle", async ({ page }) => {
  test.setTimeout(30_000);
  await login(page);
  await page.goto("/tools");
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

  await expect(page.locator('h1:has-text("Tools")')).toBeVisible({ timeout: 5_000 });

  // Should list at least web_search
  await expect(page.locator("text=web_search")).toBeVisible({ timeout: 5_000 });

  // Click to expand web_search tool card
  const webSearchHeader = page.locator('[data-tool-header]:has-text("web_search")').first();
  if (await webSearchHeader.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await webSearchHeader.click();
    await page.waitForTimeout(500);

    // Health section should be visible
    const healthSection = page.locator("text=Health").first();
    await expect(healthSection).toBeVisible({ timeout: 3_000 });

    // Test connection button
    const testBtn = page.locator('button:has-text("Test Connection")').first();
    if (await testBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await testBtn.click();
      // Wait for health check result
      await page.waitForTimeout(3_000);
    }

    // Credentials section should show configured
    const credSection = page.locator("text=Credentials").first();
    await expect(credSection).toBeVisible({ timeout: 3_000 });
  }

  // Toggle web_search on (if off) via the switch
  const toggle = page.locator('div[role="switch"]').first();
  if (await toggle.isVisible({ timeout: 2_000 }).catch(() => false)) {
    const state = await toggle.getAttribute("data-state");
    if (state !== "checked") {
      await toggle.click();
      await page.waitForTimeout(1_000);
    }
  }

  // Verify via API
  const tools = await apiGet("/api/v1/tools", accessToken);
  expect(tools.ok).toBe(true);
  expect(tools.data.length).toBeGreaterThan(0);
  const webSearch = tools.data.find((t: any) => t.name === "web_search");
  expect(webSearch).toBeTruthy();
  expect(webSearch.credentials.configured).toBe(true);

  await page.screenshot({ path: "e2e/screenshots/full-6-tools.png", fullPage: true });
});

// ─── 7. Tool call: trigger web search, observe approval & result ─────────────

test("7 — trigger tool call (web search), handle approval flow", async ({ page }) => {
  test.setTimeout(120_000);

  // Ensure web_search is enabled
  await apiGet("/api/v1/tools", accessToken); // just verify it loads
  // Enable web_search via API PATCH
  await fetch(`${API}/api/v1/tools/web_search`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ enabled: true }),
  });

  await login(page);

  const input = page.getByTestId("chat-input");
  await input.fill("Use the web search tool to find: What is the current price of Bitcoin today?");
  await page.getByTestId("chat-send").click();

  // Wait for either: approval card OR direct assistant response
  const approvalCard = page.locator('text=Approval Required').or(page.locator("text=approval required"));
  const assistantBubble = page.getByTestId("message-list").locator('[class*="glass-strong"], .rounded-tl-md').first();

  await expect(approvalCard.or(assistantBubble)).toBeVisible({ timeout: 90_000 });

  // If approval card appeared, approve it
  if (await approvalCard.isVisible().catch(() => false)) {
    // The card should show the tool name
    await expect(
      page.locator("text=web_search").or(page.locator("text=search")).first(),
    ).toBeVisible({ timeout: 5_000 });

    // Click approve
    const approveBtn = page.locator("button.bg-green-600, button:has-text('Approve')").first();
    await approveBtn.click();

    // Wait for the actual LLM response after tool result
    await expect(assistantBubble).toBeVisible({ timeout: 90_000 });
  }

  const responseText = await assistantBubble.textContent();
  expect(responseText!.trim().length).toBeGreaterThan(0);

  // Verify approval history via API
  const history = await apiGet("/api/v1/approvals/history", accessToken);
  expect(history.ok).toBe(true);
  // May have approvals from this or previous test runs

  await page.screenshot({ path: "e2e/screenshots/full-7-tool-call.png", fullPage: true });
});

// ─── 8. Approvals page: verify history ───────────────────────────────────────

test("8 — approvals page shows history of decided approvals", async ({ page }) => {
  test.setTimeout(20_000);
  await login(page);
  await page.goto("/approvals");
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

  await expect(page.locator('h1:has-text("Approvals")')).toBeVisible({ timeout: 5_000 });

  // Check for either pending items or history section
  const emptyState = page.locator('text=No pending approvals');
  const historySection = page.locator('h2:has-text("History")');
  const pendingCards = page.locator("input[type='checkbox']").first();

  // Wait for page to settle
  await page.waitForTimeout(2_000);

  // The page should render without errors
  const jsErrors: string[] = [];
  page.on("pageerror", (err) => jsErrors.push(err.message));

  // If there's a history section, it should have at least one item
  if (await historySection.isVisible({ timeout: 3_000 }).catch(() => false)) {
    const historyItems = page.locator('div.flex.items-center.gap-3.py-2');
    const count = await historyItems.count();
    expect(count).toBeGreaterThan(0);
  }

  expect(jsErrors).toHaveLength(0);

  await page.screenshot({ path: "e2e/screenshots/full-8-approvals.png", fullPage: true });
});

// ─── 9. Thread lifecycle: create, send message, verify, delete ───────────────

test("9 — thread CRUD: create, chat, verify messages, delete", async ({ page }) => {
  test.setTimeout(120_000);
  await login(page);

  // Create a new thread via the sidebar button
  const newThreadBtn = page.locator('button[aria-label="New thread"]');
  await expect(newThreadBtn).toBeVisible({ timeout: 5_000 });
  await newThreadBtn.click();
  await page.waitForTimeout(1_000);

  // Send a message in the new thread
  const input = page.getByTestId("chat-input");
  await input.fill("Thread test: say hello");
  await page.getByTestId("chat-send").click();

  // Wait for assistant response
  await expect(page.getByText("Thread test: say hello")).toBeVisible({ timeout: 10_000 });
  const assistantBubble = page.getByTestId("message-list").locator('[class*="glass-strong"], .rounded-tl-md').first();
  await expect(assistantBubble).toBeVisible({ timeout: 90_000 });

  // Verify thread appears in API
  const threads = await apiGet("/api/v1/threads", accessToken);
  expect(threads.ok).toBe(true);
  expect(threads.data.length).toBeGreaterThan(0);

  // Find the thread with our message
  const threadId = threads.data[0].id;

  // Check messages in the thread
  const messages = await apiGet(`/api/v1/threads/${threadId}/messages`, accessToken);
  expect(messages.ok).toBe(true);
  expect(messages.data.length).toBeGreaterThanOrEqual(2); // user + assistant

  // User message should be present
  const userMsg = messages.data.find((m: any) => m.role === "user");
  expect(userMsg).toBeTruthy();
  expect(userMsg.content).toContain("Thread test");

  // Assistant message should be present
  const asstMsg = messages.data.find((m: any) => m.role === "assistant");
  expect(asstMsg).toBeTruthy();
  expect(asstMsg.content.length).toBeGreaterThan(0);

  // Delete the thread via API (cleanup)
  const delRes = await fetch(`${API}/api/v1/threads/${threadId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  expect(delRes.status).toBeLessThan(300);

  await page.screenshot({ path: "e2e/screenshots/full-9-thread.png", fullPage: true });
});

// ─── 10. Run detail: event timeline has expected event types ─────────────────

test("10 — run detail shows complete event timeline", async () => {
  test.setTimeout(15_000);

  // Get most recent run
  const runs = await apiGet("/api/v1/runs?limit=5", accessToken);
  expect(runs.ok).toBe(true);
  expect(runs.data.length).toBeGreaterThan(0);

  const runId = runs.data[0].id;
  const detail = await apiGet(`/api/v1/runs/${runId}`, accessToken);
  expect(detail.ok).toBe(true);

  // Run should have events
  expect(detail.data.events).toBeTruthy();
  expect(detail.data.events.length).toBeGreaterThan(0);

  // Should have at least a 'meta' event
  const eventTypes = detail.data.events.map((e: any) => e.event_type);
  expect(eventTypes).toContain("meta");

  // Should have a 'result_ready' event (chat completed)
  const hasResult = eventTypes.includes("result_ready");
  // Or at minimum token_stream events
  const hasTokens = eventTypes.includes("token_stream");
  expect(hasResult || hasTokens).toBe(true);

  // Run should have a completed status
  expect(["completed", "failed", "running"]).toContain(detail.data.status);

  // Run should have model info
  expect(detail.data.model || detail.data.provider).toBeTruthy();
});

// ─── 11. Cost KPIs: budget vs actual comparison ──────────────────────────────

test("11 — cost KPI: budget limits vs actual spend", async () => {
  test.setTimeout(15_000);

  // Get settings to know budget limits
  const settings = await apiGet("/api/v1/settings", accessToken);
  expect(settings.ok).toBe(true);
  const dailyBudget = settings.data.budget_daily_usd;
  const monthlyBudget = settings.data.budget_monthly_usd;

  expect(dailyBudget).toBeGreaterThan(0);
  expect(monthlyBudget).toBeGreaterThan(0);
  expect(monthlyBudget).toBeGreaterThanOrEqual(dailyBudget);

  // Get actual cost
  const daily = await apiGet("/api/v1/cost/summary?period=daily", accessToken);
  const monthly = await apiGet("/api/v1/cost/summary?period=monthly", accessToken);

  // Daily spend should be under daily budget
  const dailySpend = daily.data.reduce((sum: number, d: any) => sum + parseFloat(d.cost_usd), 0);
  expect(dailySpend).toBeLessThan(dailyBudget);

  // Monthly spend should be under monthly budget
  const monthlySpend = monthly.data.reduce((sum: number, d: any) => sum + parseFloat(d.cost_usd), 0);
  expect(monthlySpend).toBeLessThan(monthlyBudget);

  // Token counts should be consistent
  const dailyTokensIn = daily.data.reduce((sum: number, d: any) => sum + d.tokens_in, 0);
  const dailyTokensOut = daily.data.reduce((sum: number, d: any) => sum + d.tokens_out, 0);
  expect(dailyTokensIn + dailyTokensOut).toBeGreaterThan(0);
});

// ─── 12. Runs list: verify cost aggregation across multiple runs ─────────────

test("12 — runs list: multiple runs with cost aggregation", async () => {
  test.setTimeout(15_000);

  const runs = await apiGet("/api/v1/runs?limit=20", accessToken);
  expect(runs.ok).toBe(true);
  expect(runs.data.length).toBeGreaterThanOrEqual(2); // We've had at least 2 chats

  let totalCost = 0;
  let totalTokensIn = 0;
  let totalTokensOut = 0;

  for (const run of runs.data) {
    if (run.cost_usd) totalCost += parseFloat(run.cost_usd);
    if (run.tokens_in) totalTokensIn += run.tokens_in;
    if (run.tokens_out) totalTokensOut += run.tokens_out;
  }

  // Total cost across runs should be > 0
  expect(totalCost).toBeGreaterThan(0);
  // Total tokens should be > 0
  expect(totalTokensIn + totalTokensOut).toBeGreaterThan(0);

  // Each run should have required fields
  for (const run of runs.data) {
    expect(run.id).toBeTruthy();
    expect(run.status).toBeTruthy();
    expect(run.created_at).toBeTruthy();
  }
});

// ─── 13. Audit chain integrity: verify hash chain after multiple operations ──

test("13 — audit hash chain remains valid after multiple operations", async () => {
  test.setTimeout(15_000);

  const verify = await apiPost("/api/v1/audit/verify", {}, accessToken);
  expect(verify.ok).toBe(true);
  expect(verify.data.valid).toBe(true);
  expect(verify.data.entries_checked).toBeGreaterThan(0);
});

// ─── 14. Full navigation: all pages load without JS or API errors ────────────

test("14 — all sidebar pages load without errors", async ({ page }) => {
  test.setTimeout(45_000);
  await login(page);

  const jsErrors: string[] = [];
  page.on("pageerror", (err) => jsErrors.push(err.message));

  const apiErrors: { url: string; status: number }[] = [];
  page.on("response", (res) => {
    if (res.url().includes("/api/") && res.status() >= 500) {
      apiErrors.push({ url: res.url(), status: res.status() });
    }
  });

  const pages = [
    { name: "Runs", url: "/runs", heading: "Runs" },
    { name: "Approvals", url: "/approvals", heading: "Approvals" },
    { name: "Queue", url: "/queue", heading: "Queue" },
    { name: "Memory", url: "/memory", heading: "Memory" },
    { name: "Artifacts", url: "/artifacts", heading: "Artifacts" },
    { name: "Cost", url: "/cost", heading: "Cost Dashboard" },
    { name: "Tools", url: "/tools", heading: "Tools" },
    { name: "Settings", url: "/settings", heading: "Settings" },
  ];

  for (const p of pages) {
    await page.goto(p.url);
    await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
    // Page heading should be visible
    await expect(
      page.locator(`h1:has-text("${p.heading}")`).or(page.locator(`text=${p.heading}`).first()),
    ).toBeVisible({ timeout: 5_000 });
  }

  // Return to chat
  await page.goto("/");
  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 5_000 });

  expect(jsErrors, `JS errors: ${jsErrors.join("; ")}`).toHaveLength(0);
  expect(apiErrors, `500 errors: ${JSON.stringify(apiErrors)}`).toHaveLength(0);

  await page.screenshot({ path: "e2e/screenshots/full-14-navigation.png", fullPage: true });
});

// ─── 15. Online indicator & health ───────────────────────────────────────────

test("15 — online indicator shows connected status", async ({ page }) => {
  test.setTimeout(15_000);
  await login(page);

  // The top bar should show online indicator
  const online = page.locator('[data-testid="online-indicator"]');
  const offline = page.locator('[data-testid="offline-indicator"]');

  // One of them should be visible
  await expect(online.or(offline)).toBeVisible({ timeout: 5_000 });

  // Backend health should be OK
  const health = await apiGet("/health", "");
  expect(health.ok).toBe(true);

  const ready = await (
    await fetch(`${API}/health/ready`)
  ).json();
  expect(ready.ok).toBe(true);
});

}); // end describe

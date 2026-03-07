import { test as base, type Page } from "@playwright/test";

/**
 * Intercept all /api/v1/* calls with mock responses so the app
 * runs without a backend. Auth calls set the localStorage flag
 * that the app checks for authentication state.
 */
async function setupApiMocks(page: Page) {
  // Auth - login
  await page.route("**/api/v1/auth/login", async (route) => {
    const req = route.request();
    const body = req.postDataJSON();

    if (body?.email === "fail@example.com") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: false,
          data: null,
          error: { code: "UNAUTHORIZED", message: "Invalid credentials" },
          trace_id: "test",
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: { authenticated: true },
        error: null,
        trace_id: "test",
      }),
    });
  });

  // Auth - register
  await page.route("**/api/v1/auth/register", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: { user_id: "u_test_123" },
        error: null,
        trace_id: "test",
      }),
    });
  });

  // Auth - logout
  await page.route("**/api/v1/auth/logout", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: { status: "logged_out" },
        error: null,
        trace_id: "test",
      }),
    });
  });

  // Threads (needed after login redirect to /)
  await page.route("**/api/v1/threads", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: [],
        error: null,
        trace_id: "test",
      }),
    });
  });

  // Settings (loaded on app init)
  await page.route("**/api/v1/settings", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          default_provider: "anthropic",
          default_model: "claude-sonnet-4",
          default_privacy_mode: "private",
          budget_daily_usd: 5.0,
          budget_monthly_usd: 50.0,
        },
        error: null,
        trace_id: "test",
      }),
    });
  });

  // Usage
  await page.route("**/api/v1/usage", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          daily: { used: 0, limit: 100000, cost_usd: 0 },
          monthly: { used: 0, limit: 2000000, cost_usd: 0 },
        },
        error: null,
        trace_id: "test",
      }),
    });
  });

  // Runs (Chat page fetches runs)
  await page.route("**/api/v1/runs", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: [],
        error: null,
        trace_id: "test",
      }),
    });
  });

  // Queue (sidebar may fetch)
  await page.route("**/api/v1/queue", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: [],
        error: null,
        trace_id: "test",
      }),
    });
  });

  // Memory facts (memory page)
  await page.route("**/api/v1/memory/facts", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: [],
        error: null,
        trace_id: "test",
      }),
    });
  });

  // Approvals pending (sidebar badge)
  await page.route("**/api/v1/approvals/pending", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: [],
        error: null,
        trace_id: "test",
      }),
    });
  });
}

/** Perform login via the UI and return the authenticated page. */
async function loginViaUI(page: Page, email = "test@example.com", password = "password123") {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  // Wait for redirect to chat page
  await page.waitForURL("/", { timeout: 5000 });
}

export const test = base.extend<{ authenticatedPage: Page }>({
  authenticatedPage: async ({ page }, use) => {
    await setupApiMocks(page);
    await loginViaUI(page);
    await use(page);
  },
});

export { setupApiMocks, loginViaUI };
export { expect } from "@playwright/test";

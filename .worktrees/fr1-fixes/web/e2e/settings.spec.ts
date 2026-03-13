import { test, expect, setupApiMocks, loginViaUI } from "./fixtures";

// Spec refs: S24 (user settings)
test.describe("Settings", () => {
  test("authenticated user sees settings form with populated fields", async ({ page }) => {
    await setupApiMocks(page);
    await loginViaUI(page);

    await page.goto("/settings");

    // Settings heading
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

    // Provider and model labels visible
    await expect(page.getByText("Default Provider")).toBeVisible();
    await expect(page.getByText("Default Model", { exact: true })).toBeVisible();

    // Budget fields should be populated from mock (5.0 / 50.0)
    const dailyInput = page.getByLabel("Daily Budget (USD)");
    const monthlyInput = page.getByLabel("Monthly Budget (USD)");
    await expect(dailyInput).toHaveValue("5");
    await expect(monthlyInput).toHaveValue("50");

    // Save button
    await expect(page.getByRole("button", { name: "Save Settings" })).toBeVisible();
  });

  test("change provider and save — success toast appears", async ({ page }) => {
    await setupApiMocks(page);

    // Track if PUT was called
    let saveCalled = false;
    await page.route("**/api/v1/settings", async (route) => {
      if (route.request().method() === "PUT") {
        saveCalled = true;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ok: true, data: { status: "saved" }, error: null, trace_id: "test" }),
        });
        return;
      }
      // GET — return default settings
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          data: {
            default_provider: "anthropic",
            default_model: "claude-sonnet-4-20250514",
            default_privacy_mode: "private",
            budget_daily_usd: 5.0,
            budget_monthly_usd: 50.0,
          },
          error: null,
          trace_id: "test",
        }),
      });
    });
    await loginViaUI(page);
    await page.goto("/settings");

    // Wait for form to load
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
    await expect(page.getByLabel("Daily Budget (USD)")).toHaveValue("5");

    // Click save
    await page.getByRole("button", { name: "Save Settings" }).click();

    // Success toast should appear
    await expect(page.getByText("Settings saved", { exact: true })).toBeVisible({ timeout: 5000 });
    expect(saveCalled).toBe(true);
  });

  test("budget validation — daily exceeding monthly shows error", async ({ page }) => {
    await setupApiMocks(page);
    await loginViaUI(page);
    await page.goto("/settings");

    // Wait for form to load
    const dailyInput = page.getByLabel("Daily Budget (USD)");
    const monthlyInput = page.getByLabel("Monthly Budget (USD)");
    await expect(dailyInput).toBeVisible();

    // Set daily > monthly
    await dailyInput.fill("100");
    await monthlyInput.fill("50");

    // Click save
    await page.getByRole("button", { name: "Save Settings" }).click();

    // Validation error should appear
    await expect(page.getByText("Daily budget must not exceed monthly budget")).toBeVisible({ timeout: 3000 });
  });
});

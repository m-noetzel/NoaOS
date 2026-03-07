import { test, expect, setupApiMocks, loginViaUI } from "./fixtures";

test.describe("Navigation", () => {
  test("unknown route shows 404 page", async ({ page }) => {
    await setupApiMocks(page);
    await page.goto("/this-route-does-not-exist");

    await expect(page.getByText("404")).toBeVisible();
  });

  test("sidebar links navigate to correct pages", async ({ authenticatedPage: page }) => {
    // Verify we start on chat (/)
    expect(page.url()).toMatch(/\/$/);

    // Navigate to Settings via sidebar
    await page.getByRole("link", { name: "Settings" }).click();
    await page.waitForURL("/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

    // Navigate to Memory via sidebar
    await page.getByRole("link", { name: "Memory" }).click();
    await page.waitForURL("/memory");

    // Navigate back to Chat
    await page.getByRole("link", { name: "Chat" }).click();
    await page.waitForURL("/");
  });

  test("auth-protected pages redirect when unauthenticated", async ({ page }) => {
    await setupApiMocks(page);

    // Try to access protected routes without login
    const protectedRoutes = ["/settings", "/memory", "/runs", "/cost"];

    for (const route of protectedRoutes) {
      await page.goto(route);
      await page.waitForURL(/\/login/, { timeout: 3000 });
      expect(page.url()).toContain("/login");
    }
  });
});

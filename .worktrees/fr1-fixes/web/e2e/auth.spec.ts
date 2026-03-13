import { test, expect, setupApiMocks } from "./fixtures";

// Spec refs: S23 (authentication), S25 (session management)
test.describe("Auth - Login", () => {
  test("login page renders with email and password fields", async ({ page }) => {
    await setupApiMocks(page);
    await page.goto("/login");

    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("successful login redirects to chat", async ({ page }) => {
    await setupApiMocks(page);
    await page.goto("/login");

    await page.getByLabel("Email").fill("test@example.com");
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();

    await page.waitForURL("/");
    expect(page.url()).toMatch(/\/$/);
  });

  test("invalid credentials show error message", async ({ page }) => {
    await setupApiMocks(page);
    await page.goto("/login");

    await page.getByLabel("Email").fill("fail@example.com");
    await page.getByLabel("Password").fill("wrongpass");
    await page.getByRole("button", { name: "Sign in" }).click();

    // Toast error should appear
    await expect(page.getByText("Login failed", { exact: true })).toBeVisible({ timeout: 5000 });
  });
});

test.describe("Auth - Route Guards", () => {
  test("unauthenticated user redirected to /login", async ({ page }) => {
    await setupApiMocks(page);
    // Navigate to protected route without logging in
    await page.goto("/");

    await page.waitForURL(/\/login/, { timeout: 5000 });
    expect(page.url()).toContain("/login");
  });

  test("logout clears session and redirects to login", async ({ authenticatedPage: page }) => {
    // We're logged in via fixture — verify we're on chat
    expect(page.url()).toMatch(/\/$/);

    // Find and click logout button in the sidebar
    const logoutButton = page.getByRole("button", { name: /log\s*out|sign\s*out/i });
    await expect(logoutButton).toBeVisible({ timeout: 5000 });
    await logoutButton.click();

    // Should redirect to login
    await page.waitForURL(/\/login/, { timeout: 5000 });
    expect(page.url()).toContain("/login");
  });
});

test.describe("Auth - Register", () => {
  test("register page renders with form fields", async ({ page }) => {
    await setupApiMocks(page);
    await page.goto("/register");

    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel(/^Password$/)).toBeVisible();
    await expect(page.getByLabel("Confirm Password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Create account" })).toBeVisible();
  });

  test("successful registration redirects to chat", async ({ page }) => {
    await setupApiMocks(page);
    await page.goto("/register");

    await page.getByLabel("Email").fill("new@example.com");
    await page.getByLabel(/^Password$/).fill("securePass123");
    await page.getByLabel("Confirm Password").fill("securePass123");
    await page.getByRole("button", { name: "Create account" }).click();

    // After successful registration, should redirect to login or auto-login to chat
    await page.waitForURL(/\/(login)?$/, { timeout: 5000 });
  });
});

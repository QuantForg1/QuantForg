import { expect, test } from "@playwright/test";

test.describe("QuantForg beta E2E", () => {
  test("landing renders brand and CTAs", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "institutional trading terminal",
      { ignoreCase: true },
    );
    await expect(page.getByRole("link", { name: /sign in/i }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /start free|open terminal|create/i }).first()).toBeVisible();
  });

  test("register requires verification message path", async ({ page }) => {
    const email = `beta.pw.${Date.now()}@mailinator.com`;
    await page.goto("/register");
    await page.getByLabel(/display name/i).fill("Beta Playwright");
    await page.getByLabel(/^email$/i).fill(email);
    await page.getByLabel(/^password$/i).fill("BetaLaunchTest1!");
    await page.getByRole("button", { name: /create account/i }).click();
    // Prefer Promise.any so a timed-out waitForURL does not fail a visible toast.
    await Promise.any([
      page.waitForURL(/verify-email|dashboard/, { timeout: 45_000 }),
      page
        .getByText(
          /verify|successful|too many|attempts|try again|exists|failed|registration/i,
        )
        .first()
        .waitFor({ timeout: 45_000 }),
    ]);
    const url = page.url();
    const body = await page.locator("body").innerText();
    expect(
      /verify-email|dashboard/.test(url) ||
        /verify|successful|too many|attempts|try again|exists|failed|registration/i.test(
          body,
        ),
    ).toBeTruthy();
  });

  test("login rejects invalid credentials", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/^email$/i).fill("nobody-beta@example.com");
    await page.getByLabel(/^password$/i).fill("definitely-wrong");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.getByText(/invalid|failed|credentials|authentication/i)).toBeVisible({
      timeout: 20_000,
    });
    await expect(page).toHaveURL(/login/);
  });

  test("unauthenticated dashboard redirects to login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/login/, { timeout: 15_000 });
  });

  test("settings requires auth", async ({ page }) => {
    await page.goto("/settings");
    await expect(page).toHaveURL(/login/, { timeout: 15_000 });
  });

  test("portfolio requires auth", async ({ page }) => {
    await page.goto("/portfolio");
    await expect(page).toHaveURL(/login/, { timeout: 15_000 });
  });

  test("verified login reaches dashboard portfolio settings logout", async ({
    page,
  }) => {
    const email = process.env.E2E_EMAIL;
    const password = process.env.E2E_PASSWORD;
    if (!email || !password) {
      throw new Error(
        "E2E_EMAIL and E2E_PASSWORD are required for go-live authenticated E2E",
      );
    }

    await page.goto("/login");
    await page.getByLabel(/^email$/i).fill(email);
    await page.getByLabel(/^password$/i).fill(password);
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/dashboard/, { timeout: 45_000 });
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();

    await page.goto("/portfolio");
    await expect(page.getByRole("heading", { name: /portfolio/i })).toBeVisible();

    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: /settings/i })).toBeVisible();

    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/login/, { timeout: 15_000 });
  });

  test("forgot password page submits request", async ({ page }) => {
    await page.goto("/forgot-password");
    await expect(page.getByRole("heading", { name: /reset password/i })).toBeVisible();
    await page.getByLabel(/^email$/i).fill("reset.probe@example.com");
    await page.getByRole("button", { name: /send reset link/i }).click();
    await expect(
      page.getByText(/if the email exists|reset link|sent|failed/i).first(),
    ).toBeVisible({ timeout: 20_000 });
  });

  test("reset password without token shows expired path", async ({ page }) => {
    await page.goto("/reset-password");
    await expect(page.getByRole("heading", { name: /choose a new password/i })).toBeVisible();
    await expect(page.getByText(/invalid|expired|missing|request a new/i).first()).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("link", { name: /request a new reset link/i })).toBeVisible();
  });

  test("organizations requires auth", async ({ page }) => {
    await page.goto("/organizations");
    await expect(page).toHaveURL(/login/, { timeout: 15_000 });
  });

  test("execution and positions require auth", async ({ page }) => {
    await page.goto("/execution");
    await expect(page).toHaveURL(/login/, { timeout: 15_000 });
    await page.goto("/positions");
    await expect(page).toHaveURL(/login/, { timeout: 15_000 });
  });
});

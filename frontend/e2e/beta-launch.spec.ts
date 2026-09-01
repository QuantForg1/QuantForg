import { expect, test } from "@playwright/test";

test.describe("QuantForg beta E2E", () => {
  test("landing renders brand and CTAs", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "institutional trading terminal",
      { ignoreCase: true },
    );
    await expect(page.getByRole("link", { name: /sign in/i }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /contact sales/i }).first()).toBeVisible();
  });

  test("public register is available without a purchase wall", async ({ page }) => {
    await page.goto("/register");
    await expect(page).toHaveURL(/register/, { timeout: 15_000 });
    await expect(
      page.getByRole("heading", { name: /create your account/i }),
    ).toBeVisible();
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
    test.setTimeout(180_000);
    const { loginAsE2E } = await import("./helpers");
    await loginAsE2E(page);
    await expect(
      page.getByRole("heading", { name: /good (morning|afternoon|evening)/i }),
    ).toBeVisible({
      timeout: 20_000,
    });

    await page.goto("/portfolio");
    await expect(page).toHaveURL(/portfolio/);
    await expect(page.getByRole("heading", { name: "Portfolio", exact: true })).toBeVisible({
      timeout: 30_000,
    });

    await page.goto("/settings");
    await expect(page).toHaveURL(/settings/);
    await expect(page.getByRole("heading", { name: /settings/i })).toBeVisible({
      timeout: 20_000,
    });

    await page.getByRole("button", { name: "Sign out" }).click({ force: true });
    await expect(page).toHaveURL(/login/, { timeout: 45_000 });
  });

  test("forgot password collects email", async ({ page }) => {
    await page.goto("/forgot-password");
    await expect(
      page.getByRole("heading", { name: /reset your password/i }),
    ).toBeVisible();
    await expect(page.getByLabel(/^email$/i)).toBeVisible();
  });

  test("reset password requires a valid reset link", async ({ page }) => {
    await page.goto("/reset-password");
    await expect(
      page.getByRole("heading", { name: /choose a new password/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: /request a new reset link/i }),
    ).toBeVisible();
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

import { expect, test } from "@playwright/test";
import { loginAsE2E } from "./helpers";

test.describe("Research Lab (auth gate)", () => {
  test("/research-lab requires authentication", async ({ page }) => {
    await page.goto("/research-lab");
    await expect(page).toHaveURL(/login/, { timeout: 15_000 });
  });
});

test.describe("Research Lab (authenticated)", () => {
  test("Research Lab workspace loads advisory modules", async ({ page }) => {
    test.setTimeout(180_000);
    await loginAsE2E(page);

    await page.goto("/research-lab");
    await expect(page.getByRole("heading", { name: /^Research Lab$/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(
      page
        .getByText(/advisory only|never_submits_orders|EXECUTION_ENABLED|Research Lab API unavailable/i)
        .first(),
    ).toBeVisible({ timeout: 90_000 });
    await expect(page.getByRole("tablist", { name: /Research Lab modules/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Library/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Validation/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Promotion/i })).toBeVisible();
  });
});

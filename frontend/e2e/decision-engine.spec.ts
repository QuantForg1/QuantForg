import { expect, test } from "@playwright/test";
import { loginAsE2E } from "./helpers";

test.describe("Decision Engine (auth gate)", () => {
  test("/decision-engine requires authentication", async ({ page }) => {
    await page.goto("/decision-engine");
    await expect(page).toHaveURL(/login/, { timeout: 15_000 });
  });
});

test.describe("Decision Engine (authenticated)", () => {
  test("Decision Engine desk loads wait-biased advisory surface", async ({ page }) => {
    test.setTimeout(180_000);
    await loginAsE2E(page);

    await page.goto("/decision-engine");
    await expect(page.getByRole("heading", { name: /^Decision Engine$/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(
      page
        .getByText(/paper default|advisory only|EXECUTION_ENABLED|never_submits_orders|Decision Engine unavailable/i)
        .first(),
    ).toBeVisible({ timeout: 90_000 });
    await expect(
      page.getByText(/WAIT|TRADE_IDEA|Capital preservation|unavailable/i).first(),
    ).toBeVisible({ timeout: 30_000 });
  });
});

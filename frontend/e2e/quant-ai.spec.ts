import { expect, test } from "@playwright/test";
import { loginAsE2E } from "./helpers";

test.describe("Quant AI (auth gate)", () => {
  test("/quant-ai requires authentication", async ({ page }) => {
    await page.goto("/quant-ai");
    await expect(page).toHaveURL(/login/, { timeout: 15_000 });
  });
});

test.describe("Quant AI (authenticated)", () => {
  test("Quant AI desk loads advisory surface", async ({ page }) => {
    test.setTimeout(180_000);
    await loginAsE2E(page);

    await page.goto("/quant-ai");
    await expect(page.getByRole("heading", { name: /^Quant AI$/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(
      page.getByText(/advisory only|never submits|EXECUTION_ENABLED|Quant AI unavailable/i).first(),
    ).toBeVisible({ timeout: 90_000 });
    await expect(page.getByText(/Intelligence modules|Why|Market dashboard/i).first()).toBeVisible({
      timeout: 30_000,
    });
  });
});

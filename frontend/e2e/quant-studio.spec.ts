import { expect, test } from "@playwright/test";
import { loginAsE2E } from "./helpers";

test.describe("Quant Studio (auth gate)", () => {
  test("/quant-studio requires authentication", async ({ page }) => {
    await page.goto("/quant-studio");
    await expect(page).toHaveURL(/login/, { timeout: 15_000 });
  });
});

test.describe("Quant Studio (authenticated)", () => {
  test("Quant Studio workspace loads advisory modules", async ({ page }) => {
    test.setTimeout(180_000);
    await loginAsE2E(page);

    await page.goto("/quant-studio");
    await expect(page.getByRole("heading", { name: /^Quant Studio$/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(
      page.getByText(/advisory only|never_submits_orders|EXECUTION_ENABLED|Quant Studio unavailable/i).first(),
    ).toBeVisible({ timeout: 90_000 });
    await expect(page.getByRole("tablist", { name: /Quant Studio modules/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Visual Builder/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Backtest Studio/i })).toBeVisible();
  });
});

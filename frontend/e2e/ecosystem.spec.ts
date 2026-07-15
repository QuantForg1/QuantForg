import { expect, test } from "@playwright/test";
import { loginAsE2E } from "./helpers";

test.describe("Ecosystem (auth gate)", () => {
  test("/ecosystem requires authentication", async ({ page }) => {
    await page.goto("/ecosystem");
    await expect(page).toHaveURL(/login/, { timeout: 15_000 });
  });
});

test.describe("Ecosystem (authenticated)", () => {
  test("Ecosystem hub loads workflow modules", async ({ page }) => {
    test.setTimeout(180_000);
    await loginAsE2E(page);

    await page.goto("/ecosystem");
    await expect(page.getByRole("heading", { name: /^Ecosystem$/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(
      page
        .getByText(/advisory only|never_submits_orders|EXECUTION_ENABLED|Ecosystem API unavailable/i)
        .first(),
    ).toBeVisible({ timeout: 90_000 });
    await expect(page.getByRole("tablist", { name: /Ecosystem modules/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Journal/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Playbooks/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Coach/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Cloud Sync/i })).toBeVisible();
  });
});

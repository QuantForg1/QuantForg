import { expect, test } from "@playwright/test";
import { loginAsE2E } from "./helpers";

test.describe("Institutional desk regression (auth gates)", () => {
  test("broker / workspace / execution / intel require auth", async ({ page }) => {
    for (const path of ["/broker", "/workspace", "/execution", "/execution-intel"]) {
      await page.goto(path);
      await expect(page).toHaveURL(/login/, { timeout: 15_000 });
    }
  });
});

test.describe("Institutional desk regression (authenticated)", () => {
  test("Broker + Terminal + OMS book + Execution intel load without regression", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await loginAsE2E(page);

    // Analytics first (prod dashboard ~40s) — avoid long workspace session first.
    await page.goto("/execution-intel");
    await expect(page.getByRole("heading", { name: /Execution Intelligence/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(
      page.getByText(/Trade lifecycle|never enables live trading/i).first(),
    ).toBeVisible();
    await expect(
      page
        .getByText(
          /Fill rate|Lifecycle timeline|EXECUTION_ENABLED|Execution intelligence unavailable/i,
        )
        .first(),
    ).toBeVisible({ timeout: 90_000 });

    // Broker Workspace
    await page.goto("/broker");
    await expect(
      page.locator("main").getByText(/Broker Workspace/i).first(),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.locator("main").getByText(/Gateway/i).first()).toBeVisible();

    // Trading Terminal (/workspace — same institutional shell as /execution)
    await page.goto("/workspace");
    await expect(
      page.getByRole("application", { name: /Institutional trading terminal/i }),
    ).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/Market Watch/i).first()).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/Order Ticket/i).first()).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("button", { name: /Buy market/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Sell market/i })).toBeVisible();

    // OMS + journal + execution analytics tape
    await expect(page.getByRole("region", { name: /Institutional book panel/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Open Positions/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Pending Orders/i })).toBeVisible();

    await page.getByRole("tab", { name: /^Journal$/i }).click();
    await expect(
      page
        .getByText(/No execution journal yet|Latency|Result|Execution journal/i)
        .first(),
    ).toBeVisible({ timeout: 30_000 });

    await page.getByRole("tab", { name: /Execution Log/i }).click();
    await expect(
      page.getByText(/Fill rate|Success rate|No execution tape|Stages|Result/i).first(),
    ).toBeVisible({ timeout: 30_000 });

    await page.getByRole("tab", { name: /Open Positions/i }).click();
    await expect(
      page.getByText(/Live Position Manager|No open positions|Trading disabled/i).first(),
    ).toBeVisible({ timeout: 20_000 });

    await page.getByRole("tab", { name: /Pending Orders/i }).click();
    await expect(
      page.getByText(/Orders Workspace|No pending orders|Orders unavailable/i).first(),
    ).toBeVisible({ timeout: 20_000 });

    // /execution reuses WorkspaceShell (covered above). Auth gate already asserts /execution.
  });
});

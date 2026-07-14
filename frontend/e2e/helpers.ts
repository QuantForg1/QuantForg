import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";

/** Suppress first-run product tour so authenticated desk assertions aren't blocked. */
export async function seedDeskOnboarding(page: Page): Promise<void> {
  await page.addInitScript(() => {
    try {
      localStorage.setItem("qf.onboarding.tour.dismissed.v1", "1");
      localStorage.setItem("qf.onboarding.first_run.dismissed.v1", "1");
      localStorage.setItem(
        "qf.onboarding.checklist.v1",
        JSON.stringify({
          invite: true,
          tour: true,
          paper: true,
          broker: true,
          feedback: true,
          whats_new: true,
        }),
      );
    } catch {
      /* ignore */
    }
  });
}

export async function loginAsE2E(page: Page): Promise<void> {
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  if (!email || !password) {
    throw new Error("E2E_EMAIL and E2E_PASSWORD are required");
  }
  await seedDeskOnboarding(page);

  async function attempt(): Promise<void> {
    await page.goto("/login");
    await page.getByLabel(/^email$/i).fill(email);
    await page.getByLabel(/^password$/i).fill(password);
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForURL(/dashboard/, { timeout: 60_000 });
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible({
      timeout: 30_000,
    });
    await page.waitForFunction(() => Boolean(localStorage.getItem("qf_access_token")), null, {
      timeout: 15_000,
    });
  }

  try {
    await attempt();
  } catch {
    await page.waitForTimeout(2_000);
    await attempt();
  }

  const close = page.getByRole("button", { name: /^close$/i });
  if (await close.isVisible().catch(() => false)) {
    await close.click();
  }
}

import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const logs = [];

page.on("console", (msg) => {
  logs.push({ type: msg.type(), text: msg.text().slice(0, 240) });
});

await page.goto("http://localhost:3000/login", {
  waitUntil: "networkidle",
  timeout: 60_000,
});
await page.waitForTimeout(2500);

const apiBase = await page.evaluate(async () => {
  // Probe via a no-auth path if any; otherwise inspect performance resource URLs.
  const entries = performance.getEntriesByType("resource");
  const apiHits = entries
    .map((e) => e.name)
    .filter((u) => /railway\.app|127\.0\.0\.1:8000|localhost:8000|\/api\/v1\//.test(u));
  return {
    apiHits: apiHits.slice(0, 8),
    banner: document.body?.innerText?.includes("API unreachable") ||
      document.body?.innerText?.includes("offline"),
  };
});

const spam = logs.filter(
  (l) =>
    l.type === "error" &&
    /qf_monitored_error|Failed to fetch/i.test(l.text),
);
const warns = logs.filter((l) => /qf_api_unreachable/i.test(l.text));

console.log(
  JSON.stringify(
    {
      apiHitsSample: apiBase.apiHits,
      usesLocalFallback: apiBase.apiHits.some((u) => /127\.0\.0\.1:8000|localhost:8000/.test(u)),
      usesRailway: apiBase.apiHits.some((u) => /railway\.app/.test(u)),
      errorSpamCount: spam.length,
      unreachableWarnCount: warns.length,
      consoleErrors: logs.filter((l) => l.type === "error").slice(0, 5),
    },
    null,
    2,
  ),
);

await browser.close();

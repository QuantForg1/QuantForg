import { chromium } from "playwright";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const API =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://quantforg-production.up.railway.app/api/v1";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

const consoleLogs = [];
const pageErrors = [];
const failedRequests = [];
const apiResponses = [];
const corsLike = [];

page.on("console", (msg) => {
  const text = msg.text();
  consoleLogs.push({ type: msg.type(), text: text.slice(0, 500) });
  if (/CORS|Access-Control|Failed to fetch/i.test(text)) {
    corsLike.push(text.slice(0, 300));
  }
});
page.on("pageerror", (err) => pageErrors.push(String(err).slice(0, 500)));
page.on("requestfailed", (req) => {
  failedRequests.push({
    url: req.url().slice(0, 280),
    method: req.method(),
    failure: req.failure()?.errorText || "unknown",
  });
});
page.on("response", (res) => {
  const url = res.url();
  if (/\/api\/v1\/|railway\.app|127\.0\.0\.1:8000|localhost:8000/.test(url)) {
    apiResponses.push({ url: url.slice(0, 280), status: res.status() });
  }
});

// 1) Login page
await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 60_000 });
await page.waitForTimeout(1500);
const loginOk = await page.locator("h1", { hasText: "Welcome back" }).count();

// 2) Direct API health from browser context (CORS check)
const health = await page.evaluate(async (apiBase) => {
  try {
    const res = await fetch(`${apiBase.replace(/\/$/, "")}/../health`.replace("/api/v1/../health", "/health"), {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    return { ok: res.ok, status: res.status, url: res.url };
  } catch (e) {
    return { ok: false, status: 0, error: String(e) };
  }
}, API);

// Better: hit /api/v1 docs or a known unauthenticated endpoint
const openApiProbe = await page.evaluate(async (apiBase) => {
  const targets = [
    `${apiBase}/auth/me`,
    `${apiBase.replace(/\/api\/v1$/, "")}/health`,
    `${apiBase.replace(/\/api\/v1$/, "")}/health/live`,
  ];
  const out = [];
  for (const url of targets) {
    try {
      const res = await fetch(url, { headers: { Accept: "application/json" } });
      out.push({ url, status: res.status, ok: res.ok });
    } catch (e) {
      out.push({ url, status: 0, error: String(e.message || e) });
    }
  }
  return out;
}, API);

// 3) Auth attempt without credentials (should not spam network); with invalid login
await page.fill("#email", "release-gate-invalid@example.com");
await page.fill("#password", "invalid-password-for-gate");
await page.click('button[type="submit"]');
await page.waitForTimeout(3000);

const afterLoginAttempt = {
  url: page.url(),
  toastOrError: await page.locator("[data-sonner-toast], [role=status], [role=alert]").count(),
};

// 4) Protected route redirect
await page.goto(`${BASE}/terminal`, { waitUntil: "networkidle", timeout: 60_000 });
await page.waitForTimeout(1000);
const terminalRedirect = page.url();

const spam = consoleLogs.filter((l) =>
  /qf_monitored_error|Failed to fetch|CORS|Access-Control/i.test(l.text),
);
const errors = consoleLogs.filter((l) => l.type === "error");
const statusBad = apiResponses.filter((r) => r.status >= 500);
const status404 = apiResponses.filter((r) => r.status === 404);

console.log(
  JSON.stringify(
    {
      loginPageLoaded: loginOk > 0,
      health,
      openApiProbe,
      afterLoginAttempt,
      terminalRedirect,
      apiResponses: apiResponses.slice(0, 30),
      failedRequests,
      pageErrors,
      consoleErrors: errors.slice(0, 15),
      spam,
      corsLike,
      status500: statusBad,
      status404,
    },
    null,
    2,
  ),
);

await browser.close();

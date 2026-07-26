import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const errors = [];

page.on("console", (msg) => {
  const t = msg.text();
  if (/hydrat|mismatch|did not match/i.test(t) || msg.type() === "error") {
    errors.push({ type: msg.type(), text: t.slice(0, 800) });
  }
});
page.on("pageerror", (err) => {
  errors.push({ type: "pageerror", text: String(err).slice(0, 800) });
});

await page.goto("http://localhost:3000/login", {
  waitUntil: "networkidle",
  timeout: 60_000,
});
await page.waitForTimeout(2500);

const hasCursorRefs = await page.locator("[data-cursor-ref]").count();
const issueButtons = await page.getByRole("button", { name: /issue/i }).count();
const title = await page.locator("h1").textContent();
const hydrationErrors = errors.filter((e) =>
  /hydrat|mismatch|did not match/i.test(e.text),
);

console.log(
  JSON.stringify(
    {
      title,
      hasCursorRefs,
      issueButtons,
      hydrationErrorCount: hydrationErrors.length,
      hydrationErrors,
      otherErrors: errors.filter((e) => !/hydrat|mismatch|did not match/i.test(e.text)).slice(0, 5),
    },
    null,
    2,
  ),
);

await browser.close();

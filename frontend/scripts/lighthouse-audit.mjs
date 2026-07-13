#!/usr/bin/env node
/**
 * Lighthouse audit against a running Next.js server (default http://127.0.0.1:3000).
 */
import fs from "node:fs";
import lighthouse from "lighthouse";
import * as chromeLauncher from "chrome-launcher";

async function main() {
  const url = process.env.LIGHTHOUSE_URL || "http://127.0.0.1:3000/";
  const chrome = await chromeLauncher.launch({
    chromeFlags: ["--headless", "--no-sandbox", "--disable-gpu"],
  });
  try {
    const result = await lighthouse(url, {
      port: chrome.port,
      output: "json",
      onlyCategories: ["performance", "accessibility", "best-practices", "seo"],
      preset: "desktop",
    });
    if (!result) throw new Error("Lighthouse returned no result");
    const cats = result.lhr.categories;
    const scores = {
      performance: Math.round((cats.performance?.score || 0) * 100),
      accessibility: Math.round((cats.accessibility?.score || 0) * 100),
      bestPractices: Math.round((cats["best-practices"]?.score || 0) * 100),
      seo: Math.round((cats.seo?.score || 0) * 100),
      url,
      fetchTime: result.lhr.fetchTime,
    };
    fs.writeFileSync("/tmp/qf_lighthouse.json", JSON.stringify(scores, null, 2));
    console.log(JSON.stringify(scores, null, 2));
  } finally {
    await chrome.kill();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

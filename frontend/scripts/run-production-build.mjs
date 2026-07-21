#!/usr/bin/env node
/**
 * Production build wrapper — ensures NEXT_PUBLIC_API_BASE_URL is set.
 * Prefer process env / CI; otherwise load the public URL from .env.example.
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "..");

function loadExampleApiBase() {
  const examplePath = path.join(frontendRoot, ".env.example");
  if (!fs.existsSync(examplePath)) return null;
  const text = fs.readFileSync(examplePath, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const m = trimmed.match(/^NEXT_PUBLIC_API_BASE_URL\s*=\s*(.+)$/);
    if (m) return m[1].trim().replace(/^["']|["']$/g, "");
  }
  return null;
}

const env = { ...process.env };
if (!env.NEXT_PUBLIC_API_BASE_URL?.trim()) {
  const fromExample = loadExampleApiBase();
  if (!fromExample) {
    console.error(
      "NEXT_PUBLIC_API_BASE_URL is required. Set it in the environment or frontend/.env.example.",
    );
    process.exit(1);
  }
  env.NEXT_PUBLIC_API_BASE_URL = fromExample;
  console.log(
    `NEXT_PUBLIC_API_BASE_URL unset — using value from .env.example for build: ${fromExample}`,
  );
}

const result = spawnSync("npx", ["next", "build"], {
  cwd: frontendRoot,
  env,
  stdio: "inherit",
  shell: true,
});

process.exit(result.status ?? 1);

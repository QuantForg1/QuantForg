/**
 * API base URL helpers — no framework imports (unit-testable from Node).
 */

export const PRODUCTION_API_ORIGIN =
  "https://quantforg-production.up.railway.app";
export const PRODUCTION_API_BASE_URL = `${PRODUCTION_API_ORIGIN}/api/v1`;

export function normalizeApiBaseUrl(raw: string): string {
  const trimmed = raw.replace(/\/$/, "");
  if (!trimmed) return "";
  if (trimmed.endsWith("/api/v1")) return trimmed;
  return `${trimmed}/api/v1`;
}

/** True when the value is an absolute http(s) API origin (with or without /api/v1). */
export function isValidApiBaseUrl(raw: string): boolean {
  const candidate = raw.trim();
  if (!candidate) return false;
  try {
    const parsed = new URL(candidate);
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return false;
    return Boolean(parsed.hostname);
  } catch {
    return false;
  }
}

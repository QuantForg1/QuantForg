/**
 * Environment resolution for QuantForg frontend.
 *
 * API traffic always targets the configured backend (Railway in production).
 * App/canonical URLs resolve for localhost, Vercel previews, and custom domains
 * without baking a single hard-coded host into client redirects.
 */

function normalizeApiBaseUrl(raw: string): string {
  const trimmed = raw.replace(/\/$/, "");
  if (trimmed.endsWith("/api/v1")) return trimmed;
  return `${trimmed}/api/v1`;
}

function resolveApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configured) return normalizeApiBaseUrl(configured);

  // Local/dev fallback only — never silently bind production builds to a hardcoded host.
  if (process.env.NODE_ENV !== "production") {
    return normalizeApiBaseUrl("http://127.0.0.1:8000/api/v1");
  }

  throw new Error(
    "NEXT_PUBLIC_API_BASE_URL is required for production builds. Set it in the environment.",
  );
}

function stripTrailingSlash(url: string): string {
  return url.replace(/\/$/, "");
}

/**
 * Canonical site URL for metadata / SSR.
 * Prefer explicit NEXT_PUBLIC_APP_URL, then Vercel URL, then production apex/www canonical.
 */
function resolveAppUrl(): string {
  const configured = process.env.NEXT_PUBLIC_APP_URL?.trim();
  if (configured) return stripTrailingSlash(configured);

  const vercelHost = (
    process.env.NEXT_PUBLIC_VERCEL_URL ||
    process.env.VERCEL_URL ||
    ""
  )
    .trim()
    .replace(/^https?:\/\//, "");
  if (vercelHost) return `https://${stripTrailingSlash(vercelHost)}`;

  if (process.env.NODE_ENV !== "production") {
    return "http://localhost:3000";
  }

  // Production builds without an explicit APP_URL: prefer www (apex redirects there).
  return "https://www.quantforg.com";
}

export const env = {
  apiBaseUrl: resolveApiBaseUrl(),
  appUrl: resolveAppUrl(),
  // Production never serves mock AI. Dev may opt in via NEXT_PUBLIC_MOCK_AI=true.
  useMockAi:
    process.env.NODE_ENV !== "production" &&
    process.env.NEXT_PUBLIC_MOCK_AI === "true",
  buildVersion:
    process.env.NEXT_PUBLIC_BUILD_VERSION?.trim() ||
    process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA?.slice(0, 7) ||
    "1.0.0",
  appEnv: process.env.NEXT_PUBLIC_APP_ENV?.trim() || process.env.NODE_ENV || "development",
};

/**
 * Browser origin for auth redirects (password reset, OAuth).
 * Uses the live page origin so custom domains and previews stay correct
 * even when NEXT_PUBLIC_APP_URL still points at a legacy host.
 */
export function getClientAppOrigin(): string {
  if (typeof window !== "undefined" && window.location?.origin) {
    return stripTrailingSlash(window.location.origin);
  }
  return env.appUrl;
}

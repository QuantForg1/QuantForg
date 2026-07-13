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

export const env = {
  apiBaseUrl: resolveApiBaseUrl(),
  appUrl:
    process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "") ||
    "http://localhost:3000",
  useMockAi: process.env.NEXT_PUBLIC_MOCK_AI === "true",
  buildVersion:
    process.env.NEXT_PUBLIC_BUILD_VERSION?.trim() ||
    process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA?.slice(0, 7) ||
    "1.0.0",
  appEnv: process.env.NEXT_PUBLIC_APP_ENV?.trim() || process.env.NODE_ENV || "development",
};

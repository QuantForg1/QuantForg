function normalizeApiBaseUrl(raw: string): string {
  const trimmed = raw.replace(/\/$/, "");
  if (trimmed.endsWith("/api/v1")) return trimmed;
  return `${trimmed}/api/v1`;
}

const configuredApi =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
  "https://quantforg-production.up.railway.app/api/v1";

export const env = {
  apiBaseUrl: normalizeApiBaseUrl(configuredApi),
  appUrl:
    process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "") ||
    "http://localhost:3000",
  useMockAi: process.env.NEXT_PUBLIC_MOCK_AI === "true",
};

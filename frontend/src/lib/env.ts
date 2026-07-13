export const env = {
  apiBaseUrl:
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
    "https://quantforg-production.up.railway.app/api/v1",
  appUrl:
    process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "") ||
    "http://localhost:3000",
  useMockAi: process.env.NEXT_PUBLIC_MOCK_AI === "true",
};

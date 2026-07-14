import type { QueryClient } from "@tanstack/react-query";

/** Invalidate desk datasets after an institutional pipeline run — no page refresh. */
export const POST_TRADE_QUERY_KEYS = [
  "positions",
  "portfolio",
  "orders",
  "history",
  "mt5-account",
  "execution-journal",
  "execution-analytics",
  "execution-intelligence-dashboard",
  "risk",
] as const;

export async function invalidatePostTrade(qc: QueryClient): Promise<void> {
  await Promise.all(
    POST_TRADE_QUERY_KEYS.map((key) => qc.invalidateQueries({ queryKey: [key] })),
  );
}

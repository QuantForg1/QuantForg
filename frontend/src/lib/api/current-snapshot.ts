/**
 * One current trading snapshot — shared React Query keys.
 * Widgets must reuse these keys instead of minting per-surface aliases.
 */

import { TRADING_SYMBOL } from "../trading/gold-only";

export const SNAPSHOT_QUERY_KEYS = {
  health: ["weltrade-health"] as const,
  mt5Status: ["mt5-status"] as const,
  mt5Account: ["mt5-account"] as const,
  portfolio: ["portfolio"] as const,
  positions: ["positions"] as const,
  orders: ["orders"] as const,
  history: ["history"] as const,
  tick: (symbol: string = TRADING_SYMBOL) => ["mt5-tick", symbol] as const,
  autoTrading: ["ite-ops-auto-trading"] as const,
} as const;

export type ControlPlaneSnapshot = {
  cycle_id?: string;
  snapshot_id?: string;
  symbol: string;
  timestamp: string;
  quote: { bid?: string; ask?: string };
  positions: unknown[];
  account: Record<string, unknown>;
  risk?: Record<string, unknown>;
  safety?: Record<string, unknown>;
};

export function snapshotReuseKey(cycleId: string, snapshotId: string): string {
  return `${cycleId}:${snapshotId}:${TRADING_SYMBOL}`;
}

/** Telemetry query keys — must not share the critical snapshot. */
export const TELEMETRY_QUERY_KEYS = {
  observabilityHealth: ["institutional-observability"] as const,
  observabilityResources: ["institutional-observability-resources"] as const,
  executionJournal: ["execution-journal"] as const,
  executionAudits: ["execution-audits"] as const,
  executionAnalytics: ["execution-analytics"] as const,
  iteAudit: ["ite-ops-audit"] as const,
} as const;

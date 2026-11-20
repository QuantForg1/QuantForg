import { apiFetch } from "@/lib/api/client";
import { figureLabel, statusLabel, type TrustFigure } from "@/lib/trust/performance-label";

export { figureLabel, statusLabel };
export type { TrustFigure };

export type TrustTrade = {
  position_id?: string | number | null;
  symbol?: string;
  direction?: TrustFigure;
  net_pnl?: TrustFigure;
  entry_time?: TrustFigure;
  exit_time?: TrustFigure;
};

export type TrustReport = {
  schema_version?: string;
  history_available?: boolean;
  account_scope?: string;
  account_id_masked?: string | null;
  read_at?: string | null;
  source?: string;
  live_performance?: boolean;
  known_limitations?: string[];
  performance?: Record<string, TrustFigure>;
  trades?: TrustTrade[];
  strategy_performance?: Array<Record<string, TrustFigure | string | null>>;
};

export const TRUST_METRICS: ReadonlyArray<{ key: string; label: string }> = [
  { key: "total_trades", label: "Closed trades" },
  { key: "winning_trades", label: "Winning trades" },
  { key: "losing_trades", label: "Losing trades" },
  { key: "win_rate", label: "Win rate" },
  { key: "profit_factor", label: "Profit factor" },
  { key: "net_realized_pnl", label: "Net realized P/L" },
  { key: "maximum_drawdown", label: "Maximum drawdown" },
  { key: "average_holding_time_seconds", label: "Average holding time" },
  { key: "trading_costs", label: "Trading costs" },
];

export function loadTrustPerformance(): Promise<TrustReport> {
  return apiFetch<TrustReport>("/trust/performance");
}

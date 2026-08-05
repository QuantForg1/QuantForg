"use client";

import { useMemo } from "react";
import { Trophy } from "lucide-react";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { useLiveTrades } from "@/hooks/use-live-trades";
import { computeTradeRr, formatDuration } from "@/lib/orders/history";
import { formatNumber } from "@/lib/utils";

const FAMILIES = [
  "SMC",
  "Trend",
  "Momentum",
  "Breakout",
  "Mean Reversion",
] as const;

function familyOf(strategy: string, comment: string): (typeof FAMILIES)[number] | "Other" {
  const blob = `${strategy} ${comment}`.toLowerCase();
  if (/smc|order.?block|liquidity|fvg|bos|choch/.test(blob)) return "SMC";
  if (/trend|ema|ma.?cross|structure/.test(blob)) return "Trend";
  if (/momentum|rsi|macd|impulse/.test(blob)) return "Momentum";
  if (/breakout|range.?break|donchian/.test(blob)) return "Breakout";
  if (/mean.?rev|reversion|fade|vwap/.test(blob)) return "Mean Reversion";
  return "Other";
}

/** Strategy leaderboard from LIVE closed trades only. */
export function StrategyLeaderboardWorkspace() {
  const { trades, loading } = useLiveTrades("month");
  const closed = useMemo(
    () => trades.filter((t) => t.status === "closed"),
    [trades],
  );

  const rows = useMemo(() => {
    const map = new Map<
      string,
      {
        trades: number;
        wins: number;
        pnl: number;
        rrSum: number;
        rrN: number;
        holdSum: number;
        holdN: number;
        peak: number;
        equity: number;
        maxDd: number;
      }
    >();
    for (const name of FAMILIES) {
      map.set(name, {
        trades: 0,
        wins: 0,
        pnl: 0,
        rrSum: 0,
        rrN: 0,
        holdSum: 0,
        holdN: 0,
        peak: 0,
        equity: 0,
        maxDd: 0,
      });
    }
    const chronological = [...closed].sort(
      (a, b) => a.time.getTime() - b.time.getTime(),
    );
    for (const t of chronological) {
      const fam = familyOf(t.strategy, t.comment);
      if (fam === "Other") continue;
      const row = map.get(fam)!;
      row.trades += 1;
      if (t.netPl > 0) row.wins += 1;
      row.pnl += t.netPl;
      const rr = computeTradeRr(t);
      if (rr != null) {
        row.rrSum += rr;
        row.rrN += 1;
      }
      if (t.durationMs != null) {
        row.holdSum += t.durationMs;
        row.holdN += 1;
      }
      row.equity += t.netPl;
      row.peak = Math.max(row.peak, row.equity);
      row.maxDd = Math.max(row.maxDd, row.peak - row.equity);
    }
    return FAMILIES.map((name) => {
      const r = map.get(name)!;
      const grossWin = chronological
        .filter((t) => familyOf(t.strategy, t.comment) === name && t.netPl > 0)
        .reduce((s, t) => s + t.netPl, 0);
      const grossLoss = Math.abs(
        chronological
          .filter((t) => familyOf(t.strategy, t.comment) === name && t.netPl < 0)
          .reduce((s, t) => s + t.netPl, 0),
      );
      return {
        name,
        trades: r.trades,
        winRate: r.trades ? r.wins / r.trades : null,
        profitFactor: grossLoss > 0 ? grossWin / grossLoss : null,
        avgRr: r.rrN ? r.rrSum / r.rrN : null,
        avgHold: r.holdN ? r.holdSum / r.holdN : null,
        pnl: r.pnl,
        drawdown: r.maxDd,
      };
    }).sort((a, b) => b.pnl - a.pnl);
  }, [closed]);

  if (loading && !closed.length) return <DeskSkeleton rows={6} />;
  if (!closed.length) {
    return (
      <DeskEmpty
        icon={Trophy}
        title="No LIVE strategy sample"
        description="Leaderboard ranks SMC / Trend / Momentum / Breakout / Mean Reversion from closed LIVE trades."
      />
    );
  }

  return (
    <div className="space-y-3">
      <Badge tone="success" className="h-5 w-fit">
        LIVE only
      </Badge>
      <div className="overflow-x-auto border border-[var(--border)]">
        <table className="min-w-full text-left text-[12px]">
          <thead className="bg-[var(--surface)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
            <tr>
              <th className="px-3 py-2">Rank</th>
              <th className="px-3 py-2">Strategy</th>
              <th className="px-3 py-2">Win Rate</th>
              <th className="px-3 py-2">PF</th>
              <th className="px-3 py-2">Avg RR</th>
              <th className="px-3 py-2">Avg Hold</th>
              <th className="px-3 py-2">Trades</th>
              <th className="px-3 py-2">PnL</th>
              <th className="px-3 py-2">Drawdown</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.name} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 tabular">{i + 1}</td>
                <td className="px-3 py-2 font-medium">{r.name}</td>
                <td className="px-3 py-2 tabular">
                  {r.winRate != null ? `${(r.winRate * 100).toFixed(1)}%` : "—"}
                </td>
                <td className="px-3 py-2 tabular">
                  {r.profitFactor != null ? formatNumber(r.profitFactor, 2) : "—"}
                </td>
                <td className="px-3 py-2 tabular">
                  {r.avgRr != null ? formatNumber(r.avgRr, 2) : "—"}
                </td>
                <td className="px-3 py-2 tabular">{formatDuration(r.avgHold)}</td>
                <td className="px-3 py-2 tabular">{r.trades}</td>
                <td
                  className={`px-3 py-2 tabular ${r.pnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}`}
                >
                  {formatNumber(r.pnl, 2)}
                </td>
                <td className="px-3 py-2 tabular">{formatNumber(r.drawdown, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

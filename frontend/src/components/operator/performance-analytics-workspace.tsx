"use client";

import { useMemo, useState } from "react";
import { BarChart3 } from "lucide-react";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { Button } from "@/components/ui/button";
import { useLiveTrades } from "@/hooks/use-live-trades";
import {
  computeTradeRr,
  formatDuration,
  inferTradeSession,
  type HistoryRange,
} from "@/lib/orders/history";
import { formatNumber } from "@/lib/utils";

type Slice = "symbol" | "session" | "strategy" | "day" | "week" | "month";

/** Multi-dimension performance analytics from LIVE trades. */
export function PerformanceAnalyticsWorkspace() {
  const [range, setRange] = useState<HistoryRange>("month");
  const [slice, setSlice] = useState<Slice>("symbol");
  const { trades, analytics, loading } = useLiveTrades(range);
  const closed = useMemo(
    () => trades.filter((t) => t.status === "closed"),
    [trades],
  );

  const table = useMemo(() => {
    const groups = new Map<string, typeof closed>();
    for (const t of closed) {
      let key = t.symbol;
      if (slice === "session") key = inferTradeSession(t.time);
      else if (slice === "strategy") key = t.strategy || "Unspecified";
      else if (slice === "day") key = t.time.toISOString().slice(0, 10);
      else if (slice === "week") {
        const d = new Date(t.time);
        const onejan = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
        const week = Math.ceil(
          ((d.getTime() - onejan.getTime()) / 86400000 + onejan.getUTCDay() + 1) /
            7,
        );
        key = `${d.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
      } else if (slice === "month") key = t.time.toISOString().slice(0, 7);
      const list = groups.get(key) ?? [];
      list.push(t);
      groups.set(key, list);
    }
    return [...groups.entries()]
      .map(([label, list]) => {
        const wins = list.filter((t) => t.netPl > 0);
        const losses = list.filter((t) => t.netPl < 0);
        const grossWin = wins.reduce((s, t) => s + t.netPl, 0);
        const grossLoss = Math.abs(losses.reduce((s, t) => s + t.netPl, 0));
        const rrs = list
          .map((t) => computeTradeRr(t))
          .filter((x): x is number => x != null);
        const holds = list
          .map((t) => t.durationMs)
          .filter((x): x is number => x != null);
        return {
          label,
          trades: list.length,
          winRate: list.length ? wins.length / list.length : null,
          rr: rrs.length ? rrs.reduce((a, b) => a + b, 0) / rrs.length : null,
          hold: holds.length
            ? holds.reduce((a, b) => a + b, 0) / holds.length
            : null,
          pf: grossLoss > 0 ? grossWin / grossLoss : null,
          pnl: list.reduce((s, t) => s + t.netPl, 0),
          latency: "—",
          spread: "—",
          slippage: "—",
          execution: "LIVE",
        };
      })
      .sort((a, b) => b.pnl - a.pnl);
  }, [closed, slice]);

  if (loading && !closed.length) return <DeskSkeleton rows={8} />;
  if (!closed.length) {
    return (
      <DeskEmpty
        icon={BarChart3}
        title="No analytics sample"
        description="Per-symbol / session / strategy / day / week / month metrics require LIVE closed trades."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {(["today", "week", "month"] as HistoryRange[]).map((r) => (
          <Button
            key={r}
            size="sm"
            variant={range === r ? "default" : "outline"}
            onClick={() => setRange(r)}
          >
            {r}
          </Button>
        ))}
        {(
          ["symbol", "session", "strategy", "day", "week", "month"] as Slice[]
        ).map((s) => (
          <Button
            key={s}
            size="sm"
            variant={slice === s ? "secondary" : "ghost"}
            onClick={() => setSlice(s)}
          >
            {s}
          </Button>
        ))}
      </div>

      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Win Rate", analytics.winRate != null ? `${(analytics.winRate * 100).toFixed(1)}%` : "—"],
          ["Profit Factor", analytics.profitFactor != null ? formatNumber(analytics.profitFactor, 2) : "—"],
          ["Avg RR", analytics.averageRr != null ? formatNumber(analytics.averageRr, 2) : "—"],
          ["Drawdown", analytics.maxDrawdown != null ? formatNumber(analytics.maxDrawdown, 2) : "—"],
        ].map(([k, v]) => (
          <div key={k} className="border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
            <dt className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">{k}</dt>
            <dd className="mt-1 font-mono text-[14px] text-[var(--fg)]">{v}</dd>
          </div>
        ))}
      </dl>

      <div className="overflow-x-auto border border-[var(--border)]">
        <table className="min-w-full text-left text-[12px]">
          <thead className="bg-[var(--surface)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
            <tr>
              <th className="px-3 py-2">{slice}</th>
              <th className="px-3 py-2">Win Rate</th>
              <th className="px-3 py-2">RR</th>
              <th className="px-3 py-2">Hold</th>
              <th className="px-3 py-2">Latency</th>
              <th className="px-3 py-2">Spread</th>
              <th className="px-3 py-2">Slippage</th>
              <th className="px-3 py-2">Execution</th>
              <th className="px-3 py-2">PF</th>
              <th className="px-3 py-2">PnL</th>
            </tr>
          </thead>
          <tbody>
            {table.map((r) => (
              <tr key={r.label} className="border-t border-[var(--border)]">
                <td className="px-3 py-2 font-mono">{r.label}</td>
                <td className="px-3 py-2 tabular">
                  {r.winRate != null ? `${(r.winRate * 100).toFixed(1)}%` : "—"}
                </td>
                <td className="px-3 py-2 tabular">
                  {r.rr != null ? formatNumber(r.rr, 2) : "—"}
                </td>
                <td className="px-3 py-2 tabular">{formatDuration(r.hold)}</td>
                <td className="px-3 py-2 text-[var(--fg-muted)]">{r.latency}</td>
                <td className="px-3 py-2 text-[var(--fg-muted)]">{r.spread}</td>
                <td className="px-3 py-2 text-[var(--fg-muted)]">{r.slippage}</td>
                <td className="px-3 py-2">{r.execution}</td>
                <td className="px-3 py-2 tabular">
                  {r.pf != null ? formatNumber(r.pf, 2) : "—"}
                </td>
                <td
                  className={`px-3 py-2 tabular ${r.pnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}`}
                >
                  {formatNumber(r.pnl, 2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Latency / spread / slippage show “—” unless present on LIVE deal rows — never fabricated.
      </p>
    </div>
  );
}

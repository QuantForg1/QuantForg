"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PlatformStatusBoard } from "@/components/ops/platform-status-board";
import { PortfolioHeatmapWorkspace } from "@/components/operator/portfolio-heatmap-workspace";
import { useLiveTrades } from "@/hooks/use-live-trades";
import { asRecord, num, str } from "@/lib/desk";
import { classifyAsset } from "@/lib/operator/asset-class";
import { useTradingSession } from "@/providers/trading-session-provider";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { useMemo } from "react";

/** CEO / executive dashboard — LIVE capital & status, never fabricated. */
export function ExecutiveDashboardWorkspace() {
  const session = useTradingSession();
  const { analytics, trades } = useLiveTrades("month");
  const today = useLiveTrades("today");

  const equity = num(session.equity, NaN);
  const balance = num(session.balance, NaN);
  const floatPnl = session.positions.reduce(
    (s, p) => s + num(asRecord(p).profit, 0),
    0,
  );
  const monthPnl = trades
    .filter((t) => t.status === "closed")
    .reduce((s, t) => s + t.netPl, 0);

  const allocation = useMemo(() => {
    const m = new Map<string, number>();
    for (const p of session.positions) {
      const r = asRecord(p);
      const cls = classifyAsset(str(r.symbol));
      m.set(cls, (m.get(cls) ?? 0) + Math.abs(num(r.volume ?? r.lots, 0)));
    }
    const total = [...m.values()].reduce((a, b) => a + b, 0) || 1;
    return [...m.entries()].map(([k, v]) => ({
      label: k,
      pct: (v / total) * 100,
    }));
  }, [session.positions]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={session.connected ? "success" : "warning"} className="h-5">
          {session.connected ? "Live status" : "Degraded session"}
        </Badge>
        <Button asChild size="sm" variant="outline">
          <Link href="/mission-control">System status</Link>
        </Button>
        <Button asChild size="sm" variant="ghost">
          <Link href="/daily-reports">Reports</Link>
        </Button>
      </div>

      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          [
            "Today's Revenue / PnL",
            Number.isFinite(today.analytics.todayPl)
              ? formatNumber(today.analytics.todayPl, 2)
              : "—",
          ],
          [
            "Month PnL",
            formatNumber(monthPnl, 2),
          ],
          [
            "Capital (Equity)",
            Number.isFinite(equity) ? formatCurrency(equity) : "—",
          ],
          [
            "Balance",
            Number.isFinite(balance) ? formatCurrency(balance) : "—",
          ],
          [
            "Win Rate",
            analytics.winRate != null
              ? `${(analytics.winRate * 100).toFixed(1)}%`
              : "—",
          ],
          [
            "Profit Factor",
            analytics.profitFactor != null
              ? formatNumber(analytics.profitFactor, 2)
              : "—",
          ],
          [
            "Drawdown",
            analytics.maxDrawdown != null
              ? formatNumber(analytics.maxDrawdown, 2)
              : "—",
          ],
          ["Float PnL", formatNumber(floatPnl, 2)],
        ].map(([k, v]) => (
          <div
            key={k}
            className="border border-[var(--border)] bg-[var(--surface)] px-3 py-3"
          >
            <dt className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              {k}
            </dt>
            <dd className="mt-1 font-mono text-[18px] text-[var(--fg)]">{v}</dd>
          </div>
        ))}
      </dl>

      <section className="space-y-2">
        <h2 className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Portfolio allocation
        </h2>
        {allocation.length ? (
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {allocation.map((a) => (
              <li
                key={a.label}
                className="flex items-center justify-between border border-[var(--border)] px-3 py-2 text-[12px]"
              >
                <span className="uppercase text-[var(--fg-muted)]">{a.label}</span>
                <span className="font-mono tabular text-[var(--fg)]">
                  {a.pct.toFixed(1)}%
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[12px] text-[var(--fg-muted)]">Flat book — no open allocation.</p>
        )}
      </section>

      <PortfolioHeatmapWorkspace />
      <PlatformStatusBoard />
    </div>
  );
}

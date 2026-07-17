"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { LazyBarChart, LazyEquityChart } from "@/components/charts/lazy";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DeskTable } from "@/components/desk/primitives";
import { DeskQueryState } from "@/components/desk/query-state";
import { PageMotion } from "@/components/desk/motion";
import { paperApi, portfolioApi } from "@/lib/api/endpoints";
import {
  asList,
  asRecord,
  mapEquityCurve,
  metric,
  num,
  str,
  toneFromNumber,
} from "@/lib/desk";
import { formatCurrency, formatNumber, formatPct } from "@/lib/utils";

function fmtMoney(v: number) {
  return Number.isFinite(v) ? formatCurrency(v) : "—";
}

function fmtPctSafe(v: number) {
  return Number.isFinite(v) ? formatPct(v) : "—";
}

export default function PerformancePage() {
  const paper = useQuery({
    queryKey: ["paper-performance"],
    queryFn: paperApi.performance,
    retry: false,
  });
  const history = useQuery({
    queryKey: ["history"],
    queryFn: portfolioApi.history,
    retry: false,
  });

  const perf = asRecord(paper.data?.performance);
  const portfolio = asRecord(paper.data?.portfolio);
  const realized = metric(perf, "realized_pnl");
  const floating = metric(perf, "floating_pnl");
  const netProfit =
    (Number.isFinite(realized) ? realized : 0) + (Number.isFinite(floating) ? floating : 0);
  const winRate = metric(perf, "win_rate");
  const profitFactor = metric(perf, "profit_factor");
  const drawdown = metric(perf, "max_drawdown_pct");
  const initial = metric(portfolio, "initial_balance");
  const equity = metric(perf, "equity", "balance") || metric(portfolio, "equity");
  const roi =
    Number.isFinite(initial) && initial !== 0 && Number.isFinite(equity)
      ? ((equity - initial) / initial) * 100
      : NaN;

  const deals = asList(history.data?.deals).map(asRecord);
  const monthlyMap = new Map<string, number>();
  for (const d of deals) {
    const t = str(d.time, "");
    const key = t.slice(0, 7) || "—";
    monthlyMap.set(key, (monthlyMap.get(key) || 0) + num(d.profit, 0));
  }
  const monthly = [...monthlyMap.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([label, value]) => ({ label, value }));

  const curve = mapEquityCurve(
    monthly.map((m, i) => ({
      t: m.label,
      equity: (initial || 0) + monthly.slice(0, i + 1).reduce((s, x) => s + x.value, 0),
    })),
  );

  const heatDays = Array.from({ length: 35 }, (_, i) => {
    const dayDeals = deals.filter((d) => {
      const day = str(d.time, "").slice(0, 10);
      return day && i % 7 === new Date(day + "T00:00:00").getDay();
    });
    const pnl = dayDeals.reduce((s, d) => s + num(d.profit, 0), 0);
    return { i, pnl };
  });

  const loading = paper.isLoading;
  const errored = paper.isError && history.isError;

  return (
    <div>
      <PageHeader
        title="Performance"
        description="Net profit, risk-adjusted returns, and equity trajectory across paper and live history."
      />

      <DeskQueryState
        isLoading={loading}
        isError={errored}
        errorMessage="Unable to load performance."
        onRetry={() => paper.refetch()}
        skeleton="page"
      >
        <PageMotion>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
            <StatCard
              label="Equity"
              value={fmtMoney(equity)}
              tone={toneFromNumber(roi)}
            />
            <StatCard label="Return %" value={fmtPctSafe(roi)} tone={toneFromNumber(roi)} />
            <StatCard
              label="Net Profit"
              value={fmtMoney(Number.isFinite(realized) ? realized + (Number.isFinite(floating) ? floating : 0) : netProfit)}
              tone={toneFromNumber(realized)}
            />
            <StatCard
              label="Win Rate"
              value={Number.isFinite(winRate) ? `${formatNumber(winRate * (winRate <= 1 ? 100 : 1), 1)}%` : "—"}
            />
            <StatCard
              label="Profit Factor"
              value={Number.isFinite(profitFactor) ? formatNumber(profitFactor, 2) : "—"}
            />
            <StatCard
              label="Drawdown"
              value={Number.isFinite(drawdown) ? `${formatNumber(drawdown, 2)}%` : "—"}
              tone={Number.isFinite(drawdown) && drawdown > 0 ? "down" : "neutral"}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Monthly PnL</CardTitle>
                <Badge tone="accent">Deals</Badge>
              </CardHeader>
              <CardContent>
                <LazyBarChart data={monthly} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Cumulative Equity</CardTitle>
              </CardHeader>
              <CardContent>
                <LazyEquityChart data={curve} emptyLabel="No equity series yet" />
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
            <Card>
              <CardHeader>
                <CardTitle>Calendar Heatmap</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-7 gap-1.5">
                  {heatDays.map((d) => {
                    const intensity = Math.min(1, Math.abs(d.pnl) / 500);
                    const bg =
                      d.pnl > 0
                        ? `rgba(52, 211, 153, ${0.15 + intensity * 0.7})`
                        : d.pnl < 0
                          ? `rgba(248, 113, 113, ${0.15 + intensity * 0.7})`
                          : "var(--surface-2)";
                    return (
                      <div
                        key={d.i}
                        className="aspect-square rounded-md border border-[var(--border)]"
                        style={{ background: bg }}
                        title={`PnL ${d.pnl.toFixed(2)}`}
                      />
                    );
                  })}
                </div>
                <p className="mt-3 text-xs text-[var(--fg-subtle)]">
                  Intensity maps to deal profitability by weekday sample.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Performance Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <DeskTable
                  columns={["Metric", "Value"]}
                  rows={[
                    ["Balance", fmtMoney(metric(perf, "balance"))],
                    ["Equity", fmtMoney(metric(perf, "equity"))],
                    ["Realized PnL", fmtMoney(realized)],
                    ["Floating PnL", fmtMoney(floating)],
                    ["Total trades", str(perf.total_trades, "—")],
                    ["Wins / Losses", `${str(perf.win_count, "—")} / ${str(perf.loss_count, "—")}`],
                    [
                      "Sharpe",
                      Number.isFinite(metric(perf, "sharpe_ratio"))
                        ? formatNumber(metric(perf, "sharpe_ratio"), 2)
                        : "—",
                    ],
                    ["Expectancy", Number.isFinite(metric(perf, "expectancy")) ? formatNumber(metric(perf, "expectancy"), 4) : "—"],
                  ].map(([k, v]) => [k, v])}
                />
              </CardContent>
            </Card>
          </div>
        </PageMotion>
      </DeskQueryState>
    </div>
  );
}

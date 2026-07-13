"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { FlaskConical } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { LazyBarChart, LazyEquityChart } from "@/components/charts/lazy";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { backtestApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, mapEquityCurve, metric, num, str } from "@/lib/desk";
import { formatCurrency, formatNumber } from "@/lib/utils";

function sampleBars(n = 80) {
  const bars = [];
  let price = 1.085;
  const start = Date.now() - n * 15 * 60 * 1000;
  for (let i = 0; i < n; i++) {
    const open = price;
    const close = price + (Math.random() - 0.48) * 0.0015;
    const high = Math.max(open, close) + Math.random() * 0.0004;
    const low = Math.min(open, close) - Math.random() * 0.0004;
    const t = new Date(start + i * 15 * 60 * 1000).toISOString();
    bars.push({
      open_time: t,
      open: open.toFixed(5),
      high: high.toFixed(5),
      low: low.toFixed(5),
      close: close.toFixed(5),
      volume: "100",
      close_time: new Date(start + (i + 1) * 15 * 60 * 1000).toISOString(),
    });
    price = close;
  }
  return bars;
}

export default function BacktestingPage() {
  const qc = useQueryClient();
  const [symbol, setSymbol] = useState("EURUSD");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const listQ = useQuery({
    queryKey: ["backtests"],
    queryFn: backtestApi.list,
    retry: false,
  });
  const detailQ = useQuery({
    queryKey: ["backtest", selectedId],
    queryFn: () => backtestApi.get(selectedId!),
    enabled: Boolean(selectedId),
    retry: false,
  });

  const run = useMutation({
    mutationFn: backtestApi.run,
    onSuccess: async (data) => {
      const id = str(asRecord(data).id);
      toast.success("Backtest completed");
      setSelectedId(id);
      await qc.invalidateQueries({ queryKey: ["backtests"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Backtest failed"),
  });

  const items = asList(listQ.data).map(asRecord);
  const report = asRecord(detailQ.data ?? items[0]);
  const metrics = asRecord(report.metrics);
  const trades = asList(report.trades).map(asRecord);
  const curve = mapEquityCurve(report.equity_curve);
  const ddSeries = asList(report.equity_curve).map((p, i) => {
    const r = asRecord(p);
    return { label: String(i + 1), value: -Math.abs(num(r.drawdown_pct, 0)) };
  });
  const monthly = (() => {
    const map = new Map<string, number>();
    for (const t of trades) {
      const key = str(t.closed_at ?? t.opened_at, "").slice(0, 7) || "n/a";
      map.set(key, (map.get(key) || 0) + num(t.pnl, 0));
    }
    return [...map.entries()].map(([label, value]) => ({ label, value }));
  })();

  return (
    <div>
      <PageHeader
        title="Backtesting"
        description="Institutional backtest reports — equity, drawdown, and trade ledger."
        actions={
          <Button
            size="sm"
            disabled={run.isPending}
            onClick={() =>
              run.mutate({
                request_id: `bt-${Date.now()}`,
                symbol,
                timeframe: "m15",
                initial_balance: "10000",
                bars: sampleBars(80),
                auto_analysis: true,
              })
            }
          >
            Run backtest
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label>Symbol</Label>
          <Input className="w-40" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
        </div>
      </div>

      {listQ.isLoading ? (
        <DeskSkeleton rows={4} />
      ) : listQ.isError ? (
        <DeskError message="Unable to load backtests." onRetry={() => listQ.refetch()} />
      ) : (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard label="Sharpe" value={fmt(metric(metrics, "sharpe_ratio"))} />
            <StatCard label="Sortino" value={fmt(metric(metrics, "sortino_ratio"))} />
            <StatCard label="CAGR" value={pct(metric(metrics, "cagr_pct"))} />
            <StatCard label="Profit Factor" value={fmt(metric(metrics, "profit_factor"))} />
            <StatCard label="Expectancy" value={fmt(metric(metrics, "expectancy"), 4)} />
          </div>

          <div className="grid gap-4 xl:grid-cols-[0.7fr_1.3fr]">
            <Card>
              <CardHeader>
                <CardTitle>Runs</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {items.length === 0 ? (
                  <DeskEmpty
                    icon={FlaskConical}
                    title="No backtests yet"
                    description="Run a backtest to generate an institutional report."
                    actionLabel="Run now"
                    onAction={() =>
                      run.mutate({
                        request_id: `bt-${Date.now()}`,
                        symbol,
                        timeframe: "m15",
                        bars: sampleBars(80),
                      })
                    }
                  />
                ) : (
                  items.map((item) => {
                    const id = str(item.id);
                    return (
                      <button
                        key={id}
                        type="button"
                        onClick={() => setSelectedId(id)}
                        className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-sm ${
                          selectedId === id || (!selectedId && id === str(report.id))
                            ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                            : "border-[var(--border)] bg-[var(--surface-2)]"
                        }`}
                      >
                        <span>
                          {str(item.symbol)} · {str(item.timeframe)}
                        </span>
                        <Badge tone={str(item.status) === "completed" ? "success" : "warning"}>
                          {str(item.status)}
                        </Badge>
                      </button>
                    );
                  })
                )}
              </CardContent>
            </Card>

            <div className="space-y-4">
              <div className="grid gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Equity</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {detailQ.isLoading && selectedId ? (
                      <DeskSkeleton rows={3} />
                    ) : (
                      <LazyEquityChart data={curve} emptyLabel="Select or run a backtest" />
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Drawdown</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <LazyBarChart data={ddSeries} />
                  </CardContent>
                </Card>
              </div>
              <Card>
                <CardHeader>
                  <CardTitle>Monthly Returns</CardTitle>
                </CardHeader>
                <CardContent>
                  <LazyBarChart data={monthly} />
                </CardContent>
              </Card>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Metrics</CardTitle>
              </CardHeader>
              <CardContent>
                <DeskTable
                  columns={["Metric", "Value"]}
                  rows={[
                    ["Total return %", pct(metric(metrics, "total_return_pct"))],
                    ["Max drawdown %", pct(metric(metrics, "max_drawdown_pct"))],
                    ["Win rate", pct(metric(metrics, "win_rate") * (metric(metrics, "win_rate") <= 1 ? 100 : 1))],
                    ["Trades", str(metrics.trade_count ?? report.trade_count, "—")],
                    ["Wins / Losses", `${str(metrics.win_count, "—")} / ${str(metrics.loss_count, "—")}`],
                  ].map(([a, b]) => [a, b])}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Trades</CardTitle>
              </CardHeader>
              <CardContent>
                {trades.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">No trades in this run.</p>
                ) : (
                  <DeskTable
                    columns={["Side", "Entry", "Exit", "PnL", "Reason"]}
                    rows={trades.slice(0, 25).map((t) => [
                      str(t.side),
                      str(t.entry_price),
                      str(t.exit_price),
                      <span
                        key="p"
                        className={num(t.pnl, 0) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}
                      >
                        {formatCurrency(num(t.pnl, 0))}
                      </span>,
                      str(t.exit_reason),
                    ])}
                  />
                )}
              </CardContent>
            </Card>
          </div>
        </motion.div>
      )}
    </div>
  );
}

function fmt(v: number, digits = 2) {
  return Number.isFinite(v) ? formatNumber(v, digits) : "—";
}
function pct(v: number) {
  return Number.isFinite(v) ? `${formatNumber(v, 2)}%` : "—";
}

"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { BarChart3 } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { LazyBarChart } from "@/components/charts/lazy";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskTable } from "@/components/desk/primitives";
import { DeskQueryState } from "@/components/desk/query-state";
import { paperApi, portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, metric, num, str, toneFromNumber } from "@/lib/desk";
import { formatCurrency, formatNumber, formatPct } from "@/lib/utils";

export default function AnalyticsPage() {
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
  const paperHistory = useQuery({
    queryKey: ["paper-history"],
    queryFn: paperApi.history,
    retry: false,
  });

  const deals = asList(history.data?.deals).map(asRecord);
  const trades = asList(asRecord(paperHistory.data).trades).map(asRecord);

  const analytics = useMemo(() => {
    const all = [...deals, ...trades];
    const now = Date.now();
    const dayMs = 86400000;
    const sumIn = (ms: number) =>
      all.reduce((s, d) => {
        const t = Date.parse(str(d.time ?? d.closed_at ?? d.opened_at, ""));
        if (!Number.isFinite(t) || now - t > ms) return s;
        return s + num(d.profit ?? d.pnl, 0);
      }, 0);

    const daily = sumIn(dayMs);
    const weekly = sumIn(dayMs * 7);
    const monthly = sumIn(dayMs * 30);
    const pnls = all.map((d) => num(d.profit ?? d.pnl, 0)).filter(Number.isFinite);
    const mean = pnls.length ? pnls.reduce((a, b) => a + b, 0) / pnls.length : 0;
    const variance =
      pnls.length > 1
        ? pnls.reduce((s, p) => s + (p - mean) ** 2, 0) / (pnls.length - 1)
        : 0;
    const volatility = Math.sqrt(variance);

    const buckets = [
      { label: "< -100", value: 0 },
      { label: "-100–0", value: 0 },
      { label: "0–100", value: 0 },
      { label: "> 100", value: 0 },
    ];
    for (const p of pnls) {
      if (p < -100) buckets[0].value += 1;
      else if (p < 0) buckets[1].value += 1;
      else if (p <= 100) buckets[2].value += 1;
      else buckets[3].value += 1;
    }

    const durations = trades
      .map((t) => {
        const a = Date.parse(str(t.opened_at, ""));
        const b = Date.parse(str(t.closed_at, ""));
        if (!Number.isFinite(a) || !Number.isFinite(b) || b < a) return null;
        return (b - a) / 60000;
      })
      .filter((n): n is number => n != null);
    const durationBuckets = [
      { label: "<15m", value: durations.filter((d) => d < 15).length },
      { label: "15–60m", value: durations.filter((d) => d >= 15 && d < 60).length },
      { label: "1–4h", value: durations.filter((d) => d >= 60 && d < 240).length },
      { label: ">4h", value: durations.filter((d) => d >= 240).length },
    ];

    const bySymbol = new Map<string, number>();
    for (const d of all) {
      const sym = str(d.symbol, "—");
      bySymbol.set(sym, (bySymbol.get(sym) || 0) + num(d.profit ?? d.pnl, 0));
    }
    const ranked = [...bySymbol.entries()].sort((a, b) => b[1] - a[1]);
    const exposure = ranked.slice(0, 8).map(([label, value]) => ({ label, value: Math.abs(value) }));

    return {
      daily,
      weekly,
      monthly,
      volatility,
      buckets,
      durationBuckets,
      exposure,
      best: ranked.slice(0, 5),
      worst: ranked.slice().reverse().slice(0, 5),
    };
  }, [deals, trades]);

  const perf = asRecord(paper.data?.performance);

  return (
    <div>
      <PageHeader
        title="Analytics"
        description="Returns, volatility, distribution, and symbol exposure from live and paper fills."
      />

      <DeskQueryState
        isLoading={paper.isLoading && history.isLoading}
        isError={paper.isError && history.isError}
        errorMessage="Unable to load analytics."
        onRetry={() => paper.refetch()}
        skeleton="list"
        skeletonRows={5}
      >
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Daily Return"
              value={formatCurrency(analytics.daily)}
              tone={toneFromNumber(analytics.daily)}
            />
            <StatCard
              label="Weekly Return"
              value={formatCurrency(analytics.weekly)}
              tone={toneFromNumber(analytics.weekly)}
            />
            <StatCard
              label="Monthly Return"
              value={formatCurrency(analytics.monthly)}
              tone={toneFromNumber(analytics.monthly)}
            />
            <StatCard
              label="Volatility"
              value={Number.isFinite(analytics.volatility) ? formatNumber(analytics.volatility, 2) : "—"}
              hint={
                Number.isFinite(metric(perf, "win_rate"))
                  ? `Win rate ${formatPct(metric(perf, "win_rate") * (metric(perf, "win_rate") <= 1 ? 100 : 1))}`
                  : undefined
              }
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>PnL Distribution</CardTitle>
                <Badge tone="accent">Trades</Badge>
              </CardHeader>
              <CardContent>
                <LazyBarChart data={analytics.buckets} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Trade Duration</CardTitle>
              </CardHeader>
              <CardContent>
                <LazyBarChart data={analytics.durationBuckets} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Market Exposure</CardTitle>
              </CardHeader>
              <CardContent>
                <LazyBarChart data={analytics.exposure} />
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Best Symbols</CardTitle>
              </CardHeader>
              <CardContent>
                {analytics.best.length === 0 ? (
                  <DeskEmpty
                    icon={BarChart3}
                    title="No symbol performance yet"
                    description="Best performers appear after synced fills."
                  />
                ) : (
                  <DeskTable
                    columns={["Symbol", "PnL"]}
                    rows={analytics.best.map(([s, p]) => [
                      s,
                      <span key={s} className="text-[var(--success)]">
                        {formatCurrency(p)}
                      </span>,
                    ])}
                  />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Worst Symbols</CardTitle>
              </CardHeader>
              <CardContent>
                {analytics.worst.length === 0 ? (
                  <DeskEmpty
                    icon={BarChart3}
                    title="No symbol performance yet"
                    description="Underperformers appear after synced fills."
                  />
                ) : (
                  <DeskTable
                    columns={["Symbol", "PnL"]}
                    rows={analytics.worst.map(([s, p]) => [
                      s,
                      <span
                        key={s}
                        className={p >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}
                      >
                        {formatCurrency(p)}
                      </span>,
                    ])}
                  />
                )}
              </CardContent>
            </Card>
          </div>
        </motion.div>
      </DeskQueryState>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Layers3 } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LazyBarChart, LazyDonutChart } from "@/components/charts/lazy";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { portfolioIntelligenceApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber, formatPct } from "@/lib/utils";

function heatColor(v: number | null): string {
  if (v == null || Number.isNaN(v)) return "var(--surface-2)";
  // blue (neg) → neutral → amber (pos)
  if (v >= 0) {
    const a = Math.min(1, v);
    return `color-mix(in oklab, var(--warning) ${Math.round(a * 70)}%, var(--surface-2))`;
  }
  const a = Math.min(1, Math.abs(v));
  return `color-mix(in oklab, var(--accent) ${Math.round(a * 70)}%, var(--surface-2))`;
}

export default function RiskLabPage() {
  const [maxAlloc, setMaxAlloc] = useState("40");
  const [maxRisk, setMaxRisk] = useState("100");
  const [targetVol, setTargetVol] = useState("");

  const dashQ = useQuery({
    queryKey: ["portfolio-intelligence-dashboard"],
    queryFn: () => portfolioIntelligenceApi.dashboard(0.95),
    retry: false,
  });

  const optimize = useMutation({
    mutationFn: portfolioIntelligenceApi.optimize,
    onSuccess: () => toast.success("Optimization refreshed"),
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Optimize failed"),
  });

  const data = asRecord(dashQ.data);
  const risk = asRecord(data.risk);
  const metrics = asRecord(risk.metrics);
  const stress = asRecord(data.stress);
  const corr = asRecord(data.correlation);
  const journal = asRecord(data.journal);
  const attribution = asRecord(data.attribution);
  const optimizer = asRecord(data.optimizer);
  const scenarios = asList(stress.scenarios).map(asRecord);
  const labels = asList(corr.labels).map(String);
  const matrix = asList(corr.matrix) as unknown[][];
  const sectors = asList(risk.sector_allocation).map(asRecord);
  const currencies = asList(risk.currency_allocation).map(asRecord);
  const recommendations = asList(
    asRecord(optimize.data ?? optimizer).recommendations,
  ).map(asRecord);
  const journalMetrics = asRecord(journal.metrics);
  const rankings = asRecord(journal.rankings);

  const sectorChart = sectors.map((s) => ({
    name: str(s.sector),
    value: num(s.weight_pct, 0),
  }));

  const attrSymbol = asList(attribution.by_symbol)
    .map(asRecord)
    .slice(0, 8)
    .map((r) => ({ label: str(r.key), value: num(r.pnl, 0) }));

  const scatterData = recommendations.map((r) => ({
    symbol: str(r.symbol),
    current: num(r.current_weight_pct, 0),
    target: num(r.target_weight_pct, 0),
  }));

  const unavailable = data.portfolio_available === false;

  return (
    <div>
      <PageHeader
        title="Portfolio Intelligence"
        description="Risk laboratory over live portfolio and deal history — recommendations only, never autonomous execution."
        actions={
          <Button size="sm" variant="secondary" onClick={() => dashQ.refetch()}>
            Refresh
          </Button>
        }
      />

      {dashQ.isLoading ? (
        <DeskSkeleton rows={6} />
      ) : dashQ.isError ? (
        <DeskError
          message="Risk laboratory unavailable."
          onRetry={() => dashQ.refetch()}
        />
      ) : (
        <div className="space-y-4">
          {unavailable ? (
            <Card>
              <CardContent className="py-4 text-sm text-[var(--fg-muted)]">
                Portfolio sync unavailable: {str(data.portfolio_unavailable_reason)}.
                Connect MT5 to load live positions. Analytics never invent data.
              </CardContent>
            </Card>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Portfolio VaR 95%"
              value={
                metrics.portfolio_var_status === "unavailable"
                  ? "n/a"
                  : formatNumber(num(metrics.portfolio_var, 0), 2)
              }
              hint={str(metrics.portfolio_var_reason) || "Historical deal PnL"}
            />
            <StatCard
              label="Expected Shortfall"
              value={
                metrics.expected_shortfall_status === "unavailable"
                  ? "n/a"
                  : formatNumber(num(metrics.expected_shortfall, 0), 2)
              }
              hint="CVaR beyond VaR"
            />
            <StatCard
              label="Exposure"
              value={formatNumber(num(metrics.exposure, 0), 0)}
              hint={
                metrics.exposure_pct_equity != null
                  ? `${formatPct(num(metrics.exposure_pct_equity, 0) / 100)} of equity`
                  : "Notional"
              }
            />
            <StatCard
              label="Margin usage"
              value={
                metrics.margin_usage_pct != null
                  ? formatPct(num(metrics.margin_usage_pct, 0) / 100)
                  : "n/a"
              }
              hint={`Lev ${str(metrics.leverage_account)} · HHI ${formatNumber(num(metrics.concentration_hhi, 0), 3)}`}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Sector allocation</CardTitle>
              </CardHeader>
              <CardContent>
                {sectorChart.length === 0 ? (
                  <DeskEmpty
                    icon={Layers3}
                    title="No open exposure"
                    description="Open positions required."
                  />
                ) : (
                  <LazyDonutChart data={sectorChart} />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Currency allocation</CardTitle>
              </CardHeader>
              <CardContent>
                <DeskTable
                  columns={["Currency", "Weight", "Exposure"]}
                  rows={currencies.map((c) => [
                    str(c.currency),
                    formatPct(num(c.weight_pct, 0) / 100),
                    formatNumber(num(c.exposure, 0), 2),
                  ])}
                />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-2">
              <CardTitle>Correlation matrix</CardTitle>
              <Badge tone={corr.status === "available" ? "success" : "warning"}>
                {str(corr.status)}
              </Badge>
            </CardHeader>
            <CardContent>
              {corr.status !== "available" || labels.length === 0 ? (
                <p className="text-sm text-[var(--fg-subtle)]">
                  {str(corr.reason) || "Correlation unavailable — need overlapping deal days."}
                </p>
              ) : (
                <>
                  <p className="mb-3 text-xs text-[var(--fg-subtle)]">
                    Diversification score:{" "}
                    {corr.diversification_score == null
                      ? "n/a"
                      : formatNumber(num(corr.diversification_score, 0), 3)}
                  </p>
                  <div className="overflow-x-auto">
                    <div
                      className="grid gap-1"
                      style={{
                        gridTemplateColumns: `auto repeat(${labels.length}, minmax(3rem, 1fr))`,
                      }}
                    >
                      <div />
                      {labels.map((l) => (
                        <div
                          key={`h-${l}`}
                          className="truncate text-center text-[10px] text-[var(--fg-subtle)]"
                        >
                          {l}
                        </div>
                      ))}
                      {labels.map((row, i) => (
                        <div key={`row-${row}`} className="contents">
                          <div className="truncate pr-2 text-[10px] text-[var(--fg-subtle)]">
                            {row}
                          </div>
                          {labels.map((col, j) => {
                            const cell = matrix[i]?.[j];
                            const v =
                              typeof cell === "number"
                                ? cell
                                : cell == null
                                  ? null
                                  : Number(cell);
                            return (
                              <motion.div
                                key={`${row}-${col}`}
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="flex h-10 items-center justify-center rounded-sm text-[10px] font-medium"
                                style={{ background: heatColor(v) }}
                                title={`${row}×${col}: ${v == null ? "n/a" : v.toFixed(2)}`}
                              >
                                {v == null || Number.isNaN(v) ? "—" : v.toFixed(2)}
                              </motion.div>
                            );
                          })}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="mt-3">
                    <p className="mb-1 text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                      Clusters
                    </p>
                    <ul className="flex flex-wrap gap-2">
                      {asList(corr.clusters)
                        .map(asRecord)
                        .map((c) => (
                          <Badge key={str(c.id)} tone="neutral">
                            #{str(c.id)} · {asList(c.members).map(String).join(", ")}
                          </Badge>
                        ))}
                    </ul>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Stress scenarios</CardTitle>
            </CardHeader>
            <CardContent>
              <DeskTable
                columns={["Scenario", "Status", "Impact", "Assumption"]}
                rows={scenarios.map((s) => [
                  str(s.name),
                  str(s.status),
                  s.status === "available"
                    ? formatNumber(num(s.impact_pnl, 0), 2)
                    : str(s.reason) || "unavailable",
                  str(s.assumption || s.reason),
                ])}
              />
            </CardContent>
          </Card>

          <div className="grid gap-4 xl:grid-cols-[1fr_1.2fr]">
            <Card>
              <CardHeader>
                <CardTitle>Optimizer</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-2 sm:grid-cols-3">
                  <div className="space-y-1">
                    <Label>Max allocation %</Label>
                    <Input value={maxAlloc} onChange={(e) => setMaxAlloc(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>Max risk %</Label>
                    <Input value={maxRisk} onChange={(e) => setMaxRisk(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>Target vol (opt)</Label>
                    <Input
                      value={targetVol}
                      onChange={(e) => setTargetVol(e.target.value)}
                      placeholder="optional"
                    />
                  </div>
                </div>
                <Button
                  size="sm"
                  disabled={optimize.isPending}
                  onClick={() =>
                    optimize.mutate({
                      max_allocation_pct: Number(maxAlloc) || 40,
                      max_risk_pct: Number(maxRisk) || 100,
                      target_volatility: targetVol ? Number(targetVol) : null,
                    })
                  }
                >
                  Recommend allocations
                </Button>
                <p className="text-xs text-[var(--fg-subtle)]">
                  Never places trades. Each row includes reason, metrics, risk impact,
                  confidence, and data source.
                </p>
                <ul className="space-y-2">
                  {recommendations.map((r) => {
                    const ex = asRecord(r.explanation);
                    return (
                      <li
                        key={str(r.symbol)}
                        className="rounded-lg border border-[var(--border)] p-3 text-xs"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium text-[var(--fg)]">
                            {str(r.symbol)}
                          </span>
                          <Badge tone="accent">
                            {formatNumber(num(r.target_weight_pct, 0), 1)}%
                          </Badge>
                        </div>
                        <p className="mt-1 text-[var(--fg-muted)]">{str(ex.reason)}</p>
                        <p className="text-[var(--fg-subtle)]">
                          conf {formatNumber(num(ex.confidence, 0) * 100, 0)}% ·{" "}
                          {str(ex.data_source)}
                        </p>
                      </li>
                    );
                  })}
                </ul>
                {scatterData.length > 0 ? (
                  <div className="h-48 w-full pt-2">
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
                        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                        <XAxis
                          type="number"
                          dataKey="current"
                          name="Current %"
                          unit="%"
                          stroke="var(--fg-subtle)"
                          fontSize={10}
                        />
                        <YAxis
                          type="number"
                          dataKey="target"
                          name="Target %"
                          unit="%"
                          stroke="var(--fg-subtle)"
                          fontSize={10}
                        />
                        <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                        <Scatter data={scatterData} fill="var(--accent)" />
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Trade journal</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {journal.status !== "available" ? (
                  <p className="text-sm text-[var(--fg-subtle)]">
                    {str(journal.reason) || "No trades available"}
                  </p>
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      <StatCard
                        label="Win rate"
                        value={
                          journalMetrics.win_rate == null
                            ? "n/a"
                            : formatPct(num(journalMetrics.win_rate, 0))
                        }
                      />
                      <StatCard
                        label="Loss rate"
                        value={
                          journalMetrics.loss_rate == null
                            ? "n/a"
                            : formatPct(num(journalMetrics.loss_rate, 0))
                        }
                      />
                      <StatCard
                        label="Avg hold (h)"
                        value={
                          journalMetrics.average_hold_hours == null
                            ? "n/a"
                            : formatNumber(num(journalMetrics.average_hold_hours, 0), 2)
                        }
                      />
                      <StatCard
                        label="Avg RR"
                        value={
                          journalMetrics.average_rr == null
                            ? "n/a"
                            : formatNumber(num(journalMetrics.average_rr, 0), 2)
                        }
                        hint={str(journalMetrics.rr_note) || undefined}
                      />
                    </div>
                    <DeskTable
                      columns={["Best symbols", "PnL"]}
                      rows={asList(rankings.best_symbols)
                        .map(asRecord)
                        .map((r) => [str(r.symbol), formatNumber(num(r.net_pnl, 0), 2)])}
                    />
                    <DeskTable
                      columns={["Sessions", "PnL"]}
                      rows={asList(rankings.best_sessions)
                        .map(asRecord)
                        .map((r) => [str(r.session), formatNumber(num(r.net_pnl, 0), 2)])}
                    />
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Performance attribution</CardTitle>
            </CardHeader>
            <CardContent>
              {attribution.status !== "available" ? (
                <p className="text-sm text-[var(--fg-subtle)]">
                  {str(attribution.reason) || "Attribution unavailable"}
                </p>
              ) : (
                <div className="grid gap-4 lg:grid-cols-2">
                  <LazyBarChart data={attrSymbol} />
                  <DeskTable
                    columns={["Month", "PnL"]}
                    rows={asList(attribution.by_month)
                      .map(asRecord)
                      .slice(0, 12)
                      .map((r) => [str(r.key), formatNumber(num(r.pnl, 0), 2)])}
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

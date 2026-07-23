"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PieChart } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

const OpportunityTrendChart = dynamic(
  () =>
    import("@/components/charts/opportunity-trend-chart").then(
      (m) => m.OpportunityTrendChart,
    ),
  { ssr: false, loading: () => <Skeleton className="h-44 w-full" /> },
);

function fmt(v: unknown, d = 2): string {
  const n = num(v, NaN);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(d);
}

function fmtPct(v: unknown): string {
  const n = num(v, NaN);
  if (!Number.isFinite(n)) return "—";
  return `${n.toFixed(2)}%`;
}

function isoLabel(t: string): string {
  if (!t) return "";
  return t.length >= 8 ? t.slice(-8) : t;
}

function mapCurveSeries(
  timestamps: unknown,
  values: unknown,
): { label: string; v: number; t?: string }[] {
  const ts = asList(timestamps).map((x) => str(x));
  const vs = asList(values);
  const out: { label: string; v: number; t?: string }[] = [];
  for (let i = 0; i < Math.min(ts.length, vs.length); i++) {
    const v = num(vs[i], NaN);
    if (!Number.isFinite(v)) continue;
    const t = ts[i] ?? "";
    out.push({ label: isoLabel(t), v, ...(t ? { t } : {}) });
  }
  return out;
}

function downloadBlob(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadCsv(payload: Record<string, unknown>) {
  const sections = asRecord(payload.sections);
  const lines: string[] = ["section,metric,value"];
  for (const [sectionName, sectionRaw] of Object.entries(sections)) {
    const section = asRecord(sectionRaw);
    if (sectionName === "time") {
      for (const [kind, kindRaw] of Object.entries(section)) {
        const kindData = asRecord(kindRaw);
        for (const [bucket, statsRaw] of Object.entries(
          asRecord(kindData.buckets),
        )) {
          const stats = asRecord(statsRaw);
          lines.push(
            `time_${kind},${bucket},${str(stats.total_pnl, "0")}`,
          );
        }
      }
      continue;
    }
    if (sectionName === "health_score") {
      lines.push(`health_score,overall,${str(section.score)}`);
      for (const [comp, val] of Object.entries(asRecord(section.components))) {
        lines.push(`health_score,${comp},${str(val)}`);
      }
      continue;
    }
    for (const [metric, value] of Object.entries(section)) {
      if (typeof value === "object" && value !== null) continue;
      lines.push(`${sectionName},${metric},${str(value)}`);
    }
  }
  downloadBlob(
    `portfolio-analytics-${Date.now()}.csv`,
    lines.join("\n"),
    "text/csv",
  );
}

function HealthBanner({ health }: { health: Record<string, unknown> }) {
  const status = str(health.status, "YELLOW");
  const label = str(health.label, "Monitor");
  const score = health.score == null ? "—" : String(num(health.score));
  return (
    <div
      className={cn(
        "border px-4 py-4",
        status === "GREEN" && "border-[var(--success)]/40 bg-[var(--success)]/10",
        status === "YELLOW" && "border-[var(--warning)]/40 bg-[var(--warning)]/10",
        status === "RED" && "border-[var(--danger)]/40 bg-[var(--danger)]/10",
      )}
    >
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
        Institutional Health Score
      </p>
      <p
        className={cn(
          "mt-1 text-[28px] font-semibold tabular-nums tracking-tight",
          status === "GREEN" && "text-[var(--success)]",
          status === "YELLOW" && "text-[var(--warning)]",
          status === "RED" && "text-[var(--danger)]",
        )}
      >
        {score}
        <span className="ml-2 text-[14px] font-medium">{status}</span>
      </p>
      <p className="mt-1 text-[14px] text-[var(--fg)]">{str(health.summary, label)}</p>
    </div>
  );
}

function MetricGrid({
  rows,
}: {
  rows: { label: string; value: string; tone?: "ok" | "warn" | "bad" }[];
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {rows.map((row) => (
        <MetricCard
          key={row.label}
          label={row.label}
          value={row.value}
          tone={row.tone}
        />
      ))}
    </div>
  );
}

function TimeBucketPanel({ time }: { time: Record<string, unknown> }) {
  const kinds = ["hour", "dow", "week", "month"] as const;
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {kinds.map((kind) => {
        const block = asRecord(time[kind]);
        const best = str(block.best, "—");
        const worst = str(block.worst, "—");
        return (
          <div
            key={kind}
            className="border border-[var(--border)] bg-[var(--bg)]/30 px-3 py-3"
          >
            <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              {kind}
            </p>
            <p className="mt-2 font-mono text-[12px] text-[var(--success)]">
              Best · {best}
            </p>
            <p className="mt-1 font-mono text-[12px] text-[var(--danger)]">
              Worst · {worst}
            </p>
          </div>
        );
      })}
    </div>
  );
}

export function PortfolioAnalyticsWorkspace() {
  const [showWeeklyReport, setShowWeeklyReport] = useState(false);

  const q = useQuery({
    queryKey: ["ite-ops-portfolio-analytics", 365],
    queryFn: () => iteOpsApi.portfolioAnalytics(365),
    retry: false,
    refetchInterval: 60_000,
  });

  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Portfolio Analytics unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }

  const root = asRecord(q.data);
  const sections = asRecord(root.sections);
  const dashboard = asRecord(sections.dashboard);
  const risk = asRecord(sections.risk);
  const performance = asRecord(sections.performance);
  const behavior = asRecord(sections.behavior);
  const time = asRecord(sections.time);
  const equityAnalytics = asRecord(sections.equity_analytics);
  const health = asRecord(sections.health_score);
  const reports = asRecord(root.reports);
  const weekly = asRecord(reports.weekly);
  const tradeCount = num(root.trade_count, 0);
  const readOnly = root.analytics_only !== false;

  const equitySeries = mapCurveSeries(
    equityAnalytics.timestamps,
    equityAnalytics.equity_curve,
  );
  const drawdownSeries = mapCurveSeries(
    equityAnalytics.timestamps,
    equityAnalytics.drawdown_pct_curve,
  );
  const rollingWinSeries = mapCurveSeries(
    equityAnalytics.timestamps,
    equityAnalytics.rolling_win_rate,
  ).filter((p) => Number.isFinite(p.v));

  const weeklyAnalysis = asRecord(weekly.analysis);
  const weeklySections = asRecord(weeklyAnalysis.sections);
  const weeklyHealth = asRecord(weeklySections.health_score);
  const executiveSummary = str(
    weekly.executive_summary,
    str(weeklyHealth.summary, ""),
  );

  if (tradeCount === 0) {
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="neutral">PORTFOLIO ANALYTICS</Badge>
          <Badge tone="success">READ-ONLY</Badge>
        </div>
        <DeskEmpty
          icon={PieChart}
          title="No closed trades in window"
          description="Portfolio analytics fills from MT5 closed XAUUSD deals. Engines remain unchanged."
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">PORTFOLIO ANALYTICS</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">ENGINES UNCHANGED</Badge>
        <Badge tone="neutral">{tradeCount} closed trades · 365d</Badge>
        <Button size="sm" variant="secondary" onClick={() => downloadCsv(root)}>
          Download CSV
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setShowWeeklyReport((v) => !v)}
        >
          {showWeeklyReport ? "Hide Report" : "Open Report"}
        </Button>
        <Button asChild size="sm" variant="outline">
          <Link href="/market-regime-intelligence">Market Regime</Link>
        </Button>
        <Button asChild size="sm" variant="outline">
          <Link href="/strategy-intelligence-center">Strategy Intelligence</Link>
        </Button>
      </div>

      {readOnly ? (
        <p className="text-[11px] text-[var(--fg-subtle)]">
          Analytics only — never modifies strategy, risk, safety, OMS, execution,
          auto trading, or thresholds.
        </p>
      ) : null}

      <HealthBanner health={health} />

      {showWeeklyReport && executiveSummary ? (
        <OpsPanel title="Weekly Executive Summary">
          <p className="text-[13px] leading-relaxed text-[var(--fg)]">
            {executiveSummary}
          </p>
          <p className="mt-2 font-mono text-[11px] text-[var(--fg-subtle)]">
            Window · {str(weekly.window_start, "—")} →{" "}
            {str(weekly.window_end, "—")} · {num(weekly.trade_count, 0)} trades
          </p>
        </OpsPanel>
      ) : null}

      <OpsPanel title="Portfolio Dashboard">
        <MetricGrid
          rows={[
            { label: "Balance", value: fmt(dashboard.balance) },
            { label: "Equity", value: fmt(dashboard.equity) },
            { label: "Floating P/L", value: fmt(dashboard.floating_pnl) },
            { label: "Closed P/L", value: fmt(dashboard.closed_pnl) },
            { label: "Net P/L", value: fmt(dashboard.net_profit), tone: "ok" },
            { label: "Gross profit", value: fmt(dashboard.gross_profit) },
            { label: "Gross loss", value: fmt(dashboard.gross_loss) },
            { label: "HWM", value: fmt(dashboard.high_water_mark) },
            { label: "LWM", value: fmt(dashboard.low_water_mark) },
            { label: "Return (today)", value: fmtPct(dashboard.return_today_pct) },
            { label: "Return (week)", value: fmtPct(dashboard.return_week_pct) },
            { label: "Return (month)", value: fmtPct(dashboard.return_month_pct) },
            { label: "Return (year)", value: fmtPct(dashboard.return_year_pct) },
          ]}
        />
      </OpsPanel>

      <OpsPanel title="Risk">
        <MetricGrid
          rows={[
            {
              label: "Max drawdown",
              value: fmtPct(risk.max_drawdown_pct),
              tone: num(risk.max_drawdown_pct, 0) > 15 ? "bad" : "ok",
            },
            {
              label: "Current drawdown",
              value: fmtPct(risk.current_drawdown_pct),
            },
            { label: "Recovery factor", value: fmt(risk.recovery_factor, 4) },
            { label: "Ulcer index", value: fmt(risk.ulcer_index, 4) },
            {
              label: "Risk of ruin",
              value: fmt(risk.risk_of_ruin_estimate, 4),
            },
            {
              label: "Capital efficiency",
              value: fmtPct(risk.capital_efficiency_pct),
            },
          ]}
        />
      </OpsPanel>

      <OpsPanel title="Performance">
        <MetricGrid
          rows={[
            {
              label: "Win rate",
              value: fmtPct(performance.win_rate_pct),
              tone: "ok",
            },
            { label: "Loss rate", value: fmtPct(performance.loss_rate_pct) },
            { label: "Profit factor", value: fmt(performance.profit_factor, 4) },
            { label: "Expectancy", value: fmt(performance.expectancy, 4) },
            { label: "Payoff", value: fmt(performance.payoff_ratio, 4) },
            { label: "Avg R", value: fmt(performance.average_r_multiple, 4) },
            { label: "Sharpe", value: fmt(performance.sharpe_ratio, 4) },
            { label: "Sortino", value: fmt(performance.sortino_ratio, 4) },
            { label: "Calmar", value: fmt(performance.calmar_ratio, 4) },
            {
              label: "Wins / Losses",
              value: `${num(performance.wins, 0)} / ${num(performance.losses, 0)}`,
            },
            { label: "Avg win / loss", value: `${fmt(performance.average_win)} / ${fmt(performance.average_loss)}` },
            { label: "Net profit", value: fmt(performance.net_profit) },
          ]}
        />
      </OpsPanel>

      <OpsPanel title="Behavior">
        <MetricGrid
          rows={[
            {
              label: "Avg hold (sec)",
              value: fmt(behavior.average_holding_time_sec, 1),
            },
            {
              label: "Best hold (sec)",
              value: fmt(behavior.best_holding_time_sec, 1),
            },
            {
              label: "Worst hold (sec)",
              value: fmt(behavior.worst_holding_time_sec, 1),
            },
            {
              label: "Trades / day",
              value: fmt(behavior.trades_per_day, 3),
            },
            {
              label: "Trades / week",
              value: fmt(behavior.trades_per_week, 3),
            },
            {
              label: "Frequency",
              value: str(behavior.trading_frequency, "—"),
            },
            { label: "Active days", value: String(num(behavior.active_days, 0)) },
            {
              label: "Avg spread",
              value: fmt(behavior.average_spread_at_entry, 4),
            },
            { label: "Avg ATR", value: fmt(behavior.average_atr_at_entry, 4) },
          ]}
        />
      </OpsPanel>

      <OpsPanel title="Time — best / worst buckets">
        <TimeBucketPanel time={time} />
      </OpsPanel>

      <OpsPanel title="Equity charts">
        <div className="grid gap-3 lg:grid-cols-2">
          <OpportunityTrendChart
            title="Equity curve"
            data={equitySeries}
            color="var(--accent)"
          />
          <OpportunityTrendChart
            title="Drawdown %"
            data={drawdownSeries}
            color="var(--danger)"
          />
          <OpportunityTrendChart
            title="Rolling win rate"
            data={rollingWinSeries}
            color="var(--success)"
            yDomain={[0, 100]}
          />
        </div>
      </OpsPanel>
    </div>
  );
}

"use client";

import { useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import {
  BarChart3,
  ClipboardList,
  LineChart,
  Sigma,
  Target,
  TrendingDown,
  TrendingUp,
  Waves,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  PERFORMANCE_PERIODS,
  computePerformanceWindow,
  type PerformancePeriod,
} from "@/lib/dashboard/performance-window";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";

function Metric({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: string;
  tone?: "success" | "danger" | "neutral";
  icon: ReactNode;
}) {
  return (
    <article className="qf-overview-card flex min-w-0 items-center gap-2.5 px-3 py-3">
      <span
        className={cn(
          "qf-overview-icon qf-overview-icon-sm",
          tone === "success" &&
            "border-[color-mix(in_srgb,var(--success)_40%,var(--border))] bg-[var(--success-soft)] text-[var(--success)]",
          tone === "danger" &&
            "border-[color-mix(in_srgb,var(--danger)_40%,var(--border))] bg-[var(--danger-soft)] text-[var(--danger)]",
        )}
        aria-hidden
      >
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          {label}
        </p>
        <p
          className={cn(
            "mt-1 truncate text-base font-semibold tabular tracking-tight sm:text-lg",
            tone === "success" && "text-[var(--success)]",
            tone === "danger" && "text-[var(--danger)]",
            !tone && "text-[var(--fg)]",
          )}
        >
          {value}
        </p>
      </div>
    </article>
  );
}

function fmtMoney(v: number, currency: string): string {
  return Number.isFinite(v) ? formatCurrency(v, currency) : "—";
}

function fmtPct(v: number): string {
  return Number.isFinite(v) ? `${formatNumber(v * 100, 1)}%` : "—";
}

function fmtRatio(v: number): string {
  return Number.isFinite(v) ? formatNumber(v, 2) : "—";
}

function axisTick(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1000) return `${sign}${(abs / 1000).toFixed(abs >= 10000 ? 0 : 1)}k`;
  return `${sign}${abs.toFixed(abs >= 100 ? 0 : 2)}`;
}

function shortDate(raw: string): string {
  const match = raw.match(/(\d{2})-(\d{2})/);
  if (!match) return raw.slice(0, 8);
  const month = Number(match[1]);
  const day = Number(match[2]);
  const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  if (month < 1 || month > 12 || day < 1 || day > 31) return raw.slice(0, 8);
  return `${day} ${names[month - 1]}`;
}

function AreaChart({ values, labels }: { values: number[]; labels: string[] }) {
  if (values.length < 2) {
    return (
      <div className="flex h-40 items-center justify-center rounded-[var(--radius-os)] border border-dashed border-[var(--border)] px-3 text-center text-xs text-[var(--fg-muted)]">
        Insufficient equity history
      </div>
    );
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1e-9, max - min);
  const yOf = (v: number) => 8 + (1 - (v - min) / span) * 78;
  const pts = values.map((v, i) => ({
    x: (i / (values.length - 1)) * 100,
    y: yOf(v),
    v,
  }));
  const start = values[0];
  const baseY = yOf(start);
  const runs: { above: boolean; points: { x: number; y: number }[] }[] = [];
  let above = pts[0].v >= start;
  let current: { x: number; y: number }[] = [pts[0]];
  for (let i = 1; i < pts.length; i += 1) {
    const prev = pts[i - 1];
    const next = pts[i];
    const nextAbove = next.v >= start;
    if (nextAbove !== above && next.v !== prev.v) {
      const t = (start - prev.v) / (next.v - prev.v);
      const cross = {
        x: prev.x + (next.x - prev.x) * t,
        y: baseY,
      };
      current.push(cross);
      runs.push({ above, points: current });
      current = [cross, next];
      above = nextAbove;
    } else {
      current.push(next);
    }
  }
  runs.push({ above, points: current });
  const line = pts.map((p) => `${p.x},${p.y}`).join(" ");
  const shown = [0, Math.floor((labels.length - 1) / 2), labels.length - 1]
    .filter((index, pos, all) => labels[index] && all.indexOf(index) === pos)
    .map((index) => shortDate(labels[index]));

  return (
    <div>
      <div className="flex gap-2">
        <div className="flex h-44 w-10 shrink-0 flex-col justify-between py-1 text-right font-mono text-[10px] tabular text-[var(--fg-subtle)]">
          <span>{axisTick(max)}</span>
          <span>{axisTick((max + min) / 2)}</span>
          <span>{axisTick(min)}</span>
        </div>
        <svg
          viewBox="0 0 100 100"
          className="h-44 min-w-0 flex-1"
          preserveAspectRatio="none"
          role="img"
          aria-label="Closed-trade equity series for the selected period"
        >
          {[18, 47, 76].map((y) => (
            <line
              key={y}
              x1="0"
              x2="100"
              y1={y}
              y2={y}
              stroke="var(--border)"
              strokeWidth="0.4"
              vectorEffect="non-scaling-stroke"
            />
          ))}
          <line
            x1="0"
            x2="100"
            y1={baseY}
            y2={baseY}
            stroke="var(--fg-subtle)"
            strokeDasharray="2 2"
            strokeWidth="0.6"
            vectorEffect="non-scaling-stroke"
          />
          {runs.map((run, index) => {
            const first = run.points[0];
            const last = run.points[run.points.length - 1];
            const poly = `${first.x},${baseY} ${run.points.map((p) => `${p.x},${p.y}`).join(" ")} ${last.x},${baseY}`;
            return (
              <polygon
                key={index}
                points={poly}
                fill={run.above ? "var(--success)" : "var(--danger)"}
                opacity="0.18"
              />
            );
          })}
          <polyline
            fill="none"
            stroke={values[values.length - 1] >= start ? "var(--success)" : "var(--danger)"}
            strokeWidth="1.8"
            strokeLinejoin="round"
            strokeLinecap="round"
            points={line}
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </div>
      {shown.length > 0 ? (
        <div className="mt-1 flex justify-between pl-12 font-mono text-[10px] text-[var(--fg-subtle)]">
          {shown.map((label, index) => (
            <span key={`${label}-${index}`}>{label}</span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Outcomes({
  wins,
  losses,
  closed,
}: {
  wins: number;
  losses: number;
  closed: number;
}) {
  const flat = Math.max(0, closed - wins - losses);
  const parts = [
    { n: wins, color: "var(--success)", label: "Wins" },
    { n: losses, color: "var(--danger)", label: "Losses" },
    { n: flat, color: "var(--fg-subtle)", label: "Unchanged" },
  ].filter((part) => part.n > 0);
  const total = parts.reduce((sum, part) => sum + part.n, 0);
  if (closed <= 0 || total <= 0) {
    return (
      <div className="flex min-w-0 flex-col items-center gap-4 sm:flex-row sm:items-center">
        <svg viewBox="0 0 100 100" className="h-36 w-36 shrink-0 sm:h-40 sm:w-40" aria-hidden>
          <circle cx="50" cy="50" r={34} fill="none" stroke="var(--border)" strokeWidth="10" />
          <text x="50" y="48" textAnchor="middle" fill="var(--fg)" fontSize="16" fontWeight="600">
            {closed > 0 ? closed : "0"}
          </text>
          <text x="50" y="62" textAnchor="middle" fill="var(--fg-muted)" fontSize="7">
            Trades
          </text>
        </svg>
        <p className="text-xs text-[var(--fg-muted)]">No closed trades in this period.</p>
      </div>
    );
  }
  const radius = 34;
  const circ = 2 * Math.PI * radius;
  let offset = 0;
  return (
    <div className="flex min-w-0 flex-col items-center gap-4 sm:flex-row sm:items-center">
      <svg viewBox="0 0 100 100" className="h-36 w-36 shrink-0 sm:h-40 sm:w-40" aria-hidden>
        <circle cx="50" cy="50" r={radius} fill="none" stroke="var(--border)" strokeWidth="10" />
        {parts.map((part) => {
          const len = (part.n / total) * circ;
          const node = (
            <circle
              key={part.label}
              cx="50"
              cy="50"
              r={radius}
              fill="none"
              stroke={part.color}
              strokeWidth="10"
              strokeDasharray={`${len} ${circ - len}`}
              strokeDashoffset={-offset}
              transform="rotate(-90 50 50)"
            />
          );
          offset += len;
          return node;
        })}
        <text x="50" y="48" textAnchor="middle" fill="var(--fg)" fontSize="16" fontWeight="600">
          {closed}
        </text>
        <text x="50" y="62" textAnchor="middle" fill="var(--fg-muted)" fontSize="7">
          Trades
        </text>
      </svg>
      <ul className="min-w-0 space-y-1.5 text-xs">
        {parts.map((part) => (
          <li key={part.label} className="flex items-center gap-2 text-[var(--fg)]">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: part.color }} />
            <span>{part.label}</span>
            <span className="tabular text-[var(--fg-muted)]">
              {part.n} ({Math.round((part.n / total) * 1000) / 10}%)
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TradingPerformancePanel({
  deals,
  floatingPnl,
  equity,
  currency = "USD",
  available,
}: {
  deals: Record<string, unknown>[];
  floatingPnl: number;
  equity: number;
  currency?: string;
  available: boolean;
}) {
  const [period, setPeriod] = useState<PerformancePeriod>("30d");
  const stats = useMemo(
    () =>
      computePerformanceWindow(deals, {
        period,
        floatingPnl,
        equity,
      }),
    [deals, period, floatingPnl, equity],
  );

  const code = currency && currency !== "—" ? currency : "USD";
  const periodLabel = PERFORMANCE_PERIODS.find((item) => item.id === period)?.label ?? "Period";
  const blank = !available || stats.insufficient;
  const money = (value: number) => (blank || !Number.isFinite(value) ? "—" : fmtMoney(value, code));
  const toneOf = (value: number): "success" | "danger" | "neutral" =>
    blank || !Number.isFinite(value) ? "neutral" : value >= 0 ? "success" : "danger";

  return (
    <section
      aria-labelledby="trading-performance"
      className="qf-overview-panel space-y-4 p-3 sm:p-4"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <span className="qf-overview-icon hidden sm:flex" aria-hidden>
              <BarChart3 className="h-4 w-4" />
            </span>
          <div className="min-w-0">
          <h2
            id="trading-performance"
            className="text-base font-semibold tracking-tight text-[var(--fg)]"
          >
            Trading Performance
          </h2>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">
            Realized and floating P&amp;L from account history.
          </p>
          </div>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <div
            className="flex max-w-full flex-wrap gap-1"
            role="tablist"
            aria-label="Performance period"
          >
            {PERFORMANCE_PERIODS.map((p) => (
              <button
                key={p.id}
                type="button"
                role="tab"
                aria-selected={period === p.id}
                className={cn(
                  "h-8 rounded-lg px-2.5 text-xs font-semibold transition-[color,background-color] duration-200",
                  period === p.id
                    ? "bg-[var(--accent)] text-[var(--accent-fg)]"
                    : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]",
                )}
                onClick={() => setPeriod(p.id)}
              >
                {p.label}
              </button>
            ))}
          </div>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/journal">Journal</Link>
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Metric
              label="Realized P&L"
              icon={<LineChart className="h-3.5 w-3.5" />}
              value={money(stats.realizedPnl)}
              tone={toneOf(stats.realizedPnl)}
            />
            <Metric
              label="Floating P&L"
              icon={<Waves className="h-3.5 w-3.5" />}
              value={money(stats.floatingPnl)}
              tone={toneOf(stats.floatingPnl)}
            />
            <Metric
              label="Period total"
              icon={<Sigma className="h-3.5 w-3.5" />}
              value={money(stats.totalPnl)}
              tone={toneOf(stats.totalPnl)}
            />
            <Metric
              label="Win rate"
              icon={<Target className="h-3.5 w-3.5" />}
              value={blank ? "—" : fmtPct(stats.winRate)}
            />
            <Metric
              label="Profit factor"
              icon={<TrendingUp className="h-3.5 w-3.5" />}
              value={blank ? "—" : fmtRatio(stats.profitFactor)}
            />
            <Metric
              label="Closed trades"
              icon={<ClipboardList className="h-3.5 w-3.5" />}
              value={
                blank
                  ? "—"
                  : Number.isFinite(stats.closedTrades)
                    ? String(stats.closedTrades)
                    : "—"
              }
            />
            <Metric label="Avg win" icon={<TrendingUp className="h-3.5 w-3.5" />} value={money(stats.averageWin)} />
            <Metric
              label="Avg loss"
              icon={<TrendingDown className="h-3.5 w-3.5" />}
              value={money(stats.averageLoss)}
              tone={blank || !Number.isFinite(stats.averageLoss) ? "neutral" : "danger"}
            />
          </div>
          <div className="grid items-stretch gap-3 lg:grid-cols-[minmax(0,1.4fr)_minmax(16rem,0.8fr)]">
            <div className="flex min-h-[16rem] min-w-0 flex-col rounded-[var(--radius-os)] border border-[color-mix(in_srgb,var(--accent)_16%,var(--border))] bg-[color-mix(in_srgb,var(--bg)_35%,transparent)] p-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                P&amp;L performance ({periodLabel})
              </p>
              <AreaChart
                key={period}
                values={blank ? [] : stats.spark}
                labels={blank ? [] : stats.sparkLabels}
              />
            </div>
            <div className="flex min-h-[16rem] min-w-0 flex-col rounded-[var(--radius-os)] border border-[color-mix(in_srgb,var(--accent)_16%,var(--border))] bg-[color-mix(in_srgb,var(--bg)_35%,transparent)] p-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Trade outcomes
              </p>
              <Outcomes
                wins={blank ? 0 : stats.wins}
                losses={blank ? 0 : stats.losses}
                closed={blank ? 0 : stats.closedTrades}
              />
            </div>
          </div>
    </section>
  );
}

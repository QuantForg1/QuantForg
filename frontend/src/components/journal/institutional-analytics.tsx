"use client";

import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { LineChart, RefreshCw, Unplug } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { LazyBarChart, LazyEquityChart } from "@/components/charts/lazy";
import { StrategyIntelligencePanel } from "@/components/journal/strategy-intelligence";
import { portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, num } from "@/lib/desk";
import { computeInstitutionalMetrics } from "@/lib/orders/institutional-metrics";
import {
  pairDealsIntoTrades,
  parseLiveDeal,
  rangeToIso,
  type HistoryRange,
} from "@/lib/orders/history";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn, formatNumber } from "@/lib/utils";

const NA = "Not available";

function sessionMoney(raw: string): number | null {
  const n = num(raw.replace(/[^0-9.\-]/g, ""), NaN);
  return Number.isFinite(n) ? n : null;
}

function fmtMoney(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return NA;
  return formatNumber(v, digits);
}

function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return NA;
  return `${(v * 100).toFixed(digits)}%`;
}

function fmtRatio(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return NA;
  return formatNumber(v, digits);
}

function plTone(v: number | null | undefined): string | undefined {
  if (v == null || !Number.isFinite(v)) return undefined;
  if (v > 0) return "text-[var(--success)]";
  if (v < 0) return "text-[var(--danger)]";
  return undefined;
}

function KpiCell({
  label,
  value,
  tone,
  note,
}: {
  label: string;
  value: string;
  tone?: string;
  note?: string;
}) {
  return (
    <div className="min-w-0 rounded-md border border-[var(--border)] bg-[var(--bg-panel)] px-2.5 py-2 transition-colors duration-[var(--duration-os)]">
      <p className="truncate text-[9px] font-medium uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p
        className={cn(
          "mt-0.5 truncate font-mono text-sm tabular-nums text-[var(--fg)]",
          tone,
          value === NA && "text-[var(--fg-subtle)]",
        )}
      >
        {value}
      </p>
      {note ? (
        <p className="mt-0.5 truncate text-[9px] text-[var(--fg-subtle)]">{note}</p>
      ) : null}
    </div>
  );
}

function ChartPanel({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--bg-panel)] p-3">
      <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {title}
      </p>
      {children}
    </div>
  );
}

/**
 * Institutional Analytics Desk — live MT5 deal-derived metrics only.
 * MAE/MFE stay Not available without bar-path data. Never fabricates curves.
 */
export function InstitutionalAnalyticsDesk() {
  const session = useTradingSession();
  const [range, setRange] = useState<HistoryRange>("month");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");

  const equityNum = sessionMoney(session.equity);

  const iso = useMemo(
    () => rangeToIso(range, customFrom, customTo),
    [range, customFrom, customTo],
  );

  const historyQ = useQuery({
    queryKey: ["journal-analytics", iso.date_from, iso.date_to, session.connected],
    queryFn: () => portfolioApi.historyRange(iso),
    enabled: session.connected,
    refetchInterval: session.connected ? 30_000 : false,
  });

  const trades = useMemo(() => {
    const deals = asList(asRecord(historyQ.data).deals)
      .map((row) => parseLiveDeal(asRecord(row)))
      .filter((d): d is NonNullable<typeof d> => d != null);
    return pairDealsIntoTrades(deals);
  }, [historyQ.data]);

  const metrics = useMemo(
    () => computeInstitutionalMetrics(trades, { startingEquity: equityNum ?? 0 }),
    [trades, equityNum],
  );

  const equityChartData = useMemo(
    () =>
      metrics.equityCurve.map((p) => ({
        t: new Date(p.t).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        }),
        equity: p.equity,
      })),
    [metrics.equityCurve],
  );

  const hasAnyChart =
    metrics.equityCurve.length > 0 ||
    metrics.dailyPl.length > 0 ||
    metrics.bySession.length > 0 ||
    metrics.byHour.length > 0 ||
    metrics.byWeekday.some((b) => b.value !== 0) ||
    metrics.holdBuckets.some((b) => b.value > 0) ||
    metrics.profitDistribution.some((b) => b.value > 0) ||
    metrics.bySymbol.length > 0;

  if (!session.connected) {
    return (
      <div className="p-3 sm:p-4 md:p-6">
        <DeskEmpty
          icon={Unplug}
          title="Broker offline"
          description="Connect MT5 on Broker to load institutional analytics from live deal history."
        />
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto p-3 sm:p-4 md:p-6">
      <header className="flex shrink-0 flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Journal · Analytics
          </p>
          <h1 className="font-[family-name:var(--font-display)] text-xl tracking-tight text-[var(--fg)]">
            Institutional Analytics
          </h1>
          <p className="mt-1 max-w-2xl text-xs text-[var(--fg-muted)]">
            Expectancy, risk ratios, and distribution charts from live MetaTrader deals.
            Missing fields show as Not available — never invented.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => void historyQ.refetch()}
          disabled={historyQ.isFetching}
        >
          <RefreshCw
            className={cn("mr-1.5 h-3.5 w-3.5", historyQ.isFetching && "animate-spin")}
          />
          Refresh
        </Button>
      </header>

      <div className="flex shrink-0 flex-wrap items-end gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-panel)] p-2.5">
        <div className="flex flex-wrap gap-1">
          {(
            [
              ["today", "Today"],
              ["week", "Week"],
              ["month", "Month"],
              ["custom", "Custom"],
            ] as const
          ).map(([id, label]) => (
            <Button
              key={id}
              type="button"
              size="sm"
              variant={range === id ? "default" : "outline"}
              className="transition-[background-color,border-color,color] duration-[var(--duration-os)]"
              onClick={() => setRange(id)}
            >
              {label}
            </Button>
          ))}
        </div>
        {range === "custom" ? (
          <>
            <Input
              type="date"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
              className="h-8 w-[9.5rem]"
            />
            <Input
              type="date"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
              className="h-8 w-[9.5rem]"
            />
          </>
        ) : null}
        <p className="ml-auto text-[10px] text-[var(--fg-subtle)]">
          {metrics.closedCount} closed trade{metrics.closedCount === 1 ? "" : "s"}
        </p>
      </div>

      {historyQ.isLoading ? (
        <DeskSkeleton rows={8} />
      ) : historyQ.isError ? (
        <DeskError
          message="Live deal history unavailable from the MT5 gateway."
          onRetry={() => void historyQ.refetch()}
        />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            <KpiCell label="Expectancy" value={fmtMoney(metrics.expectancy)} tone={plTone(metrics.expectancy)} />
            <KpiCell
              label="Kelly %"
              value={
                metrics.kellyPct == null || !Number.isFinite(metrics.kellyPct)
                  ? NA
                  : `${formatNumber(metrics.kellyPct, 1)}%`
              }
            />
            <KpiCell label="Sharpe" value={fmtRatio(metrics.sharpe)} />
            <KpiCell label="Sortino" value={fmtRatio(metrics.sortino)} />
            <KpiCell label="Calmar" value={fmtRatio(metrics.calmar)} />
            <KpiCell label="Recovery" value={fmtRatio(metrics.recoveryFactor)} />
            <KpiCell label="MAR" value={fmtRatio(metrics.mar)} />
            <KpiCell label="Ulcer Index" value={fmtRatio(metrics.ulcerIndex)} />
            <KpiCell label="SQN" value={fmtRatio(metrics.sqn)} />
            <KpiCell
              label="Average MAE"
              value={fmtMoney(metrics.averageMae)}
              note="Requires bar path"
            />
            <KpiCell
              label="Average MFE"
              value={fmtMoney(metrics.averageMfe)}
              note="Requires bar path"
            />
            <KpiCell
              label="Max MAE"
              value={fmtMoney(metrics.maxMae)}
              note="Requires bar path"
            />
            <KpiCell
              label="Max MFE"
              value={fmtMoney(metrics.maxMfe)}
              note="Requires bar path"
            />
            <KpiCell label="Win Rate" value={fmtPct(metrics.winRate)} />
            <KpiCell label="Profit Factor" value={fmtRatio(metrics.profitFactor)} />
            <KpiCell label="Max Drawdown" value={fmtMoney(metrics.maxDrawdown)} />
            <KpiCell label="Avg RR" value={fmtRatio(metrics.averageRr)} />
            <KpiCell
              label="Largest Win"
              value={fmtMoney(metrics.largestWin)}
              tone={metrics.largestWin != null ? "text-[var(--success)]" : undefined}
            />
            <KpiCell
              label="Largest Loss"
              value={fmtMoney(metrics.largestLoss)}
              tone={metrics.largestLoss != null ? "text-[var(--danger)]" : undefined}
            />
          </div>

          <p className="text-[10px] text-[var(--fg-subtle)]">
            MAE/MFE Not available without bar path — QuantForg never fabricates excursion
            metrics from incomplete deal data.
          </p>

          {hasAnyChart ? (
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {metrics.equityCurve.length > 0 ? (
                <ChartPanel title="Equity curve">
                  <div className="h-44 [&_[role=img]]:!h-44">
                    <LazyEquityChart
                      data={equityChartData}
                      emptyLabel="No equity path in range"
                    />
                  </div>
                </ChartPanel>
              ) : null}
              {metrics.dailyPl.length > 0 ? (
                <ChartPanel title="Daily P/L">
                  <div className="h-44 [&_[role=img]]:!h-44">
                    <LazyBarChart
                      data={metrics.dailyPl.map((d) => ({
                        label: d.day.slice(5),
                        value: d.pl,
                      }))}
                    />
                  </div>
                </ChartPanel>
              ) : null}
              {metrics.bySession.length > 0 ? (
                <ChartPanel title="By session">
                  <div className="h-44 [&_[role=img]]:!h-44">
                    <LazyBarChart data={metrics.bySession} />
                  </div>
                </ChartPanel>
              ) : null}
              {metrics.byHour.length > 0 ? (
                <ChartPanel title="By hour">
                  <div className="h-44 overflow-x-auto [&_[role=img]]:!h-44">
                    <LazyBarChart data={metrics.byHour} />
                  </div>
                </ChartPanel>
              ) : null}
              {metrics.byWeekday.some((b) => b.value !== 0) ? (
                <ChartPanel title="By weekday">
                  <div className="h-44 [&_[role=img]]:!h-44">
                    <LazyBarChart data={metrics.byWeekday} />
                  </div>
                </ChartPanel>
              ) : null}
              {metrics.holdBuckets.some((b) => b.value > 0) ? (
                <ChartPanel title="Hold buckets">
                  <div className="h-44 [&_[role=img]]:!h-44">
                    <LazyBarChart data={metrics.holdBuckets} />
                  </div>
                </ChartPanel>
              ) : null}
              {metrics.profitDistribution.some((b) => b.value > 0) ? (
                <ChartPanel title="Profit distribution">
                  <div className="h-44 [&_[role=img]]:!h-44">
                    <LazyBarChart data={metrics.profitDistribution} />
                  </div>
                </ChartPanel>
              ) : null}
              {metrics.bySymbol.length > 0 ? (
                <ChartPanel title="By symbol">
                  <div className="h-44 overflow-x-auto [&_[role=img]]:!h-44">
                    <LazyBarChart data={metrics.bySymbol} />
                  </div>
                </ChartPanel>
              ) : null}
            </div>
          ) : (
            <DeskEmpty
              icon={LineChart}
              title="No analytics curves yet"
              description="Charts appear when closed deals exist in the selected range."
            />
          )}

          <StrategyIntelligencePanel symbol={TRADING_SYMBOL} />
        </>
      )}
    </div>
  );
}

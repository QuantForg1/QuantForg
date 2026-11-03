"use client";

import { useState, type ReactNode } from "react";
import {
  Activity,
  Coins,
  Layers,
  LineChart,
  Shield,
  Wallet,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { WorkspaceChart } from "@/components/workspace/chart-panel";
import { OverviewTradePanel } from "@/components/trading/overview-trade-panel";
import { TRADING_SYMBOL, displayTradingSymbol } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

function KpiCard({
  label,
  value,
  hint,
  bar,
  icon,
}: {
  label: string;
  value: string;
  hint?: string;
  bar?: number | null;
  icon: ReactNode;
}) {
  return (
    <article className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] p-4 shadow-[var(--shadow-card)] backdrop-blur-[8px]">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          {label}
        </p>
        <span
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[var(--border)] bg-[color-mix(in_srgb,var(--accent-soft)_55%,transparent)] text-[var(--accent)]"
          aria-hidden
        >
          {icon}
        </span>
      </div>
      <p className="mt-2 text-xl font-semibold tabular tracking-tight text-[var(--fg)]">
        {value}
      </p>
      {hint ? (
        <p className="mt-1 text-xs text-[var(--fg-muted)]">{hint}</p>
      ) : null}
      {bar != null ? (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[var(--bg)]/70" aria-hidden>
          <div
            className="h-full rounded-full bg-[var(--accent)]"
            style={{ width: `${Math.max(0, Math.min(100, bar))}%` }}
          />
        </div>
      ) : null}
    </article>
  );
}

/**
 * Reference Overview composition: KPI strip, live chart + AI panel, and Trade ticket.
 * Order entry reuses ExecutionOrderTicket — never a parallel engine.
 * All figures are caller-supplied live session / research values — never samples.
 */
export function OverviewReferenceDesk({
  equity,
  balance,
  todayPnl,
  openPositions,
  pendingOrders,
  accountRiskLabel,
  accountRiskPct,
  connected,
  marketBias,
  marketBiasDetail,
  currentPrice,
  support,
  resistance,
  regime,
  confidencePct,
  sessionName,
  lastUpdate,
  topSignal,
}: {
  equity: string;
  balance: string;
  todayPnl: string;
  openPositions: string;
  pendingOrders: string;
  accountRiskLabel: string;
  accountRiskPct: number | null;
  connected: boolean;
  marketBias: string;
  marketBiasDetail: string;
  currentPrice: string;
  support: string;
  resistance: string;
  regime: string;
  confidencePct: number | null;
  sessionName: string;
  lastUpdate: string;
  topSignal: Record<string, unknown> | null;
}) {
  const [timeframe, setTimeframe] = useState("M15");
  const [chartType, setChartType] = useState<"candles" | "line" | "area">("candles");
  const [showVolume, setShowVolume] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  const [intelTab, setIntelTab] = useState<"overview" | "signal" | "analysis" | "news">(
    "overview",
  );
  const biasTone =
    /bull/i.test(marketBias) || marketBias === "BUY"
      ? "success"
      : /bear/i.test(marketBias) || marketBias === "SELL"
        ? "danger"
        : "neutral";

  return (
    <div className="space-y-4">
      <section
        aria-label="Account metrics"
        className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"
      >
        <KpiCard
          label="Account Equity"
          value={equity}
          icon={<Wallet className="h-4 w-4" />}
        />
        <KpiCard
          label="Available Balance"
          value={balance}
          icon={<Coins className="h-4 w-4" />}
        />
        <KpiCard
          label="Today's P&L"
          value={todayPnl}
          icon={<LineChart className="h-4 w-4" />}
        />
        <KpiCard
          label="Open Positions"
          value={openPositions}
          hint={`${pendingOrders} pending orders`}
          icon={<Layers className="h-4 w-4" />}
        />
        <KpiCard
          label="Account Risk"
          value={accountRiskLabel}
          hint={
            accountRiskPct == null
              ? undefined
              : `${Math.round(accountRiskPct)}% of daily limit`
          }
          bar={accountRiskPct}
          icon={<Shield className="h-4 w-4" />}
        />
      </section>

      <div className="grid gap-4 xl:grid-cols-[1.55fr_0.85fr]">
        <section className="flex h-[min(520px,70vh)] min-h-[420px] flex-col overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg-elevated)] shadow-[var(--shadow-card)]">
          <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-4 py-2.5">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold">
                {displayTradingSymbol(TRADING_SYMBOL)}
              </h2>
              <span className="font-mono text-lg font-semibold tabular tracking-tight text-[var(--fg)] sm:text-xl">
                {currentPrice}
              </span>
              <Badge tone={connected ? "success" : "neutral"}>
                {connected ? "LIVE" : "OFFLINE"}
              </Badge>
            </div>
          </div>
          <div className="min-h-0 flex-1">
            <WorkspaceChart
              symbol={TRADING_SYMBOL}
              connected={connected}
              timeframe={timeframe}
              onTimeframeChange={setTimeframe}
              chartType={chartType}
              onChartTypeChange={setChartType}
              showVolume={showVolume}
              onShowVolumeChange={setShowVolume}
              fullscreen={fullscreen}
              onFullscreenChange={setFullscreen}
            />
          </div>
        </section>

        <section className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] shadow-[var(--shadow-card)] backdrop-blur-[8px] xl:self-start">
          <div
            className="flex gap-1 border-b border-[var(--border)] px-2 pt-2"
            role="tablist"
            aria-label="AI Market Intelligence"
          >
            {(
              [
                ["overview", "Overview"],
                ["signal", "Signal"],
                ["analysis", "Analysis"],
                ["news", "News"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={intelTab === id}
                className={cn(
                  "rounded-t-lg px-3 py-2 text-xs font-semibold transition",
                  intelTab === id
                    ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                    : "text-[var(--fg-muted)] hover:text-[var(--fg)]",
                )}
                onClick={() => setIntelTab(id)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="space-y-4 p-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Market Bias
              </p>
              <div
                className={cn(
                  "mt-2 rounded-xl border px-3 py-2.5",
                  biasTone === "success" &&
                    "border-[var(--border)] bg-[color-mix(in_srgb,var(--success-soft)_55%,var(--bg))]",
                  biasTone === "danger" &&
                    "border-[var(--border)] bg-[color-mix(in_srgb,var(--danger-soft)_45%,var(--bg))]",
                  biasTone === "neutral" && "border-[var(--border)] bg-[var(--bg)]/40",
                )}
              >
                <p className="text-sm font-semibold text-[var(--fg)]">{marketBias}</p>
                <p className="mt-1 text-xs leading-relaxed text-[var(--fg-muted)]">
                  {marketBiasDetail}
                </p>
              </div>
            </div>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--fg-muted)]">Current Price</dt>
                <dd className="font-mono tabular font-medium">{currentPrice}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--fg-muted)]">Key Support</dt>
                <dd className="font-mono tabular font-medium">{support}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--fg-muted)]">Key Resistance</dt>
                <dd className="font-mono tabular font-medium">{resistance}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--fg-muted)]">Market Regime</dt>
                <dd className="font-medium">{regime}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--fg-muted)]">Session</dt>
                <dd className="font-medium">{sessionName}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--fg-muted)]">Last Update</dt>
                <dd className="font-medium">{lastUpdate}</dd>
              </div>
            </dl>
            <div>
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  Confidence
                </p>
                <p className="font-mono text-sm tabular">
                  {confidencePct == null ? "—" : `${confidencePct}%`}
                </p>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--bg)]/70" aria-hidden>
                <div
                  className="h-full rounded-full bg-[var(--accent)]"
                  style={{
                    width: confidencePct == null ? "0%" : `${confidencePct}%`,
                  }}
                />
              </div>
            </div>
            {intelTab === "signal" ? (
              topSignal ? (
                <p className="text-xs text-[var(--fg-muted)]">
                  Active research row for {displayTradingSymbol(TRADING_SYMBOL)}. Open Signals
                  for the full desk.
                </p>
              ) : (
                <p className="flex items-start gap-2 text-xs text-[var(--fg-muted)]">
                  <Activity className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                  No live gold signal is available right now.
                </p>
              )
            ) : null}
            {intelTab === "analysis" ? (
              <p className="text-xs text-[var(--fg-muted)]">
                Analysis detail uses the live research bias and levels shown above.
              </p>
            ) : null}
            {intelTab === "news" ? (
              <p className="text-xs text-[var(--fg-muted)]">
                News feed is not wired on this desk. Market bias uses live research only.
              </p>
            ) : null}
          </div>
        </section>
      </div>

      <OverviewTradePanel connected={connected} />
    </div>
  );
}

"use client";

import { useState, type ReactNode } from "react";
import {
  Activity,
  Coins,
  Gauge,
  Layers,
  LineChart,
  Shield,
  Wallet,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { WorkspaceChart } from "@/components/workspace/chart-panel";
import { OverviewTradePanel } from "@/components/trading/overview-trade-panel";
import {
  TRADING_SYMBOL,
  displayTradingSymbol,
  displayTradingSymbolCode,
  tradingInstrumentDescription,
} from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

function KpiCard({
  label,
  value,
  hint,
  icon,
}: {
  label: string;
  value: string;
  hint?: string;
  icon: ReactNode;
}) {
  return (
    <article className="flex min-h-0 flex-col rounded-[var(--radius-os)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] px-3 py-2.5 shadow-[var(--shadow-card)] backdrop-blur-[8px]">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          {label}
        </p>
        <span
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-[var(--border)] bg-[color-mix(in_srgb,var(--accent-soft)_55%,transparent)] text-[var(--accent)]"
          aria-hidden
        >
          {icon}
        </span>
      </div>
      <p className="mt-1.5 truncate text-base font-semibold tabular tracking-tight text-[var(--fg)] sm:text-lg">
        {value}
      </p>
      {hint ? (
        <p className="mt-0.5 truncate text-[11px] leading-snug text-[var(--fg-muted)]">
          {hint}
        </p>
      ) : null}
    </article>
  );
}

function unavailable(value: string): string {
  if (!value || value === "—" || value === "Not available") return "Unavailable";
  return value;
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
  accountRiskHint,
  dailyRiskLabel,
  dailyRiskHint,
  brokerConnected,
  marketLive,
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
  lastPrice,
}: {
  equity: string;
  balance: string;
  todayPnl: string;
  openPositions: string;
  pendingOrders: string;
  accountRiskLabel: string;
  accountRiskHint?: string;
  dailyRiskLabel: string;
  dailyRiskHint?: string;
  brokerConnected: boolean;
  marketLive: boolean;
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
  lastPrice?: number;
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
        className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6"
      >
        <KpiCard
          label="Account Equity"
          value={equity}
          icon={<Wallet className="h-3.5 w-3.5" />}
        />
        <KpiCard
          label="Available Balance"
          value={balance}
          icon={<Coins className="h-3.5 w-3.5" />}
        />
        <KpiCard
          label="Today's P&L"
          value={todayPnl}
          icon={<LineChart className="h-3.5 w-3.5" />}
        />
        <KpiCard
          label="Open Positions"
          value={openPositions}
          hint={
            pendingOrders === "—"
              ? "Pending unavailable"
              : `${pendingOrders} pending orders`
          }
          icon={<Layers className="h-3.5 w-3.5" />}
        />
        <KpiCard
          label="Account Risk"
          value={accountRiskLabel}
          hint={accountRiskHint}
          icon={<Shield className="h-3.5 w-3.5" />}
        />
        <KpiCard
          label="Daily Risk"
          value={dailyRiskLabel}
          hint={dailyRiskHint}
          icon={<Gauge className="h-3.5 w-3.5" />}
        />
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(280px,0.85fr)] xl:items-stretch">
        <section className="flex h-[min(520px,70vh)] min-h-[420px] flex-col overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg-elevated)] shadow-[var(--shadow-card)]">
          <div className="flex shrink-0 flex-wrap items-start justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base font-semibold tracking-tight sm:text-lg">
                  {displayTradingSymbolCode(TRADING_SYMBOL)}
                </h2>
                <Badge tone={marketLive ? "success" : "neutral"}>
                  {marketLive ? "LIVE" : "OFFLINE"}
                </Badge>
              </div>
              <p className="mt-0.5 text-xs text-[var(--fg-muted)] sm:text-sm">
                {tradingInstrumentDescription(TRADING_SYMBOL)}
              </p>
            </div>
            <p className="font-mono text-2xl font-semibold tabular tracking-tight text-[var(--fg)] sm:text-3xl">
              {currentPrice === "—" || currentPrice.startsWith("$")
                ? currentPrice
                : currentPrice === "Not available" || currentPrice === "Unavailable"
                  ? "—"
                  : `$${currentPrice}`}
            </p>
          </div>
          <div className="min-h-0 flex-1">
            <WorkspaceChart
              symbol={TRADING_SYMBOL}
              connected={brokerConnected}
              marketFeedEnabled
              timeframe={timeframe}
              onTimeframeChange={setTimeframe}
              chartType={chartType}
              onChartTypeChange={setChartType}
              showVolume={showVolume}
              onShowVolumeChange={setShowVolume}
              fullscreen={fullscreen}
              onFullscreenChange={setFullscreen}
              lastPrice={lastPrice}
              hideSymbolLabel
            />
          </div>
        </section>

        <section className="flex min-h-0 flex-col overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] shadow-[var(--shadow-card)] backdrop-blur-[8px] xl:h-[min(520px,70vh)] xl:min-h-[420px]">
          <div
            className="flex shrink-0 gap-0.5 overflow-x-auto border-b border-[var(--border)] px-2 pt-2"
            role="tablist"
            aria-label="Market insights"
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
                  "shrink-0 rounded-t-lg px-3 py-2 text-xs font-semibold transition",
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
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
            {intelTab === "overview" ? (
              <>
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
                <dl className="space-y-2.5 text-sm">
                  <div className="flex justify-between gap-3">
                    <dt className="text-[var(--fg-muted)]">Current Price</dt>
                    <dd className="font-mono tabular font-medium">
                      {unavailable(currentPrice)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-[var(--fg-muted)]">Key Support</dt>
                    <dd className="font-mono tabular font-medium">{unavailable(support)}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-[var(--fg-muted)]">Key Resistance</dt>
                    <dd className="font-mono tabular font-medium">
                      {unavailable(resistance)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-[var(--fg-muted)]">Market Regime</dt>
                    <dd className="font-medium">{unavailable(regime)}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-[var(--fg-muted)]">Session</dt>
                    <dd className="font-medium">{sessionName}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-[var(--fg-muted)]">Last Update</dt>
                    <dd className="font-medium">{unavailable(lastUpdate)}</dd>
                  </div>
                </dl>
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                      Confidence
                    </p>
                    <p className="font-mono text-sm tabular">
                      {confidencePct == null ? "Unavailable" : `${confidencePct}%`}
                    </p>
                  </div>
                  {confidencePct != null ? (
                    <div
                      className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--bg)]/70"
                      aria-hidden
                    >
                      <div
                        className="h-full rounded-full bg-[var(--accent)]"
                        style={{ width: `${confidencePct}%` }}
                      />
                    </div>
                  ) : null}
                </div>
              </>
            ) : null}
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
                Analysis detail uses the live research bias and levels shown on Overview.
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

      <OverviewTradePanel connected={brokerConnected} />
    </div>
  );
}

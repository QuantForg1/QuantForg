"use client";

import { useState, type ReactNode } from "react";
import {
  Activity,
  Coins,
  Gauge,
  Layers,
  LineChart,
  Wallet,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { WorkspaceChart } from "@/components/workspace/chart-panel";
import dynamic from "next/dynamic";
import { useAuth } from "@/providers/auth-provider";
import { normalizePlatformRole } from "@/lib/auth/ite-ops-access";

// Manual order entry is an owner/admin desk tool (customers trade through
// their robot). Loaded on demand so customer sessions never fetch it.
const OverviewTradePanel = dynamic(
  () =>
    import("@/components/trading/overview-trade-panel").then(
      (m) => m.OverviewTradePanel,
    ),
  { ssr: false },
);
import {
  TRADING_SYMBOL,
  displayTradingSymbolCode,
  tradingInstrumentDescription,
} from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";
import { OverviewMarketIntelligence } from "@/components/trading/overview-market-intelligence";

function KpiCard({
  label,
  value,
  hint,
  icon,
  tone,
  title,
}: {
  label: string;
  value: string;
  hint?: string;
  icon: ReactNode;
  tone?: "success" | "danger" | "neutral";
  title?: string;
}) {
  return (
    <article
      title={title}
      className="flex min-h-0 min-w-0 flex-col rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-3 py-2.5 shadow-[var(--shadow-card)]"
    >
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
      <p
        className={cn(
          "mt-1.5 truncate text-base font-semibold tabular tracking-tight sm:text-lg",
          tone === "success" && "text-[var(--success)]",
          tone === "danger" && "text-[var(--danger)]",
          (!tone || tone === "neutral") && "text-[var(--fg)]",
        )}
      >
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

/**
 * Reference Overview composition: KPI strip, live chart + AI panel, and Trade ticket.
 * Order entry reuses ExecutionOrderTicket — never a parallel engine.
 * All figures are caller-supplied live session / research values — never samples.
 */
export function OverviewReferenceDesk({
  equity,
  balance,
  todayPnl,
  todayPnlTone,
  openPositions,
  pendingOrders,
  dailyRiskLabel,
  dailyRiskHint,
  metricsUpdatedAt,
  brokerConnected,
  marketLive,
  marketFeedStatus,
  tickUpdatedAt,
  tickTime,
  tickLoading,
  tickError,
  marketBias,
  marketBiasDetail,
  currentPrice,
  support,
  resistance,
  confidencePct,
  signalDirection = "WAIT",
  topSignal,
  lastPrice,
}: {
  equity: string;
  balance: string;
  todayPnl: string;
  todayPnlTone?: "success" | "danger" | "neutral";
  openPositions: string;
  pendingOrders: string;
  /** @deprecated Prefer dailyRiskLabel — Account Risk card removed per overview reference. */
  accountRiskLabel?: string;
  accountRiskHint?: string;
  dailyRiskLabel: string;
  dailyRiskHint?: string;
  metricsUpdatedAt?: string;
  brokerConnected: boolean;
  marketLive: boolean;
  /** Platform feed status — live | delayed | closed | unavailable */
  marketFeedStatus?: string;
  tickUpdatedAt?: number;
  tickTime?: string;
  tickLoading?: boolean;
  tickError?: boolean;
  marketBias: string;
  marketBiasDetail: string;
  currentPrice: string;
  support: string;
  resistance: string;
  confidencePct: number | null;
  signalDirection?: "BUY" | "SELL" | "WAIT";
  topSignal: Record<string, unknown> | null;
  lastPrice?: number;
}) {
  const { user } = useAuth();
  const role = normalizePlatformRole(user?.role);
  const canUseManualTicket = role === "owner" || role === "admin";
  const [timeframe, setTimeframe] = useState("M15");
  const [chartType, setChartType] = useState<"candles" | "line" | "area">("candles");
  const [showVolume, setShowVolume] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [intelTab, setIntelTab] = useState<"overview" | "signal" | "analysis" | "news">(
    "overview",
  );
  return (
    <div className="space-y-4">
      <section
        aria-label="Account metrics"
        className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5"
      >
        <KpiCard
          label="Account Equity"
          value={equity}
          hint={metricsUpdatedAt ? `Updated ${metricsUpdatedAt}` : undefined}
          title="Live account equity from your authorized broker session."
          icon={<Wallet className="h-3.5 w-3.5" />}
        />
        <KpiCard
          label="Available Balance"
          value={balance}
          hint={metricsUpdatedAt ? `Updated ${metricsUpdatedAt}` : undefined}
          title="Account balance available for margin from the broker session."
          icon={<Coins className="h-3.5 w-3.5" />}
        />
        <KpiCard
          label="Today's P&L"
          value={todayPnl}
          tone={todayPnlTone}
          hint={
            todayPnl === "—"
              ? "Unavailable until session or deals load"
              : "Realized today + floating where available"
          }
          title="Today's combined realized and floating profit or loss."
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
          title="Open positions on your authorized account."
          icon={<Layers className="h-3.5 w-3.5" />}
        />
        <KpiCard
          label="Daily Risk"
          value={dailyRiskLabel}
          hint={dailyRiskHint}
          title="Daily loss usage versus the owner daily-loss halt ceiling."
          icon={<Gauge className="h-3.5 w-3.5" />}
        />
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(280px,0.85fr)] xl:items-stretch">
        <section className="flex h-[min(68vh,520px)] min-h-[300px] flex-col overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg-elevated)] shadow-[var(--shadow-card)] sm:min-h-[420px]">
          <div className="flex shrink-0 flex-wrap items-start justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base font-semibold tracking-tight sm:text-lg">
                  {displayTradingSymbolCode(TRADING_SYMBOL)}
                </h2>
                {(() => {
                  const status = (marketFeedStatus || (marketLive ? "live" : "unavailable")).toLowerCase();
                  if (status === "live") return <Badge tone="success">LIVE</Badge>;
                  if (status === "delayed") return <Badge tone="warning">DELAYED</Badge>;
                  if (status === "closed") return <Badge tone="warning">MARKET CLOSED</Badge>;
                  return <Badge tone="neutral">OFFLINE</Badge>;
                })()}
              </div>
              <p className="mt-0.5 text-xs text-[var(--fg-muted)] sm:text-sm">
                {tradingInstrumentDescription(TRADING_SYMBOL)}
              </p>
            </div>
            <p className="font-mono text-xl font-semibold tabular tracking-tight text-[var(--fg)] sm:text-3xl">
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

        <section className="flex min-w-0 flex-col overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-card)] xl:h-[min(520px,70vh)] xl:min-h-[420px]">
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
              <OverviewMarketIntelligence
                timeframe={timeframe}
                lastPrice={lastPrice}
                marketFeedStatus={marketFeedStatus}
                tickUpdatedAt={tickUpdatedAt}
                tickTime={tickTime}
                tickLoading={tickLoading}
                tickError={tickError}
                support={support}
                resistance={resistance}
                confidencePct={confidencePct}
                signalDirection={signalDirection}
              />
            ) : null}
            {intelTab === "signal" ? (
              topSignal ? (
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-[var(--fg)]">{marketBias}</p>
                  <p className="text-xs leading-relaxed text-[var(--fg-muted)]">{marketBiasDetail}</p>
                </div>
              ) : (
                <p className="flex items-start gap-2 text-xs text-[var(--fg-muted)]">
                  <Activity className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                  No live gold signal is available right now.
                </p>
              )
            ) : null}
            {intelTab === "analysis" ? (
              <p className="text-xs text-[var(--fg-muted)]">
                Support, resistance, regime, and momentum on Overview are calculated from closed {timeframe} candles. They are not used for orders.
              </p>
            ) : null}
            {intelTab === "news" ? (
              <p className="text-xs text-[var(--fg-muted)]">
                No news feed is connected on this desk.
              </p>
            ) : null}
          </div>
        </section>
      </div>

      {canUseManualTicket ? (
        <OverviewTradePanel connected={brokerConnected} />
      ) : null}
    </div>
  );
}

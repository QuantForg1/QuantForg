"use client";

import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Banknote,
  Coins,
  LineChart,
  Shield,
  Wallet,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { WorkspaceChart } from "@/components/workspace/chart-panel";
import dynamic from "next/dynamic";
// Manual order entry reuses the existing ticket. Loaded on demand.
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
import { intelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import {
  presentField,
  presentLevel,
  signalBoardDirection,
} from "@/lib/trading/trader-ux";

function KpiCard({
  label,
  value,
  icon,
  tone,
  delay = 0,
}: {
  label: string;
  value: string;
  icon: ReactNode;
  tone?: "success" | "danger" | "neutral";
  delay?: number;
}) {
  const tile =
    tone === "success"
      ? "border-[color-mix(in_srgb,var(--success)_40%,var(--border))] bg-[var(--success-soft)] text-[var(--success)]"
      : tone === "danger"
        ? "border-[color-mix(in_srgb,var(--danger)_40%,var(--border))] bg-[var(--danger-soft)] text-[var(--danger)]"
        : "";
  return (
    <article
      className="qf-overview-card qf-overview-enter flex h-full min-h-[5.5rem] min-w-0 items-center gap-3 px-3.5 py-3.5 sm:px-4"
      style={{ animationDelay: `${delay}ms` }}
    >
      <span className={cn("qf-overview-icon", tile)} aria-hidden>
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {label}
        </p>
        <p
          className={cn(
            "mt-1 truncate text-xl font-semibold tabular tracking-tight sm:text-2xl",
            tone === "success" && "text-[var(--success)]",
            tone === "danger" && "text-[var(--danger)]",
            (!tone || tone === "neutral") && "text-[var(--fg)]",
          )}
        >
          {value}
        </p>
      </div>
    </article>
  );
}

/**
 * Reference Overview composition: KPI strip, live chart + AI panel, and Trade ticket.
 * Order entry reuses ExecutionOrderTicket — never a parallel engine.
 * All figures are caller-supplied live session / research values — never samples.
 */
function usable(value: string) {
  const text = value.trim();
  return (
    text.length > 0 &&
    text !== "—" &&
    text !== "Not available" &&
    text !== "Unavailable" &&
    text !== "Price unavailable"
  );
}

function directionLabel(row: Record<string, unknown>) {
  const board = signalBoardDirection(row);
  if (board === "BUY") return "Bullish";
  if (board === "SELL") return "Bearish";
  if (board === "NEUTRAL" || board === "WAIT") return "Neutral";
  return board;
}

function prefersGold(row: Record<string, unknown>) {
  const blob = `${str(row.title)} ${str(row.event)} ${str(row.currency)} ${str(row.country)} ${str(row.symbol)}`.toUpperCase();
  return /XAU|GOLD|USD/.test(blob);
}

function NewsPanel({
  newsQ,
  calendarQ,
}: {
  newsQ: { isLoading: boolean; isError: boolean; data: unknown };
  calendarQ: { isLoading: boolean; isError: boolean; data: unknown };
}) {
  if (newsQ.isLoading || calendarQ.isLoading) {
    return <p className="text-xs text-[var(--fg-muted)]">Loading the connected news and calendar feeds.</p>;
  }
  if (newsQ.isError && calendarQ.isError) {
    return (
      <p className="text-xs leading-relaxed text-[var(--fg-muted)]">
        The news and economic-calendar feeds could not be loaded. No headlines are shown in their place.
      </p>
    );
  }
  const events = asList(calendarQ.isError ? [] : calendarQ.data)
    .map(asRecord)
    .sort((a, b) => Number(prefersGold(b)) - Number(prefersGold(a)));
  const headlines = asList(newsQ.isError ? [] : newsQ.data)
    .map(asRecord)
    .sort((a, b) => Number(prefersGold(b)) - Number(prefersGold(a)));
  if (events.length === 0 && headlines.length === 0) {
    return (
      <p className="text-xs leading-relaxed text-[var(--fg-muted)]">
        No Gold or market headlines are available from the connected news and calendar feeds.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      {events.length > 0 ? (
        <ul className="space-y-2">
          {events.slice(0, 8).map((event, index) => {
            const href = str(event.url || event.link, "");
            const title = str(event.title || event.event, "Untitled event");
            return (
              <li key={`${title}-${index}`} className="min-w-0 border-b border-[var(--border)] pb-2 last:border-0">
                <p className="text-sm font-medium text-[var(--fg)]">
                  {href ? (
                    <a href={href} target="_blank" rel="noreferrer" className="hover:text-[var(--accent)]">
                      {title}
                    </a>
                  ) : (
                    title
                  )}
                </p>
                <p className="mt-1 text-[11px] text-[var(--fg-subtle)]">
                  {[str(event.scheduled_at || event.time, ""), str(event.currency || event.country, ""), str(event.impact, "")]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </li>
            );
          })}
        </ul>
      ) : null}
      {headlines.length > 0 ? (
        <ul className="space-y-2">
          {headlines.slice(0, 8).map((item, index) => {
            const href = str(item.url || item.link, "");
            const title = str(item.title || item.headline, "Untitled");
            return (
              <li key={`${title}-${index}`} className="min-w-0">
                <p className="text-sm font-medium text-[var(--fg)]">
                  {href ? (
                    <a href={href} target="_blank" rel="noreferrer" className="hover:text-[var(--accent)]">
                      {title}
                    </a>
                  ) : (
                    title
                  )}
                </p>
                <p className="mt-1 text-[11px] text-[var(--fg-subtle)]">
                  {[str(item.published_at || item.time, ""), str(item.source, "")]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

function SignalFacts({ row }: { row: Record<string, unknown> }) {
  const confidence = row.ai_confidence ?? row.confidence ?? row.opportunity_score;
  const confidenceText =
    typeof confidence === "number" && Number.isFinite(confidence)
      ? `${confidence <= 1 ? Math.round(confidence * 100) : Math.round(confidence)}%`
      : "";
  const facts = [
    ["Direction", directionLabel(row)],
    ["Status", presentField(row.status ?? row.signal_status ?? row.state)],
    ["Time", presentField(row.created_at ?? row.timestamp ?? row.as_of ?? row.time)],
    ["Timeframe", presentField(row.timeframe ?? row.tf)],
    ["Entry", presentLevel(row.entry ?? row.entry_price ?? row.entry_candidate, "Entry")],
    ["Stop loss", presentLevel(row.stop_loss ?? row.SL_candidate, "SL")],
    ["Take profit", presentLevel(row.take_profit ?? row.TP_candidate, "TP")],
    ["Confidence", confidenceText],
  ].filter(([, value]) => usable(value));
  return (
    <dl className="grid grid-cols-2 gap-3">
      {facts.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
            {label}
          </dt>
          <dd className="mt-1 truncate text-sm font-semibold text-[var(--fg)]">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function OverviewReferenceDesk({
  equity,
  balance,
  todayPnl,
  todayPnlTone,
  openPositions,
  dailyRiskLabel,
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
  const [timeframe, setTimeframe] = useState("M15");
  const [chartType, setChartType] = useState<"candles" | "line" | "area">("candles");
  const [showVolume, setShowVolume] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [intelTab, setIntelTab] = useState<"overview" | "signal" | "analysis" | "news">(
    "overview",
  );
  const newsQ = useQuery({
    queryKey: ["desk-intelligence-news"],
    queryFn: () => intelligenceApi.news(12),
    enabled: intelTab === "news",
    retry: false,
    staleTime: 60_000,
  });
  const calendarQ = useQuery({
    queryKey: ["desk-intelligence-calendar"],
    queryFn: () => intelligenceApi.calendar(12),
    enabled: intelTab === "news",
    retry: false,
    staleTime: 60_000,
  });
  return (
    <div className="space-y-4">
      <section aria-label="Account metrics" className="min-w-0">
        <p className="sr-only">
          {metricsUpdatedAt
            ? `Account figures updated ${metricsUpdatedAt}.`
            : "Account figures from the broker session."}
        </p>
        <div className="grid grid-cols-2 items-stretch gap-2 sm:gap-3 xl:grid-cols-4">
        <KpiCard
          label="Account Equity"
          value={equity}
          delay={0}
          icon={<Wallet className="h-4 w-4" />}
        />
        <KpiCard
          label="Available Balance"
          value={balance}
          delay={40}
          icon={<Banknote className="h-4 w-4" />}
        />
        <KpiCard
          label="Today's P&L"
          value={todayPnl}
          tone={todayPnlTone}
          delay={80}
          icon={<LineChart className="h-4 w-4" />}
        />
        <KpiCard
          label="Daily Risk"
          value={dailyRiskLabel}
          delay={120}
          icon={<Shield className="h-4 w-4" />}
        />
        </div>
        <p className="mt-2 text-xs text-[var(--fg-muted)]">
          Open positions{" "}
          <span className="font-semibold tabular text-[var(--fg)]">{openPositions}</span>
        </p>
      </section>

      <div className="grid items-stretch gap-4 lg:grid-cols-[minmax(0,1.65fr)_minmax(280px,0.85fr)] lg:grid-rows-1">
        <section className="qf-overview-panel qf-overview-enter flex min-h-[22rem] flex-col overflow-hidden lg:h-[34rem]" style={{ animationDelay: "80ms" }}>
          <div className="flex shrink-0 flex-col gap-3 border-b border-[color-mix(in_srgb,var(--accent)_16%,var(--border))] px-3 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-4">
            <div className="flex min-w-0 items-center gap-3">
              <span className="qf-overview-icon" aria-hidden>
                <Coins className="h-4 w-4" />
              </span>
              <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base font-semibold tracking-tight sm:text-lg">
                  {displayTradingSymbolCode(TRADING_SYMBOL)}
                </h2>
                {(() => {
                  const status = (marketFeedStatus || (marketLive ? "live" : "unavailable")).toLowerCase();
                  if (status === "live") return <Badge tone="success">LIVE</Badge>;
                  if (status === "delayed") return null;
                  if (status === "closed") return <Badge tone="warning">MARKET CLOSED</Badge>;
                  return <Badge tone="neutral">OFFLINE</Badge>;
                })()}
              </div>
              <p className="mt-0.5 text-xs text-[var(--fg-muted)] sm:text-sm">
                {tradingInstrumentDescription(TRADING_SYMBOL)}
              </p>
              </div>
            </div>
            <p className="max-w-full font-mono text-xl font-semibold tabular tracking-tight text-[var(--fg)] sm:text-right sm:text-3xl">
              {currentPrice === "—" || currentPrice.startsWith("$")
                ? currentPrice
                : currentPrice === "Not available" || currentPrice === "Unavailable"
                  ? "—"
                  : `$${currentPrice}`}
            </p>
          </div>
          <div className="min-h-0 flex-1 px-1 pb-1">
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
              comfortable
            />
          </div>
        </section>

        <section className="qf-overview-panel flex min-h-[22rem] min-w-0 flex-col overflow-hidden lg:h-[34rem]">
          <div
            className="flex shrink-0 gap-1 overflow-x-auto border-b border-[color-mix(in_srgb,var(--accent)_16%,var(--border))] px-2 py-2 sm:px-3"
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
                  "h-9 shrink-0 rounded-lg px-3 text-xs font-semibold transition-[color,background-color,box-shadow] duration-200",
                  intelTab === id
                    ? "bg-[var(--accent)] text-[var(--accent-fg)] shadow-[var(--shadow-card)]"
                    : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]",
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
                <div className="space-y-3">
                  <SignalFacts row={topSignal} />
                  {usable(marketBiasDetail) ? (
                    <p className="text-xs leading-relaxed text-[var(--fg-muted)]">{marketBiasDetail}</p>
                  ) : null}
                  <p className="text-[11px] text-[var(--fg-subtle)]">
                    Research signal only. It does not place or modify an order.
                  </p>
                </div>
              ) : (
                <p className="flex items-start gap-2 text-xs leading-relaxed text-[var(--fg-muted)]">
                  <Activity className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                  No live Gold signal is currently available from the signal service.
                </p>
              )
            ) : null}
            {intelTab === "analysis" ? (
              <div className="space-y-3">
                <p className="text-xs leading-relaxed text-[var(--fg-muted)]">
                  Advisory read of closed {timeframe} candles and the current tick. This explanation is not an executable signal and is not sent to the order path.
                </p>
                {usable(marketBias) ? (
                  <p className="text-sm font-semibold text-[var(--fg)]">{marketBias}</p>
                ) : null}
                {usable(marketBiasDetail) ? (
                  <p className="text-xs leading-relaxed text-[var(--fg-muted)]">{marketBiasDetail}</p>
                ) : null}
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
              </div>
            ) : null}
            {intelTab === "news" ? (
              <NewsPanel newsQ={newsQ} calendarQ={calendarQ} />
            ) : null}
          </div>
        </section>
      </div>

      <OverviewTradePanel connected={brokerConnected} />
    </div>
  );
}

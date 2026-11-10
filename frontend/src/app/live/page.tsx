"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { LiveMarketChat } from "@/components/marketing/live-market-chat";
import { PricingFooter, PricingHeader } from "@/components/pricing/marketing-chrome";
import { WorkspaceChart } from "@/components/workspace/chart-panel";
import { mt5Api } from "@/lib/api/endpoints";
import { asRecord, num, str } from "@/lib/desk";
import {
  displayTradingSymbol,
  TRADING_SYMBOL,
} from "@/lib/trading/gold-only";
import { publicFeedBadge } from "@/lib/trading/market-status";
import { formatNumber } from "@/lib/utils";

/**
 * Public Live Market page — chart + discussion, no login required to view.
 */
export default function PublicLiveMarketPage() {
  const [timeframe, setTimeframe] = useState("H1");
  const [chartType, setChartType] = useState<"candles" | "line" | "area">("candles");
  const [showVolume, setShowVolume] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  const [mobileTab, setMobileTab] = useState<"chart" | "chat">("chart");

  const tickQ = useQuery({
    queryKey: ["public-market-tick", TRADING_SYMBOL],
    queryFn: () => mt5Api.publicTick(TRADING_SYMBOL),
    retry: 1,
    refetchInterval: 15_000,
  });

  const tickPayload = asRecord(tickQ.data);
  const tick = asRecord(tickPayload.tick);
  const bid = num(tick.bid);
  const ask = num(tick.ask);
  const mid =
    Number.isFinite(bid) && Number.isFinite(ask)
      ? (bid + ask) / 2
      : Number.isFinite(bid)
        ? bid
        : Number.NaN;
  const status = tickQ.isLoading
    ? "loading"
    : str(tickPayload.status || (tickQ.isSuccess ? "live" : "unavailable"));
  const badge = publicFeedBadge(status);
  const asOf = str(tickPayload.as_of || "");
  const source = str(tickPayload.source || "");

  const priceLabel = useMemo(() => {
    if (Number.isFinite(mid)) return formatNumber(mid, 2);
    return "—";
  }, [mid]);

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--fg)]">
      <PricingHeader active="live" />
      <main id="main-content" className="mx-auto w-full max-w-6xl px-4 pb-16 pt-8 sm:px-6">
        <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--fg-muted)]">
              Live Market
            </p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">
              {displayTradingSymbol(TRADING_SYMBOL)}
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-[var(--fg-muted)]">
              Public market chart and discussion powered by the QuantForg platform feed. No
              login required to view. Trading actions still require authentication.
            </p>
          </div>
          <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-right">
            <p className="text-[10px] font-semibold tracking-wide text-[var(--fg-muted)]">
              {badge.label}
              {source ? ` · ${source}` : ""}
            </p>
            <p className="mt-1 font-mono text-2xl tabular text-[var(--fg)]">{priceLabel}</p>
            {asOf ? (
              <p className="mt-1 text-[10px] text-[var(--fg-subtle)]">Updated {asOf}</p>
            ) : null}
          </div>
        </header>

        <div className="mb-3 flex gap-1 lg:hidden" role="tablist" aria-label="Live Market panels">
          {(
            [
              ["chart", "Chart"],
              ["chat", "Chat"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={mobileTab === id}
              className={
                mobileTab === id
                  ? "h-9 rounded-[var(--radius-sm)] bg-[var(--surface-2)] px-3 text-sm font-medium text-[var(--fg)]"
                  : "h-9 rounded-[var(--radius-sm)] px-3 text-sm text-[var(--fg-muted)]"
              }
              onClick={() => setMobileTab(id)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.7fr)_minmax(280px,0.9fr)]">
          <section
            className={
              fullscreen
                ? "fixed inset-0 z-50 bg-[var(--bg)] p-3"
                : mobileTab === "chart"
                  ? "h-[min(70vh,640px)] overflow-hidden rounded-[var(--radius-md)] border border-[var(--border)]"
                  : "hidden h-[min(70vh,640px)] overflow-hidden rounded-[var(--radius-md)] border border-[var(--border)] lg:block"
            }
          >
            <WorkspaceChart
              symbol={TRADING_SYMBOL}
              connected={false}
              marketFeedEnabled
              timeframe={timeframe}
              onTimeframeChange={setTimeframe}
              chartType={chartType}
              onChartTypeChange={setChartType}
              showVolume={showVolume}
              onShowVolumeChange={setShowVolume}
              fullscreen={fullscreen}
              onFullscreenChange={setFullscreen}
              lastPrice={Number.isFinite(mid) ? mid : undefined}
              hideSymbolLabel={false}
            />
          </section>

          <div className={mobileTab === "chat" ? "block min-h-[420px]" : "hidden min-h-[420px] lg:block"}>
            <LiveMarketChat channel="xauusd" className="h-full min-h-[420px] lg:min-h-[640px]" />
          </div>
        </div>

        <p className="mt-4 text-xs text-[var(--fg-muted)]">
          Want to trade or connect a broker?{" "}
          <Link href="/login" className="text-[var(--accent)] underline">
            Sign in
          </Link>{" "}
          or{" "}
          <Link href="/register" className="text-[var(--accent)] underline">
            create an account
          </Link>
          .
        </p>
      </main>
      <PricingFooter />
    </div>
  );
}

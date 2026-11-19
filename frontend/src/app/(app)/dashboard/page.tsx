"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Cable } from "lucide-react";
import { Button } from "@/components/ui/button";
import { OverviewReferenceDesk } from "@/components/trading/overview-reference-desk";
import { TradingPerformancePanel } from "@/components/trading/dashboard-intelligence/trading-performance-panel";
import {
  mt5Api,
  portfolioApi,
  signalCenterApi,
  tradingSessionApi,
} from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import {
  netDealPnl,
  startOfUtcDayMs,
} from "@/lib/dashboard/performance-window";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import { TRADING_SYMBOL, XAUUSD_SPECS } from "@/lib/trading/gold-only";
import {
  normalizeSignalCenterPayload,
  presentField,
  presentLevel,
  priceDisplay,
  researchAvailabilityAsCatalogue,
  signalBoardDirection,
  signalHumanExplanation,
  SIGNAL_CENTER_QUERY_KEY,
  resolveConnectionPresentation,
  topResearchOpportunities,
  TRADER_POLL_MS,
  UNIVERSE_POLL_MS,
} from "@/lib/trading/trader-ux";

function workspaceGreeting(now = new Date(), firstName = ""): string {
  const hour = now.getHours();
  const part =
    hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  return firstName ? `${part}, ${firstName}` : part;
}

function moneyOrDash(
  raw: unknown,
  available: boolean,
  currency = "USD",
): string {
  if (!available) return "—";
  if (raw == null || raw === "" || raw === "—") return "—";
  const n = num(raw);
  const code = currency && currency !== "—" ? currency : "USD";
  return Number.isFinite(n) ? formatCurrency(n, code) : "—";
}

export default function DashboardPage() {
  const { user } = useAuth();

  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    refetchInterval: TRADER_POLL_MS,
    staleTime: 10_000,
  });
  const portfolio = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    retry: false,
    refetchInterval: TRADER_POLL_MS,
  });
  const history = useQuery({
    queryKey: ["history"],
    queryFn: portfolioApi.history,
    retry: false,
    refetchInterval: UNIVERSE_POLL_MS,
  });

  const session = asRecord(sessionQ.data);
  const connection = resolveConnectionPresentation(session);
  const positions = asList(portfolio.data?.positions).map(asRecord);
  const deals = asList(history.data?.deals).map(asRecord);
  const noBroker = connection.state === "BROKER_NOT_CONNECTED";
  const sessionMismatch = connection.state === "ACCOUNT_SESSION_MISMATCH";
  const tickQ = useQuery({
    queryKey: ["research-tick", TRADING_SYMBOL],
    queryFn: async () => {
      try {
        return await mt5Api.publicTick(TRADING_SYMBOL);
      } catch {
        return mt5Api.researchTick(TRADING_SYMBOL);
      }
    },
    retry: 1,
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
  const signalsQ = useQuery({
    queryKey: SIGNAL_CENTER_QUERY_KEY,
    queryFn: () => signalCenterApi.list({ enabled_only: false }),
    retry: false,
    refetchInterval: TRADER_POLL_MS,
  });
  const research = normalizeSignalCenterPayload(
    signalsQ.isError ? null : asRecord(signalsQ.data),
  );
  const researchAvailability = signalsQ.isError
    ? ("UNAVAILABLE" as const)
    : research.availability;
  const signalState = researchAvailabilityAsCatalogue(researchAvailability);
  const signalPreview =
    signalState === "LIVE_ROWS"
      ? topResearchOpportunities(research.rows, signalState, 3)
      : [];

  const positionsUnavailable = Boolean(portfolio.isError) && !noBroker && !sessionMismatch;
  const activityUnavailable = Boolean(history.isError) && !noBroker && !sessionMismatch;
  const showMetrics =
    connection.connected && !sessionMismatch && !connection.accountUnavailable;

  const firstName = (user?.display_name || user?.email || "")
    .split(" ")[0]
    ?.split("@")[0] ?? "";

  const greeting = workspaceGreeting(new Date(), firstName);
  const topSignal = signalPreview[0] ?? null;
  const biasDir = topSignal ? signalBoardDirection(topSignal) : "WAIT";
  const confRaw = topSignal
    ? num(topSignal.ai_confidence ?? topSignal.confidence ?? topSignal.opportunity_score)
    : NaN;
  const confPct = Number.isFinite(confRaw)
    ? confRaw <= 1
      ? Math.round(confRaw * 100)
      : Math.round(confRaw)
    : null;
  const floatingFromPositions = positions.reduce((sum, row) => {
    const p = num(row.profit);
    return Number.isFinite(p) ? sum + p : sum;
  }, 0);
  const sessionProfit = num(session.profit ?? session.daily_pnl ?? session.today_pnl);
  const todayStartMs = startOfUtcDayMs();
  const closedTodayPnl = deals.reduce((sum, deal) => {
    const stamp = Date.parse(str(deal.time ?? deal.close_time ?? deal.deal_time));
    if (!Number.isFinite(stamp) || stamp < todayStartMs) return sum;
    const p = netDealPnl(deal);
    return Number.isFinite(p) ? sum + p : sum;
  }, 0);
  const todayPnlRaw = Number.isFinite(sessionProfit)
    ? sessionProfit
    : showMetrics && !positionsUnavailable && !activityUnavailable
      ? floatingFromPositions + closedTodayPnl
      : showMetrics && !positionsUnavailable && positions.length > 0
        ? floatingFromPositions
        : NaN;
  const equityNum = num(session.equity);
  const dailyLossAmount =
    Number.isFinite(todayPnlRaw) && todayPnlRaw < 0 ? Math.abs(todayPnlRaw) : null;
  const dailyLossPctOfEquity =
    dailyLossAmount != null &&
    Number.isFinite(equityNum) &&
    equityNum > 0
      ? (dailyLossAmount / equityNum) * 100
      : Number.isFinite(todayPnlRaw) && todayPnlRaw >= 0
        ? 0
        : null;
  const riskPctRaw = num(session.risk_pct ?? session.daily_risk_pct);
  const riskPct = Number.isFinite(riskPctRaw) ? riskPctRaw : null;
  const accountCurrency = str(session.currency, "USD");
  const metricsUpdatedAt =
    sessionQ.dataUpdatedAt
      ? formatRelativeTime(new Date(sessionQ.dataUpdatedAt))
      : undefined;
  const todayPnlTone =
    !showMetrics || !Number.isFinite(todayPnlRaw)
      ? ("neutral" as const)
      : todayPnlRaw > 0
        ? ("success" as const)
        : todayPnlRaw < 0
          ? ("danger" as const)
          : ("neutral" as const);
  const tickEnvelope = asRecord(tickQ.data);
  const tick = asRecord(tickEnvelope.tick ?? tickQ.data);
  const tickBid = num(tick.bid);
  const tickAsk = num(tick.ask);
  const tickMid =
    Number.isFinite(tickBid) && Number.isFinite(tickAsk)
      ? (tickBid + tickAsk) / 2
      : Number.isFinite(tickBid)
        ? tickBid
        : Number.isFinite(tickAsk)
          ? tickAsk
          : NaN;
  const publicTickStatus = str(tickEnvelope.status || "").toLowerCase();
  const marketLive =
    tickQ.isSuccess &&
    Number.isFinite(tickMid) &&
    (publicTickStatus === "" || publicTickStatus === "live");
  const liveMarketPrice = Number.isFinite(tickMid)
    ? priceDisplay(tickMid, XAUUSD_SPECS.digits)
    : "—";

  return (
    <div className="qf-overview qf-page-stack min-w-0 space-y-4 sm:space-y-5">
      <header className="qf-overview-enter relative flex flex-col gap-3 overflow-hidden sm:flex-row sm:items-end sm:justify-between">
        <svg className="qf-overview-wave" viewBox="0 0 480 120" fill="none" aria-hidden>
          <path
            d="M0 78C78 78 118 22 198 42s128 52 282-8"
            stroke="currentColor"
            strokeWidth="2.2"
          />
          <path
            d="M0 96C104 96 168 46 246 60s132 42 234-6"
            stroke="currentColor"
            strokeWidth="1.6"
            opacity="0.65"
          />
          <path
            d="M36 52C132 8 214 86 318 42s96-18 162-4"
            stroke="currentColor"
            strokeWidth="1.3"
            opacity="0.45"
          />
        </svg>
        <div className="relative z-[1] min-w-0">
          <h1 className="text-[1.35rem] font-semibold leading-tight tracking-tight text-[var(--fg)] sm:text-[1.85rem]">
            {greeting}
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-[var(--fg-muted)]">
            {showMetrics
              ? "Connected session balances, market status, and research insights."
              : "Account figures appear when your broker session is available. The chart uses the platform feed."}
          </p>
        </div>
        {noBroker || sessionMismatch ? (
          <Button asChild className="relative z-[1]">
            <Link href="/broker">
              <Cable className="h-4 w-4" /> Connect broker
            </Link>
          </Button>
        ) : null}
      </header>

      <OverviewReferenceDesk
        equity={moneyOrDash(session.equity, showMetrics, accountCurrency)}
        balance={moneyOrDash(session.balance, showMetrics, accountCurrency)}
        todayPnl={
          showMetrics && Number.isFinite(todayPnlRaw)
            ? formatCurrency(
                todayPnlRaw,
                accountCurrency === "—" ? "USD" : accountCurrency,
              )
            : "—"
        }
        todayPnlTone={todayPnlTone}
        accountRiskLabel={
          riskPct == null
            ? "—"
            : riskPct < 30
              ? "Low"
              : riskPct < 60
                ? "Moderate"
                : "Elevated"
        }
        accountRiskHint={
          riskPct == null
            ? "Unavailable from session"
            : `${Math.round(riskPct)}% session risk`
        }
        openPositions={
          !showMetrics || positionsUnavailable ? "—" : String(positions.length)
        }
        dailyRiskLabel={
          !showMetrics
            ? "—"
            : dailyLossPctOfEquity != null
              ? `${dailyLossPctOfEquity.toFixed(1)}%`
              : "—"
        }
        dailyRiskHint={
          !showMetrics
            ? "Requires broker session"
            : dailyLossPctOfEquity != null
              ? dailyLossPctOfEquity <= 0
                ? "No daily loss recorded"
                : `${formatCurrency(
                    dailyLossAmount ?? 0,
                    accountCurrency === "—" ? "USD" : accountCurrency,
                  )} daily loss vs equity — manage limits in Robot & Risk`
              : "Unavailable"
        }
        metricsUpdatedAt={metricsUpdatedAt}
        brokerConnected={showMetrics}
        marketLive={marketLive}
        marketFeedStatus={publicTickStatus || (marketLive ? "live" : "unavailable")}
        tickUpdatedAt={tickQ.dataUpdatedAt || undefined}
        tickTime={str(tick.time || tick.timestamp || tickEnvelope.as_of || "")}
        tickLoading={tickQ.isLoading}
        tickError={tickQ.isError}
        signalDirection={biasDir === "BUY" || biasDir === "SELL" ? biasDir : "WAIT"}
        marketBias={
          biasDir === "BUY"
            ? "Bullish"
            : biasDir === "SELL"
              ? "Bearish"
              : presentField(topSignal?.regime ?? topSignal?.market_regime) !==
                  "Not available"
                ? presentField(topSignal?.regime ?? topSignal?.market_regime)
                : "Neutral"
        }
        marketBiasDetail={
          topSignal
            ? signalHumanExplanation(topSignal)
            : "Live research bias appears when a gold signal is available."
        }
        currentPrice={liveMarketPrice}
        support={
          topSignal ? presentLevel(topSignal.support ?? topSignal.key_support) : "—"
        }
        resistance={
          topSignal
            ? presentLevel(topSignal.resistance ?? topSignal.key_resistance)
            : "—"
        }
        confidencePct={confPct}
        topSignal={topSignal}
        lastPrice={Number.isFinite(tickMid) ? tickMid : undefined}
      />

      <TradingPerformancePanel
          deals={deals}
          floatingPnl={floatingFromPositions}
          equity={Number.isFinite(equityNum) ? equityNum : NaN}
          currency={accountCurrency === "—" ? "USD" : accountCurrency}
          available={showMetrics && !activityUnavailable}
      />
    </div>
  );
}

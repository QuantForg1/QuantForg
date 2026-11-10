"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Cable, Layers } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DeskDataTable, type DeskColumn } from "@/components/desk/data-table";
import { DeskEmpty, DeskMetric, DeskSkeleton } from "@/components/desk/primitives";
import { IntelligenceDetail } from "@/components/trading/intelligence-detail";
import { OverviewReferenceDesk } from "@/components/trading/overview-reference-desk";
import { TradingPerformancePanel } from "@/components/trading/dashboard-intelligence/trading-performance-panel";
import { RiskIntelligencePanel } from "@/components/trading/dashboard-intelligence/risk-intelligence-panel";
import { RobotActivityPanel } from "@/components/trading/dashboard-intelligence/robot-activity-panel";
import {
  RecentActivityPanel,
  buildActivityFromAccount,
} from "@/components/trading/dashboard-intelligence/recent-activity-panel";
import {
  NotificationsStrip,
  mapPlatformNotifications,
} from "@/components/trading/dashboard-intelligence/notifications-strip";
import { SignalCard } from "@/components/trading/signal-card";
import { Dialog, SheetContent } from "@/components/ui/dialog";
import {
  mt5Api,
  platformApi,
  portfolioApi,
  signalCenterApi,
  tradingSessionApi,
} from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { deriveRiskIntelligence } from "@/lib/dashboard/risk-intelligence";
import {
  netDealPnl,
  startOfUtcDayMs,
} from "@/lib/dashboard/performance-window";
import { OWNER_RISK_POLICY_DISPLAY } from "@/lib/trading/owner-risk-policy-display";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
// Auth still required for session; Admin link removed from trader Home.
import { ApiError } from "@/lib/api/client";
import { toast } from "sonner";
import { TRADING_SYMBOL, XAUUSD_SPECS } from "@/lib/trading/gold-only";
import {
  lastUpdatedCopy,
  normalizeSignalCenterPayload,
  presentField,
  presentLevel,
  priceDisplay,
  researchAvailabilityAsCatalogue,
  researchDeskLiveTradingStatus,
  researchDeskStatusLabel,
  researchSignalsEmptyCopy,
  signalBoardDirection,
  signalHumanExplanation,
  SIGNAL_CENTER_QUERY_KEY,
  numericDisplay,
  positionExposureLabel,
  resolveConnectionPresentation,
  robotDisplayState,
  topResearchOpportunities,
  TRADER_POLL_MS,
  traderFacingErrorMessage,
  UNIVERSE_POLL_MS,
} from "@/lib/trading/trader-ux";

type Row = Record<string, unknown>;

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

function marketSessionName(at = new Date()): string {
  const hour = at.getUTCHours();
  if (hour >= 7 && hour < 16) return "London";
  if (hour >= 16 && hour < 21) return "New York";
  if (hour >= 0 && hour < 7) return "Tokyo";
  return "Sydney";
}

function statusTone(
  value: string,
): "success" | "warning" | "danger" | "neutral" {
  const v = value.toLowerCase();
  if (["connected", "healthy", "running", "enabled", "ready"].includes(v))
    return "success";
  if (["paused", "degraded", "starting", "connecting"].includes(v)) return "warning";
  if (
    [
      "disconnected",
      "error",
      "stopped",
      "blocked",
      "disabled",
      "broker_not_connected",
      "account_session_mismatch",
    ].includes(v)
  )
    return "danger";
  return "neutral";
}

export default function DashboardPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<Row | null>(null);

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
  const robotStatusQ = useQuery({
    queryKey: ["trading-robot-status"],
    queryFn: tradingSessionApi.robotStatus,
    retry: false,
    refetchInterval: TRADER_POLL_MS,
    staleTime: 10_000,
  });
  const notificationsQ = useQuery({
    queryKey: ["dashboard-notifications"],
    queryFn: () => platformApi.notifications(false),
    retry: false,
    refetchInterval: UNIVERSE_POLL_MS,
    staleTime: 15_000,
  });
  const tradingComponentsQ = useQuery({
    queryKey: ["trading-components-health"],
    queryFn: platformApi.tradingComponents,
    retry: false,
    refetchInterval: UNIVERSE_POLL_MS,
    staleTime: 20_000,
  });

  const session = asRecord(sessionQ.data);
  const connection = resolveConnectionPresentation(session);
  const positions = asList(portfolio.data?.positions).map(asRecord);
  const deals = asList(history.data?.deals).map(asRecord);
  const noBroker = connection.state === "BROKER_NOT_CONNECTED";
  const sessionMismatch = connection.state === "ACCOUNT_SESSION_MISMATCH";
  const robot = robotDisplayState(session, connection);
  const liveTradingHint = researchDeskLiveTradingStatus(connection, session.trading, {
    liveTradingState: session.live_trading_state,
    ordersMaySubmit: session.orders_may_submit,
    liveAuthorization: session.live_authorization,
  });

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
  const signalCopy = researchSignalsEmptyCopy({
    fetchError: Boolean(signalsQ.isError),
    fabricatedBlocked: research.fabricatedBlocked,
    empty: true,
  });

  const positionsUnavailable = Boolean(portfolio.isError) && !noBroker && !sessionMismatch;
  const activityUnavailable = Boolean(history.isError) && !noBroker && !sessionMismatch;
  const showMetrics =
    connection.connected && !sessionMismatch && !connection.accountUnavailable;

  const robotMut = useMutation({
    mutationFn: (action: "start" | "pause" | "stop") => {
      if (action === "start") return tradingSessionApi.startRobot();
      if (action === "pause") return tradingSessionApi.pauseRobot();
      return tradingSessionApi.stopRobot();
    },
    onSuccess: async (_data, action) => {
      toast.success(
        action === "start"
          ? "Robot started"
          : action === "pause"
            ? "Robot paused"
            : "Robot stopped",
      );
      await qc.invalidateQueries({ queryKey: ["trading-session"] });
    },
    onError: (e) =>
      toast.error(
        e instanceof ApiError
          ? traderFacingErrorMessage(e)
          : "Robot action failed",
      ),
  });

  const firstName = (user?.display_name || user?.email || "")
    .split(" ")[0]
    ?.split("@")[0] ?? "";

  const positionCols: DeskColumn<Row>[] = useMemo(
    () => [
      {
        id: "symbol",
        header: "Symbol",
        sortable: true,
        accessor: (r) => str(r.symbol),
        cell: (r) => <span className="font-medium">{str(r.symbol)}</span>,
      },
      {
        id: "side",
        header: "Side",
        accessor: (r) => positionExposureLabel(r.side),
        cell: (r) => {
          const side = positionExposureLabel(r.side);
          return (
            <Badge tone={side === "LONG" ? "success" : side === "SHORT" ? "danger" : "neutral"}>
              {side}
            </Badge>
          );
        },
      },
      {
        id: "volume",
        header: "Volume",
        accessor: (r) => num(r.volume),
        cell: (r) => <span className="tabular">{numericDisplay(r.volume)}</span>,
      },
      {
        id: "entry",
        header: "Entry",
        cell: (r) => <span className="tabular">{numericDisplay(r.open_price)}</span>,
      },
      {
        id: "current",
        header: "Current",
        cell: (r) => (
          <span className="tabular">
            {numericDisplay(r.current_price ?? r.price)}
          </span>
        ),
      },
      {
        id: "pnl",
        header: "P/L",
        sortable: true,
        accessor: (r) => num(r.profit),
        cell: (r) => {
          const pnl = num(r.profit);
          if (!Number.isFinite(pnl)) return <span className="tabular">—</span>;
          return (
            <span
              className={
                pnl >= 0
                  ? "tabular text-[var(--success)]"
                  : "tabular text-[var(--danger)]"
              }
            >
              {formatCurrency(pnl)}
            </span>
          );
        },
      },
      {
        id: "status",
        header: "Status",
        cell: (r) => <span>{str(r.status, "—")}</span>,
      },
    ],
    [],
  );

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
  const riskIntel = deriveRiskIntelligence({
    equity: session.equity,
    balance: session.balance,
    floatingPnl: floatingFromPositions,
    todayPnl: todayPnlRaw,
    openPositionCount: positions.length,
    riskLocked: session.risk_locked ?? session.daily_loss_exceeded,
    emergencyStop: session.emergency_stop ?? session.global_emergency_stop,
    liveAuthorization: session.live_authorization,
    ordersMaySubmit: session.orders_may_submit,
  });
  const activityItems = buildActivityFromAccount({
    positions,
    deals,
    riskState: riskIntel.state,
    riskReason: riskIntel.reason,
  });
  const notificationItems = mapPlatformNotifications(
    asList(notificationsQ.data).map(asRecord),
  );
  const robotStatus = asRecord(robotStatusQ.data);
  const components = asRecord(tradingComponentsQ.data);
  const componentsHealthy =
    tradingComponentsQ.isError
      ? null
      : components.status
        ? String(components.status).toLowerCase() === "ok" ||
          String(components.status).toLowerCase() === "healthy"
        : components.healthy == null
          ? null
          : Boolean(components.healthy);
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
    : topSignal
      ? priceDisplay(
          topSignal.mid ?? topSignal.price ?? topSignal.current_price,
          XAUUSD_SPECS.digits,
        )
      : "—";
  const sessionLabel = marketSessionName();
  const lastUpdateLabel =
    lastUpdatedCopy(research.asOf) ||
    (tickQ.dataUpdatedAt
      ? formatRelativeTime(new Date(tickQ.dataUpdatedAt))
      : "—");

  return (
    <div className="min-w-0 space-y-5">
      <PageHeader
        eyebrow="Overview"
        title={greeting}
        description={
          showMetrics
            ? "Your trading system is running smoothly. Here's your market overview."
            : "Account figures appear when your broker session is available. Market research and the chart use the platform feed independently."
        }
        actions={
          noBroker || sessionMismatch ? (
            <Button asChild>
              <Link href="/broker">
                <Cable className="h-4 w-4" /> Connect broker
              </Link>
            </Button>
          ) : (
            <Button variant="secondary" size="sm" asChild>
              <Link href="/signals">Open signals</Link>
            </Button>
          )
        }
      />

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
        openPositions={
          noBroker || sessionMismatch || positionsUnavailable
            ? "—"
            : String(positions.length)
        }
        pendingOrders={
          noBroker || sessionMismatch
            ? "—"
            : String(num(session.pending_orders) || 0)
        }
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
        dailyRiskLabel={
          !showMetrics
            ? "—"
            : dailyLossPctOfEquity != null
              ? `${dailyLossPctOfEquity.toFixed(1)}% / ${OWNER_RISK_POLICY_DISPLAY.dailyLossHaltPercent}%`
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
                  )} used of ${OWNER_RISK_POLICY_DISPLAY.dailyLossHaltPercent}% halt`
              : "Unavailable"
        }
        metricsUpdatedAt={metricsUpdatedAt}
        brokerConnected={showMetrics}
        marketLive={marketLive}
        marketFeedStatus={publicTickStatus || (marketLive ? "live" : "unavailable")}
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
        regime={
          topSignal
            ? presentField(topSignal.regime ?? topSignal.market_regime)
            : "—"
        }
        confidencePct={confPct}
        sessionName={sessionLabel}
        lastUpdate={lastUpdateLabel}
        topSignal={topSignal}
        lastPrice={Number.isFinite(tickMid) ? tickMid : undefined}
      />

      <div className="grid gap-4 xl:grid-cols-2">
        <TradingPerformancePanel
          deals={deals}
          floatingPnl={floatingFromPositions}
          equity={Number.isFinite(equityNum) ? equityNum : NaN}
          currency={accountCurrency === "—" ? "USD" : accountCurrency}
          available={showMetrics && !activityUnavailable}
        />
        <RiskIntelligencePanel
          equity={session.equity}
          balance={session.balance}
          floatingPnl={floatingFromPositions}
          todayPnl={todayPnlRaw}
          openPositionCount={
            noBroker || sessionMismatch || positionsUnavailable
              ? 0
              : positions.length
          }
          riskLocked={session.risk_locked ?? session.daily_loss_exceeded}
          emergencyStop={session.emergency_stop ?? session.global_emergency_stop}
          liveAuthorization={session.live_authorization}
          ordersMaySubmit={session.orders_may_submit}
          currency={accountCurrency === "—" ? "USD" : accountCurrency}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <RobotActivityPanel
          robotState={robot}
          brokerLabel={
            sessionQ.isError
              ? "Unavailable"
              : noBroker
                ? "Disconnected"
                : sessionMismatch
                  ? "Reconnect required"
                  : "Connected"
          }
          tradingAuthLabel={liveTradingHint.label}
          tradingAuthDetail={liveTradingHint.detail}
          lastHeartbeat={
            str(
              robotStatus.last_heartbeat_at ??
                session.last_heartbeat_at ??
                connection.lastVerified,
              "",
            ) || null
          }
          lastSignalLabel={
            topSignal
              ? `${str(topSignal.broker_symbol || topSignal.symbol, TRADING_SYMBOL)} · ${signalBoardDirection(topSignal)}`
              : "No live signal"
          }
          lastExecutionLabel={
            str(
              session.last_execution_at ??
                robotStatus.last_execution_at ??
                deals[0]?.time,
              "No execution recorded",
            )
          }
          lastExecutionResult={
            str(
              session.last_execution_result ??
                robotStatus.last_execution_result ??
                deals[0]?.status ??
                deals[0]?.comment,
              "—",
            )
          }
          omsLabel={
            str(
              session.oms_status ?? robotStatus.oms_status,
              session.orders_may_submit === false
                ? "Blocked"
                : showMetrics
                  ? "Ready"
                  : "Unavailable",
            )
          }
          lastSyncLabel={
            connection.lastVerified
              ? formatRelativeTime(connection.lastVerified)
              : metricsUpdatedAt || "—"
          }
          recentError={
            str(
              session.last_error ?? robotStatus.last_error ?? session.error,
              "",
            ) || null
          }
          componentsHealthy={componentsHealthy}
        />
        <NotificationsStrip
          items={notificationItems}
          unavailable={Boolean(notificationsQ.isError)}
        />
      </div>

      <RecentActivityPanel
        items={activityItems}
        unavailable={activityUnavailable || positionsUnavailable}
        noBroker={noBroker || sessionMismatch}
      />

      <details className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)]">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-[var(--fg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
          Desk details · signals, positions, and activity
        </summary>
        <div className="space-y-5 border-t border-[var(--border)] px-4 py-4">
      <section
        aria-label="Workspace status"
        className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg)]/30 px-4 py-3 text-sm"
      >
        <span>
          <span className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
            Research{" "}
          </span>
          <span className="font-medium text-[var(--fg)]">
            {researchDeskStatusLabel({
              fetchError: Boolean(signalsQ.isError),
              workerStatus: String(
                asRecord(research.researchAnalysis).status || "",
              ),
              availability: researchAvailability,
            })}
          </span>
        </span>
        <span>
          <span className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
            Broker{" "}
          </span>
          <span className="font-medium text-[var(--fg)]">
            {sessionQ.isError
              ? "Unavailable"
              : noBroker
                ? "Not connected"
                : sessionMismatch
                  ? "Reconnect required"
                  : "Connected"}
          </span>
        </span>
        <span>
          <span className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
            Live trading{" "}
          </span>
          <span className="font-medium text-[var(--fg)]">
            {liveTradingHint.label}
          </span>
        </span>
      </section>

      <section aria-labelledby="top-signals">
        <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="top-signals" className="text-sm font-medium text-[var(--fg)]">
              Top signals
            </h2>
            {lastUpdatedCopy(research.asOf) ? (
              <p className="mt-1 text-xs text-[var(--fg-subtle)]">{lastUpdatedCopy(research.asOf)}</p>
            ) : null}
          </div>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/signals">View all signals</Link>
          </Button>
        </div>
        <p className="mb-3 text-sm text-[var(--fg-muted)]">
          Research is not a trade authorization. Live Gold candles require an active broker connection.
        </p>
        {signalState === "UNAVAILABLE" ? (
          <DeskEmpty
            icon={Activity}
            title="Signals unavailable"
            description={signalCopy.description}
          />
        ) : signalState === "NOT_READY" || signalsQ.isLoading ? (
          <DeskSkeleton rows={3} />
        ) : signalState === "LIVE_EMPTY" || signalPreview.length === 0 ? (
          <DeskEmpty
            icon={Activity}
            title="No signals"
            description={signalCopy.description}
          />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Top signals">
            {signalPreview.map((row, i) => (
              <li key={str(row.broker_symbol || row.symbol, String(i))}>
                <SignalCard compact row={row} onOpen={() => setSelected(row)} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="open-positions">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 id="open-positions" className="text-sm font-medium text-[var(--fg)]">
            Open positions
          </h2>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/portfolio">View portfolio</Link>
          </Button>
        </div>
        {noBroker || sessionMismatch ? (
          <DeskEmpty
            icon={Layers}
            title={noBroker ? "No broker connected" : "Session mismatch"}
            description="Connect your broker to load your positions. Research and signals remain available."
            actionLabel="Connect Broker"
            actionHref="/broker"
          />
        ) : positionsUnavailable ? (
          <DeskEmpty
            icon={Layers}
            title="Positions unavailable"
            description="Your positions could not be loaded. This is not zero positions."
          />
        ) : (
          <div className="min-w-0 overflow-x-auto">
            <DeskDataTable
              columns={positionCols}
              rows={positions}
              rowKey={(r, i) => str(r.ticket, String(i))}
              searchKeys={(r) => `${str(r.symbol)} ${positionExposureLabel(r.side)}`}
              pageSize={8}
              aria-label="Open positions"
              empty={
                <DeskEmpty
                  icon={Layers}
                  title="No open positions"
                  description="No open positions on your account."
                />
              }
            />
          </div>
        )}
      </section>

      <section aria-labelledby="recent-activity">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 id="recent-activity" className="text-sm font-medium text-[var(--fg)]">
            Recent activity
          </h2>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/portfolio">View portfolio</Link>
          </Button>
        </div>
        {noBroker || sessionMismatch ? (
          <DeskEmpty
            icon={Activity}
            title="No activity yet"
            description="Fills appear after you connect your broker."
          />
        ) : activityUnavailable ? (
          <DeskEmpty
            icon={Activity}
            title="Activity unavailable"
            description="Your account could not be queried. This is not an empty history."
          />
        ) : deals.length === 0 ? (
          <DeskEmpty
            icon={Activity}
            title="No recent activity"
            description="No recent fills for your account."
          />
        ) : (
          <ul className="space-y-2">
            {deals.slice(0, 6).map((d, i) => {
              const pnl = num(d.profit);
              return (
                <li
                  key={str(d.ticket, String(i))}
                  className="flex min-w-0 items-center justify-between gap-2 rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-sm"
                >
                  <span className="truncate">
                    {str(d.symbol)} {positionExposureLabel(d.side)}
                  </span>
                  <span
                    className={
                      Number.isFinite(pnl) && pnl >= 0
                        ? "tabular text-[var(--success)]"
                        : Number.isFinite(pnl)
                          ? "tabular text-[var(--danger)]"
                          : "tabular"
                    }
                  >
                    {Number.isFinite(pnl) ? formatCurrency(pnl) : "—"}
                  </span>
                  <span className="shrink-0 text-xs text-[var(--fg-subtle)]">
                    {formatRelativeTime(str(d.time, ""))}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <details className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
        <summary className="cursor-pointer rounded-sm text-sm font-medium text-[var(--fg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
          Account details
        </summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <DeskMetric
            label="Balance"
            value={moneyOrDash(session.balance, showMetrics, accountCurrency)}
          />
          <DeskMetric
            label="Equity"
            value={moneyOrDash(session.equity, showMetrics, accountCurrency)}
          />
          <DeskMetric
            label="Margin"
            value={moneyOrDash(session.margin, showMetrics, accountCurrency)}
          />
          <DeskMetric
            label="Free margin"
            value={moneyOrDash(session.free_margin, showMetrics, accountCurrency)}
          />
        </div>
      </details>

      <details className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
        <summary className="cursor-pointer rounded-sm text-sm font-medium text-[var(--fg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
          Advanced · analysis controls
        </summary>
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={statusTone(robot)}>{robot}</Badge>
            <span className="text-xs text-[var(--fg-subtle)]">{liveTradingHint.detail}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={robotMut.isPending || noBroker || sessionMismatch || robot === "RUNNING"}
              onClick={() => robotMut.mutate("start")}
            >
              Start
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={robotMut.isPending || robot !== "RUNNING"}
              onClick={() => robotMut.mutate("pause")}
            >
              Pause
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={
                robotMut.isPending || (robot !== "RUNNING" && robot !== "PAUSED")
              }
              onClick={() => robotMut.mutate("stop")}
            >
              Stop
            </Button>
          </div>
        </div>
      </details>
        </div>
      </details>

      <Dialog open={selected != null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent aria-describedby={undefined}>
          {selected ? <IntelligenceDetail row={selected} kind="signal" /> : null}
        </SheetContent>
      </Dialog>
    </div>
  );
}

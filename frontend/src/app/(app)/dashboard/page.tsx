"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Cable, Layers, Shield } from "lucide-react";
import { WorkspaceChart } from "@/components/workspace/chart-panel";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DeskDataTable, type DeskColumn } from "@/components/desk/data-table";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { MarketCatalogueRows } from "@/components/trading/market-catalogue-rows";
import { IntelligenceDetail } from "@/components/trading/intelligence-detail";
import { SignalCard } from "@/components/trading/signal-card";
import { Dialog, SheetContent } from "@/components/ui/dialog";
import {
  marketUniverseApi,
  portfolioApi,
  signalCenterApi,
  tradingSessionApi,
} from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
// Auth still required for session; Admin link removed from trader Home.
import { ApiError } from "@/lib/api/client";
import { toast } from "sonner";
import {
  lastUpdatedCopy,
  MARKET_UNIVERSE_QUERY_KEY,
  mergeCatalogueRows,
  hasResearchSignal,
  knownInstrumentCountLabel,
  normalizeSignalCenterPayload,
  researchAvailabilityAsCatalogue,
  researchDeskLiveTradingStatus,
  researchDeskStatusLabel,
  researchSignalsEmptyCopy,
  researchUniverseViewState,
  skippedMalformedInstrumentCount,
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
import { filterTradingSymbolRecords } from "@/lib/trading/gold-only";

type Row = Record<string, unknown>;

function workspaceGreeting(now = new Date(), firstName = ""): string {
  const hour = now.getHours();
  const part =
    hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  return firstName ? `${part}, ${firstName}` : part;
}

function moneyOrUnavailable(raw: unknown, available: boolean): string {
  if (!available) return "Unavailable";
  if (raw == null || raw === "") return "Unavailable";
  const n = num(raw);
  return Number.isFinite(n) ? formatCurrency(n) : "Unavailable";
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
  const [timeframe, setTimeframe] = useState("M15");
  const [chartType, setChartType] = useState<"candles" | "line" | "area">("candles");
  const [showVolume, setShowVolume] = useState(true);
  const [chartFull, setChartFull] = useState(false);

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
  const robot = robotDisplayState(session, connection);
  const liveTradingHint = researchDeskLiveTradingStatus(connection, session.trading, {
    liveTradingState: session.live_trading_state,
    ordersMaySubmit: session.orders_may_submit,
    liveAuthorization: session.live_authorization,
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

  const universeQ = useQuery({
    queryKey: MARKET_UNIVERSE_QUERY_KEY,
    queryFn: () => marketUniverseApi.snapshot(),
    retry: false,
    refetchInterval: UNIVERSE_POLL_MS,
  });
  const universe = asRecord(universeQ.data);
  const instruments = filterTradingSymbolRecords(
    asList(universe.instruments).map(asRecord),
  );
  const catalogue = researchUniverseViewState({
    snapshotFetched: universeQ.isFetched,
    snapshotError: Boolean(universeQ.isError),
    catalogueSource: universe.catalogue_source,
    instrumentCount: instruments.length - skippedMalformedInstrumentCount(instruments),
  });
  const rows =
    catalogue === "LIVE_ROWS"
      ? mergeCatalogueRows(
          instruments,
          asList(asRecord(universe.opportunity_board).rows).map(asRecord),
        )
      : [];
  const marketPreview = [
    ...rows.filter(hasResearchSignal),
    ...rows.filter((row) => !hasResearchSignal(row)),
  ];

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
  const dayStart = new Date();
  dayStart.setHours(0, 0, 0, 0);
  let todayPnl: number | null = null;
  if (showMetrics && !history.isLoading && !history.isError) {
    todayPnl = 0;
    for (const deal of deals) {
      const when = Date.parse(str(deal.time));
      const profit = num(deal.profit);
      if (!Number.isFinite(when) || when < dayStart.getTime() || !Number.isFinite(profit)) continue;
      todayPnl += profit;
    }
  }
  const availableRaw = session.free_margin ?? session.margin_free ?? session.balance;
  const bid = num(session.bid);
  const ask = num(session.ask);
  const lastPrice =
    showMetrics && Number.isFinite(bid) && Number.isFinite(ask)
      ? (bid + ask) / 2
      : showMetrics && Number.isFinite(bid)
        ? bid
        : undefined;

  return (
    <div className="min-w-0 space-y-5">
      {sessionQ.isError ? (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3"
        >
          <p className="text-sm text-[var(--fg-muted)]">
            Trading session temporarily unavailable. Gold research still needs a reachable broker Gateway.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              void sessionQ.refetch();
            }}
          >
            Retry
          </Button>
        </div>
      ) : null}
      <PageHeader
        eyebrow="Overview"
        title={greeting}
        description="QuantForg workspace. Account figures appear only from the connected broker session."
        actions={
          noBroker || sessionMismatch ? (
            <Button asChild>
              <Link href="/broker">
                <Cable className="h-4 w-4" /> Connect broker
              </Link>
            </Button>
          ) : (
            <Button variant="secondary" size="sm" asChild>
              <Link href="/terminal">Open terminal</Link>
            </Button>
          )
        }
      />

      <section aria-label="Account statistics" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <article className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
          <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">Account equity</p>
          <p className="mt-1 text-xl font-semibold tabular">{moneyOrUnavailable(session.equity, showMetrics)}</p>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">Broker session equity</p>
        </article>
        <article className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
          <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">Available balance</p>
          <p className="mt-1 text-xl font-semibold tabular">{moneyOrUnavailable(availableRaw, showMetrics)}</p>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">Free margin when the session sends it</p>
        </article>
        <article className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
          <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">Today&apos;s P&amp;L</p>
          <p className={`mt-1 text-xl font-semibold tabular ${todayPnl != null && todayPnl < 0 ? "text-[var(--danger)]" : todayPnl != null && todayPnl > 0 ? "text-[var(--success)]" : ""}`}>
            {todayPnl == null ? "Unavailable" : formatCurrency(todayPnl)}
          </p>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">Closed deals since local midnight</p>
        </article>
        <article className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
          <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">Open positions</p>
          <p className="mt-1 text-xl font-semibold tabular">{showMetrics ? String(positions.length) : "—"}</p>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">{showMetrics ? "Live account" : "Connect a broker to load positions"}</p>
        </article>
        <article className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
          <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">Account risk</p>
          <p className="mt-1 text-xl font-semibold">{sessionQ.isError ? "Unavailable" : liveTradingHint.label}</p>
          <p className="mt-1 line-clamp-2 text-xs text-[var(--fg-muted)]">{liveTradingHint.detail}</p>
        </article>
      </section>

      <section
        aria-label="Workspace status"
        className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg-elevated)] px-4 py-2.5 text-sm"
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
        <span>
          <span className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
            Markets{" "}
          </span>
          <span className="font-medium text-[var(--fg)]">
            {catalogue === "LIVE_ROWS"
              ? knownInstrumentCountLabel(catalogue, marketPreview.length) || "Live"
              : catalogue === "LIVE_EMPTY"
                ? "Empty"
                : catalogue === "NOT_READY"
                  ? "Loading"
                  : "Unavailable"}
          </span>
        </span>
      </section>

      <div className="grid items-start gap-3 xl:grid-cols-[minmax(0,1.55fr)_minmax(260px,0.75fr)]">
        <section className="min-h-[22rem] overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)]" aria-label="XAUUSD chart">
          {showMetrics ? (
            <div className="h-[28rem]">
              <WorkspaceChart
                symbol={TRADING_SYMBOL}
                connected
                timeframe={timeframe}
                onTimeframeChange={setTimeframe}
                chartType={chartType}
                onChartTypeChange={setChartType}
                showVolume={showVolume}
                onShowVolumeChange={setShowVolume}
                fullscreen={chartFull}
                onFullscreenChange={setChartFull}
                lastPrice={lastPrice}
              />
            </div>
          ) : (
            <div className="flex h-full min-h-[12rem] flex-col justify-center px-5 py-6">
              <p className="text-sm font-medium">XAUUSD chart</p>
              <p className="mt-1 max-w-md text-sm text-[var(--fg-muted)]">
                Candles load from the broker gateway after the session connects. No sample prices are drawn in their place.
              </p>
              <Button className="mt-3 w-fit" size="sm" asChild>
                <Link href="/broker">Connect broker</Link>
              </Button>
            </div>
          )}
        </section>
        <section className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4" aria-labelledby="market-intel">
          <h2 id="market-intel" className="text-base font-semibold">AI Market Intelligence</h2>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">
            Research is not a trade authorization. Live Gold candles still require a reachable broker Gateway.
          </p>
          <dl className="mt-4 space-y-2 text-sm">
            <div className="flex justify-between gap-3 border-b border-[var(--border)] py-2">
              <dt className="text-[var(--fg-muted)]">Research</dt>
              <dd className="text-right font-medium">
                {researchDeskStatusLabel({
                  fetchError: Boolean(signalsQ.isError),
                  workerStatus: String(asRecord(research.researchAnalysis).status || ""),
                  availability: researchAvailability,
                })}
              </dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-[var(--border)] py-2">
              <dt className="text-[var(--fg-muted)]">Robot</dt>
              <dd><Badge tone={statusTone(robot)}>{robot}</Badge></dd>
            </div>
            <div className="flex justify-between gap-3 py-2">
              <dt className="text-[var(--fg-muted)]">Live trading</dt>
              <dd className="text-right font-medium">{liveTradingHint.label}</dd>
            </div>
          </dl>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" disabled={robotMut.isPending || noBroker || sessionMismatch || robot === "RUNNING"} onClick={() => robotMut.mutate("start")}>Start</Button>
            <Button size="sm" variant="secondary" disabled={robotMut.isPending || robot !== "RUNNING"} onClick={() => robotMut.mutate("pause")}>Pause</Button>
            <Button size="sm" variant="secondary" disabled={robotMut.isPending || (robot !== "RUNNING" && robot !== "PAUSED")} onClick={() => robotMut.mutate("stop")}>Stop</Button>
          </div>
          <p className="mt-3 flex items-start gap-2 text-xs text-[var(--fg-subtle)]">
            <Shield className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            {liveTradingHint.detail}
          </p>
        </section>
      </div>

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
          Research is not a trade authorization. Live Gold candles still require a reachable broker Gateway.
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

      <section aria-labelledby="markets-preview">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 id="markets-preview" className="text-sm font-medium text-[var(--fg)]">
            Markets
          </h2>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/markets">View all markets</Link>
          </Button>
        </div>
        {noBroker ? (
          <p className="mb-3 text-sm text-[var(--fg-muted)]" role="status">
            Global research is available without a broker. Live trading stays unavailable until you connect.
          </p>
        ) : null}
        {sessionMismatch ? (
          <p className="mb-3 text-sm text-[var(--warning)]" role="status">
            Broker session mismatch — live trading is blocked. Global research remains available.
          </p>
        ) : null}
        {catalogue === "UNAVAILABLE" ? (
          <DeskEmpty
            icon={Activity}
            title="Market catalogue unavailable"
            description="The global market catalogue is currently unavailable. This is not an empty market."
          />
        ) : catalogue === "NOT_READY" || universeQ.isLoading ? (
          <DeskSkeleton rows={3} />
        ) : catalogue === "LIVE_EMPTY" ? (
          <DeskEmpty
            icon={Activity}
            title="No markets in catalogue"
            description="The live catalogue was queried. No instruments are listed."
          />
        ) : (
          <MarketCatalogueRows rows={marketPreview} limit={8} compact enableDetail={false} />
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

      <Dialog open={selected != null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent aria-describedby={undefined}>
          {selected ? <IntelligenceDetail row={selected} kind="signal" /> : null}
        </SheetContent>
      </Dialog>
    </div>
  );
}

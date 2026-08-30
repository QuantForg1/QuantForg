"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Bot, Cable, Layers } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DeskDataTable, type DeskColumn } from "@/components/desk/data-table";
import { DeskEmpty, DeskError, DeskMetric, DeskSkeleton } from "@/components/desk/primitives";
import { ConnectionStatus } from "@/components/trading/connection-status";
import { MarketCatalogueRows } from "@/components/trading/market-catalogue-rows";
import {
  marketUniverseApi,
  portfolioApi,
  signalCenterApi,
  tradingSessionApi,
} from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps } from "@/lib/auth/ite-ops-access";
import { ApiError } from "@/lib/api/client";
import { toast } from "sonner";
import { directionTone, freshnessTone } from "@/components/trading/intelligence-detail";
import {
  catalogueViewState,
  isLiveBrokerCatalogue,
  lastUpdatedCopy,
  MARKET_UNIVERSE_QUERY_KEY,
  mergeCatalogueRows,
  hasResearchSignal,
  normalizeSignalCenterPayload,
  researchAvailabilityAsCatalogue,
  researchSignalsEmptyCopy,
  skippedMalformedInstrumentCount,
  SIGNAL_CENTER_QUERY_KEY,
  numericDisplay,
  positionExposureLabel,
  resolveConnectionPresentation,
  robotDisplayState,
  scoreDisplay,
  signalBoardDirection,
  signalFreshness,
  SIGNALS_NOT_AUTHORIZATION,
  RESEARCH_OPPORTUNITY,
  topResearchOpportunities,
  TRADER_POLL_MS,
  traderFacingErrorMessage,
  UNIVERSE_POLL_MS,
} from "@/lib/trading/trader-ux";

type Row = Record<string, unknown>;

function moneyOrUnavailable(raw: unknown, available: boolean): string {
  if (!available) return "—";
  if (raw == null || raw === "") return "—";
  const n = num(raw);
  return Number.isFinite(n) ? formatCurrency(n) : "—";
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
  const isOperator = canAccessIteOps(user);
  const qc = useQueryClient();

  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    refetchInterval: TRADER_POLL_MS,
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
  const liveCatalogue = isLiveBrokerCatalogue(session);
  const noBroker = connection.state === "BROKER_NOT_CONNECTED";
  const sessionMismatch = connection.state === "ACCOUNT_SESSION_MISMATCH";
  const robot = robotDisplayState(session, connection);

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
    enabled: connection.connected && !sessionMismatch && liveCatalogue,
    retry: false,
    refetchInterval: UNIVERSE_POLL_MS,
  });
  const universe = asRecord(universeQ.data);
  const instruments = asList(universe.instruments).map(asRecord);
  const catalogue = catalogueViewState({
    connected: connection.connected,
    mismatch: sessionMismatch,
    liveBrokerSession: liveCatalogue,
    catalogueUnavailable: connection.catalogueUnavailable,
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

  if (sessionQ.isLoading) {
    return (
      <div>
        <PageHeader title="Welcome back" description="Your account and markets." />
        <DeskSkeleton variant="page" />
      </div>
    );
  }

  if (sessionQ.isError) {
    return (
      <div>
        <PageHeader title="Welcome back" description="Your account and markets." />
        <DeskError
          message="Unable to load your trading session."
          onRetry={() => {
            void sessionQ.refetch();
          }}
        />
      </div>
    );
  }

  const greeting = firstName ? `Welcome back, ${firstName}` : "Welcome back";

  return (
    <div className="min-w-0 space-y-5">
      <PageHeader
        title={greeting}
        description={
          noBroker
            ? "Research signals are available without a broker. Connect to unlock account data and markets."
            : sessionMismatch
              ? "Your trading session needs to be reconnected."
              : "Your account, robot, signals, and markets."
        }
        actions={
          noBroker || sessionMismatch ? (
            <Button asChild>
              <Link href="/broker">
                <Cable className="h-4 w-4" /> Connect Broker
              </Link>
            </Button>
          ) : (
            <Button variant="secondary" size="sm" asChild>
              <Link href="/terminal">Open terminal</Link>
            </Button>
          )
        }
      />

      <ConnectionStatus session={session} />

      <section aria-labelledby="portfolio-snapshot">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 id="portfolio-snapshot" className="text-sm font-medium text-[var(--fg)]">
            Account snapshot
          </h2>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/portfolio">View portfolio</Link>
          </Button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <DeskMetric label="Balance" value={moneyOrUnavailable(session.balance, showMetrics)} />
          <DeskMetric label="Equity" value={moneyOrUnavailable(session.equity, showMetrics)} />
          <DeskMetric label="Margin" value={moneyOrUnavailable(session.margin, showMetrics)} />
          <DeskMetric
            label="Free margin"
            value={moneyOrUnavailable(session.free_margin, showMetrics)}
          />
        </div>
      </section>

      <section aria-labelledby="robot-status">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 id="robot-status" className="text-sm font-medium text-[var(--fg)]">
            Robot
          </h2>
          <Badge tone={statusTone(robot)}>{robot}</Badge>
        </div>
        {noBroker ? (
          <p className="mb-3 text-sm text-[var(--fg-muted)]">BROKER NOT CONNECTED</p>
        ) : sessionMismatch ? (
          <p className="mb-3 text-sm text-[var(--fg-muted)]">ACCOUNT SESSION MISMATCH</p>
        ) : null}
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
          {isOperator ? (
            <Button variant="secondary" size="sm" asChild>
              <Link href="/admin">
                <Bot className="h-4 w-4" /> Admin
              </Link>
            </Button>
          ) : null}
        </div>
      </section>

      <section aria-labelledby="top-signals">
        <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="top-signals" className="text-sm font-medium text-[var(--fg)]">
              Top opportunities
            </h2>
            {lastUpdatedCopy(research.asOf) ? (
              <p className="mt-1 text-xs text-[var(--fg-subtle)]">{lastUpdatedCopy(research.asOf)}</p>
            ) : null}
          </div>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/signals">View all signals</Link>
          </Button>
        </div>
        <p className="mb-3 text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
          {RESEARCH_OPPORTUNITY} · {SIGNALS_NOT_AUTHORIZATION}
        </p>
        {signalState === "UNAVAILABLE" ? (
          <DeskEmpty
            icon={Activity}
            title={signalCopy.title}
            description={signalCopy.description}
          />
        ) : signalState === "NOT_READY" || signalsQ.isLoading ? (
          <DeskSkeleton rows={3} />
        ) : signalState === "LIVE_EMPTY" || signalPreview.length === 0 ? (
          <DeskEmpty
            icon={Activity}
            title={signalCopy.title}
            description={signalCopy.description}
          />
        ) : (
          <ul className="space-y-2">
            {signalPreview.map((row, i) => {
              const dir = signalBoardDirection(row);
              const freshness = signalFreshness(row);
              return (
                <li
                  key={str(row.broker_symbol || row.symbol, String(i))}
                  className="flex items-center justify-between gap-2 rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-sm"
                >
                  <span className="truncate font-medium">
                    {str(row.broker_symbol || row.symbol)}
                  </span>
                  <Badge tone={directionTone(dir)}>{dir}</Badge>
                  <span className="tabular text-[var(--fg-muted)]">
                    {scoreDisplay(row.opportunity_score)}
                  </span>
                  <Badge tone={freshnessTone(freshness)}>{freshness}</Badge>
                </li>
              );
            })}
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
            title={noBroker ? "BROKER NOT CONNECTED" : "ACCOUNT SESSION MISMATCH"}
            description="Connect your broker to load your positions."
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
        {noBroker || sessionMismatch ? (
          <DeskEmpty
            icon={Activity}
            title="MARKETS UNAVAILABLE"
            description="Connect to see broker-discovered markets."
          />
        ) : catalogue === "UNAVAILABLE" ? (
          <DeskEmpty
            icon={Activity}
            title="MARKETS UNAVAILABLE"
            description="Broker market catalogue is currently unavailable. This is not an empty market."
          />
        ) : catalogue === "NOT_READY" || universeQ.isLoading ? (
          <DeskSkeleton rows={3} />
        ) : catalogue === "LIVE_EMPTY" ? (
          <DeskEmpty
            icon={Activity}
            title="No markets in catalogue"
            description="The live broker catalogue was queried. No instruments are listed for your account."
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
    </div>
  );
}

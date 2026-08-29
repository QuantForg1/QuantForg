"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Bot, Cable, Layers } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DeskDataTable, type DeskColumn } from "@/components/desk/data-table";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { ConnectionStatus } from "@/components/trading/connection-status";
import { MarketCatalogueRows } from "@/components/trading/market-catalogue-rows";
import {
  marketUniverseApi,
  portfolioApi,
  tradingSessionApi,
} from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps } from "@/lib/auth/ite-ops-access";
import { ApiError } from "@/lib/api/client";
import { toast } from "sonner";
import {
  catalogueViewState,
  defaultSortedSignals,
  isLiveBrokerCatalogue,
  mergeCatalogueRows,
  numericDisplay,
  resolveConnectionPresentation,
  robotDisplayState,
  scoreDisplay,
  signalAvailability,
  signalBoardDirection,
  SIGNALS_NOT_AUTHORIZATION,
  traderFacingErrorMessage,
  unavailableSignalsTitle,
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
    refetchInterval: 15_000,
  });
  const portfolio = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    retry: false,
  });
  const history = useQuery({
    queryKey: ["history"],
    queryFn: portfolioApi.history,
    retry: false,
  });

  const session = asRecord(sessionQ.data);
  const connection = resolveConnectionPresentation(session);
  const positions = asList(portfolio.data?.positions).map(asRecord);
  const deals = asList(history.data?.deals).map(asRecord);
  const liveCatalogue = isLiveBrokerCatalogue(session);
  const noBroker = connection.state === "BROKER_NOT_CONNECTED";
  const sessionMismatch = connection.state === "ACCOUNT_SESSION_MISMATCH";
  const robot = robotDisplayState(session, connection);

  const universeQ = useQuery({
    queryKey: ["market-universe-snapshot", "home"],
    queryFn: () => marketUniverseApi.snapshot(),
    enabled: connection.connected && !sessionMismatch && liveCatalogue,
    retry: false,
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
    instrumentCount: instruments.length,
  });
  const rows =
    catalogue === "LIVE_ROWS"
      ? mergeCatalogueRows(
          instruments,
          asList(asRecord(universe.opportunity_board).rows).map(asRecord),
        )
      : [];
  const signalState = signalAvailability(catalogue);
  const signalPreview =
    signalState === "LIVE_ROWS" ? defaultSortedSignals(rows).slice(0, 4) : [];
  const signalCopy = unavailableSignalsTitle({
    noBroker,
    mismatch: sessionMismatch,
    catalogue,
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
        accessor: (r) => str(r.side),
        cell: (r) => (
          <Badge tone={str(r.side).toLowerCase() === "buy" ? "success" : "warning"}>
            {str(r.side, "—")}
          </Badge>
        ),
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
            ? "Connect your broker to see your account and markets."
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
          ) : null
        }
      />

      <ConnectionStatus session={session} />

      <section aria-labelledby="account-overview">
        <h2 id="account-overview" className="mb-2 text-sm font-medium text-[var(--fg)]">
          Account overview
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Balance" value={moneyOrUnavailable(session.balance, showMetrics)} />
          <MetricCard label="Equity" value={moneyOrUnavailable(session.equity, showMetrics)} />
          <MetricCard label="Margin" value={moneyOrUnavailable(session.margin, showMetrics)} />
          <MetricCard
            label="Free margin"
            value={moneyOrUnavailable(session.free_margin, showMetrics)}
          />
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Robot</CardTitle>
            <Badge tone={statusTone(robot)}>{robot}</Badge>
          </CardHeader>
          <CardContent className="space-y-3">
            {noBroker ? (
              <p className="text-sm text-[var(--fg-muted)]">BROKER NOT CONNECTED</p>
            ) : sessionMismatch ? (
              <p className="text-sm text-[var(--fg-muted)]">ACCOUNT SESSION MISMATCH</p>
            ) : (
              <p className="text-sm text-[var(--fg-muted)]">
                Your robot for this connected account.
              </p>
            )}
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
            {isOperator ? (
              <Button variant="secondary" size="sm" asChild>
                <Link href="/admin">
                  <Bot className="h-4 w-4" /> Admin portal
                </Link>
              </Button>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Signals</CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/signals">View all</Link>
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
              {SIGNALS_NOT_AUTHORIZATION}
            </p>
            {noBroker || sessionMismatch || signalState === "UNAVAILABLE" ? (
              <DeskEmpty
                icon={Activity}
                title={signalCopy.title}
                description={signalCopy.description}
              />
            ) : signalState === "NOT_READY" || universeQ.isLoading ? (
              <DeskSkeleton rows={3} />
            ) : signalState === "LIVE_EMPTY" || signalPreview.length === 0 ? (
              <DeskEmpty
                icon={Activity}
                title="No ranked signals"
                description="The live catalogue was queried. No ranked research signals right now."
              />
            ) : (
              <ul className="space-y-2">
                {signalPreview.map((row, i) => {
                  const dir = signalBoardDirection(row);
                  return (
                    <li
                      key={str(row.broker_symbol || row.symbol, String(i))}
                      className="flex items-center justify-between gap-2 rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-sm"
                    >
                      <span className="truncate font-medium">
                        {str(row.broker_symbol || row.symbol)}
                      </span>
                      <Badge tone={dir === "BUY" ? "success" : dir === "SELL" ? "warning" : "neutral"}>
                        {dir}
                      </Badge>
                      <span className="tabular text-[var(--fg-muted)]">
                        {scoreDisplay(row.opportunity_score)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Positions</CardTitle>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/portfolio">View all</Link>
          </Button>
        </CardHeader>
        <CardContent>
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
                searchKeys={(r) => `${str(r.symbol)} ${str(r.side)}`}
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
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Market snapshot</CardTitle>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/markets">View all</Link>
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {noBroker || sessionMismatch ? (
            <DeskEmpty
              icon={Activity}
              title="BROKER NOT CONNECTED"
              description="Connect to see broker-discovered markets."
            />
          ) : catalogue === "UNAVAILABLE" ? (
            <DeskEmpty
              icon={Activity}
              title="CATALOGUE UNAVAILABLE"
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
            <MarketCatalogueRows rows={rows} limit={8} showFilters compact />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Recent activity</CardTitle>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/portfolio">Portfolio</Link>
          </Button>
        </CardHeader>
        <CardContent>
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
                      {str(d.symbol)} {str(d.side)}
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
        </CardContent>
      </Card>
    </div>
  );
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3">
      <p className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
        {label}
      </p>
      <p className="mt-1 truncate tabular text-lg font-semibold text-[var(--fg)]">
        {value}
      </p>
    </div>
  );
}

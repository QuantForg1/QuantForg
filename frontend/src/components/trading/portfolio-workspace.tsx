"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Layers } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskDataTable, type DeskColumn } from "@/components/desk/data-table";
import { DeskEmpty, DeskError, DeskMetric, DeskSkeleton } from "@/components/desk/primitives";
import { portfolioApi, tradingSessionApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import {
  accountHealth,
  accountHealthSummary,
  closedTradeStats,
  exposureUnavailableReason,
  isLiveBrokerCatalogue,
  moneyDisplay,
  numericDisplay,
  periodPnl,
  portfolioAccount,
  positionExposureLabel,
  resolveConnectionPresentation,
  robotDisplayState,
  TRADER_POLL_MS,
  traderFacingErrorMessage,
  UNIVERSE_POLL_MS,
} from "@/lib/trading/trader-ux";

type Row = Record<string, unknown>;

function healthTone(state: string): "success" | "warning" | "danger" | "neutral" {
  if (state === "Healthy") return "success";
  if (state === "Attention") return "warning";
  if (state === "Blocked") return "danger";
  return "neutral";
}

function robotTone(robot: string): "success" | "warning" | "danger" | "neutral" {
  if (robot === "RUNNING" || robot === "READY") return "success";
  if (robot === "PAUSED" || robot === "STOPPED") return "warning";
  return "danger";
}

export function PortfolioWorkspace() {
  const qc = useQueryClient();

  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    refetchInterval: TRADER_POLL_MS,
  });
  const portfolioQ = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    retry: false,
    refetchInterval: TRADER_POLL_MS,
  });
  const historyQ = useQuery({
    queryKey: ["history"],
    queryFn: portfolioApi.history,
    retry: false,
    refetchInterval: UNIVERSE_POLL_MS,
  });

  const session = asRecord(sessionQ.data);
  const connection = resolveConnectionPresentation(session);
  const noBroker = connection.state === "BROKER_NOT_CONNECTED";
  const mismatch = connection.state === "ACCOUNT_SESSION_MISMATCH";
  const liveCatalogue = isLiveBrokerCatalogue(session);
  const robot = robotDisplayState(session, connection);

  const portfolio = asRecord(portfolioQ.data);
  const account = portfolioAccount(portfolio);
  const positions = asList(portfolio.positions).map(asRecord);
  const deals = asList(historyQ.data?.deals ?? portfolio.history_deals).map(asRecord);

  const metricsReady =
    connection.connected && !mismatch && !connection.accountUnavailable && !portfolioQ.isError;
  const positionsUnavailable = Boolean(portfolioQ.isError) && !noBroker && !mismatch;
  const historyUnavailable = Boolean(historyQ.isError) && !noBroker && !mismatch;
  const currency = str(account.currency || session.currency, "USD");

  const money = (value: unknown) => {
    const raw = moneyDisplay(value, metricsReady);
    if (raw === "Unavailable" || raw === "—") return "Unavailable";
    const n = num(value);
    return Number.isFinite(n)
      ? formatCurrency(n, currency === "—" ? "USD" : currency)
      : raw;
  };

  const now = Date.now();
  const startOfDay = new Date();
  startOfDay.setHours(0, 0, 0, 0);
  const weekAgo = now - 7 * 24 * 60 * 60 * 1000;
  const monthStart = new Date();
  monthStart.setDate(1);
  monthStart.setHours(0, 0, 0, 0);
  const historyReady = !historyUnavailable && !noBroker && !mismatch && historyQ.isFetched;
  const todayPnl = historyReady ? periodPnl(deals, startOfDay.getTime()) : "Unavailable";
  const weekPnl = historyReady ? periodPnl(deals, weekAgo) : "Unavailable";
  const monthPnl = historyReady ? periodPnl(deals, monthStart.getTime()) : "Unavailable";
  const tradeStats = closedTradeStats(deals, historyReady);
  const formatPeriod = (raw: string) => {
    if (raw === "—" || raw === "Unavailable") return "Unavailable";
    const n = Number(raw);
    return Number.isFinite(n)
      ? formatCurrency(n, currency === "—" ? "USD" : currency)
      : "Unavailable";
  };

  const health = accountHealth({
    connection,
    robot,
    liveCatalogue,
    positionsError: positionsUnavailable,
    positionsLoaded: portfolioQ.isFetched && !portfolioQ.isError,
    marginAvailable: metricsReady && numericDisplay(account.margin ?? session.margin) !== "—",
    accountUnavailable: connection.accountUnavailable || Boolean(portfolioQ.isError),
  });

  const robotMut = useMutation({
    mutationFn: (action: "start" | "pause" | "stop") => {
      if (action === "start") return tradingSessionApi.startRobot();
      if (action === "pause") return tradingSessionApi.pauseRobot();
      return tradingSessionApi.stopRobot();
    },
    onSuccess: async (_data, action) => {
      toast.success(
        action === "start" ? "Robot started" : action === "pause" ? "Robot paused" : "Robot stopped",
      );
      await qc.invalidateQueries({ queryKey: ["trading-session"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? traderFacingErrorMessage(e) : "Robot action failed"),
  });

  const positionCols: DeskColumn<Row>[] = useMemo(
    () => [
      {
        id: "symbol",
        header: "Instrument",
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
        cell: (r) => <span className="tabular">{numericDisplay(r.current_price)}</span>,
      },
      {
        id: "sl",
        header: "SL",
        cell: (r) => <span className="tabular">{numericDisplay(r.stop_loss)}</span>,
      },
      {
        id: "tp",
        header: "TP",
        cell: (r) => <span className="tabular">{numericDisplay(r.take_profit)}</span>,
      },
      {
        id: "pnl",
        header: "Unrealized P&L",
        sortable: true,
        accessor: (r) => num(r.profit),
        cell: (r) => {
          const pnl = num(r.profit);
          if (!Number.isFinite(pnl)) return <span className="tabular">—</span>;
          return (
            <span className={pnl >= 0 ? "tabular text-[var(--success)]" : "tabular text-[var(--danger)]"}>
              {formatCurrency(pnl, currency === "—" ? "USD" : currency)}
            </span>
          );
        },
      },
      {
        id: "duration",
        header: "Duration",
        cell: (r) => <span>{formatRelativeTime(str(r.opened_at, "")) || "—"}</span>,
      },
      {
        id: "status",
        header: "Status",
        cell: (r) => <span>{str(r.status, "Open")}</span>,
      },
    ],
    [currency],
  );

  if (sessionQ.isLoading) {
    return (
      <div>
        <PageHeader
          eyebrow="Account"
          title="Portfolio"
          description="Equity, margin, positions, and exposure from your own broker session."
        />
        <DeskSkeleton variant="page" />
      </div>
    );
  }

  if (sessionQ.isError) {
    return (
      <div>
        <PageHeader
          eyebrow="Account"
          title="Portfolio"
          description="Equity, margin, positions, and exposure from your own broker session."
        />
        <DeskError
          message="Unable to load your trading session."
          onRetry={() => {
            void sessionQ.refetch();
          }}
        />
      </div>
    );
  }

  return (
    <div className="min-w-0 space-y-5">
      <PageHeader
        eyebrow="Account"
        title="Portfolio"
        description="Equity, margin, positions, and exposure from your own broker session. Never fabricated."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" asChild>
              <Link href="/signals">Signals</Link>
            </Button>
            <Button variant="secondary" size="sm" asChild>
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />

      {noBroker ? (
        <DeskEmpty
          icon={Activity}
          title="No broker connected"
          description="Connect your broker to load this account's portfolio. Research and signals remain available."
          actionLabel="Connect Broker"
          actionHref="/broker"
        />
      ) : mismatch ? (
        <DeskEmpty
          icon={Activity}
          title="Session mismatch"
          description="This terminal is bound to another session. Reconnect your own account."
          actionLabel="Reconnect"
          actionHref="/broker"
        />
      ) : null}

      <section aria-labelledby="portfolio-kpis">
        <h2 id="portfolio-kpis" className="mb-2 text-sm font-medium text-[var(--fg)]">
          Current account
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
          <DeskMetric label="Balance" value={money(account.balance ?? session.balance)} />
          <DeskMetric label="Equity" value={money(account.equity ?? session.equity)} />
          <DeskMetric label="Free margin" value={money(account.free_margin ?? session.free_margin)} />
          <DeskMetric label="Margin" value={money(account.margin ?? session.margin)} />
          <DeskMetric
            label="Margin level"
            value={
              metricsReady
                ? numericDisplay(account.margin_level ?? session.margin_level) === "—"
                  ? "Unavailable"
                  : numericDisplay(account.margin_level ?? session.margin_level)
                : "Unavailable"
            }
          />
          <DeskMetric label="Unrealized P&L" value={money(account.profit ?? session.profit)} />
          <DeskMetric
            label="Realized P&L"
            value={
              tradeStats.realized === "—" || tradeStats.realized.startsWith("INSUFFICIENT")
                ? tradeStats.realized === "—"
                  ? "Unavailable"
                  : tradeStats.realized
                : formatPeriod(tradeStats.realized)
            }
          />
          <DeskMetric
            label="Open positions"
            value={
              noBroker
                ? "Broker not connected"
                : mismatch
                  ? "Waiting for broker"
                  : positionsUnavailable || portfolioQ.isLoading
                    ? "Unavailable"
                    : positions.length === 0
                      ? "No open positions"
                      : String(positions.length)
            }
          />
          <DeskMetric label="Today" value={formatPeriod(todayPnl)} />
          <DeskMetric label="This week" value={formatPeriod(weekPnl)} />
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Robot control</CardTitle>
            <Badge tone={noBroker ? "warning" : robotTone(robot)}>
              {noBroker ? "Not connected" : robot}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2">
                <p className="text-xs uppercase tracking-wide text-[var(--fg-subtle)]">
                  Research analysis
                </p>
                <p className="mt-1 text-sm text-[var(--fg)]">ACTIVE</p>
                <p className="text-xs text-[var(--fg-muted)]">
                  Scans supported markets via Signals — broker not required.
                </p>
              </div>
              <div className="rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2">
                <p className="text-xs uppercase tracking-wide text-[var(--fg-subtle)]">
                  Live trading
                </p>
                <p className="mt-1 text-sm text-[var(--fg)]">
                  {noBroker || mismatch ? "DISABLED" : robot === "RUNNING" ? "ON" : "OFF"}
                </p>
                <p className="text-xs text-[var(--fg-muted)]">
                  Explicit opt-in only. Connecting a broker does not enable live trading.
                </p>
              </div>
            </div>
            <p className="text-sm text-[var(--fg-muted)]">
              Start / Pause / Stop control live trading for this owned session. Research signals stay on{" "}
              <Link href="/signals" className="text-[var(--accent)] underline-offset-2 hover:underline">
                /signals
              </Link>
              .
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={robotMut.isPending || noBroker || mismatch || robot === "RUNNING"}
                onClick={() => robotMut.mutate("start")}
              >
                Start live trading
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
                disabled={robotMut.isPending || (robot !== "RUNNING" && robot !== "PAUSED")}
                onClick={() => robotMut.mutate("stop")}
              >
                Stop
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Account health</CardTitle>
            <Badge tone={healthTone(accountHealthSummary(health))}>
              {accountHealthSummary(health)}
            </Badge>
          </CardHeader>
          <CardContent>
            <ul className="grid gap-2 sm:grid-cols-2">
              {health.map((item) => (
                <li
                  key={item.id}
                  className="flex items-center justify-between gap-2 rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-[var(--fg)]">{item.label}</p>
                    <p className="truncate text-xs text-[var(--fg-subtle)]">{item.detail}</p>
                  </div>
                  <Badge tone={healthTone(item.state)}>{item.state}</Badge>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Open positions</CardTitle>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/terminal">Terminal</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {noBroker || mismatch ? (
            <DeskEmpty
              icon={Layers}
              title={noBroker ? "No broker connected" : "Session mismatch"}
              description="Connect your own broker to load positions."
            />
          ) : portfolioQ.isLoading ? (
            <DeskSkeleton rows={4} />
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
                pageSize={10}
                aria-label="Open positions"
                empty={
                  <DeskEmpty
                    icon={Layers}
                    title="No open positions"
                    description="No open positions on this account."
                  />
                }
              />
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Exposure</CardTitle>
          </CardHeader>
          <CardContent>
            <DeskEmpty
              icon={Activity}
              title={exposureUnavailableReason()}
              description="Asset-class and concentration exposure are not provided by the account APIs."
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Performance</CardTitle>
          </CardHeader>
          <CardContent>
            {noBroker || mismatch ? (
              <DeskEmpty
                icon={Activity}
                title="No broker connected"
                description="Connect your broker to load account history."
              />
            ) : historyQ.isLoading ? (
              <DeskSkeleton rows={3} />
            ) : historyUnavailable ? (
              <DeskEmpty
                icon={Activity}
                title="History unavailable"
                description="Closed-trade history could not be loaded. This is not a zero performance chart."
              />
            ) : deals.length === 0 ? (
              <DeskEmpty
                icon={Activity}
                title="INSUFFICIENT SAMPLE"
                description="No closed trades are available for this account yet."
              />
            ) : (
              <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <DeskMetric label="Daily P/L" value={formatPeriod(todayPnl)} />
                  <DeskMetric label="Weekly P/L" value={formatPeriod(weekPnl)} />
                  <DeskMetric label="Monthly P/L" value={formatPeriod(monthPnl)} />
                  <DeskMetric label="Win rate" value={tradeStats.winRate} />
                  <DeskMetric label="Profit factor" value={tradeStats.profitFactor} />
                  <DeskMetric label="Drawdown" value={tradeStats.drawdown} />
                </div>
                <ul className="space-y-2" aria-label="Recent closed trades">
                {deals.slice(0, 8).map((d, i) => {
                  const pnl = num(d.profit);
                  return (
                    <li
                      key={str(d.ticket, String(i))}
                      className="flex items-center justify-between gap-2 rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-sm"
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
                        {Number.isFinite(pnl) ? formatCurrency(pnl, currency === "—" ? "USD" : currency) : "—"}
                      </span>
                    </li>
                  );
                })}
              </ul>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

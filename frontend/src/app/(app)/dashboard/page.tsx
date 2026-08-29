"use client";

import { useMemo, useState } from "react";
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
  brokersApi,
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
  isLiveBrokerCatalogue,
  mergeCatalogueRows,
  resolveConnectionPresentation,
  traderFacingErrorMessage,
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
  if (["connected", "healthy", "running", "enabled", "robot_ready", "ready"].includes(v))
    return "success";
  if (["paused", "degraded", "starting", "catalogue_unavailable", "connecting"].includes(v))
    return "warning";
  if (
    [
      "disconnected",
      "error",
      "stopped",
      "disabled",
      "no_broker",
      "session_mismatch",
      "broker_not_connected",
    ].includes(v)
  )
    return "danger";
  return "neutral";
}

function maskAccountId(raw: string): string {
  const digits = raw.replace(/\D/g, "") || raw.trim();
  if (digits.length <= 4) return "••••";
  return `${digits.slice(0, 2)}•••${digits.slice(-2)}`;
}

function greeting(name: string): string {
  const h = new Date().getHours();
  const part =
    h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  const trimmed = name.trim();
  return trimmed ? `${part}, ${trimmed}` : part;
}

function uxCopy(state: string): { title: string; detail: string } {
  switch (state) {
    case "NO_BROKER":
    case "BROKER_NOT_CONNECTED":
      return {
        title: "BROKER NOT CONNECTED",
        detail: "QuantForg uses your connected account only — never a shared default.",
      };
    case "CONNECTING":
      return {
        title: "CONNECTING",
        detail: "Validating the session. Your password is never stored in the browser.",
      };
    case "CONNECTED":
    case "ROBOT_READY":
      return {
        title: "CONNECTED",
        detail: "Your account is linked. Start the robot when you are ready.",
      };
    case "ROBOT_RUNNING":
      return {
        title: "Robot is running.",
        detail: "Live execution is bound to your connected account.",
      };
    case "ROBOT_PAUSED":
      return {
        title: "Robot is paused.",
        detail: "Your account session is still connected.",
      };
    case "SESSION_MISMATCH":
    case "ACCOUNT_SESSION_MISMATCH":
      return {
        title: "ACCOUNT_SESSION_MISMATCH",
        detail: "This workspace cannot use another account’s live terminal session.",
      };
    case "CATALOGUE_UNAVAILABLE":
      return {
        title: "CONNECTED",
        detail: "Market catalogue is unavailable. This is not an empty market.",
      };
    case "ATTENTION":
      return {
        title: "Robot needs attention.",
        detail: "Check your broker connection, then retry.",
      };
    default:
      return {
        title: "Your account",
        detail: "Status is scoped to this login.",
      };
  }
}

export default function DashboardPage() {
  const { user } = useAuth();
  const isOperator = canAccessIteOps(user);
  const qc = useQueryClient();
  const [selectedAccountId, setSelectedAccountId] = useState("");

  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    refetchInterval: 15_000,
  });
  const accountsQ = useQuery({
    queryKey: ["broker-accounts"],
    queryFn: brokersApi.accounts,
    retry: false,
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
  const uxState = str(session.ux_state, "NO_BROKER");
  const copy = uxCopy(connection.state === "CONNECTED" ? uxState : connection.state);
  const positions = asList(portfolio.data?.positions).map(asRecord);
  const deals = asList(history.data?.deals).map(asRecord);
  const ownedAccounts = asList(accountsQ.data).map(asRecord);
  const liveCatalogue = isLiveBrokerCatalogue(session);
  const noBroker = connection.state === "BROKER_NOT_CONNECTED";
  const sessionMismatch = connection.state === "ACCOUNT_SESSION_MISMATCH";
  const catalogueUnavailable = connection.catalogueUnavailable || !liveCatalogue;

  const universeQ = useQuery({
    queryKey: ["market-universe-snapshot", "home"],
    queryFn: () => marketUniverseApi.snapshot(),
    enabled: connection.connected && !sessionMismatch && liveCatalogue,
    retry: false,
  });
  const universe = asRecord(universeQ.data);
  const instruments = asList(universe.instruments).map(asRecord);
  const universeLive =
    str(universe.catalogue_source) === "LIVE_BROKER" && instruments.length > 0;
  const rows = universeLive
    ? mergeCatalogueRows(
        instruments,
        asList(asRecord(universe.opportunity_board).rows).map(asRecord),
      )
    : [];

  const robot = str(session.robot, "Stopped");
  const robotDisplay =
    uxState === "ROBOT_READY" && robot === "Stopped" ? "Ready" : robot;
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
        header: "Direction",
        accessor: (r) => str(r.side),
        cell: (r) => (
          <Badge tone={str(r.side).toLowerCase() === "buy" ? "success" : "warning"}>
            {str(r.side)}
          </Badge>
        ),
      },
      {
        id: "size",
        header: "Size",
        accessor: (r) => num(r.volume),
        cell: (r) => <span className="tabular">{str(r.volume, "—")}</span>,
      },
      {
        id: "entry",
        header: "Entry",
        cell: (r) => <span className="tabular">{str(r.open_price, "—")}</span>,
      },
      {
        id: "current",
        header: "Current",
        cell: (r) => (
          <span className="tabular">{str(r.current_price, str(r.price, "—"))}</span>
        ),
      },
      {
        id: "pnl",
        header: "PnL",
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
    ],
    [],
  );

  if (sessionQ.isLoading) {
    return (
      <div>
        <PageHeader title="Home" description="Your account, broker, and robot." />
        <DeskSkeleton variant="page" />
      </div>
    );
  }

  if (sessionQ.isError) {
    return (
      <div>
        <PageHeader title="Home" description="Your account, broker, and robot." />
        <DeskError
          message="DATA UNAVAILABLE. Unable to load your trading session."
          onRetry={() => {
            void sessionQ.refetch();
          }}
        />
      </div>
    );
  }

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title={greeting(firstName)}
        description={copy.title}
        actions={
          <>
            {noBroker || sessionMismatch ? (
              <Button asChild>
                <Link href="/broker">
                  <Cable className="h-4 w-4" /> Connect Broker
                </Link>
              </Button>
            ) : null}
          </>
        }
      />

      <p className="max-w-2xl text-sm text-[var(--fg-muted)]">{copy.detail}</p>

      <ConnectionStatus session={session} />

      {ownedAccounts.length > 1 ? (
        <label className="flex min-w-0 max-w-md flex-col gap-1 text-sm">
          <span className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
            Current account
          </span>
          <select
            className="h-10 w-full min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3"
            value={selectedAccountId}
            onChange={(e) => {
              setSelectedAccountId(e.target.value);
              void sessionQ.refetch();
              void portfolio.refetch();
              void history.refetch();
            }}
          >
            <option value="">
              {str(session.account, "Connected account")} · {str(session.server)}
            </option>
            {ownedAccounts.map((row, i) => {
              const id = str(row.id, String(i));
              const ext = maskAccountId(
                str(row.external_account_id, str(row.label)),
              );
              return (
                <option key={id} value={id}>
                  {ext} · {str(row.server, "Broker")}
                </option>
              );
            })}
          </select>
        </label>
      ) : null}

      {noBroker ? (
        <Card>
          <CardContent className="py-6">
            <DeskEmpty
              icon={Cable}
              title="BROKER NOT CONNECTED"
              description="Connect your broker account to start. There is no shared or default account."
              actionLabel="Connect Broker"
              actionHref="/broker"
            />
          </CardContent>
        </Card>
      ) : null}

      {sessionMismatch ? (
        <Card>
          <CardContent className="py-6">
            <DeskEmpty
              icon={Cable}
              title="ACCOUNT_SESSION_MISMATCH"
              description="This live terminal is bound to another session. Reconnect your own account before trading. Concurrent independent live logins are not supported."
              actionLabel="Reconnect"
              actionHref="/broker"
            />
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Balance"
          value={moneyOrUnavailable(session.balance, showMetrics)}
        />
        <MetricCard
          label="Equity"
          value={moneyOrUnavailable(session.equity, showMetrics)}
        />
        <MetricCard
          label="Margin"
          value={moneyOrUnavailable(session.margin, showMetrics)}
        />
        <MetricCard
          label="Free margin"
          value={moneyOrUnavailable(session.free_margin, showMetrics)}
        />
      </div>
      {connection.accountUnavailable && connection.connected ? (
        <p className="text-xs text-[var(--warning)]">DATA UNAVAILABLE — account figures are hidden, not shown as zero.</p>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Your robot</CardTitle>
            <Badge tone={statusTone(robotDisplay)}>{robotDisplay}</Badge>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-[var(--fg-muted)]">
            <p>
              {noBroker
                ? "BROKER NOT CONNECTED"
                : sessionMismatch
                  ? "ACCOUNT_SESSION_MISMATCH"
                  : copy.title}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={
                  robotMut.isPending || noBroker || sessionMismatch || robot === "Running"
                }
                onClick={() => robotMut.mutate("start")}
              >
                Start
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={robotMut.isPending || robot !== "Running"}
                onClick={() => robotMut.mutate("pause")}
              >
                Pause
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={
                  robotMut.isPending || (robot !== "Running" && robot !== "Paused")
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
            ) : (
              <p className="text-xs text-[var(--fg-subtle)]">
                You can start or stop the robot for this connected account only.
                Concurrent independent live logins require additional terminals.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
          </CardHeader>
          <CardContent>
            {noBroker || sessionMismatch ? (
              <DeskEmpty
                icon={Activity}
                title="EMPTY"
                description="Activity appears after you connect. Fills belong to your account only."
              />
            ) : activityUnavailable ? (
              <DeskEmpty
                icon={Activity}
                title="DATA UNAVAILABLE"
                description="Your account could not be queried. This is not an empty history."
              />
            ) : deals.length === 0 ? (
              <DeskEmpty
                icon={Activity}
                title="EMPTY"
                description="No recent fills for this connected account."
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

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Positions</CardTitle>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/terminal">Terminal</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {noBroker || sessionMismatch ? (
            <DeskEmpty
              icon={Layers}
              title={noBroker ? "BROKER NOT CONNECTED" : "ACCOUNT_SESSION_MISMATCH"}
              description="Connect your broker to load live exposure. Unavailable data is not shown as zero."
              actionLabel="Connect Broker"
              actionHref="/broker"
            />
          ) : positionsUnavailable ? (
            <DeskEmpty
              icon={Layers}
              title="DATA UNAVAILABLE"
              description="POSITIONS UNAVAILABLE. This is not zero positions."
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
                    title="EMPTY"
                    description="No open positions on this connected account."
                  />
                }
              />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Markets</CardTitle>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/markets">Open markets</Link>
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {noBroker || sessionMismatch ? (
            <DeskEmpty
              icon={Activity}
              title="BROKER NOT CONNECTED"
              description="Connect to see broker-discovered markets. Research cannot place orders."
            />
          ) : catalogueUnavailable || (universeQ.isFetched && !universeLive) ? (
            <DeskEmpty
              icon={Activity}
              title="CATALOGUE UNAVAILABLE"
              description="Connect or verify your broker and refresh market data. This is not an empty market."
            />
          ) : universeQ.isLoading ? (
            <DeskSkeleton rows={3} />
          ) : universeQ.isError ? (
            <DeskEmpty
              icon={Activity}
              title="CATALOGUE UNAVAILABLE"
              description="Connect or verify your broker and refresh market data."
            />
          ) : rows.length === 0 ? (
            <DeskEmpty
              icon={Activity}
              title="EMPTY"
              description="The live catalogue was queried. Nothing is listed for this session."
            />
          ) : (
            <MarketCatalogueRows rows={rows} limit={6} />
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

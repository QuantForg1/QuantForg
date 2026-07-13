"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Cable,
  Layers,
  Radio,
  Server,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { LazyEquityChart } from "@/components/charts/lazy";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DeskDataTable, type DeskColumn } from "@/components/desk/data-table";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { PageMotion, StaggerGrid, StaggerItem } from "@/components/desk/motion";
import { mt5Api, paperApi, portfolioApi, platformApi } from "@/lib/api/endpoints";
import {
  asList,
  asRecord,
  mapEquityCurve,
  metric,
  num,
  str,
  toneFromNumber,
} from "@/lib/desk";
import { formatCurrency, formatNumber, formatPct } from "@/lib/utils";

type PositionRow = Record<string, unknown>;

export default function DashboardPage() {
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
  const paper = useQuery({
    queryKey: ["paper-performance"],
    queryFn: paperApi.performance,
    retry: false,
  });
  const mt5 = useQuery({ queryKey: ["mt5-status"], queryFn: mt5Api.status, retry: false });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: platformApi.health,
    retry: false,
  });
  const version = useQuery({ queryKey: ["version"], queryFn: platformApi.version });

  const account = asRecord(portfolio.data?.account);
  const positions = asList(portfolio.data?.positions).map(asRecord);
  const deals = asList(history.data?.deals).map(asRecord);
  const perf = asRecord(paper.data?.performance);
  const paperPortfolio = asRecord(paper.data?.portfolio);

  const balance = metric(account, "balance");
  const equity = metric(account, "equity");
  const profit = metric(account, "profit");
  const freeMargin = metric(account, "free_margin");
  const winRate = metric(perf, "win_rate");
  const profitFactor = metric(perf, "profit_factor");
  const sharpe = metric(perf, "sharpe_ratio");
  const drawdown = metric(perf, "max_drawdown_pct") || metric(paperPortfolio, "max_drawdown_pct");
  const initial = metric(paperPortfolio, "initial_balance");
  const paperEquity = metric(perf, "equity") || metric(paperPortfolio, "equity");
  const monthlyReturn =
    Number.isFinite(initial) && initial !== 0 && Number.isFinite(paperEquity)
      ? ((paperEquity - initial) / initial) * 100
      : NaN;

  const now = Date.now();
  const dayMs = 86400000;
  const sumWindow = (ms: number) =>
    deals.reduce((s, d) => {
      const t = Date.parse(str(d.time, ""));
      if (!Number.isFinite(t) || now - t > ms) return s;
      return s + num(d.profit, 0);
    }, 0);
  const dailyPnl = Number.isFinite(profit) ? profit : sumWindow(dayMs);
  const weeklyPnl = sumWindow(dayMs * 7);

  const curve = !deals.length
    ? ([] as { t: string; equity: number }[])
    : mapEquityCurve(
        deals
          .slice()
          .reverse()
          .reduce<{ t: string; equity: number }[]>((acc, d, i) => {
            const prev = acc.length ? acc[acc.length - 1].equity : balance || equity || 0;
            acc.push({
              t: str(d.time, String(i + 1)).slice(5, 16),
              equity: prev + num(d.profit, 0),
            });
            return acc;
          }, []),
      );

  const columns: DeskColumn<PositionRow>[] = [
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
      sortable: true,
      accessor: (r) => str(r.side),
      cell: (r) => (
        <Badge tone={str(r.side).toLowerCase() === "buy" ? "success" : "warning"}>
          {str(r.side)}
        </Badge>
      ),
    },
    {
      id: "volume",
      header: "Volume",
      sortable: true,
      accessor: (r) => num(r.volume, 0),
      cell: (r) => <span className="tabular">{str(r.volume)}</span>,
    },
    {
      id: "profit",
      header: "PnL",
      sortable: true,
      accessor: (r) => num(r.profit, 0),
      cell: (r) => (
        <span
          className={
            num(r.profit, 0) >= 0 ? "tabular text-[var(--success)]" : "tabular text-[var(--danger)]"
          }
        >
          {formatCurrency(num(r.profit, 0))}
        </span>
      ),
    },
  ];

  const apiOk = !health.isError && (str(health.data?.status) === "healthy" || str(health.data?.status) === "alive");

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Institutional desk overview — equity, risk, connectivity, and execution readiness."
        actions={
          <>
            <Button variant="secondary" asChild>
              <Link href="/mt5">MT5 status</Link>
            </Button>
            <Button asChild>
              <Link href="/execution">
                Trade <ArrowUpRight className="h-4 w-4" />
              </Link>
            </Button>
          </>
        }
      />

      {portfolio.isLoading ? (
        <DeskSkeleton variant="page" />
      ) : portfolio.isError ? (
        <DeskError
          message="Unable to load portfolio snapshot. Connect MT5 and retry."
          onRetry={() => portfolio.refetch()}
        />
      ) : (
        <PageMotion>
          <StaggerGrid className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-4">
            <StaggerItem>
              <StatCard
                label="Portfolio Value"
                value={Number.isFinite(equity) ? formatCurrency(equity) : "—"}
                hint={Number.isFinite(balance) ? `Balance ${formatCurrency(balance)}` : "Synced account equity"}
                tone={toneFromNumber(profit)}
              />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Daily PnL"
                value={formatCurrency(dailyPnl)}
                tone={toneFromNumber(dailyPnl)}
              />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Weekly PnL"
                value={formatCurrency(weeklyPnl)}
                tone={toneFromNumber(weeklyPnl)}
              />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Monthly Return"
                value={Number.isFinite(monthlyReturn) ? formatPct(monthlyReturn) : "—"}
                tone={toneFromNumber(monthlyReturn)}
                hint="Paper performance when live history is thin"
              />
            </StaggerItem>
          </StaggerGrid>

          <StaggerGrid className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StaggerItem>
              <StatCard
                label="Drawdown"
                value={Number.isFinite(drawdown) ? `${formatNumber(drawdown, 2)}%` : "—"}
                tone={Number.isFinite(drawdown) && drawdown > 0 ? "down" : "neutral"}
              />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Win Rate"
                value={
                  Number.isFinite(winRate)
                    ? `${formatNumber(winRate * (winRate <= 1 ? 100 : 1), 1)}%`
                    : "—"
                }
              />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Profit Factor"
                value={Number.isFinite(profitFactor) ? formatNumber(profitFactor, 2) : "—"}
              />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Sharpe Ratio"
                value={Number.isFinite(sharpe) ? formatNumber(sharpe, 2) : "—"}
              />
            </StaggerItem>
          </StaggerGrid>

          <div className="grid gap-4 xl:grid-cols-[1.45fr_0.85fr]">
            <Card className="qf-card-interactive">
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Equity curve</CardTitle>
                <Badge tone="accent">Live desk</Badge>
              </CardHeader>
              <CardContent>
                <LazyEquityChart
                  data={curve}
                  emptyLabel="Deal history will populate the equity curve after sync"
                />
              </CardContent>
            </Card>

            <div className="grid gap-4">
              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>Desk status</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2.5">
                  <StatusRow
                    icon={Radio}
                    label="Market / MT5"
                    value={mt5.data?.connected ? "Connected" : "Offline"}
                    tone={mt5.data?.connected ? "success" : "warning"}
                    detail={str(mt5.data?.server, "No terminal session")}
                  />
                  <StatusRow
                    icon={Cable}
                    label="Broker"
                    value={mt5.data?.connected ? "Synced" : "Awaiting link"}
                    tone={mt5.data?.connected ? "success" : "neutral"}
                    detail="Route via MT5 accounts"
                  />
                  <StatusRow
                    icon={Server}
                    label="API"
                    value={apiOk ? str(health.data?.status, "ok") : "Error"}
                    tone={apiOk ? "success" : "danger"}
                    detail={`v${str(version.data?.version ?? health.data?.version, "…")}`}
                  />
                  <StatusRow
                    icon={Layers}
                    label="Exposure"
                    value={`${positions.length} active`}
                    tone={positions.length ? "accent" : "neutral"}
                    detail={
                      Number.isFinite(freeMargin)
                        ? `Free margin ${formatCurrency(freeMargin)}`
                        : "No open exposure"
                    }
                  />
                </CardContent>
              </Card>

              <Card className="qf-card-interactive">
                <CardHeader>
                  <CardTitle>Quick actions</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-2">
                  {[
                    ["/execution", "Open order ticket"],
                    ["/risk", "Run risk check"],
                    ["/paper", "Paper trade"],
                    ["/ai", "Ask AI assistant"],
                  ].map(([href, label]) => (
                    <Button key={href} variant="secondary" className="justify-start" asChild>
                      <Link href={href}>{label}</Link>
                    </Button>
                  ))}
                </CardContent>
              </Card>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Active positions</CardTitle>
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/positions">View all</Link>
                </Button>
              </CardHeader>
              <CardContent>
                <DeskDataTable
                  columns={columns}
                  rows={positions}
                  rowKey={(r, i) => str(r.ticket, String(i))}
                  searchKeys={(r) => `${str(r.symbol)} ${str(r.side)}`}
                  pageSize={6}
                  aria-label="Active positions"
                  empty={
                    <DeskEmpty
                      icon={AlertTriangle}
                      title="No open positions"
                      description="Connect MT5 and sync portfolio to populate live exposure."
                      actionLabel="Connect MT5"
                      onAction={() => {
                        window.location.href = "/mt5";
                      }}
                      secondaryLabel="Paper trade"
                      onSecondary={() => {
                        window.location.href = "/paper";
                      }}
                    />
                  }
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Recent trades</CardTitle>
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/history">History</Link>
                </Button>
              </CardHeader>
              <CardContent>
                {history.isLoading ? (
                  <DeskSkeleton rows={4} />
                ) : deals.length === 0 ? (
                  <DeskEmpty
                    icon={Activity}
                    title="No recent deals"
                    description="Synced deal history will appear here after terminal sync."
                    actionLabel="Open history"
                    onAction={() => {
                      window.location.href = "/history";
                    }}
                  />
                ) : (
                  <DeskDataTable
                    columns={[
                      {
                        id: "time",
                        header: "Time",
                        sortable: true,
                        accessor: (r) => str(r.time),
                        cell: (r) => str(r.time).slice(0, 16),
                      },
                      {
                        id: "symbol",
                        header: "Symbol",
                        sortable: true,
                        accessor: (r) => str(r.symbol),
                        cell: (r) => str(r.symbol),
                      },
                      {
                        id: "profit",
                        header: "PnL",
                        sortable: true,
                        accessor: (r) => num(r.profit, 0),
                        cell: (r) => (
                          <span
                            className={
                              num(r.profit, 0) >= 0
                                ? "tabular text-[var(--success)]"
                                : "tabular text-[var(--danger)]"
                            }
                          >
                            {formatCurrency(num(r.profit, 0))}
                          </span>
                        ),
                      },
                    ]}
                    rows={deals.slice(0, 40)}
                    rowKey={(r, i) => str(r.ticket, String(i))}
                    searchKeys={(r) => `${str(r.symbol)} ${str(r.side)}`}
                    pageSize={6}
                    aria-label="Recent trades"
                  />
                )}
              </CardContent>
            </Card>
          </div>
        </PageMotion>
      )}
    </div>
  );
}

function StatusRow({
  icon: Icon,
  label,
  value,
  tone,
  detail,
}: {
  icon: typeof Radio;
  label: string;
  value: string;
  tone: "success" | "warning" | "danger" | "accent" | "neutral";
  detail: string;
}) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/70 px-3 py-2.5 transition hover:border-[var(--border-strong)]">
      <div className="flex items-start gap-2.5">
        <div className="mt-0.5 rounded-md bg-[var(--bg-elevated)] p-1.5 text-[var(--accent)]">
          <Icon className="h-3.5 w-3.5" aria-hidden />
        </div>
        <div>
          <p className="text-sm font-medium text-[var(--fg)]">{label}</p>
          <p className="text-xs text-[var(--fg-subtle)]">{detail}</p>
        </div>
      </div>
      <Badge tone={tone}>{value}</Badge>
    </div>
  );
}

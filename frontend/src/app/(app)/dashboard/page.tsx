"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  Bookmark,
  CalendarDays,
  Cable,
  Landmark,
  Layers,
  Search,
  Settings2,
  Sparkles,
  UserRound,
  Wallet,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { KpiMetricCard } from "@/components/dashboard/kpi-metric-card";
import {
  LazyDonutChart,
  LazyTerminalEquityChart,
} from "@/components/charts/lazy";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { DeskDataTable, type DeskColumn } from "@/components/desk/data-table";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { SessionBar } from "@/components/broker/session-bar";
import { PageMotion, StaggerGrid, StaggerItem } from "@/components/desk/motion";
import {
  brokersApi,
  mt5Api,
  paperApi,
  platformApi,
  portfolioApi,
  riskApi,
  strategyApi,
} from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, metric, num, str, toneFromNumber } from "@/lib/desk";
import {
  allocationFromPositions,
  buildEquitySeries,
  durationLabel,
  historicalVar95,
  marketBuckets,
  sparkFromSeries,
  sumPnlInWindow,
  symbolSpread,
  topBySpread,
} from "@/lib/dashboard/derive";
import { formatCurrency, formatNumber, formatRelativeTime } from "@/lib/utils";
import { useDashboardStream } from "@/hooks/realtime";
import {
  RealtimeConnectionBadge,
  RealtimeMeta,
} from "@/components/realtime/connection-badge";

type Row = Record<string, unknown>;

const FAV_KEY = "qf.watchlist.favorites";
const DAY = 86400000;

function money(v: number) {
  return Number.isFinite(v) ? formatCurrency(v) : "—";
}

function pct(v: number) {
  return Number.isFinite(v) ? `${formatNumber(v, 2)}%` : "—";
}

export default function DashboardPage() {
  const [watchQuery, setWatchQuery] = useState("");
  const [favorites, setFavorites] = useState<string[]>([]);
  const realtime = useDashboardStream();

  useEffect(() => {
    try {
      const raw = localStorage.getItem(FAV_KEY);
      if (raw) setFavorites(JSON.parse(raw) as string[]);
    } catch {
      /* ignore */
    }
  }, []);

  const persistFav = (next: string[]) => {
    setFavorites(next);
    localStorage.setItem(FAV_KEY, JSON.stringify(next));
  };

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
  const ordersQ = useQuery({
    queryKey: ["orders"],
    queryFn: portfolioApi.orders,
    retry: false,
  });
  const paper = useQuery({
    queryKey: ["paper-performance"],
    queryFn: paperApi.performance,
    retry: false,
  });
  const mt5 = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    retry: false,
  });
  const symbolsQ = useQuery({
    queryKey: ["mt5-symbols", "", 0],
    queryFn: () => mt5Api.symbols({ limit: 100, offset: 0, include_quotes: false }),
    retry: false,
    enabled: Boolean(mt5.data?.connected),
    staleTime: 45_000,
  });
  const brokers = useQuery({
    queryKey: ["brokers"],
    queryFn: brokersApi.list,
    retry: false,
  });
  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: () => platformApi.notifications(false),
    retry: false,
  });
  const activity = useQuery({
    queryKey: ["activity"],
    queryFn: platformApi.activity,
    retry: false,
  });
  const signals = useQuery({
    queryKey: ["strategy-signals"],
    queryFn: strategyApi.signals,
    retry: false,
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: platformApi.health,
    retry: false,
  });

  const account = asRecord(portfolio.data?.account);
  const positions = asList(portfolio.data?.positions).map(asRecord);
  const pending = asList(ordersQ.data ?? portfolio.data?.pending_orders).map(asRecord);
  const deals = asList(history.data?.deals).map(asRecord);
  const histOrders = asList(history.data?.orders).map(asRecord);
  const perf = asRecord(paper.data?.performance);
  const paperPortfolio = asRecord(paper.data?.portfolio);
  const symbols = asList(symbolsQ.data).map(asRecord);
  const signalItems = asList(signals.data).map(asRecord);
  const notifItems = asList(notifications.data).map(asRecord);
  const activityItems = asList(activity.data).map(asRecord);

  const balance = metric(account, "balance");
  const equity = metric(account, "equity");
  const margin = metric(account, "margin");
  const freeMargin = metric(account, "free_margin");
  const marginLevel = metric(account, "margin_level");
  const floating = metric(account, "profit");
  const winRate = metric(perf, "win_rate");
  const profitFactor = metric(perf, "profit_factor");
  const sharpe = metric(perf, "sharpe_ratio");
  const drawdown =
    metric(perf, "max_drawdown_pct") || metric(paperPortfolio, "max_drawdown_pct");

  const dailyPnl = Number.isFinite(floating) ? floating : sumPnlInWindow(deals, DAY);
  const weeklyPnl = sumPnlInWindow(deals, DAY * 7);
  const monthlyPnl = sumPnlInWindow(deals, DAY * 30);
  const seed = Number.isFinite(equity) ? equity : Number.isFinite(balance) ? balance : 0;
  const equitySeries = buildEquitySeries(deals, seed);
  const spark = sparkFromSeries(equitySeries);
  const allocation = allocationFromPositions(
    positions,
    Number.isFinite(freeMargin) ? freeMargin : 0,
  );
  const exposure = positions.reduce(
    (s, p) => s + Math.abs(num(p.volume, 0) * num(p.current_price ?? p.open_price, 0)),
    0,
  );
  const usedMarginPct =
    Number.isFinite(equity) && equity > 0 && Number.isFinite(margin)
      ? (margin / equity) * 100
      : NaN;
  const dealPnls = deals.map((d) => num(d.profit, 0)).filter(Number.isFinite);
  const var95 = historicalVar95(dealPnls);
  const buckets = marketBuckets(symbols);
  const moversWide = topBySpread(symbols, "wide", 5);
  const moversTight = topBySpread(symbols, "tight", 5);

  const [riskData, setRiskData] = useState<Record<string, unknown> | null>(null);
  const [riskLoading, setRiskLoading] = useState(false);

  const runRiskCheck = async () => {
    setRiskLoading(true);
    try {
      const data = await riskApi.check({
        request_id: `dash-${Date.now()}`,
        symbol: str(positions[0]?.symbol, "EURUSD"),
        side: str(positions[0]?.side, "buy"),
        equity: Number.isFinite(equity) ? String(equity) : undefined,
        balance: Number.isFinite(balance) ? String(balance) : undefined,
        daily_pnl: String(dailyPnl || 0),
        weekly_pnl: String(weeklyPnl || 0),
        monthly_pnl: String(monthlyPnl || 0),
        peak_equity: Number.isFinite(metric(paperPortfolio, "peak_equity"))
          ? String(metric(paperPortfolio, "peak_equity"))
          : undefined,
      });
      setRiskData(asRecord(data));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Risk check unavailable");
    } finally {
      setRiskLoading(false);
    }
  };

  useEffect(() => {
    if (!portfolio.isSuccess) return;
    void runRiskCheck();
    // Bootstrap once when portfolio first succeeds
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [portfolio.isSuccess]);

  const risk = riskData ?? {};
  const connectedBroker = mt5.data?.connected
    ? str(mt5.data?.server, "MT5")
    : asList(brokers.data).length
      ? `${asList(brokers.data).length} listed`
      : "None";

  const watched = symbols.filter((s) => {
    const code = str(s.code);
    const hay = `${code} ${str(s.description)}`.toLowerCase();
    if (watchQuery && !hay.includes(watchQuery.toLowerCase())) return false;
    if (favorites.length && !favorites.includes(code)) {
      // still show search hits even if not favorite when searching
      if (!watchQuery) return false;
    }
    return true;
  });

  const displayWatch = (watchQuery || favorites.length
    ? watched
    : symbols.filter((s) => s.selected).slice(0, 12)
  ).slice(0, 20);

  const fundingHint = () =>
    toast.message("Funding is managed at your broker", {
      description: "Use MT5 / broker portal for deposits and withdrawals.",
    });

  const positionCols: DeskColumn<Row>[] = [
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
      id: "entry",
      header: "Entry",
      sortable: true,
      accessor: (r) => num(r.open_price, 0),
      cell: (r) => <span className="tabular">{str(r.open_price)}</span>,
    },
    {
      id: "current",
      header: "Current",
      sortable: true,
      accessor: (r) => num(r.current_price, 0),
      cell: (r) => <span className="tabular">{str(r.current_price)}</span>,
    },
    { id: "sl", header: "SL", cell: (r) => str(r.stop_loss) },
    { id: "tp", header: "TP", cell: (r) => str(r.take_profit) },
    {
      id: "pnl",
      header: "PnL",
      sortable: true,
      accessor: (r) => num(r.profit, 0),
      cell: (r) => (
        <span
          className={
            num(r.profit, 0) >= 0 ? "tabular text-[var(--success)]" : "tabular text-[var(--danger)]"
          }
        >
          {money(num(r.profit, 0))}
        </span>
      ),
    },
    {
      id: "swap",
      header: "Swap",
      sortable: true,
      accessor: (r) => num(r.swap, 0),
      cell: (r) => <span className="tabular">{str(r.swap)}</span>,
    },
    {
      id: "volume",
      header: "Volume",
      sortable: true,
      accessor: (r) => num(r.volume, 0),
      cell: (r) => <span className="tabular">{str(r.volume)}</span>,
    },
    {
      id: "duration",
      header: "Duration",
      cell: (r) => durationLabel(r.opened_at),
    },
    {
      id: "status",
      header: "Status",
      cell: () => <Badge tone="success">Open</Badge>,
    },
    {
      id: "actions",
      header: "Actions",
      cell: (r) => (
        <Button size="sm" variant="ghost" asChild>
          <Link href={`/terminal?symbol=${encodeURIComponent(str(r.symbol))}`}>Manage</Link>
        </Button>
      ),
    },
  ];

  const orderCols: DeskColumn<Row>[] = [
    {
      id: "symbol",
      header: "Symbol",
      sortable: true,
      accessor: (r) => str(r.symbol),
      cell: (r) => str(r.symbol),
    },
    {
      id: "side",
      header: "Side",
      sortable: true,
      accessor: (r) => str(r.side),
      cell: (r) => <Badge tone="neutral">{str(r.side)}</Badge>,
    },
    {
      id: "type",
      header: "Type",
      sortable: true,
      accessor: (r) => str(r.order_type),
      cell: (r) => str(r.order_type),
    },
    {
      id: "volume",
      header: "Volume",
      sortable: true,
      accessor: (r) => num(r.volume, 0),
      cell: (r) => <span className="tabular">{str(r.volume)}</span>,
    },
    {
      id: "price",
      header: "Price",
      sortable: true,
      accessor: (r) => num(r.price, 0),
      cell: (r) => <span className="tabular">{str(r.price)}</span>,
    },
    { id: "sl", header: "SL", cell: (r) => str(r.stop_loss) },
    { id: "tp", header: "TP", cell: (r) => str(r.take_profit) },
    {
      id: "created",
      header: "Created",
      sortable: true,
      accessor: (r) => str(r.created_at),
      cell: (r) => str(r.created_at).slice(0, 16),
    },
  ];

  const tradeCols: DeskColumn<Row>[] = [
    {
      id: "time",
      header: "Execution",
      sortable: true,
      accessor: (r) => str(r.time),
      cell: (r) => str(r.time).slice(0, 19),
    },
    {
      id: "symbol",
      header: "Symbol",
      sortable: true,
      accessor: (r) => str(r.symbol),
      cell: (r) => str(r.symbol),
    },
    {
      id: "side",
      header: "Side",
      sortable: true,
      accessor: (r) => str(r.side),
      cell: (r) => str(r.side),
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
          {money(num(r.profit, 0))}
        </span>
      ),
    },
    {
      id: "commission",
      header: "Commission",
      sortable: true,
      accessor: (r) => num(r.commission, 0),
      cell: (r) => <span className="tabular">{str(r.commission)}</span>,
    },
  ];

  const exportTrades = () => {
    if (!deals.length) {
      toast.message("No trades to export");
      return;
    }
    const csv = [
      "time,symbol,side,volume,price,profit,commission,swap",
      ...deals.map((d) =>
        [
          str(d.time, ""),
          str(d.symbol, ""),
          str(d.side, ""),
          str(d.volume, ""),
          str(d.price, ""),
          str(d.profit, ""),
          str(d.commission, ""),
          str(d.swap, ""),
        ].join(","),
      ),
    ].join("\n");
    const b = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(b);
    const a = document.createElement("a");
    a.href = url;
    a.download = "quantforg-recent-trades.csv";
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Trades exported");
  };

  const insights = [
    Number.isFinite(equity)
      ? `Portfolio equity ${money(equity)} with ${positions.length} open position${positions.length === 1 ? "" : "s"}.`
      : null,
    Number.isFinite(marginLevel) && marginLevel > 0 && marginLevel < 200
      ? `Margin level ${pct(marginLevel)} is elevated — review exposure.`
      : null,
    Number.isFinite(drawdown) && drawdown >= 5
      ? `Max drawdown ${pct(drawdown)} from performance snapshot.`
      : null,
    ...asList(risk.warnings).slice(0, 3).map((w) => String(w)),
    ...signalItems.slice(0, 3).map(
      (s) =>
        `Signal ${str(s.symbol)} ${str(s.direction)} · conf ${formatNumber(num(s.confidence, 0) * (num(s.confidence, 0) <= 1 ? 100 : 1), 0)}%`,
    ),
    ...notifItems
      .filter((n) => !n.is_read)
      .slice(0, 2)
      .map((n) => `Alert: ${str(n.title)}`),
  ].filter(Boolean) as string[];

  if (portfolio.isLoading) {
    return (
      <div>
        <PageHeader
          title="Book"
          description="Institutional trading terminal — live desk overview."
        />
        <DeskSkeleton variant="page" />
      </div>
    );
  }

  if (portfolio.isError) {
    return (
      <div>
        <PageHeader title="Book" description="Portfolio, risk, and P&L from live session data." />
        <DeskError
          message="Unable to load portfolio snapshot. Connect MT5 and retry."
          onRetry={() => portfolio.refetch()}
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Book"
        description="Portfolio, risk, and P&L from live session data."
        actions={
          <>
            <RealtimeConnectionBadge status={realtime} />
            <Button variant="secondary" asChild>
              <Link href="/broker">
                <Cable className="h-4 w-4" /> Broker
              </Link>
            </Button>
            <Button asChild>
              <Link href="/terminal">
                Trade <ArrowUpRight className="h-4 w-4" />
              </Link>
            </Button>
          </>
        }
      />

      <RealtimeMeta status={realtime} className="mb-3" />
      <SessionBar className="mb-3" />

      <PageMotion className="space-y-5">
        {/* Primary KPIs — one focused row (no duplicate equity / identical sparklines) */}
        <StaggerGrid className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <StaggerItem>
            <KpiMetricCard
              label="Equity"
              value={money(equity)}
              tone={toneFromNumber(floating)}
              trend={
                Number.isFinite(floating)
                  ? `Floating ${money(floating)}`
                  : undefined
              }
              hint={`Balance ${money(balance)}`}
              status={mt5.data?.connected ? "live" : "sync"}
              spark={spark}
            />
          </StaggerItem>
          <StaggerItem>
            <KpiMetricCard
              label="Today's PnL"
              value={money(dailyPnl)}
              tone={toneFromNumber(dailyPnl)}
              trend={
                toneFromNumber(dailyPnl) === "up"
                  ? "Positive session"
                  : toneFromNumber(dailyPnl) === "down"
                    ? "Negative session"
                    : "Flat"
              }
              hint={`Week ${money(weeklyPnl)} · Month ${money(monthlyPnl)}`}
            />
          </StaggerItem>
          <StaggerItem>
            <KpiMetricCard
              label="Margin Level"
              value={pct(marginLevel)}
              tone={
                Number.isFinite(marginLevel) && marginLevel < 200
                  ? "down"
                  : "neutral"
              }
              hint={
                Number.isFinite(usedMarginPct)
                  ? `Used ${pct(usedMarginPct)} of equity`
                  : "Used margin vs equity"
              }
              status={
                Number.isFinite(marginLevel) && marginLevel < 200 ? "warn" : "ok"
              }
            />
          </StaggerItem>
          <StaggerItem>
            <KpiMetricCard
              label="Open Positions"
              value={String(portfolio.data?.position_count ?? positions.length)}
              hint={
                Number.isFinite(exposure) && exposure > 0
                  ? `Exposure ${money(exposure)}`
                  : "Live book"
              }
            />
          </StaggerItem>
          <StaggerItem>
            <KpiMetricCard
              label="Pending Orders"
              value={String(pending.length)}
              hint="Working limits & stops"
            />
          </StaggerItem>
          <StaggerItem>
            <KpiMetricCard
              label="Broker"
              value={connectedBroker}
              hint={
                mt5.data?.connected
                  ? `Login ${str(mt5.data?.login)}`
                  : "Connect via MT5"
              }
              status={mt5.data?.connected ? "live" : "offline"}
            />
          </StaggerItem>
        </StaggerGrid>

        {/* Market + Portfolio */}
        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="qf-card-interactive">
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Market Overview</CardTitle>
              <Badge tone={mt5.data?.connected ? "success" : "warning"}>
                {mt5.data?.connected ? "Market open via MT5" : "Offline"}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-4">
              {!mt5.data?.connected ? (
                <DeskEmpty
                  icon={Landmark}
                  title="No live market session"
                  description="Connect MT5 to load symbol universe, spreads, and market status."
                  actionLabel="Connect MT5"
                  actionHref="/broker"
                />
              ) : symbolsQ.isLoading ? (
                <DeskSkeleton rows={4} />
              ) : symbols.length === 0 ? (
                <p className="text-sm text-[var(--fg-muted)]">No symbols returned from MT5.</p>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                    {Object.entries(buckets).map(([k, v]) => (
                      <div
                        key={k}
                        className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2"
                      >
                        <p className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                          {k}
                        </p>
                        <p className="tabular text-lg font-semibold">{v}</p>
                      </div>
                    ))}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <p className="mb-2 text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                        Wider spreads
                      </p>
                      <ul className="space-y-1.5">
                        {moversWide.map((s) => (
                          <li
                            key={str(s.code)}
                            className="flex justify-between rounded-md border border-[var(--border)] px-2.5 py-1.5 text-sm"
                          >
                            <span>{str(s.code)}</span>
                            <span className="tabular text-[var(--fg-muted)]">
                              {formatNumber(symbolSpread(s), 5)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <p className="mb-2 text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                        Tighter spreads
                      </p>
                      <ul className="space-y-1.5">
                        {moversTight.map((s) => (
                          <li
                            key={str(s.code)}
                            className="flex justify-between rounded-md border border-[var(--border)] px-2.5 py-1.5 text-sm"
                          >
                            <span>{str(s.code)}</span>
                            <span className="tabular text-[var(--fg-muted)]">
                              {formatNumber(symbolSpread(s), 5)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <Card className="qf-card-interactive">
            <CardHeader className="flex-row items-center justify-between gap-2">
              <CardTitle>Account &amp; performance</CardTitle>
              <Badge
                tone={str(health.data?.status) === "healthy" ? "success" : "warning"}
              >
                API {str(health.data?.status, "…")}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                {[
                  ["Balance", money(balance)],
                  ["Margin", money(margin)],
                  ["Free margin", money(freeMargin)],
                  ["Exposure", money(exposure)],
                  ["Currency", str(account.currency, "USD")],
                  [
                    "Drawdown",
                    Number.isFinite(drawdown) ? pct(drawdown) : "—",
                  ],
                  [
                    "Win rate",
                    Number.isFinite(winRate)
                      ? `${formatNumber(winRate * (winRate <= 1 ? 100 : 1), 1)}%`
                      : "—",
                  ],
                  [
                    "Profit factor",
                    Number.isFinite(profitFactor)
                      ? formatNumber(profitFactor, 2)
                      : "—",
                  ],
                  [
                    "Sharpe",
                    Number.isFinite(sharpe) ? formatNumber(sharpe, 2) : "—",
                  ],
                  ["VaR 95%", Number.isFinite(var95) ? money(var95) : "—"],
                ].map(([label, value]) => (
                  <div
                    key={label}
                    className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/80 px-3 py-3"
                  >
                    <p className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                      {label}
                    </p>
                    <p className="mt-1 tabular text-lg font-semibold text-[var(--fg)]">
                      {value}
                    </p>
                  </div>
                ))}
              </div>
              <p className="text-xs text-[var(--fg-subtle)]">
                Refreshes with portfolio sync · last sync{" "}
                {str(portfolio.data?.synced_at).slice(0, 19) || "—"}
                {str(health.data?.environment)
                  ? ` · ${str(health.data?.environment)}`
                  : ""}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Equity + Allocation */}
        <div className="grid gap-4 xl:grid-cols-[1.35fr_0.85fr]">
          <Card>
            <CardHeader>
              <CardTitle>Equity Curve</CardTitle>
            </CardHeader>
            <CardContent>
              <LazyTerminalEquityChart
                data={equitySeries}
                emptyLabel="Synced deal history will populate the equity curve"
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Asset Allocation</CardTitle>
            </CardHeader>
            <CardContent>
              <LazyDonutChart data={allocation.map(({ name, value }) => ({ name, value }))} />
            </CardContent>
          </Card>
        </div>

        {/* Positions + Orders */}
        <div className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Open Positions</CardTitle>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/positions">View all</Link>
              </Button>
            </CardHeader>
            <CardContent>
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
                    description="Connect MT5 and sync to populate live exposure."
                    actionLabel="Connect MT5"
                    actionHref="/broker"
                    secondaryLabel="Paper trade"
                    secondaryHref="/paper"
                  />
                }
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Pending Orders</CardTitle>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/orders">View all</Link>
              </Button>
            </CardHeader>
            <CardContent>
              <DeskDataTable
                columns={orderCols}
                rows={pending}
                rowKey={(r, i) => str(r.ticket, String(i))}
                searchKeys={(r) => `${str(r.symbol)} ${str(r.order_type)}`}
                pageSize={8}
                aria-label="Pending orders"
                empty={
                  <DeskEmpty
                    icon={Activity}
                    title="No pending orders"
                    description="Working limit and stop orders will appear after sync."
                    actionLabel="Open execution"
                    actionHref="/terminal"
                  />
                }
              />
            </CardContent>
          </Card>
        </div>

        {/* Trades + Activity */}
        <div className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Recent Trades</CardTitle>
              <Button size="sm" variant="secondary" onClick={exportTrades} disabled={!deals.length}>
                Export CSV
              </Button>
            </CardHeader>
            <CardContent>
              <DeskDataTable
                columns={tradeCols}
                rows={deals}
                rowKey={(r, i) => str(r.ticket, String(i))}
                searchKeys={(r) => `${str(r.symbol)} ${str(r.side)}`}
                pageSize={8}
                aria-label="Recent trades"
                empty={
                  <DeskEmpty
                    icon={Activity}
                    title="No recent fills"
                    description="Deal history appears after terminal sync."
                    actionLabel="Open history"
                    actionHref="/history"
                  />
                }
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Activity Feed</CardTitle>
            </CardHeader>
            <CardContent className="max-h-[28rem] space-y-2 overflow-y-auto">
              {activity.isLoading && notifications.isLoading ? (
                <DeskSkeleton rows={5} />
              ) : activityItems.length + notifItems.length + deals.length === 0 ? (
                <DeskEmpty
                  icon={Activity}
                  title="No desk activity yet"
                  description="Trades, notifications, and profile events will stream here."
                />
              ) : (
                <>
                  {deals.slice(0, 4).map((d, i) => (
                    <FeedRow
                      key={`d-${i}`}
                      title={`Trade ${str(d.symbol)} ${str(d.side)}`}
                      body={`PnL ${money(num(d.profit, 0))}`}
                      when={str(d.time)}
                      tone={num(d.profit, 0) >= 0 ? "success" : "danger"}
                    />
                  ))}
                  {notifItems.slice(0, 4).map((n) => (
                    <FeedRow
                      key={str(n.id)}
                      title={str(n.title)}
                      body={str(n.body)}
                      when={str(n.created_at)}
                      tone={n.is_read ? "neutral" : "accent"}
                    />
                  ))}
                  {activityItems.slice(0, 4).map((a) => (
                    <FeedRow
                      key={str(a.id)}
                      title={str(a.action)}
                      body={str(a.message)}
                      when={str(a.created_at)}
                      tone="neutral"
                    />
                  ))}
                  {histOrders
                    .filter((o) => {
                      const t = str(o.deal_type ?? o.order_type, "").toLowerCase();
                      return t.includes("balance") || t.includes("deposit") || t.includes("withdraw");
                    })
                    .slice(0, 2)
                    .map((o, i) => (
                      <FeedRow
                        key={`f-${i}`}
                        title="Funding event"
                        body={`${str(o.symbol)} · ${str(o.state)}`}
                        when={str(o.time_done ?? o.time_setup)}
                        tone="accent"
                      />
                    ))}
                </>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Calendar + Watchlist */}
        <div className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Economic Calendar</CardTitle>
            </CardHeader>
            <CardContent>
              <DeskEmpty
                icon={CalendarDays}
                title="Calendar feed not connected"
                description="No economic calendar endpoint is available in this deployment. QuantForg will not invent events."
                actionLabel="Open support"
                actionHref="/support"
                secondaryLabel="View ops"
                secondaryHref="/ops"
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
              <CardTitle>Watchlist</CardTitle>
              <div className="relative w-full sm:w-56">
                <Search
                  className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-subtle)]"
                  aria-hidden
                />
                <Input
                  className="h-8 pl-8 text-xs"
                  placeholder="Search symbols…"
                  value={watchQuery}
                  onChange={(e) => setWatchQuery(e.target.value)}
                  aria-label="Search watchlist"
                />
              </div>
            </CardHeader>
            <CardContent>
              {!mt5.data?.connected ? (
                <DeskEmpty
                  icon={Bookmark}
                  title="Watchlist requires MT5"
                  description="Symbol bids and asks load from the connected terminal."
                  actionLabel="Connect MT5"
                  actionHref="/broker"
                />
              ) : displayWatch.length === 0 ? (
                <p className="text-sm text-[var(--fg-muted)]">
                  No symbols match. Select favorites or search the MT5 universe.
                </p>
              ) : (
                <ul className="max-h-80 space-y-1.5 overflow-y-auto">
                  {displayWatch.map((s) => {
                    const code = str(s.code);
                    const fav = favorites.includes(code);
                    const bid = num(s.bid);
                    const ask = num(s.ask);
                    const mid =
                      Number.isFinite(bid) && Number.isFinite(ask) ? (bid + ask) / 2 : bid || ask;
                    return (
                      <li
                        key={code}
                        className="flex items-center justify-between gap-2 rounded-lg border border-[var(--border)] px-2.5 py-2 transition hover:bg-[var(--surface-2)]"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{code}</p>
                          <p className="truncate text-[11px] text-[var(--fg-subtle)]">
                            {str(s.description, "—")} · spread{" "}
                            {Number.isFinite(symbolSpread(s))
                              ? formatNumber(symbolSpread(s), 5)
                              : "—"}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="tabular text-sm">{Number.isFinite(mid) ? formatNumber(mid, 5) : "—"}</span>
                          <Button
                            size="sm"
                            variant="ghost"
                            aria-label={fav ? "Remove favorite" : "Add favorite"}
                            onClick={() =>
                              persistFav(
                                fav ? favorites.filter((f) => f !== code) : [...favorites, code],
                              )
                            }
                          >
                            <Bookmark
                              className={fav ? "h-3.5 w-3.5 fill-[var(--accent)] text-[var(--accent)]" : "h-3.5 w-3.5"}
                            />
                          </Button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Risk + AI Insights + Quick actions */}
        <div className="grid gap-4 xl:grid-cols-3">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Risk Analytics</CardTitle>
              <Button
                size="sm"
                variant="secondary"
                disabled={riskLoading}
                onClick={() => void runRiskCheck()}
              >
                Refresh
              </Button>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <Metric
                  label="Risk Score"
                  value={
                    risk.risk_score != null ? String(risk.risk_score) : riskLoading ? "…" : "—"
                  }
                />
                <Metric label="Band" value={str(risk.risk_band, "—")} />
                <Metric label="Drawdown" value={pct(drawdown)} />
                <Metric label="Exposure" value={money(exposure)} />
                <Metric
                  label="VaR 95%"
                  value={Number.isFinite(var95) ? money(var95) : "—"}
                  hint="From synced deal PnL"
                />
                <Metric label="Margin Usage" value={pct(usedMarginPct)} />
              </div>
              <div className="grid grid-cols-7 gap-1">
                {Array.from({ length: 28 }, (_, i) => {
                  const dayDeals = deals.filter((d) => {
                    const day = str(d.time, "").slice(0, 10);
                    if (!day) return false;
                    return new Date(day + "T00:00:00").getDay() === i % 7;
                  });
                  const pnl = dayDeals.reduce((s, d) => s + num(d.profit, 0), 0);
                  const intensity = Math.min(1, Math.abs(pnl) / 400);
                  const bg =
                    pnl > 0
                      ? `rgba(52,211,153,${0.12 + intensity * 0.75})`
                      : pnl < 0
                        ? `rgba(248,113,113,${0.12 + intensity * 0.75})`
                        : "var(--surface-2)";
                  return (
                    <div
                      key={i}
                      className="aspect-square rounded-sm border border-[var(--border)]"
                      style={{ background: bg }}
                      title={`Sample PnL ${pnl.toFixed(2)}`}
                    />
                  );
                })}
              </div>
              {asList(risk.warnings).length ? (
                <ul className="space-y-1 text-xs text-[var(--warning)]">
                  {asList(risk.warnings)
                    .slice(0, 4)
                    .map((w, i) => (
                      <li key={i}>• {String(w)}</li>
                    ))}
                </ul>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>AI Insights</CardTitle>
              <Badge tone="neutral">Desk-derived</Badge>
            </CardHeader>
            <CardContent>
              <p className="mb-3 text-xs text-[var(--fg-subtle)]">
                No model gateway required — insights are assembled only from portfolio, risk, signals,
                and notifications.
              </p>
              {insights.length === 0 ? (
                <DeskEmpty
                  icon={Sparkles}
                  title="No insights yet"
                  description="Sync portfolio or generate strategy signals to populate this panel."
                  actionLabel="Strategy builder"
                  actionHref="/strategy"
                />
              ) : (
                <ul className="space-y-2">
                  {insights.slice(0, 8).map((text, i) => (
                    <li
                      key={i}
                      className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/70 px-3 py-2 text-sm text-[var(--fg-muted)]"
                    >
                      {text}
                    </li>
                  ))}
                </ul>
              )}
              <Button className="mt-3" variant="secondary" size="sm" asChild>
                <Link href="/ai">Open AI assistant</Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2">
              <Button variant="secondary" className="justify-start" onClick={fundingHint}>
                <Wallet className="h-4 w-4" /> Deposit
              </Button>
              <Button variant="secondary" className="justify-start" onClick={fundingHint}>
                <Wallet className="h-4 w-4" /> Withdraw
              </Button>
              <Button className="justify-start" asChild>
                <Link href="/terminal">
                  <ArrowUpRight className="h-4 w-4" /> Trade
                </Link>
              </Button>
              <Button variant="secondary" className="justify-start" asChild>
                <Link href="/broker">
                  <Cable className="h-4 w-4" /> Connect Broker
                </Link>
              </Button>
              <Button variant="secondary" className="justify-start" asChild>
                <Link href="/settings">
                  <Settings2 className="h-4 w-4" /> Settings
                </Link>
              </Button>
              <Button variant="secondary" className="justify-start" asChild>
                <Link href="/profile">
                  <UserRound className="h-4 w-4" /> Profile
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </PageMotion>
    </div>
  );
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">{label}</p>
      <p className="tabular text-sm font-semibold text-[var(--fg)]">{value}</p>
      {hint ? <p className="text-[10px] text-[var(--fg-subtle)]">{hint}</p> : null}
    </div>
  );
}

function FeedRow({
  title,
  body,
  when,
  tone,
}: {
  title: string;
  body: string;
  when: string;
  tone: "success" | "danger" | "accent" | "neutral";
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] px-3 py-2 transition hover:bg-[var(--surface-2)]/60">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-[var(--fg)]">{title}</p>
        <Badge tone={tone === "danger" ? "danger" : tone === "success" ? "success" : tone}>
          {formatRelativeTime(when)}
        </Badge>
      </div>
      <p className="mt-0.5 line-clamp-2 text-xs text-[var(--fg-muted)]">{body}</p>
    </div>
  );
}

"use client";

import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Copy,
  Download,
  FileSpreadsheet,
  FileText,
  History,
  RefreshCw,
  Search,
  Unplug,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { LazyBarChart, LazyEquityChart } from "@/components/charts/lazy";
import { TradeReplayPanel } from "@/components/journal/trade-replay";
import { portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, num } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn, formatNumber } from "@/lib/utils";
import {
  attachStopsFromPositions,
  computeTradeAnalytics,
  computeTradeRr,
  formatDuration,
  inferTradeSession,
  pairDealsIntoTrades,
  parseLiveDeal,
  rangeToIso,
  tradesToCsv,
  type HistoryRange,
  type LiveTrade,
} from "@/lib/orders/history";

const PAGE_SIZE = 25;
const NA = "Not available";
/** Gold contract size used for risk % when SL + equity are known. */
const GOLD_CONTRACT = 100;
const UUID_RE =
  /[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i;

/** Prefer a UUID-looking request id from comment/strategy; else undefined. */
function extractRequestId(comment: string, strategy: string): string | undefined {
  for (const raw of [comment, strategy]) {
    const t = raw.trim();
    if (!t) continue;
    const m = t.match(UUID_RE);
    if (!m?.[0]) continue;
    // Whole field is a UUID, or a UUID is embedded in the string.
    if (m[0] === t || t.includes(m[0])) return m[0];
  }
  return undefined;
}

function downloadBlob(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function sessionMoney(raw: string): number | null {
  const n = num(raw.replace(/[^0-9.\-]/g, ""), NaN);
  return Number.isFinite(n) ? n : null;
}

function fmtMoney(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return NA;
  return formatNumber(v, digits);
}

function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return NA;
  return `${(v * 100).toFixed(digits)}%`;
}

function fmtRatio(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return NA;
  return formatNumber(v, digits);
}

/** Risk % from SL distance × volume × gold contract / equity. */
function computeRiskPct(
  t: LiveTrade,
  equity: number | null,
): number | null {
  if (equity == null || equity <= 0) return null;
  if (t.sl == null || t.sl <= 0) return null;
  const dist = Math.abs(t.entry - t.sl);
  if (dist <= 0 || t.volume <= 0) return null;
  return (t.volume * dist * GOLD_CONTRACT) / equity * 100;
}

function plTone(v: number): string {
  if (v > 0) return "text-[var(--success)]";
  if (v < 0) return "text-[var(--danger)]";
  return "text-[var(--fg)]";
}

function KpiCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="min-w-0 rounded-md border border-[var(--border)] bg-[var(--bg-panel)] px-2.5 py-2 transition-colors duration-[var(--duration-os)]">
      <p className="truncate text-[9px] font-medium uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p
        className={cn(
          "mt-0.5 truncate font-mono text-sm tabular-nums text-[var(--fg)]",
          tone,
          value === NA && "text-[var(--fg-subtle)]",
        )}
      >
        {value}
      </p>
    </div>
  );
}

function ChartPanel({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--bg-panel)] p-3">
      <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {title}
      </p>
      {children}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[7.5rem_1fr] gap-2 border-b border-[var(--border)]/60 py-1.5 text-xs last:border-0">
      <dt className="text-[var(--fg-subtle)]">{label}</dt>
      <dd
        className={cn(
          "font-mono text-[var(--fg)]",
          value === NA && "font-sans text-[var(--fg-subtle)]",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section>
      <h3 className="mb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
        {title}
      </h3>
      {children}
    </section>
  );
}

export function OrdersHistoryDesk() {
  const session = useTradingSession();
  const [range, setRange] = useState<HistoryRange>("month");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState<"all" | "buy" | "sell">("all");
  const [status, setStatus] = useState<"all" | "closed" | "open">("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<LiveTrade | null>(null);

  const equityNum = sessionMoney(session.equity);
  const balanceNum = sessionMoney(session.balance);

  const iso = useMemo(
    () => rangeToIso(range, customFrom, customTo),
    [range, customFrom, customTo],
  );

  const historyQ = useQuery({
    queryKey: ["orders-history", iso.date_from, iso.date_to, session.connected],
    queryFn: () => portfolioApi.historyRange(iso),
    enabled: session.connected,
    refetchInterval: session.connected ? 15_000 : false,
  });

  const positionsQ = useQuery({
    queryKey: ["orders-history-positions", session.connected],
    queryFn: () => portfolioApi.positions(),
    enabled: session.connected,
    refetchInterval: session.connected ? 15_000 : false,
  });

  const trades = useMemo(() => {
    const deals = asList(asRecord(historyQ.data).deals)
      .map((row) => parseLiveDeal(asRecord(row)))
      .filter((d): d is NonNullable<typeof d> => d != null);
    let rows = pairDealsIntoTrades(deals);

    // portfolioApi.positions() returns unknown[] (array), not {items}.
    const posSource: unknown[] = Array.isArray(positionsQ.data)
      ? positionsQ.data
      : [];
    const posRows = posSource
      .map((row) => {
        const r = asRecord(row);
        const ticket = num(r.ticket ?? r.position, 0);
        if (!Number.isFinite(ticket) || ticket <= 0) return null;
        return {
          ticket,
          stop_loss: num(r.stop_loss ?? r.sl, 0),
          take_profit: num(r.take_profit ?? r.tp, 0),
        };
      })
      .filter((p): p is NonNullable<typeof p> => p != null);
    rows = attachStopsFromPositions(rows, posRows);

    if (symbol.trim()) {
      const q = symbol.trim().toUpperCase();
      rows = rows.filter((t) => t.symbol.includes(q));
    }
    if (side !== "all") rows = rows.filter((t) => t.side === side);
    if (status !== "all") rows = rows.filter((t) => t.status === status);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      rows = rows.filter(
        (t) =>
          t.symbol.toLowerCase().includes(q) ||
          t.comment.toLowerCase().includes(q) ||
          t.strategy.toLowerCase().includes(q) ||
          String(t.ticket).includes(q) ||
          String(t.deal).includes(q),
      );
    }
    return rows;
  }, [historyQ.data, positionsQ.data, symbol, side, status, search]);

  const analytics = useMemo(
    () => computeTradeAnalytics(trades, { startingEquity: equityNum ?? 0 }),
    [trades, equityNum],
  );

  const pageCount = Math.max(1, Math.ceil(trades.length / PAGE_SIZE));
  const pageRows = trades.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  const equityChartData = useMemo(
    () =>
      analytics.equityCurve.map((p) => ({
        t: new Date(p.t).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        }),
        equity: p.equity,
      })),
    [analytics.equityCurve],
  );

  const hasCharts =
    analytics.equityCurve.length > 0 ||
    analytics.dailyPl.length > 0 ||
    analytics.monthlyReturns.length > 0 ||
    analytics.bySymbol.length > 0 ||
    analytics.bySession.length > 0 ||
    analytics.holdBuckets.some((b) => b.value > 0) ||
    analytics.profitDistribution.some((b) => b.value > 0);

  const exportCsv = () => {
    if (!trades.length) {
      toast.message("No trades to export");
      return;
    }
    downloadBlob(`quantforg-orders-${Date.now()}.csv`, tradesToCsv(trades), "text/csv");
    toast.success("CSV exported");
  };

  const exportExcel = () => {
    if (!trades.length) {
      toast.message("No trades to export");
      return;
    }
    const csv = tradesToCsv(trades).replace(/,/g, "\t");
    downloadBlob(
      `quantforg-orders-${Date.now()}.xls`,
      csv,
      "application/vnd.ms-excel",
    );
    toast.success("Excel file exported");
  };

  const exportPdf = () => {
    if (!trades.length) {
      toast.message("No trades to export");
      return;
    }
    const lines = trades
      .slice(0, 200)
      .map(
        (t) =>
          `${t.time.toISOString()}  ${t.symbol}  ${t.side.toUpperCase()}  ${t.volume}  ${t.entry} → ${t.exit ?? "—"}  net ${t.netPl}  ticket ${t.ticket}`,
      )
      .join("\n");
    const html = `<!doctype html><html><head><title>QuantForg Orders</title>
      <style>body{font-family:ui-monospace,monospace;font-size:11px;padding:24px;color:#111}
      h1{font-size:16px;margin:0 0 12px}</style></head><body>
      <h1>QuantForg Orders History (live MT5)</h1>
      <pre>${lines.replace(/</g, "&lt;")}</pre>
      <script>window.onload=()=>window.print()</script>
      </body></html>`;
    const w = window.open("", "_blank");
    if (!w) {
      toast.error("Pop-up blocked — allow pop-ups to export PDF");
      return;
    }
    w.document.write(html);
    w.document.close();
  };

  if (!session.connected) {
    return (
      <DeskEmpty
        icon={Unplug}
        title="Broker offline"
        description="Connect MT5 on Broker to load live order and deal history from the Execution Gateway."
      />
    );
  }

  const selectedRr = selected ? computeTradeRr(selected) : null;
  const selectedRisk = selected ? computeRiskPct(selected, equityNum) : null;
  const selectedMargin =
    selected && equityNum != null && selectedRisk != null
      ? (selectedRisk / 100) * equityNum
      : null;
  const selectedRequestId = selected
    ? extractRequestId(selected.comment, selected.strategy)
    : undefined;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden p-3 sm:p-4 md:p-6">
      <header className="flex shrink-0 flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Journal · Live MT5
          </p>
          <h1 className="font-[family-name:var(--font-display)] text-xl tracking-tight text-[var(--fg)]">
            Orders History
          </h1>
          <p className="mt-1 max-w-xl text-xs text-[var(--fg-muted)]">
            Institutional ledger from live MetaTrader deals. Missing broker fields show as
            Not available — never invented.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void historyQ.refetch()}
            disabled={historyQ.isFetching}
          >
            <RefreshCw
              className={cn("mr-1.5 h-3.5 w-3.5", historyQ.isFetching && "animate-spin")}
            />
            Refresh
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={exportCsv}>
            <Download className="mr-1.5 h-3.5 w-3.5" />
            CSV
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={exportExcel}>
            <FileSpreadsheet className="mr-1.5 h-3.5 w-3.5" />
            Excel
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={exportPdf}>
            <FileText className="mr-1.5 h-3.5 w-3.5" />
            PDF
          </Button>
        </div>
      </header>

      {/* KPI strip */}
      <div className="grid shrink-0 grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-8">
        <KpiCell
          label="Balance"
          value={balanceNum == null ? NA : formatNumber(balanceNum, 2)}
        />
        <KpiCell
          label="Equity"
          value={equityNum == null ? NA : formatNumber(equityNum, 2)}
        />
        <KpiCell
          label="Today's P/L"
          value={fmtMoney(analytics.todayPl)}
          tone={plTone(analytics.todayPl)}
        />
        <KpiCell
          label="Weekly P/L"
          value={fmtMoney(analytics.weekPl)}
          tone={plTone(analytics.weekPl)}
        />
        <KpiCell
          label="Monthly P/L"
          value={fmtMoney(analytics.monthPl)}
          tone={plTone(analytics.monthPl)}
        />
        <KpiCell label="Win Rate" value={fmtPct(analytics.winRate)} />
        <KpiCell label="Profit Factor" value={fmtRatio(analytics.profitFactor)} />
        <KpiCell label="Sharpe" value={fmtRatio(analytics.sharpe)} />
        <KpiCell label="Sortino" value={fmtRatio(analytics.sortino)} />
        <KpiCell label="Recovery Factor" value={fmtRatio(analytics.recoveryFactor)} />
        <KpiCell label="Max Drawdown" value={fmtMoney(analytics.maxDrawdown)} />
        <KpiCell label="Average RR" value={fmtRatio(analytics.averageRr)} />
        <KpiCell
          label="Largest Win"
          value={fmtMoney(analytics.largestWin)}
          tone={analytics.largestWin != null ? "text-[var(--success)]" : undefined}
        />
        <KpiCell
          label="Largest Loss"
          value={fmtMoney(analytics.largestLoss)}
          tone={analytics.largestLoss != null ? "text-[var(--danger)]" : undefined}
        />
      </div>

      {/* Charts — only when live analytics exist */}
      {hasCharts ? (
        <div className="grid shrink-0 gap-2 overflow-y-auto lg:grid-cols-2 xl:grid-cols-4">
          {analytics.equityCurve.length > 0 ? (
            <ChartPanel title="Equity curve">
              <div className="h-40 [&_[role=img]]:!h-40">
                <LazyEquityChart
                  data={equityChartData}
                  emptyLabel="No equity path in range"
                />
              </div>
            </ChartPanel>
          ) : null}
          {analytics.dailyPl.length > 0 ? (
            <ChartPanel title="Daily P/L">
              <div className="h-40 [&_[role=img]]:!h-40">
                <LazyBarChart
                  data={analytics.dailyPl.map((d) => ({
                    label: d.day.slice(5),
                    value: d.pl,
                  }))}
                />
              </div>
            </ChartPanel>
          ) : null}
          {analytics.monthlyReturns.length > 0 ? (
            <ChartPanel title="Monthly P/L">
              <div className="h-40 [&_[role=img]]:!h-40">
                <LazyBarChart
                  data={analytics.monthlyReturns.map((d) => ({
                    label: d.month,
                    value: d.pl,
                  }))}
                />
              </div>
            </ChartPanel>
          ) : null}
          {analytics.bySymbol.length > 0 ? (
            <ChartPanel title="By Symbol">
              <div className="h-40 [&_[role=img]]:!h-40">
                <LazyBarChart data={analytics.bySymbol} />
              </div>
            </ChartPanel>
          ) : null}
          {analytics.bySession.length > 0 ? (
            <ChartPanel title="By Session">
              <div className="h-40 [&_[role=img]]:!h-40">
                <LazyBarChart data={analytics.bySession} />
              </div>
            </ChartPanel>
          ) : null}
          {analytics.holdBuckets.some((b) => b.value > 0) ? (
            <ChartPanel title="Hold time">
              <div className="h-40 [&_[role=img]]:!h-40">
                <LazyBarChart data={analytics.holdBuckets} />
              </div>
            </ChartPanel>
          ) : null}
          {analytics.profitDistribution.some((b) => b.value > 0) ? (
            <ChartPanel title="Win / Loss distribution">
              <div className="h-40 [&_[role=img]]:!h-40">
                <LazyBarChart data={analytics.profitDistribution} />
              </div>
            </ChartPanel>
          ) : null}
        </div>
      ) : null}

      {/* Filters */}
      <div className="flex shrink-0 flex-wrap items-end gap-2 rounded-md border border-[var(--border)] bg-[var(--bg-panel)] p-2.5">
        <div className="flex flex-wrap gap-1">
          {(
            [
              ["today", "Today"],
              ["week", "Week"],
              ["month", "Month"],
              ["custom", "Custom"],
            ] as const
          ).map(([id, label]) => (
            <Button
              key={id}
              type="button"
              size="sm"
              variant={range === id ? "default" : "outline"}
              className="transition-[background-color,border-color,color] duration-[var(--duration-os)]"
              onClick={() => {
                setRange(id);
                setPage(0);
              }}
            >
              {label}
            </Button>
          ))}
        </div>
        {range === "custom" ? (
          <>
            <Input
              type="date"
              value={customFrom}
              onChange={(e) => {
                setCustomFrom(e.target.value);
                setPage(0);
              }}
              className="h-8 w-[9.5rem]"
            />
            <Input
              type="date"
              value={customTo}
              onChange={(e) => {
                setCustomTo(e.target.value);
                setPage(0);
              }}
              className="h-8 w-[9.5rem]"
            />
          </>
        ) : null}
        <Input
          placeholder="Symbol"
          value={symbol}
          onChange={(e) => {
            setSymbol(e.target.value);
            setPage(0);
          }}
          className="h-8 w-28"
        />
        <select
          className="h-8 rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 text-xs text-[var(--fg)]"
          value={side}
          onChange={(e) => {
            setSide(e.target.value as typeof side);
            setPage(0);
          }}
          aria-label="Side filter"
        >
          <option value="all">Side: all</option>
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
        <select
          className="h-8 rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 text-xs text-[var(--fg)]"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as typeof status);
            setPage(0);
          }}
          aria-label="Status filter"
        >
          <option value="all">Status: all</option>
          <option value="closed">Closed</option>
          <option value="open">Open</option>
        </select>
        <div className="relative min-w-[12rem] flex-1">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-subtle)]" />
          <Input
            placeholder="Search ticket, deal, comment, strategy…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="h-8 pl-7"
          />
        </div>
      </div>

      {/* Table */}
      <div className="min-h-0 flex-1 overflow-x-auto overflow-y-auto rounded-md border border-[var(--border)] bg-[var(--bg-panel)]">
        {historyQ.isLoading ? (
          <div className="p-4">
            <DeskSkeleton rows={8} />
          </div>
        ) : historyQ.isError ? (
          <div className="p-4">
            <DeskError
              message="Live order history unavailable from the MT5 gateway."
              onRetry={() => void historyQ.refetch()}
            />
          </div>
        ) : pageRows.length === 0 ? (
          <div className="p-6">
            <DeskEmpty
              icon={History}
              title="No broker trades in this range"
              description="History is loaded from MetaTrader deals via the Execution Gateway. Widen the date range or place a live trade."
            />
          </div>
        ) : (
          <table className="w-full min-w-[1480px] border-collapse text-left text-[11px]">
            <thead className="sticky top-0 z-10 bg-[var(--bg-elevated)] text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
              <tr>
                {[
                  "Ticket",
                  "Deal",
                  "Symbol",
                  "Buy/Sell",
                  "Volume",
                  "Entry",
                  "Exit",
                  "SL",
                  "TP",
                  "Commission",
                  "Swap",
                  "Gross",
                  "Net",
                  "Duration",
                  "Session",
                  "Strategy",
                  "Risk %",
                  "RR",
                  "Status",
                  "",
                ].map((h) => (
                  <th key={h || "actions"} className="whitespace-nowrap px-2 py-2 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((t) => {
                const rr = computeTradeRr(t);
                const risk = computeRiskPct(t, equityNum);
                return (
                  <tr
                    key={t.id}
                    className="border-t border-[var(--border)]/70 transition-colors duration-[var(--duration-os)] hover:bg-[var(--bg-elevated)]/60"
                  >
                    <td className="whitespace-nowrap px-2 py-2 font-mono">{t.ticket}</td>
                    <td className="whitespace-nowrap px-2 py-2 font-mono">{t.deal}</td>
                    <td className="px-2 py-2 font-medium">{t.symbol}</td>
                    <td className="px-2 py-2">
                      <Badge tone={t.side === "buy" ? "success" : "danger"}>
                        {t.side.toUpperCase()}
                      </Badge>
                    </td>
                    <td className="px-2 py-2 font-mono">{formatNumber(t.volume, 2)}</td>
                    <td className="px-2 py-2 font-mono">{formatNumber(t.entry, 3)}</td>
                    <td className="px-2 py-2 font-mono">
                      {t.exit == null ? NA : formatNumber(t.exit, 3)}
                    </td>
                    <td className="px-2 py-2 font-mono text-[var(--fg-muted)]">
                      {t.sl == null ? NA : formatNumber(t.sl, 3)}
                    </td>
                    <td className="px-2 py-2 font-mono text-[var(--fg-muted)]">
                      {t.tp == null ? NA : formatNumber(t.tp, 3)}
                    </td>
                    <td className="px-2 py-2 font-mono">{formatNumber(t.commission, 2)}</td>
                    <td className="px-2 py-2 font-mono">{formatNumber(t.swap, 2)}</td>
                    <td className={cn("px-2 py-2 font-mono", plTone(t.profit))}>
                      {formatNumber(t.profit, 2)}
                    </td>
                    <td className={cn("px-2 py-2 font-mono font-medium", plTone(t.netPl))}>
                      {formatNumber(t.netPl, 2)}
                    </td>
                    <td className="px-2 py-2 font-mono">
                      {t.durationMs == null ? NA : formatDuration(t.durationMs)}
                    </td>
                    <td className="px-2 py-2 text-[var(--fg-muted)]">
                      {inferTradeSession(t.time)}
                    </td>
                    <td className="max-w-[7rem] truncate px-2 py-2 text-[var(--fg-muted)]">
                      {t.strategy || NA}
                    </td>
                    <td className="px-2 py-2 font-mono text-[var(--fg-muted)]">
                      {risk == null ? NA : `${formatNumber(risk, 2)}%`}
                    </td>
                    <td className="px-2 py-2 font-mono text-[var(--fg-muted)]">
                      {rr == null ? NA : formatNumber(rr, 2)}
                    </td>
                    <td className="px-2 py-2">
                      <Badge tone={t.status === "closed" ? "neutral" : "accent"}>
                        {t.status}
                      </Badge>
                    </td>
                    <td className="px-2 py-2">
                      <div className="flex gap-1">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="h-7 px-2"
                          onClick={() => {
                            void navigator.clipboard.writeText(String(t.ticket));
                            toast.success("Ticket copied");
                          }}
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="h-7"
                          onClick={() => setSelected(t)}
                        >
                          Details
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="flex shrink-0 items-center justify-between text-xs text-[var(--fg-muted)]">
        <span>
          {trades.length} trade{trades.length === 1 ? "" : "s"} · page {page + 1}/{pageCount}
        </span>
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={page <= 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            Prev
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={page >= pageCount - 1}
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
          >
            Next
          </Button>
        </div>
      </div>

      {/* Trade details drawer */}
      <Dialog open={selected != null} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent
          className={cn(
            "fixed inset-y-0 right-0 left-auto top-0 h-full max-h-none w-full max-w-md translate-x-0 translate-y-0 rounded-none border-l border-[var(--border)] p-0 shadow-[var(--shadow-card)]",
            "data-[state=open]:animate-in data-[state=closed]:animate-out",
          )}
        >
          <div className="flex h-full flex-col">
            <div className="shrink-0 border-b border-[var(--border)] px-5 py-4 pr-12">
              <DialogTitle>
                Trade · ticket {selected?.ticket ?? "—"}
              </DialogTitle>
              <p className="mt-1 text-xs text-[var(--fg-muted)]">
                {selected
                  ? `${selected.symbol} · ${selected.side.toUpperCase()} · ${inferTradeSession(selected.time)}`
                  : ""}
              </p>
            </div>
            {selected ? (
              <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-4">
                <Section title="Trade facts">
                  <dl>
                    <DetailRow label="Ticket" value={String(selected.ticket)} />
                    <DetailRow label="Deal" value={String(selected.deal)} />
                    <DetailRow label="Entry deal" value={String(selected.entryDeal)} />
                    <DetailRow
                      label="Exit deal"
                      value={selected.exitDeal == null ? NA : String(selected.exitDeal)}
                    />
                    <DetailRow label="Symbol" value={selected.symbol} />
                    <DetailRow label="Side" value={selected.side.toUpperCase()} />
                    <DetailRow label="Volume" value={formatNumber(selected.volume, 2)} />
                    <DetailRow label="Entry" value={formatNumber(selected.entry, 3)} />
                    <DetailRow
                      label="Exit"
                      value={selected.exit == null ? NA : formatNumber(selected.exit, 3)}
                    />
                    <DetailRow
                      label="SL"
                      value={selected.sl == null ? NA : formatNumber(selected.sl, 3)}
                    />
                    <DetailRow
                      label="TP"
                      value={selected.tp == null ? NA : formatNumber(selected.tp, 3)}
                    />
                    <DetailRow
                      label="Commission"
                      value={formatNumber(selected.commission, 2)}
                    />
                    <DetailRow label="Swap" value={formatNumber(selected.swap, 2)} />
                    <DetailRow label="Gross" value={formatNumber(selected.profit, 2)} />
                    <DetailRow label="Net" value={formatNumber(selected.netPl, 2)} />
                    <DetailRow
                      label="Duration"
                      value={
                        selected.durationMs == null
                          ? NA
                          : formatDuration(selected.durationMs)
                      }
                    />
                    <DetailRow
                      label="Session"
                      value={inferTradeSession(selected.time)}
                    />
                    <DetailRow
                      label="Strategy"
                      value={selected.strategy || NA}
                    />
                    <DetailRow
                      label="Comment"
                      value={selected.comment || NA}
                    />
                    <DetailRow label="Status" value={selected.status} />
                    <DetailRow
                      label="Time"
                      value={selected.time.toLocaleString()}
                    />
                  </dl>
                </Section>

                <Section title="Risk & reward">
                  <dl>
                    <DetailRow
                      label="Margin used"
                      value={
                        selectedMargin == null ? NA : formatNumber(selectedMargin, 2)
                      }
                    />
                    <DetailRow
                      label="Risk %"
                      value={
                        selectedRisk == null
                          ? NA
                          : `${formatNumber(selectedRisk, 2)}%`
                      }
                    />
                    <DetailRow
                      label="RR"
                      value={selectedRr == null ? NA : formatNumber(selectedRr, 2)}
                    />
                  </dl>
                </Section>

                <Section title="Broker & validation">
                  <dl>
                    <DetailRow label="Broker request" value={NA} />
                    <DetailRow label="Broker response" value={NA} />
                    <DetailRow label="Validation" value={NA} />
                    <DetailRow label="Order check" value={NA} />
                    <DetailRow label="Order send" value={NA} />
                    <DetailRow label="Latency" value={NA} />
                    <DetailRow label="Slippage" value={NA} />
                  </dl>
                </Section>

                <Section title="Context">
                  <dl>
                    <DetailRow label="Chart snapshot" value={NA} />
                    <DetailRow label="AI explanation" value={NA} />
                    <DetailRow label="Entry reason" value={NA} />
                    <DetailRow label="Exit reason" value={NA} />
                  </dl>
                </Section>

                <Section title="Execution timeline">
                  {selected.timeline.length === 0 ? (
                    <p className="text-xs text-[var(--fg-subtle)]">{NA}</p>
                  ) : (
                    <ol className="space-y-3 border-l border-[var(--border)] pl-3">
                      {selected.timeline.map((ev) => (
                        <li key={`${ev.label}-${ev.at.toISOString()}`}>
                          <p className="text-xs font-medium text-[var(--fg)]">{ev.label}</p>
                          <p className="font-mono text-[10px] text-[var(--fg-subtle)]">
                            {ev.at.toLocaleString()}
                          </p>
                          <p className="text-[11px] text-[var(--fg-muted)]">{ev.detail}</p>
                        </li>
                      ))}
                    </ol>
                  )}
                </Section>

                <Section title="Trade replay">
                  <TradeReplayPanel
                    requestId={selectedRequestId}
                    ticket={selectedRequestId ? undefined : selected.ticket}
                  />
                </Section>
              </div>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

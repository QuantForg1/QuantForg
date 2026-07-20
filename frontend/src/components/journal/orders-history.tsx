"use client";

import { useMemo, useState } from "react";
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
import { portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn, formatNumber } from "@/lib/utils";
import {
  computeTradeAnalytics,
  formatDuration,
  pairDealsIntoTrades,
  parseLiveDeal,
  rangeToIso,
  tradesToCsv,
  type HistoryRange,
  type LiveTrade,
} from "@/lib/orders/history";

const PAGE_SIZE = 25;

function Sparkline({
  points,
  className,
}: {
  points: { t: number; equity: number }[];
  className?: string;
}) {
  if (points.length < 2) {
    return (
      <div className={cn("flex h-28 items-center justify-center text-xs text-[var(--fg-subtle)]", className)}>
        No closed trades in range
      </div>
    );
  }
  const ys = points.map((p) => p.equity);
  const min = Math.min(...ys);
  const max = Math.max(...ys);
  const span = max - min || 1;
  const w = 320;
  const h = 96;
  const d = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * w;
      const y = h - ((p.equity - min) / span) * (h - 8) - 4;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={cn("h-28 w-full", className)} aria-hidden>
      <path d={d} fill="none" stroke="var(--accent)" strokeWidth="1.5" />
    </svg>
  );
}

function BarList({
  rows,
  empty,
}: {
  rows: { label: string; value: number }[];
  empty: string;
}) {
  if (!rows.length) {
    return <p className="py-6 text-center text-xs text-[var(--fg-subtle)]">{empty}</p>;
  }
  const max = Math.max(...rows.map((r) => Math.abs(r.value)), 1e-9);
  return (
    <ul className="space-y-2">
      {rows.slice(-12).map((r) => (
        <li key={r.label} className="grid grid-cols-[4.5rem_1fr_3.5rem] items-center gap-2 text-[11px]">
          <span className="font-mono text-[var(--fg-muted)]">{r.label}</span>
          <div className="h-1.5 overflow-hidden rounded bg-[var(--bg-elevated)]">
            <div
              className={cn(
                "h-full rounded",
                r.value >= 0 ? "bg-[var(--success)]" : "bg-[var(--danger)]",
              )}
              style={{ width: `${Math.min(100, (Math.abs(r.value) / max) * 100)}%` }}
            />
          </div>
          <span
            className={cn(
              "text-right font-mono",
              r.value >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
            )}
          >
            {formatNumber(r.value, 2)}
          </span>
        </li>
      ))}
    </ul>
  );
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

  const trades = useMemo(() => {
    const deals = asList(asRecord(historyQ.data).deals)
      .map((row) => parseLiveDeal(asRecord(row)))
      .filter((d): d is NonNullable<typeof d> => d != null);
    let rows = pairDealsIntoTrades(deals);
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
  }, [historyQ.data, symbol, side, status, search]);

  const analytics = useMemo(() => computeTradeAnalytics(trades), [trades]);
  const pageCount = Math.max(1, Math.ceil(trades.length / PAGE_SIZE));
  const pageRows = trades.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  const exportCsv = () => {
    if (!trades.length) {
      toast.message("No trades to export");
      return;
    }
    downloadBlob(`quantforg-orders-${Date.now()}.csv`, tradesToCsv(trades), "text/csv");
    toast.success("CSV exported");
  };

  const exportExcel = () => {
    // Spreadsheet-compatible TSV (Excel opens natively) — values from live deals only.
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

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-hidden p-4 md:p-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Journal · Live MT5
          </p>
          <h1 className="font-[family-name:var(--font-display)] text-xl text-[var(--fg)]">
            Orders History
          </h1>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">
            Real broker deals only — gateway synchronized · no mock fills
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
            <RefreshCw className={cn("mr-1.5 h-3.5 w-3.5", historyQ.isFetching && "animate-spin")} />
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

      <div className="grid shrink-0 gap-3 lg:grid-cols-4">
        {(
          [
            ["Win rate", analytics.winRate == null ? "—" : `${(analytics.winRate * 100).toFixed(1)}%`],
            [
              "Profit factor",
              analytics.profitFactor == null ? "—" : formatNumber(analytics.profitFactor, 2),
            ],
            [
              "Avg R:R",
              analytics.averageRr == null ? "—" : formatNumber(analytics.averageRr, 2),
            ],
            [
              "Max drawdown",
              analytics.maxDrawdown == null ? "—" : formatNumber(analytics.maxDrawdown, 2),
            ],
          ] as const
        ).map(([label, value]) => (
          <div
            key={label}
            className="rounded-lg border border-[var(--border)] bg-[var(--bg-panel)] px-3 py-2"
          >
            <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">{label}</p>
            <p className="mt-1 font-mono text-lg text-[var(--fg)]">{value}</p>
          </div>
        ))}
      </div>

      <div className="grid min-h-0 shrink-0 gap-3 lg:grid-cols-3">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-panel)] p-3">
          <p className="mb-2 text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
            Equity curve
          </p>
          <Sparkline points={analytics.equityCurve} />
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-panel)] p-3">
          <p className="mb-2 text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
            Daily P/L
          </p>
          <BarList
            rows={analytics.dailyPl.map((d) => ({ label: d.day.slice(5), value: d.pl }))}
            empty="No daily P/L in range"
          />
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-panel)] p-3">
          <p className="mb-2 text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
            Monthly returns
          </p>
          <BarList
            rows={analytics.monthlyReturns.map((d) => ({ label: d.month, value: d.pl }))}
            empty="No monthly returns in range"
          />
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-panel)] p-3">
        <div className="flex flex-wrap gap-1">
          {(
            [
              ["today", "Today"],
              ["week", "This week"],
              ["month", "This month"],
              ["custom", "Custom"],
            ] as const
          ).map(([id, label]) => (
            <Button
              key={id}
              type="button"
              size="sm"
              variant={range === id ? "default" : "outline"}
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
              onChange={(e) => setCustomFrom(e.target.value)}
              className="h-8 w-[9.5rem]"
            />
            <Input
              type="date"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
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
          className="h-8 rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 text-xs"
          value={side}
          onChange={(e) => {
            setSide(e.target.value as typeof side);
            setPage(0);
          }}
        >
          <option value="all">Side: all</option>
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
        <select
          className="h-8 rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 text-xs"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as typeof status);
            setPage(0);
          }}
        >
          <option value="all">Status: all</option>
          <option value="closed">Closed</option>
          <option value="open">Open</option>
        </select>
        <div className="relative min-w-[12rem] flex-1">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-subtle)]" />
          <Input
            placeholder="Search ticket, comment, strategy…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="h-8 pl-7"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-[var(--border)] bg-[var(--bg-panel)]">
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
          <table className="w-full min-w-[1200px] border-collapse text-left text-[11px]">
            <thead className="sticky top-0 z-10 bg-[var(--bg-elevated)] text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
              <tr>
                {[
                  "Time",
                  "Symbol",
                  "Side",
                  "Volume",
                  "Entry",
                  "Exit",
                  "SL",
                  "TP",
                  "Commission",
                  "Swap",
                  "P/L",
                  "Net P/L",
                  "Duration",
                  "Ticket",
                  "Deal",
                  "Strategy",
                  "Comment",
                  "",
                ].map((h) => (
                  <th key={h || "actions"} className="whitespace-nowrap px-2 py-2 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((t) => (
                <tr
                  key={t.id}
                  className="border-t border-[var(--border)]/70 hover:bg-[var(--bg-elevated)]/60"
                >
                  <td className="whitespace-nowrap px-2 py-2 font-mono text-[var(--fg-muted)]">
                    {t.time.toLocaleString()}
                  </td>
                  <td className="px-2 py-2 font-medium">{t.symbol}</td>
                  <td className="px-2 py-2">
                    <Badge tone={t.side === "buy" ? "success" : "danger"}>
                      {t.side.toUpperCase()}
                    </Badge>
                  </td>
                  <td className="px-2 py-2 font-mono">{formatNumber(t.volume, 2)}</td>
                  <td className="px-2 py-2 font-mono">{formatNumber(t.entry, 3)}</td>
                  <td className="px-2 py-2 font-mono">
                    {t.exit == null ? "—" : formatNumber(t.exit, 3)}
                  </td>
                  <td className="px-2 py-2 font-mono text-[var(--fg-subtle)]">—</td>
                  <td className="px-2 py-2 font-mono text-[var(--fg-subtle)]">—</td>
                  <td className="px-2 py-2 font-mono">{formatNumber(t.commission, 2)}</td>
                  <td className="px-2 py-2 font-mono">{formatNumber(t.swap, 2)}</td>
                  <td
                    className={cn(
                      "px-2 py-2 font-mono",
                      t.profit >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
                    )}
                  >
                    {formatNumber(t.profit, 2)}
                  </td>
                  <td
                    className={cn(
                      "px-2 py-2 font-mono font-medium",
                      t.netPl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
                    )}
                  >
                    {formatNumber(t.netPl, 2)}
                  </td>
                  <td className="px-2 py-2 font-mono">{formatDuration(t.durationMs)}</td>
                  <td className="px-2 py-2 font-mono">{t.ticket}</td>
                  <td className="px-2 py-2 font-mono">{t.deal}</td>
                  <td className="max-w-[7rem] truncate px-2 py-2 text-[var(--fg-muted)]">
                    {t.strategy || "—"}
                  </td>
                  <td className="max-w-[10rem] truncate px-2 py-2 text-[var(--fg-muted)]">
                    {t.comment || "—"}
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
              ))}
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

      <Dialog open={selected != null} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="max-w-lg">
          <DialogTitle>Trade details · ticket {selected?.ticket}</DialogTitle>
          {selected ? (
            <div className="space-y-4 text-sm">
              <dl className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <dt className="text-[var(--fg-subtle)]">Symbol</dt>
                  <dd className="font-medium">{selected.symbol}</dd>
                </div>
                <div>
                  <dt className="text-[var(--fg-subtle)]">Side</dt>
                  <dd className="font-medium uppercase">{selected.side}</dd>
                </div>
                <div>
                  <dt className="text-[var(--fg-subtle)]">Entry deal</dt>
                  <dd className="font-mono">{selected.entryDeal}</dd>
                </div>
                <div>
                  <dt className="text-[var(--fg-subtle)]">Exit deal</dt>
                  <dd className="font-mono">{selected.exitDeal ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-[var(--fg-subtle)]">Net P/L</dt>
                  <dd className="font-mono">{formatNumber(selected.netPl, 2)}</dd>
                </div>
                <div>
                  <dt className="text-[var(--fg-subtle)]">Status</dt>
                  <dd>{selected.status}</dd>
                </div>
              </dl>
              <div>
                <p className="mb-2 text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                  Broker execution timeline
                </p>
                <ol className="space-y-2 border-l border-[var(--border)] pl-3">
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
              </div>
              <p className="text-[11px] text-[var(--fg-subtle)]">
                SL/TP columns stay empty when the broker deal stream does not include stop
                levels — QuantForg never invents them.
              </p>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

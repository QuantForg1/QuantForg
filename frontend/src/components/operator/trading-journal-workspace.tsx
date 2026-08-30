"use client";

import { useMemo, useState } from "react";
import { Download, FileText, NotebookPen, Search } from "lucide-react";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLiveTrades } from "@/hooks/use-live-trades";
import { getOperatorNote, setOperatorNote } from "@/lib/operator/notes";
import { downloadText, exportPrintablePdf, toCsv } from "@/lib/operator/export";
import { computeTradeRr, formatDuration, inferTradeSession } from "@/lib/orders/history";
import { formatNumber } from "@/lib/utils";
import { executionApi, signalCenterApi } from "@/lib/api/endpoints";
import { useQuery } from "@tanstack/react-query";
import { asList, asRecord, str } from "@/lib/desk";

/**
 * Trading Journal — every LIVE closed trade becomes a journal row.
 * Operator notes/tags are client-side; metrics from LIVE deals only.
 */
export function TradingJournalWorkspace() {
  const { trades, loading, error, refetch } = useLiveTrades("month");
  const [q, setQ] = useState("");
  const [symbol, setSymbol] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [tagDraft, setTagDraft] = useState("");

  const journalQ = useQuery({
    queryKey: ["execution-journal", "trading-journal"],
    queryFn: () => executionApi.journal(120),
    staleTime: 20_000,
    refetchInterval: 40_000,
    retry: false,
  });
  const signalsQ = useQuery({
    queryKey: ["signals-center", "trading-journal"],
    queryFn: () => signalCenterApi.list({}),
    staleTime: 30_000,
    retry: false,
  });

  const closed = useMemo(
    () => trades.filter((t) => t.status === "closed"),
    [trades],
  );

  const symbols = useMemo(
    () => [...new Set(closed.map((t) => t.symbol))].sort(),
    [closed],
  );

  const signalBySymbol = useMemo(() => {
    const map = new Map<string, Record<string, unknown>>();
    for (const row of asList(
      asRecord(signalsQ.data).items || asRecord(signalsQ.data).signals || signalsQ.data,
    ).map(asRecord)) {
      const code = str(row.symbol || row.code).toUpperCase();
      if (code) map.set(code, row);
    }
    return map;
  }, [signalsQ.data]);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return closed.filter((t) => {
      if (symbol !== "all" && t.symbol !== symbol) return false;
      if (!needle) return true;
      const note = getOperatorNote(t.id);
      const hay = `${t.symbol} ${t.side} ${t.strategy} ${t.comment} ${note.notes} ${note.tags.join(" ")}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [closed, q, symbol]);

  const active = rows.find((t) => t.id === selected) ?? rows[0] ?? null;

  if (loading && !closed.length) return <DeskSkeleton rows={8} />;
  if (error && !closed.length) {
    return (
      <DeskError
        message="Unable to load closed trades for your account."
        onRetry={() => void refetch()}
      />
    );
  }

  const exportCsv = () => {
    const csv = toCsv(
      rows.map((t) => {
        const note = getOperatorNote(t.id);
        const sig = signalBySymbol.get(t.symbol) ?? {};
        const rr = computeTradeRr(t);
        return {
          id: t.id,
          time: t.time.toISOString(),
          symbol: t.symbol,
          direction: t.side,
          entry: t.entry,
          exit: t.exit,
          sl: t.sl,
          tp: t.tp,
          rr: rr ?? "",
          profit: t.netPl > 0 ? t.netPl : "",
          loss: t.netPl < 0 ? t.netPl : "",
          strategy: t.strategy,
          session: inferTradeSession(t.time),
          quality: str(sig.quality || sig.quality_score, ""),
          confidence: str(sig.confidence || sig.confidence_score, ""),
          outcome: t.netPl >= 0 ? "win" : "loss",
          tags: note.tags.join("|"),
          notes: note.notes,
        };
      }),
    );
    downloadText(`quantforg-trading-journal-${Date.now()}.csv`, csv, "text/csv");
  };

  const exportPdf = () => {
    exportPrintablePdf({
      title: "Trading Journal",
      subtitle: `${rows.length} closed trades · ${new Date().toISOString().slice(0, 10)}`,
      sections: [
        {
          heading: "Trades",
          html: `<table><thead><tr><th>Time</th><th>Symbol</th><th>Side</th><th>PnL</th><th>RR</th><th>Session</th></tr></thead><tbody>${rows
            .slice(0, 80)
            .map((t) => {
              const rr = computeTradeRr(t);
              return `<tr><td class="mono">${t.time.toISOString().slice(0, 19)}</td><td class="mono">${t.symbol}</td><td>${t.side}</td><td class="mono">${formatNumber(t.netPl, 2)}</td><td class="mono">${rr != null ? formatNumber(rr, 2) : "—"}</td><td>${inferTradeSession(t.time)}</td></tr>`;
            })
            .join("")}</tbody></table>`,
        },
      ],
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
          <div className="relative min-w-[12rem] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="pl-9"
              placeholder="Search symbol, strategy, tags, notes…"
              aria-label="Search journal"
            />
          </div>
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="h-9 rounded border border-[var(--border)] bg-[var(--surface)] px-2 text-[12px] text-[var(--fg)]"
            aria-label="Filter symbol"
          >
            <option value="all">All symbols</option>
            {symbols.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={exportCsv} disabled={!rows.length}>
            <Download className="mr-1 h-3.5 w-3.5" />
            CSV
          </Button>
          <Button size="sm" variant="outline" onClick={exportPdf} disabled={!rows.length}>
            <FileText className="mr-1 h-3.5 w-3.5" />
            PDF
          </Button>
        </div>
      </div>

      {!rows.length ? (
        <DeskEmpty
          icon={NotebookPen}
          title="No closed trades yet"
          description="Closed trades appear after they complete on your account. History is never fabricated."
        />
      ) : (
        <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="overflow-x-auto border border-[var(--border)]">
            <table className="min-w-full text-left text-[12px]">
              <thead className="bg-[var(--surface)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                <tr>
                  <th className="px-3 py-2">Time</th>
                  <th className="px-3 py-2">Symbol</th>
                  <th className="px-3 py-2">Dir</th>
                  <th className="px-3 py-2">Entry</th>
                  <th className="px-3 py-2">Exit</th>
                  <th className="px-3 py-2">RR</th>
                  <th className="px-3 py-2">PnL</th>
                  <th className="px-3 py-2">Session</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 200).map((t) => {
                  const rr = computeTradeRr(t);
                  const activeRow = active?.id === t.id;
                  return (
                    <tr
                      key={t.id}
                      className={`cursor-pointer border-t border-[var(--border)] ${activeRow ? "bg-[var(--accent-soft)]" : "hover:bg-[var(--surface-2)]"}`}
                      onClick={() => {
                        setSelected(t.id);
                        const n = getOperatorNote(t.id);
                        setNoteDraft(n.notes);
                        setTagDraft(n.tags.join(", "));
                      }}
                    >
                      <td className="px-3 py-2 font-mono text-[10px] text-[var(--fg-muted)]">
                        {t.time.toISOString().slice(0, 19)}
                      </td>
                      <td className="px-3 py-2 font-mono font-medium">{t.symbol}</td>
                      <td className="px-3 py-2 uppercase">{t.side}</td>
                      <td className="px-3 py-2 tabular">{formatNumber(t.entry, 5)}</td>
                      <td className="px-3 py-2 tabular">
                        {t.exit != null ? formatNumber(t.exit, 5) : "—"}
                      </td>
                      <td className="px-3 py-2 tabular">
                        {rr != null ? formatNumber(rr, 2) : "—"}
                      </td>
                      <td
                        className={`px-3 py-2 tabular ${t.netPl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}`}
                      >
                        {formatNumber(t.netPl, 2)}
                      </td>
                      <td className="px-3 py-2">{inferTradeSession(t.time)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {active ? (
            <DetailPanel
              tradeId={active.id}
              symbol={active.symbol}
              side={active.side}
              entry={active.entry}
              exit={active.exit}
              sl={active.sl}
              tp={active.tp}
              rr={computeTradeRr(active)}
              pnl={active.netPl}
              strategy={active.strategy || "—"}
              session={inferTradeSession(active.time)}
              hold={formatDuration(active.durationMs)}
              quality={str(
                signalBySymbol.get(active.symbol)?.quality ||
                  signalBySymbol.get(active.symbol)?.quality_score,
                "—",
              )}
              confidence={str(
                signalBySymbol.get(active.symbol)?.confidence ||
                  signalBySymbol.get(active.symbol)?.confidence_score,
                "—",
              )}
              aiReason={str(
                signalBySymbol.get(active.symbol)?.reason ||
                  signalBySymbol.get(active.symbol)?.ai_reason ||
                  signalBySymbol.get(active.symbol)?.thesis,
                "—",
              )}
              timeline={active.timeline}
              journalHint={str(
                asList(
                  asRecord(journalQ.data).items ||
                    asRecord(journalQ.data).events ||
                    journalQ.data,
                )
                  .map(asRecord)
                  .find((r) => str(r.symbol).toUpperCase() === active.symbol)
                  ?.message || "",
                "",
              )}
              noteDraft={noteDraft}
              tagDraft={tagDraft}
              onNoteChange={setNoteDraft}
              onTagChange={setTagDraft}
              onSave={() => {
                setOperatorNote(active.id, {
                  notes: noteDraft,
                  tags: tagDraft
                    .split(",")
                    .map((t) => t.trim())
                    .filter(Boolean),
                });
              }}
            />
          ) : null}
        </div>
      )}
    </div>
  );
}

function DetailPanel(props: {
  tradeId: string;
  symbol: string;
  side: string;
  entry: number;
  exit: number | null;
  sl: number | null;
  tp: number | null;
  rr: number | null;
  pnl: number;
  strategy: string;
  session: string;
  hold: string;
  quality: string;
  confidence: string;
  aiReason: string;
  timeline: { label: string; at: Date; detail: string }[];
  journalHint: string;
  noteDraft: string;
  tagDraft: string;
  onNoteChange: (v: string) => void;
  onTagChange: (v: string) => void;
  onSave: () => void;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
        <h3 className="font-mono text-[14px] font-semibold text-[var(--fg)]">
          {props.symbol}
        </h3>
      </header>
      <div className="space-y-3 p-3 text-[12px]">
        <dl className="grid grid-cols-2 gap-2">
          {[
            ["Direction", props.side.toUpperCase()],
            ["Entry", formatNumber(props.entry, 5)],
            ["Exit", props.exit != null ? formatNumber(props.exit, 5) : "—"],
            ["SL", props.sl != null ? formatNumber(props.sl, 5) : "—"],
            ["TP", props.tp != null ? formatNumber(props.tp, 5) : "—"],
            ["RR", props.rr != null ? formatNumber(props.rr, 2) : "—"],
            ["PnL", formatNumber(props.pnl, 2)],
            ["Strategy", props.strategy],
            ["Session", props.session],
            ["Hold", props.hold],
            ["Quality", props.quality],
            ["Confidence", props.confidence],
          ].map(([k, v]) => (
            <div key={k} className="border border-[var(--border)] px-2 py-1.5">
              <dt className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                {k}
              </dt>
              <dd className="mt-0.5 font-mono text-[var(--fg)]">{v}</dd>
            </div>
          ))}
        </dl>
        <div>
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            AI reason
          </p>
          <p className="text-[var(--fg-muted)]">{props.aiReason}</p>
          {props.journalHint ? (
            <p className="mt-1 text-[11px] text-[var(--fg-subtle)]">{props.journalHint}</p>
          ) : null}
        </div>
        <div>
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Execution timeline
          </p>
          <ul className="space-y-1">
            {props.timeline.length ? (
              props.timeline.map((ev, i) => (
                <li key={`${ev.label}-${i}`} className="flex gap-2 text-[11px]">
                  <span className="font-mono text-[var(--fg-subtle)]">
                    {ev.at.toISOString().slice(11, 19)}
                  </span>
                  <span className="text-[var(--fg)]">{ev.label}</span>
                  <span className="text-[var(--fg-muted)]">{ev.detail}</span>
                </li>
              ))
            ) : (
              <li className="text-[var(--fg-muted)]">No timeline events on this deal.</li>
            )}
          </ul>
        </div>
        <div className="space-y-2">
          <label className="block text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Notes
            <textarea
              value={props.noteDraft}
              onChange={(e) => props.onNoteChange(e.target.value)}
              className="mt-1 min-h-[72px] w-full rounded border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-[12px] text-[var(--fg)]"
            />
          </label>
          <label className="block text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Tags (comma-separated)
            <Input
              value={props.tagDraft}
              onChange={(e) => props.onTagChange(e.target.value)}
              className="mt-1"
            />
          </label>
          <Button size="sm" onClick={props.onSave}>
            Save notes
          </Button>
        </div>
      </div>
    </section>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Play, Pause, RotateCcw } from "lucide-react";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TradeReplayPanel } from "@/components/journal/trade-replay";
import { useLiveTrades } from "@/hooks/use-live-trades";
import { executionApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";
import { cn } from "@/lib/utils";

const PIPELINE = [
  "Signal",
  "Risk",
  "OMS",
  "Gateway",
  "Broker",
  "PME",
  "Exit",
] as const;

/**
 * AI Trade Replay — animated lifecycle over LIVE audits + closed trades.
 * Recommendations/markers only; never executes.
 */
export function AiTradeReplayWorkspace() {
  const params = useSearchParams();
  const tradeParam = params.get("trade");
  const { trades, loading } = useLiveTrades("month");
  const closed = useMemo(
    () => trades.filter((t) => t.status === "closed"),
    [trades],
  );
  const [tradeId, setTradeId] = useState<string>("");
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (tradeParam) setTradeId(tradeParam);
    else if (closed[0] && !tradeId) setTradeId(closed[0].id);
  }, [closed, tradeId, tradeParam]);

  const trade = closed.find((t) => t.id === tradeId) ?? closed[0] ?? null;

  const auditsQ = useQuery({
    queryKey: ["execution-audits-recent", "ai-replay"],
    queryFn: () => executionApi.audits(100),
    staleTime: 20_000,
    retry: false,
  });

  const requestId = useMemo(() => {
    if (!trade) return null;
    const all = asList(asRecord(auditsQ.data).items).map(asRecord);
    const hit = all.find(
      (r) =>
        num(r.order_ticket) === trade.ticket ||
        num(r.deal_ticket) === trade.deal ||
        num(asRecord(r.related_ids).order_ticket) === trade.ticket,
    );
    return str(hit?.request_id || "", "") || null;
  }, [auditsQ.data, trade]);

  useEffect(() => {
    if (!playing) return;
    if (step >= PIPELINE.length - 1) {
      setPlaying(false);
      return;
    }
    const id = window.setTimeout(() => setStep((s) => s + 1), 900);
    return () => window.clearTimeout(id);
  }, [playing, step]);

  if (loading && !closed.length) return <DeskSkeleton rows={6} />;
  if (!closed.length) {
    return (
      <DeskEmpty
        icon={Play}
        title="No trades to replay"
        description="Closed LIVE trades appear here automatically for institutional replay."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={trade?.id || ""}
          onChange={(e) => {
            setTradeId(e.target.value);
            setStep(0);
            setPlaying(false);
          }}
          className="h-9 min-w-[16rem] rounded border border-[var(--border)] bg-[var(--surface)] px-2 font-mono text-[12px] text-[var(--fg)]"
          aria-label="Select trade"
        >
          {closed.slice(0, 100).map((t) => (
            <option key={t.id} value={t.id}>
              {t.time.toISOString().slice(0, 16)} · {t.symbol} · {formatNumber(t.netPl, 2)}
            </option>
          ))}
        </select>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            if (step >= PIPELINE.length - 1) setStep(0);
            setPlaying((p) => !p);
          }}
        >
          {playing ? (
            <>
              <Pause className="mr-1 h-3.5 w-3.5" /> Pause
            </>
          ) : (
            <>
              <Play className="mr-1 h-3.5 w-3.5" /> Play
            </>
          )}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            setStep(0);
            setPlaying(false);
          }}
        >
          <RotateCcw className="mr-1 h-3.5 w-3.5" /> Reset
        </Button>
      </div>

      {trade ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Symbol", trade.symbol],
            ["Direction", trade.side.toUpperCase()],
            ["Entry", formatNumber(trade.entry, 5)],
            ["Exit", trade.exit != null ? formatNumber(trade.exit, 5) : "—"],
            ["SL", trade.sl != null ? formatNumber(trade.sl, 5) : "—"],
            ["TP", trade.tp != null ? formatNumber(trade.tp, 5) : "—"],
            ["PnL", formatNumber(trade.netPl, 2)],
            ["Trail / BE / Partial", "LIVE markers when present in audit"],
          ].map(([k, v]) => (
            <div key={k} className="border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                {k}
              </p>
              <p className="mt-1 font-mono text-[13px] text-[var(--fg)]">{v}</p>
            </div>
          ))}
        </div>
      ) : null}

      <ol className="grid gap-2 sm:grid-cols-7">
        {PIPELINE.map((label, i) => {
          const done = i <= step;
          const current = i === step;
          return (
            <li
              key={label}
              className={cn(
                "border px-2 py-3 text-center transition-colors duration-200",
                current
                  ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                  : done
                    ? "border-[var(--border)] bg-[var(--surface)]"
                    : "border-[var(--border)] opacity-50",
              )}
            >
              <Badge
                tone={current ? "success" : done ? "neutral" : "neutral"}
                className="mb-1 h-5 px-1.5 text-[10px]"
              >
                {i + 1}
              </Badge>
              <p className="text-[11px] font-medium text-[var(--fg)]">{label}</p>
            </li>
          );
        })}
      </ol>

      <TradeReplayPanel requestId={requestId} ticket={trade?.ticket ?? null} />
    </div>
  );
}

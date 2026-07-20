"use client";

import { memo, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { executionApi } from "@/lib/api/endpoints";
import { asList, asRecord, str, num } from "@/lib/desk";
import { cn, formatNumber } from "@/lib/utils";

const NA = "Not available";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[var(--border)]/70 bg-[var(--bg)]/30 px-2 py-1.5">
      <p className="text-[9px] uppercase tracking-wide text-[var(--fg-subtle)]">{label}</p>
      <p className="mt-0.5 break-all font-mono text-[11px] tabular-nums text-[var(--fg)]">
        {value || NA}
      </p>
    </div>
  );
}

/**
 * Trade Replay — immutable execution_audits timeline for a request_id.
 * Chart candle replay is Not available without historical bar storage.
 */
export const TradeReplayPanel = memo(function TradeReplayPanel({
  requestId,
  ticket,
  className,
}: {
  requestId?: string | null;
  ticket?: number | null;
  className?: string;
}) {
  const auditsQ = useQuery({
    queryKey: ["execution-audits", requestId],
    queryFn: () => executionApi.auditsByRequest(String(requestId)),
    enabled: Boolean(requestId && requestId.trim()),
    staleTime: 15_000,
    retry: false,
  });

  const recentQ = useQuery({
    queryKey: ["execution-audits-recent"],
    queryFn: () => executionApi.audits(100),
    enabled: !requestId && ticket != null && ticket > 0,
    staleTime: 15_000,
    retry: false,
  });

  const stages = useMemo(() => {
    if (requestId) {
      return asList(asRecord(auditsQ.data).items).map(asRecord);
    }
    const all = asList(asRecord(recentQ.data).items).map(asRecord);
    if (ticket == null) return [];
    return all.filter(
      (r) =>
        num(r.order_ticket) === ticket ||
        num(r.deal_ticket) === ticket ||
        num(asRecord(r.related_ids).order_ticket) === ticket,
    );
  }, [auditsQ.data, recentQ.data, requestId, ticket]);

  const loading = auditsQ.isLoading || recentQ.isLoading;

  return (
    <div className={cn("space-y-3", className)}>
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Trade Replay
        </p>
        <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
          Immutable execution audit stages · request{" "}
          <span className="font-mono">{requestId || NA}</span>
        </p>
      </div>

      {loading ? (
        <p className="text-[11px] text-[var(--fg-muted)]">Loading audit timeline…</p>
      ) : !stages.length ? (
        <p className="text-[11px] text-[var(--fg-muted)]">
          Not available — no durable audit rows for this trade yet. Audits persist after
          validate / risk / safety / submit on the new Execution Audit Engine.
        </p>
      ) : (
        <ol className="space-y-3 border-l border-[var(--border)] pl-3">
          {stages.map((s) => {
            const id = str(s.id, str(s.stage) + str(s.created_at));
            return (
              <li key={id} className="relative">
                <span className="absolute -left-[0.97rem] top-1 h-2 w-2 rounded-full bg-[var(--accent)]" />
                <p className="text-xs font-medium uppercase tracking-wide text-[var(--fg)]">
                  {str(s.stage, "stage")}
                  <span className="ml-2 font-mono text-[10px] normal-case text-[var(--fg-subtle)]">
                    {str(s.outcome)}
                  </span>
                </p>
                <p className="font-mono text-[10px] text-[var(--fg-subtle)]">
                  {str(s.created_at)}
                </p>
                <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
                  <Field
                    label="Latency"
                    value={
                      s.latency_ms != null && Number.isFinite(num(s.latency_ms, NaN))
                        ? `${formatNumber(num(s.latency_ms), 1)} ms`
                        : NA
                    }
                  />
                  <Field
                    label="Gateway latency"
                    value={
                      s.gateway_latency_ms != null &&
                      Number.isFinite(num(s.gateway_latency_ms, NaN))
                        ? `${formatNumber(num(s.gateway_latency_ms), 1)} ms`
                        : NA
                    }
                  />
                  <Field
                    label="Railway processing"
                    value={
                      s.railway_processing_ms != null &&
                      Number.isFinite(num(s.railway_processing_ms, NaN))
                        ? `${formatNumber(num(s.railway_processing_ms), 1)} ms`
                        : NA
                    }
                  />
                  <Field
                    label="Cloudflare latency"
                    value={
                      s.cloudflare_latency_ms != null &&
                      Number.isFinite(num(s.cloudflare_latency_ms, NaN))
                        ? `${formatNumber(num(s.cloudflare_latency_ms), 1)} ms`
                        : NA
                    }
                  />
                  <Field label="Spread" value={str(s.spread, NA)} />
                  <Field label="Slippage" value={str(s.slippage, NA)} />
                  <Field label="Commission" value={str(s.commission, NA)} />
                  <Field label="Swap" value={str(s.swap, NA)} />
                  <Field label="Margin used" value={str(s.margin_used, NA)} />
                  <Field label="Free margin" value={str(s.free_margin, NA)} />
                  <Field label="Balance" value={str(s.balance, NA)} />
                  <Field label="Equity" value={str(s.equity, NA)} />
                  <Field label="Leverage" value={str(s.leverage, NA)} />
                  <Field label="Broker server time" value={str(s.broker_server_time, NA)} />
                  <Field label="Market session" value={str(s.market_session, NA)} />
                  <Field label="Execution route" value={str(s.execution_route, NA)} />
                  <Field
                    label="Order ticket"
                    value={s.order_ticket != null ? String(s.order_ticket) : NA}
                  />
                  <Field
                    label="Deal ticket"
                    value={s.deal_ticket != null ? String(s.deal_ticket) : NA}
                  />
                </div>
                <details className="mt-2 text-[10px] text-[var(--fg-muted)]">
                  <summary className="cursor-pointer select-none">Payload in / out</summary>
                  <pre className="mt-1 max-h-40 overflow-auto rounded border border-[var(--border)] bg-[var(--bg)] p-2 font-mono">
                    {JSON.stringify(
                      { in: s.payload_in ?? {}, out: s.payload_out ?? {} },
                      null,
                      2,
                    )}
                  </pre>
                </details>
              </li>
            );
          })}
        </ol>
      )}

      <div className="rounded border border-[var(--border)] px-3 py-2">
        <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
          Chart replay
        </p>
        <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
          Not available — historical candle snapshots are not stored with audits. QuantForg
          never fabricates chart frames.
        </p>
      </div>
    </div>
  );
});

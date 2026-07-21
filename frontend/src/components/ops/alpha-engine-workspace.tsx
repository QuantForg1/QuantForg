"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CandlestickChart, Scale } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import {
  alphaEngineApi,
  decisionIntelligenceApi,
  mt5Api,
} from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

export function AlphaEngineWorkspace() {
  const qc = useQueryClient();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [diResult, setDiResult] = useState<Record<string, unknown> | null>(null);

  const statusQ = useQuery({
    queryKey: ["alpha-engine-status"],
    queryFn: () => alphaEngineApi.status(),
    staleTime: 20_000,
  });

  const historyQ = useQuery({
    queryKey: ["alpha-engine-history"],
    queryFn: () => alphaEngineApi.history(15),
    staleTime: 10_000,
  });

  const tickQ = useQuery({
    queryKey: ["alpha-engine-tick", TRADING_SYMBOL],
    queryFn: () => mt5Api.tick(TRADING_SYMBOL),
    staleTime: 5_000,
    retry: false,
  });

  const evaluateBody = useMemo(() => {
    const tick = asRecord(tickQ.data);
    const bid = tick.bid;
    const ask = tick.ask;
    let spread: number | null = null;
    if (typeof bid === "number" && typeof ask === "number") {
      spread = Math.abs(ask - bid);
    } else if (bid != null && ask != null) {
      const b = Number(bid);
      const a = Number(ask);
      if (Number.isFinite(b) && Number.isFinite(a)) spread = Math.abs(a - b);
    }
    const hasTick = bid != null || ask != null || spread != null;
    return {
      side: "buy",
      regime: hasTick
        ? {
            trend: null,
            atr: null,
            price: bid ?? null,
            news_driven: null,
            structure_label: null,
          }
        : null,
      liquidity: hasTick ? { spread, liquidity_pools: null, sweep_count: null } : null,
      structure: null,
      order_flow: null,
      opportunities: null,
      execution: hasTick
        ? { spread, session: null, timing_score: null }
        : null,
      exit_context: null,
      trade_factors: null,
      closed_trades: null,
    };
  }, [tickQ.data]);

  const evaluateM = useMutation({
    mutationFn: () => alphaEngineApi.evaluate(evaluateBody),
    onSuccess: async (data) => {
      setResult(data);
      setDiResult(null);
      toast.success("Alpha evaluation complete (advisory)");
      await qc.invalidateQueries({ queryKey: ["alpha-engine-history"] });
      await qc.invalidateQueries({ queryKey: ["alpha-engine-status"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Evaluate failed"),
  });

  const sendToDiM = useMutation({
    mutationFn: async () => {
      const alpha = asRecord(asRecord(result).decision_center_inputs);
      if (!Object.keys(alpha).length) {
        throw new Error("Run Alpha evaluate first");
      }
      return decisionIntelligenceApi.evaluate({
        side: str(alpha.side, "buy"),
        strategy_id: "alpha-engine-v1",
        signal_present: true,
        strategy_consensus_ok: true,
        alpha,
        // Risk/Safety intentionally unset → Decision Center HOLDs (fail closed)
      });
    },
    onSuccess: (data) => {
      setDiResult(data);
      toast.info(
        `${str(data.decision, "HOLD")} — Alpha mapped; Risk/Safety unchanged`,
      );
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Decision Center failed"),
  });

  const engines = asRecord(asRecord(result).engines);
  const caps = asRecord(statusQ.data?.capabilities);

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Alpha Engine unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <CandlestickChart className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">{TRADING_SYMBOL} market quality</span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Advisory only
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          No profitability promise
        </Badge>
        {caps.bypass_risk === false ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            Risk untouched
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "alpha-engine-v1")}
        </span>
        <Button
          size="sm"
          disabled={evaluateM.isPending}
          onClick={() => evaluateM.mutate()}
        >
          Evaluate
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={!result || sendToDiM.isPending}
          onClick={() => sendToDiM.mutate()}
        >
          <Scale className="mr-1 size-3.5" />
          Send to Decision Center
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Composite">
          {!result ? (
            <DeskEmpty
              icon={CandlestickChart}
              title="No evaluation"
              description="Run evaluate with live tick context when available. Missing fields stay unavailable — never invented."
            />
          ) : (
            <div className="space-y-2 text-[11px]">
              <div className="font-mono text-lg tabular-nums">
                {str(asRecord(result).composite_score, "—")}
              </div>
              <Badge
                tone={
                  asRecord(result).market_quality_ok ? "success" : "warning"
                }
              >
                {str(asRecord(result).market_quality_band, "unavailable")}
              </Badge>
              <div className="text-[10px] text-[var(--fg-subtle)]">
                audit: {str(asRecord(result).audit_id)}
              </div>
              {!tickQ.data || tickQ.isError ? (
                <p className="text-[10px] text-[var(--warning)]">
                  Live tick unavailable — some engines may be empty/unavailable
                </p>
              ) : (
                <p className="font-mono text-[10px] text-[var(--fg-subtle)]">
                  tick bid/ask used for spread only
                </p>
              )}
            </div>
          )}
        </Panel>

        <Panel
          title="Decision Center mapping"
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/decision-intelligence">Open</Link>
            </Button>
          }
        >
          {!result ? (
            <p className="text-[11px] text-[var(--fg-subtle)]">
              Alpha produces advisory inputs for Decision Center. It never sets
              Risk Engine or Safety Engine outcomes.
            </p>
          ) : (
            <pre className="max-h-40 overflow-auto border border-[var(--border)] bg-[var(--bg)] p-2 font-mono text-[10px]">
              {JSON.stringify(asRecord(result).decision_center_inputs, null, 2)}
            </pre>
          )}
        </Panel>

        <Panel title="Decision Center result">
          {!diResult ? (
            <DeskEmpty
              icon={Scale}
              title="Not sent"
              description="Send Alpha advisory to Decision Center. Without Risk/Safety passes, DI will HOLD (fail closed)."
            />
          ) : (
            <div className="space-y-2 text-[11px]">
              <Badge
                tone={
                  str(diResult.decision) === "APPROVE"
                    ? "success"
                    : str(diResult.decision) === "REJECT"
                      ? "danger"
                      : "warning"
                }
              >
                {str(diResult.decision, "HOLD")}
              </Badge>
              <div className="font-mono text-[10px]">
                allow_execution_path:{" "}
                {String(diResult.allow_execution_path)}
              </div>
              <pre className="max-h-28 overflow-auto border border-[var(--border)] bg-[var(--bg)] p-2 font-mono text-[10px]">
                {JSON.stringify(diResult.alpha_integration, null, 2)}
              </pre>
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Ten engines (explainable)">
        {!result ? (
          <DeskEmpty
            icon={CandlestickChart}
            title="Awaiting evaluate"
            description="Scores appear only from supplied facts."
          />
        ) : (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
            {Object.entries(engines).map(([id, raw]) => {
              const e = asRecord(raw);
              return (
                <div
                  key={id}
                  className={cn(
                    "border border-[var(--border)] bg-[var(--bg)] p-2",
                  )}
                >
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--fg-subtle)]">
                    {str(e.title, id)}
                  </div>
                  <div className="mt-1 flex items-center gap-2 font-mono text-sm">
                    {str(e.score, "—")}
                    <Badge
                      tone={
                        str(e.status) === "available"
                          ? e.passed
                            ? "success"
                            : "warning"
                          : "neutral"
                      }
                      className="text-[9px]"
                    >
                      {str(e.status)}
                    </Badge>
                  </div>
                  <ul className="mt-1 max-h-16 space-y-0.5 overflow-auto text-[9px] text-[var(--fg-muted)]">
                    {asList(e.reasons)
                      .slice(0, 4)
                      .map((r, i) => (
                        <li key={i}>{str(r)}</li>
                      ))}
                  </ul>
                </div>
              );
            })}
          </div>
        )}
      </Panel>

      <Panel title="Audit history">
        {asList(asRecord(historyQ.data).evaluations).length === 0 ? (
          <DeskEmpty
            icon={CandlestickChart}
            title="No evaluations"
            description="Every Alpha evaluate is auditable."
          />
        ) : (
          <ul className="max-h-40 space-y-1 overflow-auto font-mono text-[10px]">
            {asList(asRecord(historyQ.data).evaluations).map((row) => {
              const r = asRecord(row);
              return (
                <li
                  key={str(r.audit_id)}
                  className="flex justify-between border-b border-[var(--border)]/60 py-1"
                >
                  <span>{str(r.audit_id)}</span>
                  <span>
                    {str(r.composite_score, "—")} ·{" "}
                    {str(r.market_quality_band)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}

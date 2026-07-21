"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Activity, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { aiRobotApi, mt5Api, portfolioApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn, formatNumber } from "@/lib/utils";

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

function CapRow({ label, on }: { label: string; on: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-[var(--border)]/60 py-1.5 last:border-0">
      <span className="text-[12px] text-[var(--fg-muted)]">{label}</span>
      <Badge tone={on ? "success" : "neutral"} className="text-[10px]">
        {on ? "ON" : "OFF"}
      </Badge>
    </div>
  );
}

export function AiRobotWorkspace() {
  const session = useTradingSession();
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [evalResult, setEvalResult] = useState<Record<string, unknown> | null>(
    null,
  );

  const statusQ = useQuery({
    queryKey: ["ai-robot-status"],
    queryFn: () => aiRobotApi.status(),
    staleTime: 30_000,
  });

  const portfolioQ = useQuery({
    queryKey: ["portfolio-ai-robot"],
    queryFn: () => portfolioApi.get(),
    staleTime: 15_000,
  });

  const tickQ = useQuery({
    queryKey: ["mt5-tick", TRADING_SYMBOL, "ai-robot"],
    queryFn: () => mt5Api.tick(TRADING_SYMBOL),
    enabled: session.connected,
    staleTime: 2_000,
    refetchInterval: session.connected ? 5_000 : false,
    retry: false,
  });

  const evaluateM = useMutation({
    mutationFn: (body: Record<string, unknown>) => aiRobotApi.evaluate(body),
    onSuccess: (data) => {
      setEvalResult(data);
      if (data.allow_entry) {
        toast.success(
          "Robot V1: entry path clear — still requires Execution Gateway",
        );
      } else {
        toast.info("Robot V1: entry blocked by discipline gates");
      }
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : "Evaluate failed");
    },
  });

  const reportM = useMutation({
    mutationFn: () => aiRobotApi.selfAnalysis({}),
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : "Report failed");
    },
  });

  const caps = useMemo(() => {
    const raw = asRecord(statusQ.data?.capabilities);
    return Object.entries(raw).map(([k, v]) => ({
      key: k,
      on: Boolean(v),
      label: k.replace(/_/g, " "),
    }));
  }, [statusQ.data]);

  const equity = num(asRecord(portfolioQ.data?.account).equity, 0);
  const tick = asRecord(tickQ.data);
  const bid = num(tick.bid);
  const ask = num(tick.ask);
  const spread =
    Number.isFinite(bid) && Number.isFinite(ask) && ask >= bid
      ? Number((ask - bid).toFixed(2))
      : null;
  const mid =
    Number.isFinite(bid) && Number.isFinite(ask)
      ? Number(((bid + ask) / 2).toFixed(2))
      : null;

  const runEvaluate = () => {
    evaluateM.mutate({
      side,
      signal_present: true,
      strategy_id: "ai-robot-v1",
      strategy_valid: true,
      equity: equity || 10000,
      stop_distance: 5,
      spread,
      atr: mid != null ? Number((mid * 0.002).toFixed(2)) : 8,
      price: mid,
      daily_drawdown_pct: 0,
      consecutive_losses: 0,
      confluence: 70,
      trade_quality: 65,
      structure_bias_aligned: true,
      risk_engine_passed: null,
      safety_engine_passed: null,
    });
  };

  if (statusQ.isLoading) return <DeskSkeleton rows={6} />;
  if (statusQ.isError) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Could not load Robot V1 status."
        }
        onRetry={() => void statusQ.refetch()}
      />
    );
  }

  const status = statusQ.data ?? {};
  const pipeline = asList(status.pipeline).map(String);
  const evalPipeline = asList(asRecord(evalResult).pipeline);
  const filters = asList(asRecord(evalResult).filters);
  const blocked = asList(asRecord(evalResult).blocked_reasons).map(String);
  const report = reportM.data ?? asRecord(evalResult).self_analysis;

  return (
    <div className="grid gap-3 lg:grid-cols-12">
      <div className="space-y-3 lg:col-span-8">
        <Panel
          title="Mission"
          action={
            <Badge tone="neutral" className="font-mono text-[10px]">
              {str(status.version, "ai-robot-v1")}
            </Badge>
          }
        >
          <div className="flex items-start gap-3">
            <Shield className="mt-0.5 h-4 w-4 shrink-0 text-[var(--fg-subtle)]" />
            <div className="space-y-2">
              <p className="text-[13px] leading-relaxed text-[var(--fg)]">
                {str(
                  status.mission,
                  "Maximize discipline and capital preservation. Never promise profitability.",
                )}
              </p>
              <p className="text-[11px] text-[var(--fg-subtle)]">
                {str(status.disclaimer, "")}
              </p>
              <p className="font-mono text-[11px] text-[var(--fg-muted)]">
                Symbol {str(status.symbol, TRADING_SYMBOL)} · Pipeline:{" "}
                {pipeline.join(" → ") ||
                  "Signal → Strategy Validation → Risk → Safety → Execution"}
              </p>
            </div>
          </div>
        </Panel>

        <Panel
          title="Evaluate entry path"
          action={
            <div className="flex gap-1">
              <Button
                size="sm"
                variant={side === "buy" ? "default" : "outline"}
                onClick={() => setSide("buy")}
              >
                Buy
              </Button>
              <Button
                size="sm"
                variant={side === "sell" ? "default" : "outline"}
                onClick={() => setSide("sell")}
              >
                Sell
              </Button>
            </div>
          }
        >
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className="border border-[var(--border)] px-2 py-1.5">
              <div className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Equity
              </div>
              <div className="font-mono text-[13px]">
                {equity ? formatNumber(equity, 2) : "—"}
              </div>
            </div>
            <div className="border border-[var(--border)] px-2 py-1.5">
              <div className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Spread
              </div>
              <div className="font-mono text-[13px]">
                {spread != null ? formatNumber(spread, 2) : "—"}
              </div>
            </div>
            <div className="border border-[var(--border)] px-2 py-1.5">
              <div className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Mid
              </div>
              <div className="font-mono text-[13px]">
                {mid != null ? formatNumber(mid, 2) : "—"}
              </div>
            </div>
            <div className="border border-[var(--border)] px-2 py-1.5">
              <div className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Risk / Safety
              </div>
              <div className="font-mono text-[11px] text-[var(--fg-muted)]">
                Fail-closed until ALLOW
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={evaluateM.isPending}
              onClick={runEvaluate}
            >
              {evaluateM.isPending ? "Evaluating…" : "Run Robot V1 evaluate"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={reportM.isPending}
              onClick={() => reportM.mutate()}
            >
              Self-analysis report
            </Button>
          </div>
          {!evalResult ? (
            <div className="mt-3">
              <DeskEmpty
                icon={Shield}
                title="No evaluation yet"
                description="Robot V1 never places orders. Evaluate shows filter, sizing, confidence, and pipeline gates only."
              />
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-[12px] text-[var(--fg-muted)]">
                  allow_entry
                </span>
                <Badge tone={evalResult.allow_entry ? "success" : "danger"}>
                  {evalResult.allow_entry ? "true" : "false"}
                </Badge>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {evalPipeline.map((row, i) => {
                  const r = asRecord(row);
                  return (
                    <div
                      key={`${str(r.name)}-${i}`}
                      className={cn(
                        "border px-2 py-1.5",
                        r.passed
                          ? "border-[var(--border)]"
                          : "border-[var(--danger)]/40",
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-[11px] uppercase">
                          {str(r.name)}
                        </span>
                        <Badge tone={r.passed ? "success" : "warning"}>
                          {r.passed ? "pass" : "block"}
                        </Badge>
                      </div>
                      <p className="mt-1 text-[11px] text-[var(--fg-subtle)]">
                        {str(r.reason)}
                      </p>
                    </div>
                  );
                })}
              </div>
              <div>
                <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  Filters
                </h3>
                <div className="grid gap-1 sm:grid-cols-2">
                  {filters.map((row, i) => {
                    const r = asRecord(row);
                    return (
                      <div
                        key={`${str(r.name)}-${i}`}
                        className="flex items-center justify-between gap-2 border border-[var(--border)] px-2 py-1 text-[12px]"
                      >
                        <span>{str(r.name)}</span>
                        <span
                          className={
                            r.passed
                              ? "text-[var(--fg-muted)]"
                              : "text-[var(--danger)]"
                          }
                        >
                          {r.passed ? "pass" : "block"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
              {blocked.length > 0 ? (
                <ul className="list-inside list-disc text-[12px] text-[var(--fg-muted)]">
                  {blocked.slice(0, 8).map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          )}
        </Panel>

        {report ? (
          <Panel title="Self-analysis">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Badge tone="neutral">{str(asRecord(report).status)}</Badge>
              <span className="font-mono text-[12px]">
                discipline {str(asRecord(report).discipline_score)}
              </span>
            </div>
            <ul className="mb-2 list-inside list-disc text-[12px] text-[var(--fg-muted)]">
              {asList(asRecord(report).findings)
                .map(String)
                .slice(0, 6)
                .map((f) => (
                  <li key={f}>{f}</li>
                ))}
            </ul>
            <p className="text-[11px] text-[var(--fg-subtle)]">
              {str(asRecord(report).disclaimer, "")}
            </p>
          </Panel>
        ) : null}
      </div>

      <div className="space-y-3 lg:col-span-4">
        <Panel title="Capabilities (15)">
          {caps.length === 0 ? (
            <DeskEmpty
              icon={Activity}
              title="No capabilities"
              description="Status payload empty."
            />
          ) : (
            caps
              .filter(
                (c) =>
                  ![
                    "martingale",
                    "grid",
                    "average_losing_positions",
                  ].includes(c.key),
              )
              .map((c) => <CapRow key={c.key} label={c.label} on={c.on} />)
          )}
          <div className="mt-2 border-t border-[var(--border)] pt-2">
            <p className="mb-1 text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
              Hard-locked off
            </p>
            {["martingale", "grid", "average_losing_positions"].map((k) => (
              <CapRow key={k} label={k.replace(/_/g, " ")} on={false} />
            ))}
          </div>
        </Panel>
        <Panel title="Smart management (PME)">
          <pre className="overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(status.smart_management ?? {}, null, 2)}
          </pre>
        </Panel>
      </div>
    </div>
  );
}

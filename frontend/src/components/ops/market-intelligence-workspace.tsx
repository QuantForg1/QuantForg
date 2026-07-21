"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Radar, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import {
  marketIntelligenceApi,
  mt5Api,
  portfolioApi,
} from "@/lib/api/endpoints";
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

export function MarketIntelligenceWorkspace() {
  const session = useTradingSession();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const statusQ = useQuery({
    queryKey: ["market-intelligence-status"],
    queryFn: () => marketIntelligenceApi.status(),
    staleTime: 30_000,
  });

  const portfolioQ = useQuery({
    queryKey: ["portfolio-market-intelligence"],
    queryFn: () => portfolioApi.get(),
    staleTime: 15_000,
  });

  const tickQ = useQuery({
    queryKey: ["mt5-tick", TRADING_SYMBOL, "market-intelligence"],
    queryFn: () => mt5Api.tick(TRADING_SYMBOL),
    enabled: session.connected,
    staleTime: 2_000,
    refetchInterval: session.connected ? 5_000 : false,
    retry: false,
  });

  const evaluateM = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      marketIntelligenceApi.evaluate(body),
    onSuccess: (data) => {
      setResult(data);
      if (data.allow_submit) {
        toast.success("Pre-submit gates clear — still requires Execution Gateway");
      } else {
        toast.info("Submit blocked — review Market Intelligence gates");
      }
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : "Evaluate failed");
    },
  });

  const equity = num(asRecord(portfolioQ.data?.account).equity, 0);
  const tick = asRecord(tickQ.data);
  const bid = num(tick.bid);
  const ask = num(tick.ask);
  const mid =
    Number.isFinite(bid) && Number.isFinite(ask)
      ? Number(((bid + ask) / 2).toFixed(2))
      : null;

  const caps = useMemo(() => {
    const raw = asRecord(statusQ.data?.capabilities);
    return Object.entries(raw)
      .filter(([k]) => !["martingale", "grid", "average_down"].includes(k))
      .map(([k, v]) => ({ key: k, on: Boolean(v), label: k.replace(/_/g, " ") }));
  }, [statusQ.data]);

  const runEvaluate = (withGates: boolean) => {
    evaluateM.mutate({
      regime: {
        trend: "up",
        atr: mid != null ? Number((mid * 0.002).toFixed(2)) : 8,
        price: mid ?? 4000,
        news_driven: false,
        structure_label: "bullish_structure",
      },
      strategy_signals: [
        {
          strategy_id: "smc_bos",
          enabled: true,
          side: "buy",
          confidence: 78,
        },
        {
          strategy_id: "fvg_reclaim",
          enabled: true,
          side: "buy",
          confidence: 72,
        },
      ],
      opportunities: [
        {
          signal_id: "opp_1",
          strategy_id: "smc_bos",
          side: "buy",
          confidence: 78,
          score: 82,
        },
        {
          signal_id: "opp_2",
          strategy_id: "fvg_reclaim",
          side: "buy",
          confidence: 72,
          score: 74,
        },
      ],
      execution_quality: {
        entry_quality: 70,
        exit_quality: 68,
        timing_quality: 72,
        sample_note: "Operator-supplied sample scores for dry evaluation",
      },
      portfolio_risk: {
        equity: equity || 10000,
        allocated_pct: 25,
        daily_risk_used_pct: 0.5,
      },
      ai_health: {
        decision_quality: 70,
        execution_success: 65,
        risk_discipline: 80,
        system_reliability: 85,
      },
      day_trades: [],
      violations: [],
      risk_engine_passed: withGates ? true : null,
      safety_engine_passed: withGates ? true : null,
    });
  };

  if (statusQ.isLoading) return <DeskSkeleton rows={6} />;
  if (statusQ.isError) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Could not load Market Intelligence."
        }
        onRetry={() => void statusQ.refetch()}
      />
    );
  }

  const status = statusQ.data ?? {};
  const regime = asRecord(asRecord(result).regime);
  const consensus = asRecord(asRecord(result).consensus);
  const opportunities = asRecord(asRecord(result).opportunities);
  const review = asRecord(asRecord(result).trade_review);
  const portfolio = asRecord(asRecord(result).portfolio_risk);
  const health = asRecord(asRecord(result).ai_health);
  const daily = asRecord(asRecord(result).daily_report);
  const execQ = asRecord(asRecord(result).execution_quality);
  const ranked = asList(opportunities.ranked);

  return (
    <div className="grid gap-3 lg:grid-cols-12">
      <div className="space-y-3 lg:col-span-8">
        <Panel
          title="Mission"
          action={
            <Badge tone="neutral" className="font-mono text-[10px]">
              {str(status.version, "market-intelligence-v1")}
            </Badge>
          }
        >
          <div className="flex items-start gap-3">
            <Radar className="mt-0.5 h-4 w-4 shrink-0 text-[var(--fg-subtle)]" />
            <div className="space-y-2">
              <p className="text-[13px] leading-relaxed text-[var(--fg)]">
                {str(
                  asRecord(status.config).mission,
                  "Evaluate market conditions before any strategy may submit.",
                )}
              </p>
              <p className="text-[11px] text-[var(--fg-subtle)]">
                {str(status.disclaimer, "")}
              </p>
            </div>
          </div>
        </Panel>

        <Panel title="Pre-submit evaluation">
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
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
              onClick={() => runEvaluate(false)}
            >
              Evaluate (fail-closed Risk/Safety)
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={evaluateM.isPending}
              onClick={() => runEvaluate(true)}
            >
              Simulate Risk+Safety ALLOW
            </Button>
          </div>
          {!result ? (
            <div className="mt-3">
              <DeskEmpty
                icon={Shield}
                title="No evaluation yet"
                description="Market Intelligence never invents quotes or fills. Supply real analytics or leave panels empty."
              />
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={asRecord(result).allow_submit ? "success" : "danger"}>
                  allow_submit={String(Boolean(asRecord(result).allow_submit))}
                </Badge>
                <Badge tone="neutral">
                  regime {str(regime.primary)}
                </Badge>
                <Badge tone={consensus.accepted ? "success" : "warning"}>
                  consensus {consensus.accepted ? "ok" : "block"}
                </Badge>
              </div>
              <p className="text-[12px] text-[var(--fg-muted)]">
                {str(review.operator_summary)}
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {ranked.slice(0, 4).map((row, i) => {
                  const r = asRecord(row);
                  return (
                    <div
                      key={`${str(r.signal_id)}-${i}`}
                      className={cn(
                        "border px-2 py-1.5",
                        r.eligible
                          ? "border-[var(--border)]"
                          : "border-[var(--danger)]/40",
                      )}
                    >
                      <div className="flex justify-between gap-2 font-mono text-[11px]">
                        <span>
                          #{str(r.rank)} {str(r.strategy_id)}
                        </span>
                        <span>{str(r.score)}</span>
                      </div>
                      <p className="mt-1 text-[10px] text-[var(--fg-subtle)]">
                        {str(r.reason)}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </Panel>

        {result ? (
          <Panel title="AI trade review">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  Strengths
                </h3>
                <ul className="list-inside list-disc text-[12px] text-[var(--fg-muted)]">
                  {asList(review.strengths)
                    .map(String)
                    .slice(0, 6)
                    .map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                </ul>
              </div>
              <div>
                <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  Weaknesses
                </h3>
                <ul className="list-inside list-disc text-[12px] text-[var(--fg-muted)]">
                  {asList(review.weaknesses)
                    .map(String)
                    .slice(0, 6)
                    .map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                </ul>
              </div>
            </div>
            <p className="mt-3 text-[11px] text-[var(--fg-subtle)]">
              {str(review.disclaimer)}
            </p>
          </Panel>
        ) : null}
      </div>

      <div className="space-y-3 lg:col-span-4">
        <Panel title="Capabilities (8)">
          {caps.map((c) => (
            <div
              key={c.key}
              className="flex items-center justify-between gap-2 border-b border-[var(--border)]/60 py-1.5 last:border-0"
            >
              <span className="text-[12px] text-[var(--fg-muted)]">{c.label}</span>
              <Badge tone={c.on ? "success" : "neutral"}>
                {c.on ? "ON" : "OFF"}
              </Badge>
            </div>
          ))}
        </Panel>
        <Panel title="Portfolio risk">
          <pre className="overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(portfolio, null, 2)}
          </pre>
        </Panel>
        <Panel title="AI health">
          <pre className="overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(health, null, 2)}
          </pre>
        </Panel>
        <Panel title="Execution quality">
          <pre className="overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(execQ, null, 2)}
          </pre>
        </Panel>
        <Panel title="Daily validation">
          <pre className="overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(daily, null, 2)}
          </pre>
        </Panel>
      </div>
    </div>
  );
}

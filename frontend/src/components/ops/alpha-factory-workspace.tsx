"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FlaskConical, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { alphaFactoryApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

export function AlphaFactoryWorkspace() {
  const qc = useQueryClient();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const statusQ = useQuery({
    queryKey: ["alpha-factory-status"],
    queryFn: () => alphaFactoryApi.status(),
    staleTime: 15_000,
  });

  const evaluateM = useMutation({
    mutationFn: () =>
      alphaFactoryApi.evaluate({
        author: "researcher",
        experiment: {
          author: "researcher",
          version: "0.2.0",
          status: "active",
          description: "Liquidity sweep reclaim variant",
          family: "Liquidity",
        },
        strategy: {
          id: "lab_liq_1",
          family: "Liquidity",
          name: "Sweep Reclaim Lab",
          certified: false,
        },
        strategies: [
          {
            id: "lab_smc_1",
            family: "SMC",
            name: "BOS Continuation",
            certified: true,
          },
        ],
        replay: {
          timeframe: "5m",
          trades: Array.from({ length: 22 }, (_, i) => ({
            id: `r${i}`,
            pnl: i % 3 === 0 ? -8 : 12,
          })),
          expectancy: 4.2,
          drawdown: 3.1,
          profit_factor: 1.45,
          equity_curve: [100, 104, 101, 110],
          journal: [{ note: "Supplied replay journal row" }],
        },
        paper: {
          trades: Array.from({ length: 12 }, (_, i) => ({
            id: `p${i}`,
            pnl: i % 4 === 0 ? -5 : 9,
          })),
          performance: { expectancy: 2.1, win_rate: 58 },
          risk_metrics: { max_dd: 2.4 },
          execution_timing: { avg_latency_ms: 45 },
        },
        benchmarks: [
          {
            name: "A",
            win_rate: 55,
            profit_factor: 1.4,
            drawdown: 4,
            expectancy: 3,
            trade_count: 40,
          },
          {
            name: "B",
            win_rate: 48,
            profit_factor: 1.1,
            drawdown: 6,
            expectancy: 1.2,
            trade_count: 35,
          },
          {
            name: "C",
            win_rate: 52,
            profit_factor: 1.25,
            drawdown: 5,
            expectancy: 2,
            trade_count: 28,
          },
        ],
        promotion: {
          stage: "Paper Trading",
          approvals: { research: true, risk: false, operator: false },
          observed_regimes: ["trend", "london"],
          observed_sessions: ["london", "new_york"],
          risk_profile: "moderate",
          known_limitations: ["Lab only — not production certified"],
        },
        score_inputs: {
          consistency: 72,
          risk_discipline: 80,
          edge_stability: 68,
          capital_preservation: 75,
          market_adaptability: 70,
          execution_quality: 74,
        },
        history_event: {
          experiment_id: "exp_demo",
          changes: "Adjusted sweep filter",
          comments: "Append-only history demo",
        },
      }),
    onSuccess: async (data) => {
      setResult(data);
      toast.success(
        `Alpha Factory · stage ${str(asRecord(data.research_summary).promotion_stage, "—")}`,
      );
      await qc.invalidateQueries({ queryKey: ["alpha-factory-status"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Evaluate failed"),
  });

  const caps = asRecord(statusQ.data?.capabilities);
  const summary = asRecord(asRecord(result).research_summary);
  const certified = asRecord(asRecord(result).certified_strategies);
  const modules = asRecord(asRecord(result).modules);
  const certItems = asList(certified.items);

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Alpha Factory unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <FlaskConical className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">{TRADING_SYMBOL} Alpha Factory</span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Outside production
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          No auto-promote
        </Badge>
        {caps.never_modify_live_strategy === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            Live strategy locked
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "alpha-factory")}
        </span>
        <Button
          size="sm"
          disabled={evaluateM.isPending}
          onClick={() => evaluateM.mutate()}
        >
          Run research cycle
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Research summary">
          {!result ? (
            <DeskEmpty
              icon={FlaskConical}
              title="No cycle"
              description="Create experiments · replay · paper · promote gates"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Active experiments</span>
                <span className="font-mono">
                  {str(summary.active_experiments, "0")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Promotion stage</span>
                <span className="font-mono text-[10px]">
                  {str(summary.promotion_stage, "—")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Alpha score</span>
                <span className="font-mono">
                  {str(summary.alpha_score, "Insufficient Data")}
                </span>
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                Audit {str(result.audit_id, "—")}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Certified (research metadata)">
          {!result ? (
            <DeskEmpty
              icon={Shield}
              title="No certifications"
              description="Certified ≠ live enablement"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Count</span>
                <span className="font-mono">{str(certified.count, "0")}</span>
              </div>
              <ul className="max-h-28 space-y-1 overflow-auto font-mono text-[10px]">
                {certItems.length === 0 ? (
                  <li className="text-[var(--fg-subtle)]">None certified</li>
                ) : (
                  certItems.map((item) => {
                    const row = asRecord(item);
                    return (
                      <li key={str(row.id, "c")}>
                        {str(row.name, str(row.id))} · {str(row.family)}
                      </li>
                    );
                  })
                )}
              </ul>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                {str(certified.note, "")}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Isolation guarantees">
          <ul className="space-y-1 text-[10px] text-[var(--fg-muted)]">
            <li>Never modifies live strategy</li>
            <li>Never modifies Risk / Safety / Decision</li>
            <li>Never modifies Execution / Auto Trading</li>
            <li>Never automatic promotion to Production</li>
          </ul>
        </Panel>
      </div>

      <Panel title="Modules">
        {!Object.keys(modules).length ? (
          <DeskEmpty
            icon={FlaskConical}
            title="No modules"
            description="Workspace → promotion report"
          />
        ) : (
          <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
            {Object.entries(modules).map(([key, val]) => {
              const row = asRecord(val);
              return (
                <li
                  key={key}
                  className={cn(
                    "border px-2 py-2",
                    row.status === "insufficient_data"
                      ? "border-[var(--warning)]/40"
                      : "border-[var(--border)]",
                  )}
                >
                  <p className="text-[10px] font-medium leading-tight">
                    {str(row.module, key).replace(/_/g, " ")}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-[var(--fg-subtle)]">
                    {str(row.status, "—")} · {str(row.score, "—")}
                  </p>
                  <p className="mt-1 text-[9px] text-[var(--fg-muted)] line-clamp-2">
                    {str(row.recommendation, "")}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}

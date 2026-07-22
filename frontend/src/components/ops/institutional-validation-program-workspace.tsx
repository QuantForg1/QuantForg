"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ClipboardCheck, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { institutionalValidationProgramApi } from "@/lib/api/endpoints";
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

function sampleTrades(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    id: `t${i}`,
    pnl: i % 3 === 0 ? -12 : 18,
    rr: i % 3 === 0 ? -1 : 1.4,
    hold_minutes: 8 + (i % 20),
    regime: [
      "trend",
      "range",
      "high_volatility",
      "low_volatility",
      "london",
      "new_york",
      "asia",
      "news",
    ][i % 8],
  }));
}

export function InstitutionalValidationProgramWorkspace() {
  const qc = useQueryClient();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const statusQ = useQuery({
    queryKey: ["ivp-status"],
    queryFn: () => institutionalValidationProgramApi.status(),
    staleTime: 15_000,
  });

  const evaluateM = useMutation({
    mutationFn: () =>
      institutionalValidationProgramApi.evaluate({
        strategy_id: "scalp_xau_v2",
        configuration_id: "cfg_a",
        completed_trades: sampleTrades(60),
        configurations: [
          {
            id: "cfg_a",
            trades: sampleTrades(40),
          },
          {
            id: "cfg_b",
            trades: sampleTrades(35).map((t, i) => ({
              ...t,
              pnl: i % 4 === 0 ? -10 : 14,
            })),
          },
        ],
        risk_facts: {
          capital_preservation: { status: "observed", max_loss_pct: 2.1 },
          drawdown_behavior: { peak_to_trough: 3.4 },
          position_sizing_consistency: { variance: 0.12 },
          risk_rule_compliance: { violations: 0 },
        },
        replay_results: {
          expectancy: 4.2,
          win_rate: 58,
          profit_factor: 1.4,
          drawdown: 3.1,
          trade_count: 60,
        },
        paper_results: {
          expectancy: 2.8,
          win_rate: 54,
          profit_factor: 1.25,
          drawdown: 4.0,
          trade_count: 48,
        },
        history_event: {
          comments: "Append-only validation demo",
        },
      }),
    onSuccess: async (data) => {
      setResult(data);
      const summary = asRecord(data.evidence_summary);
      toast.success(
        `IVP · strength ${str(summary.strength_pct, "—")}%`,
      );
      await qc.invalidateQueries({ queryKey: ["ivp-status"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Evaluate failed"),
  });

  const caps = asRecord(statusQ.data?.capabilities);
  const summary = asRecord(asRecord(result).evidence_summary);
  const modules = asRecord(asRecord(result).modules);
  const dash = asRecord(modules.evidence_dashboard);
  const dashDetails = asRecord(dash.details);
  const hdp = asRecord(modules.human_decision_package);
  const hdpDetails = asRecord(hdp.details);
  const strengths = asList(dashDetails.known_strengths);
  const weaknesses = asList(dashDetails.known_weaknesses);
  const unknowns = asList(dashDetails.unknown_areas);

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "IVP unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <ClipboardCheck className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">
          {TRADING_SYMBOL} Institutional Validation Program
        </span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Read-only
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          Never trades
        </Badge>
        {caps.never_auto_promote_research === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            No auto-promote
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "ivp")}
        </span>
        <Button
          size="sm"
          disabled={evaluateM.isPending}
          onClick={() => evaluateM.mutate()}
        >
          Run validation
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Evidence summary">
          {!result ? (
            <DeskEmpty
              icon={ClipboardCheck}
              title="No evaluation"
              description="Supply trades · regimes · replay vs paper"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Evidence strength</span>
                <span className="font-mono">
                  {str(summary.strength_pct, "—")}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Sample size</span>
                <span className="font-mono">
                  {str(summary.sample_size, "—")}
                </span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-[var(--fg-muted)]">Deployment</span>
                <span className="font-mono text-[10px] text-right">
                  {str(summary.deployment_recommendation, "NONE")}
                </span>
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                Audit {str(result.audit_id, "—")}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Evidence dashboard">
          {!result ? (
            <DeskEmpty
              icon={Shield}
              title="Await evaluation"
              description="Strengths · weaknesses · unknowns"
            />
          ) : (
            <div className="space-y-2 text-[10px]">
              <div>
                <p className="mb-1 text-[var(--fg-muted)]">Strengths</p>
                <ul className="max-h-16 space-y-0.5 overflow-auto font-mono">
                  {strengths.length === 0 ? (
                    <li className="text-[var(--fg-subtle)]">—</li>
                  ) : (
                    strengths.slice(0, 4).map((s) => (
                      <li key={String(s)}>{String(s)}</li>
                    ))
                  )}
                </ul>
              </div>
              <div>
                <p className="mb-1 text-[var(--fg-muted)]">Weaknesses</p>
                <ul className="max-h-16 space-y-0.5 overflow-auto font-mono">
                  {weaknesses.length === 0 ? (
                    <li className="text-[var(--fg-subtle)]">—</li>
                  ) : (
                    weaknesses.slice(0, 4).map((s) => (
                      <li key={String(s)}>{String(s)}</li>
                    ))
                  )}
                </ul>
              </div>
              <div>
                <p className="mb-1 text-[var(--fg-muted)]">Unknowns</p>
                <ul className="max-h-16 space-y-0.5 overflow-auto font-mono">
                  {unknowns.length === 0 ? (
                    <li className="text-[var(--fg-subtle)]">—</li>
                  ) : (
                    unknowns.slice(0, 3).map((s) => (
                      <li key={String(s)}>{String(s)}</li>
                    ))
                  )}
                </ul>
              </div>
            </div>
          )}
        </Panel>

        <Panel title="Guarantees">
          <ul className="space-y-1 text-[10px] text-[var(--fg-muted)]">
            <li>Never places trades</li>
            <li>Never modifies strategies / execution</li>
            <li>Never modifies Risk / Safety / Decision</li>
            <li>Never auto-promotes research</li>
            <li>Append-only validation history</li>
          </ul>
          {hdpDetails.executive_summary ? (
            <p className="mt-2 text-[10px] text-[var(--fg-subtle)] line-clamp-4">
              {str(hdpDetails.executive_summary)}
            </p>
          ) : null}
        </Panel>
      </div>

      <Panel title="Modules">
        {!Object.keys(modules).length ? (
          <DeskEmpty
            icon={ClipboardCheck}
            title="No modules"
            description="Statistical → decision package"
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
                    row.status === "insufficient_evidence" ||
                      row.recommendation === "INSUFFICIENT EVIDENCE"
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

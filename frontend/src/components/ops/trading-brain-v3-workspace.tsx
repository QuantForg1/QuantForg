"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Brain, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { tradingBrainV3Api } from "@/lib/api/endpoints";
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

export function TradingBrainV3Workspace() {
  const qc = useQueryClient();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [riskOk, setRiskOk] = useState(true);
  const [safetyOk, setSafetyOk] = useState(true);

  const statusQ = useQuery({
    queryKey: ["trading-brain-v3-status"],
    queryFn: () => tradingBrainV3Api.status(),
    staleTime: 15_000,
  });

  const historyQ = useQuery({
    queryKey: ["trading-brain-v3-history"],
    queryFn: () => tradingBrainV3Api.history(15),
    staleTime: 10_000,
  });

  const evaluateM = useMutation({
    mutationFn: () =>
      tradingBrainV3Api.evaluate({
        side: "buy",
        spread: 0.35,
        atr: 12,
        regime: "trend",
        session: "london",
        news_blackout: false,
        kill_switch: false,
        confidence: 72,
        opportunity_candidates: [
          { id: "sweep-a", label: "liquidity sweep", score: 78 },
          { id: "fvg-b", label: "fvg fill", score: 64 },
        ],
        decision_center: { decision: "APPROVE", allow_execution_path: true },
        risk_engine_passed: riskOk,
        safety_engine_passed: safetyOk,
        execution_mode: "LIVE",
        open_positions: 1,
        unrealized_pnl: 12.5,
        active_trade: { side: "buy", mfe: 8, mae: -2 },
        closed_trades: [
          { pnl: 20, slippage: 0.1 },
          { pnl: -8, slippage: 0.2 },
        ],
        quality_metrics: { process_adherence: 80 },
        operator_notes: ["Preserve capital first"],
      }),
    onSuccess: async (data) => {
      setResult(data);
      toast.success(
        `Brain → ${str(data.recommendation, "No Trade")} (advisory)`,
      );
      await qc.invalidateQueries({ queryKey: ["trading-brain-v3-status"] });
      await qc.invalidateQueries({ queryKey: ["trading-brain-v3-history"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Evaluate failed"),
  });

  const caps = asRecord(statusQ.data?.capabilities);
  const modules = asRecord(asRecord(result).modules);
  const moduleEntries = Object.entries(modules);
  const advisor = asRecord(modules.operator_advisor);
  const discipline = asRecord(modules.institutional_discipline_score);
  const quality = asRecord(modules.continuous_quality_dashboard);
  const panels = asList(asRecord(quality.details).panels);
  const history = asList(asRecord(historyQ.data).items);
  const rec = str(result?.recommendation, "");

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Trading Brain V3 unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <Brain className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">{TRADING_SYMBOL} brain</span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Capital preservation
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          No profit promise
        </Badge>
        {caps.alternate_execution_path === false ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            Existing pipeline only
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "trading-brain-v3")}
        </span>
        <Button
          size="sm"
          disabled={evaluateM.isPending}
          onClick={() => evaluateM.mutate()}
        >
          Evaluate
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Authority inputs">
          <div className="space-y-2 text-xs">
            <label className="flex items-center justify-between gap-2">
              <span className="text-[var(--fg-muted)]">Risk Engine passed</span>
              <input
                type="checkbox"
                checked={riskOk}
                onChange={(e) => setRiskOk(e.target.checked)}
                className="size-3.5"
              />
            </label>
            <label className="flex items-center justify-between gap-2">
              <span className="text-[var(--fg-muted)]">Safety Engine passed</span>
              <input
                type="checkbox"
                checked={safetyOk}
                onChange={(e) => setSafetyOk(e.target.checked)}
                className="size-3.5"
              />
            </label>
            <p className="text-[10px] text-[var(--fg-subtle)]">
              Brain uses existing Decision Center, Risk, Safety, and Execution —
              never invents market data or creates alternate paths.
            </p>
            <Button asChild size="sm" variant="outline">
              <Link href="/decision-intelligence">Open Decision Center</Link>
            </Button>
          </div>
        </Panel>

        <Panel title="Recommendation">
          {!result ? (
            <DeskEmpty
              icon={Brain}
              title="No evaluation"
              description="Run evaluate with supplied facts"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Brain</span>
                <Badge
                  tone={rec === "No Trade" ? "warning" : "success"}
                  className="text-[9px] uppercase"
                >
                  {rec || "—"}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Discipline</span>
                <span className="font-mono">
                  {str(result.discipline_score, str(discipline.score, "—"))}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">order_send</span>
                <span className="font-mono">never</span>
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                Audit {str(result.audit_id, "—")}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Operator advisor">
          {!Object.keys(advisor).length ? (
            <DeskEmpty
              icon={Shield}
              title="No advice"
              description="Advisor appears after evaluate"
            />
          ) : (
            <ul className="max-h-40 space-y-1 overflow-auto text-[10px] text-[var(--fg-muted)]">
              {asList(advisor.reasons).map((r, i) => (
                <li key={`${i}-${str(r, "").slice(0, 24)}`}>{str(r, "")}</li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Ten modules">
        {!moduleEntries.length ? (
          <DeskEmpty
            icon={Brain}
            title="No modules"
            description="Environment → Discipline pipeline"
          />
        ) : (
          <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
            {moduleEntries.map(([key, val]) => {
              const row = asRecord(val);
              return (
                <li
                  key={key}
                  className={cn(
                    "border px-2 py-2",
                    row.recommendation === "No Trade"
                      ? "border-[var(--warning)]/40"
                      : "border-[var(--border)]",
                  )}
                >
                  <p className="text-[10px] font-medium leading-tight">
                    {str(row.module, key).replace(/_/g, " ")}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-[var(--fg-subtle)]">
                    {str(row.status, "—")} · score {str(row.score, "—")}
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

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel title="Quality dashboard">
          {!panels.length ? (
            <DeskEmpty
              icon={Brain}
              title="No panels"
              description="Quality panels appear from module scores"
            />
          ) : (
            <ul className="grid gap-1 sm:grid-cols-2 font-mono text-[10px]">
              {panels.map((p) => {
                const row = asRecord(p);
                return (
                  <li
                    key={str(row.panel_id, str(row.title, "p"))}
                    className="flex justify-between border border-[var(--border)] px-2 py-1"
                  >
                    <span className="truncate text-[var(--fg-muted)]">
                      {str(row.title, str(row.panel_id, "—"))}
                    </span>
                    <span>{str(row.score, str(row.status, "—"))}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel title="History">
          {!history.length ? (
            <DeskEmpty
              icon={Brain}
              title="No history"
              description="Auditable evaluations appear here"
            />
          ) : (
            <ul className="max-h-48 space-y-1 overflow-auto font-mono text-[10px]">
              {history.map((h) => {
                const row = asRecord(h);
                return (
                  <li
                    key={str(row.audit_id, "h")}
                    className="border-b border-[var(--border)]/60 py-1"
                  >
                    {str(row.audit_id, "—")} · {str(row.recommendation, "—")} ·
                    disc {str(row.discipline_score, "—")}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}

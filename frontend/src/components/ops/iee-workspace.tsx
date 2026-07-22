"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Gauge, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { institutionalEdgeEngineApi } from "@/lib/api/endpoints";
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

function sampleTrades(n = 40) {
  return Array.from({ length: n }, (_, i) => ({
    win: i % 3 !== 0,
    pnl: i % 3 !== 0 ? 12 + (i % 5) : -(8 + (i % 4)),
    rr: i % 3 !== 0 ? 1.2 + (i % 10) / 10 : 0.6,
    regime: i % 2 === 0 ? "trend" : "range",
    volatility: i % 4 === 0 ? "high" : "low",
    session: ["london", "new_york", "asia"][i % 3],
    news: i % 11 === 0,
    entry_timing: i % 7 === 0 ? "late" : i % 5 === 0 ? "early" : "ok",
    exit_timing: i % 9 === 0 ? "premature" : i % 8 === 0 ? "late" : "ok",
    mae: 0.4 + (i % 5) * 0.1,
    mfe: 1.0 + (i % 6) * 0.15,
    holding_time_sec: 60 + i * 3,
    exit_efficiency: 55 + (i % 30),
    risk_pct: 0.5 + (i % 3) * 0.05,
    missed_opportunity: i % 13 === 0,
  }));
}

export function IeeWorkspace() {
  const qc = useQueryClient();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [withTrades, setWithTrades] = useState(true);

  const statusQ = useQuery({
    queryKey: ["iee-status"],
    queryFn: () => institutionalEdgeEngineApi.status(),
    staleTime: 15_000,
  });

  const evaluateM = useMutation({
    mutationFn: () =>
      institutionalEdgeEngineApi.evaluate({
        completed_trades: withTrades ? sampleTrades(40) : [],
        discipline_facts: withTrades
          ? {
              rule_compliance_pct: 88,
              risk_consistency_pct: 80,
              position_sizing_consistency_pct: 78,
              drawdown_control_pct: 82,
              capital_preservation_pct: 85,
            }
          : {},
        prior_edge_score: 70,
        research_month: "2026-07",
      }),
    onSuccess: async (data) => {
      setResult(data);
      const grade = str(
        asRecord(data.institutional_score).overall_grade,
        "—",
      );
      toast.success(`IEE grade ${grade}`);
      await qc.invalidateQueries({ queryKey: ["iee-status"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "IEE evaluate failed"),
  });

  const caps = asRecord(statusQ.data?.capabilities);
  const edge = asRecord(asRecord(result).edge_report_summary);
  const inst = asRecord(asRecord(result).institutional_score);
  const panels = asRecord(inst.panels);
  const modules = asRecord(asRecord(result).modules);
  const explain = asList(edge.explainability);

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Edge Engine unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <Gauge className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">{TRADING_SYMBOL} IEE</span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Advisory
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          Never disables trading
        </Badge>
        {caps.never_fabricate_metrics === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            No fabricated metrics
          </Badge>
        ) : null}
        <label className="ml-2 flex items-center gap-1.5 text-[10px] text-[var(--fg-muted)]">
          <input
            type="checkbox"
            checked={withTrades}
            onChange={(e) => setWithTrades(e.target.checked)}
            className="size-3.5"
          />
          Supply sample trades
        </label>
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "iee")}
        </span>
        <Button
          size="sm"
          disabled={evaluateM.isPending}
          onClick={() => evaluateM.mutate()}
        >
          Evaluate edge
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Edge report">
          {!result ? (
            <DeskEmpty
              icon={Gauge}
              title="No evaluation"
              description="Score edge from completed trades"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Edge score</span>
                <span className="font-mono">
                  {str(edge.edge_score, "Insufficient Data")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Status</span>
                <Badge
                  tone={edge.edge_warning === true ? "warning" : "neutral"}
                  className="text-[9px] uppercase"
                >
                  {str(edge.edge_recommendation, "—")}
                </Badge>
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                Audit {str(result.audit_id, "—")}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Institutional score">
          {!result ? (
            <DeskEmpty
              icon={Shield}
              title="No grade"
              description="Composite institutional grade"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Grade</span>
                <span className="font-mono text-sm">
                  {str(inst.overall_grade, "Insufficient Data")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Score</span>
                <span className="font-mono">
                  {str(inst.overall_score, "—")}
                </span>
              </div>
              <ul className="max-h-28 space-y-1 overflow-auto font-mono text-[10px]">
                {Object.entries(panels).map(([k, v]) => {
                  const row = asRecord(v);
                  return (
                    <li key={k} className="text-[var(--fg-muted)]">
                      {k}: {str(row.score, str(row.status, "—"))}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </Panel>

        <Panel title="Explainability">
          {!explain.length ? (
            <DeskEmpty
              icon={Gauge}
              title="No report"
              description="Why edge moved — no speculation"
            />
          ) : (
            <ul className="max-h-40 space-y-1 overflow-auto text-[10px] text-[var(--fg-muted)]">
              {explain.slice(0, 12).map((line) => (
                <li key={String(line)} className="border-b border-[var(--border)]/50 py-1">
                  {String(line)}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Modules">
        {!Object.keys(modules).length ? (
          <DeskEmpty
            icon={Gauge}
            title="No modules"
            description="Edge → monthly research"
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

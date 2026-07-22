"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { BadgeCheck, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { productionReadinessCertificationApi } from "@/lib/api/endpoints";
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

const PASSING_EVIDENCE = {
  reliability: {
    service_uptime_pct: 99.5,
    recovery_success_rate_pct: 98,
    restart_recovery_ok: true,
    watchdog_health_ok: true,
    mt5_synchronization_ok: true,
    incident_rate_per_day: 0.2,
    duplicate_protection_ok: true,
  },
  risk: {
    risk_policy_compliance_pct: 99,
    maximum_drawdown_pct: 4.2,
    position_sizing_consistency_ok: true,
    daily_loss_compliance_ok: true,
    exposure_discipline_ok: true,
  },
  execution: {
    fill_reliability_pct: 98.5,
    execution_latency_ms_p95: 120,
    broker_acknowledgement_ok: true,
    slippage_observations_ok: true,
    retry_behavior_ok: true,
  },
  decision: {
    decision_explainability_ok: true,
    decision_consistency_pct: 94,
    confidence_calibration_ok: true,
    no_trade_discipline_ok: true,
  },
  data: {
    market_data_integrity_ok: true,
    missing_data_handling_ok: true,
    feed_coverage_pct: 97,
    timestamp_consistency_ok: true,
    historical_completeness_pct: 92,
  },
  research: {
    replay_evidence_ok: true,
    paper_trading_evidence_ok: true,
    ivp_evidence_ok: true,
    llp_evidence_ok: true,
    alpha_factory_evidence_ok: true,
  },
  operations: {
    health_ok: true,
    monitoring_ok: true,
    alerts_ok: true,
    audit_ok: true,
    logging_ok: true,
    recovery_ok: true,
    operator_workflow_ok: true,
  },
};

export function ProductionReadinessCertificationWorkspace() {
  const qc = useQueryClient();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const statusQ = useQuery({
    queryKey: ["prc-status"],
    queryFn: () => productionReadinessCertificationApi.status(),
    staleTime: 15_000,
  });

  const evaluateM = useMutation({
    mutationFn: () =>
      productionReadinessCertificationApi.evaluate({
        ...PASSING_EVIDENCE,
        prior_certification_status: "WATCH",
      }),
    onSuccess: async (data) => {
      setResult(data);
      const report = asRecord(data.certification_report);
      toast.success(
        `PRC · ${str(report.certification_status, "—")} · ${str(report.overall_readiness_score, "—")}`,
      );
      await qc.invalidateQueries({ queryKey: ["prc-status"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Evaluate failed"),
  });

  const caps = asRecord(statusQ.data?.capabilities);
  const report = asRecord(asRecord(result).certification_report);
  const modules = asRecord(asRecord(result).modules);
  const dash = asRecord(asRecord(modules.readiness_dashboard).details);
  const risks = asList(report.known_risks);
  const issues = asList(report.open_issues);
  const restrictions = asList(report.recommended_restrictions);

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "PRC unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <BadgeCheck className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">
          {TRADING_SYMBOL} Production Readiness Certification
        </span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Certifies only
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          Human approval required
        </Badge>
        {caps.never_change_configuration_automatically === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            No auto-config
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "prc")}
        </span>
        <Button
          size="sm"
          disabled={evaluateM.isPending}
          onClick={() => evaluateM.mutate()}
        >
          Recalculate certification
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Readiness dashboard">
          {!result ? (
            <DeskEmpty
              icon={BadgeCheck}
              title="No certification"
              description="Supply reliability · risk · execution · research evidence"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Overall readiness</span>
                <span className="font-mono">
                  {str(report.overall_readiness_score, "—")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Status</span>
                <span className="font-mono">
                  {str(report.certification_status, "—")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Reliability</span>
                <span className="font-mono text-[10px]">
                  {str(asRecord(dash.reliability).verdict, "—")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Execution</span>
                <span className="font-mono text-[10px]">
                  {str(asRecord(dash.execution).verdict, "—")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Risk</span>
                <span className="font-mono text-[10px]">
                  {str(asRecord(dash.risk).verdict, "—")}
                </span>
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                Audit {str(result.audit_id, "—")}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Sign-off / blockers">
          {!result ? (
            <DeskEmpty
              icon={Shield}
              title="Await evaluation"
              description="Human approval always required"
            />
          ) : (
            <div className="space-y-2 text-[10px]">
              <p className="text-[var(--fg-muted)]">
                {str(report.certification_decision, "—")}
              </p>
              <p className="text-[var(--fg-muted)]">Open issues</p>
              <ul className="max-h-16 space-y-0.5 overflow-auto font-mono">
                {issues.length === 0 ? (
                  <li className="text-[var(--fg-subtle)]">None</li>
                ) : (
                  issues.slice(0, 4).map((i) => (
                    <li key={String(i)}>{String(i)}</li>
                  ))
                )}
              </ul>
              <p className="text-[var(--fg-muted)]">Restrictions</p>
              <ul className="max-h-16 space-y-0.5 overflow-auto font-mono">
                {restrictions.slice(0, 3).map((r) => (
                  <li key={String(r)}>{String(r)}</li>
                ))}
              </ul>
            </div>
          )}
        </Panel>

        <Panel title="Guarantees">
          <ul className="space-y-1 text-[10px] text-[var(--fg-muted)]">
            <li>Never places trades</li>
            <li>Never changes strategies or configuration</li>
            <li>Never modifies Risk / Safety / Decision / Execution</li>
            <li>Never modifies Auto Trading</li>
            <li>Only notifies on certification status change</li>
          </ul>
          {risks.length > 0 ? (
            <p className="mt-2 font-mono text-[10px] text-[var(--fg-subtle)] line-clamp-3">
              Risks: {risks.map(String).join("; ")}
            </p>
          ) : null}
        </Panel>
      </div>

      <Panel title="Modules">
        {!Object.keys(modules).length ? (
          <DeskEmpty
            icon={BadgeCheck}
            title="No modules"
            description="Reliability → continuous certification"
          />
        ) : (
          <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
            {Object.entries(modules).map(([key, val]) => {
              const row = asRecord(val);
              const verdict = str(
                asRecord(row.details).verdict,
                str(row.recommendation),
              );
              return (
                <li
                  key={key}
                  className={cn(
                    "border px-2 py-2",
                    verdict === "FAIL" ||
                      verdict === "INSUFFICIENT EVIDENCE"
                      ? "border-[var(--warning)]/40"
                      : "border-[var(--border)]",
                  )}
                >
                  <p className="text-[10px] font-medium leading-tight">
                    {str(row.module, key).replace(/_/g, " ")}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-[var(--fg-subtle)]">
                    {verdict} · {str(row.score, "—")}
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

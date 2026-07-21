"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Scale, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { decisionIntelligenceApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
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

export function DecisionIntelligenceWorkspace() {
  const qc = useQueryClient();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [replayId, setReplayId] = useState("");

  const statusQ = useQuery({
    queryKey: ["decision-intelligence-status"],
    queryFn: () => decisionIntelligenceApi.status(),
    staleTime: 20_000,
  });

  const historyQ = useQuery({
    queryKey: ["decision-intelligence-history"],
    queryFn: () => decisionIntelligenceApi.history(20),
    staleTime: 10_000,
  });

  const policiesQ = useQuery({
    queryKey: ["decision-intelligence-policies"],
    queryFn: () => decisionIntelligenceApi.policies(),
    staleTime: 30_000,
  });

  const evaluateM = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      decisionIntelligenceApi.evaluate(body),
    onSuccess: async (data) => {
      setResult(data);
      setReplayId(str(data.audit_id, ""));
      const d = str(data.decision, "HOLD");
      if (d === "APPROVE") toast.success("APPROVE (advisory) — no order sent");
      else if (d === "REJECT") toast.error("REJECT — capital preservation");
      else toast.info("HOLD — fail closed");
      await qc.invalidateQueries({ queryKey: ["decision-intelligence-history"] });
      await qc.invalidateQueries({ queryKey: ["decision-intelligence-status"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Evaluate failed"),
  });

  const replayM = useMutation({
    mutationFn: (auditId: string) => decisionIntelligenceApi.replay(auditId),
    onSuccess: (data) => {
      toast.info(str(asRecord(data).reason, "Replay loaded"));
      setResult(asRecord(asRecord(data).replay));
    },
  });

  const policyM = useMutation({
    mutationFn: () =>
      decisionIntelligenceApi.updatePolicies({ min_confidence: 65 }),
    onSuccess: async () => {
      toast.success("Policies updated (hard locks unchanged)");
      await qc.invalidateQueries({
        queryKey: ["decision-intelligence-policies"],
      });
    },
  });

  const caps = useMemo(() => {
    const raw = asRecord(statusQ.data?.capabilities);
    return Object.entries(raw)
      .filter(
        ([k]) => !["force_execution", "bypass_risk", "bypass_safety"].includes(k),
      )
      .map(([k, v]) => ({
        key: k,
        on: Boolean(v),
        label: k.replace(/_/g, " "),
      }));
  }, [statusQ.data]);

  const baseBody = {
    side: "buy",
    strategy_id: "decision-intelligence",
    signal_present: true,
    strategy_consensus_ok: true,
    market_regime_ok: true,
    spread: 0.4,
    daily_drawdown_pct: 0.2,
    consecutive_losses: 0,
    confidence_factors: {
      signal_strength: 75,
      structure_align: 70,
      consensus: 72,
      regime_fit: 68,
      execution_quality: 70,
    },
    quality: {
      approve_precision: 70,
      reject_precision: 75,
      override_rate: 5,
      audit_completeness: 100,
    },
  };

  if (statusQ.isLoading) return <DeskSkeleton rows={6} />;
  if (statusQ.isError) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Could not load Decision Intelligence Center."
        }
        onRetry={() => void statusQ.refetch()}
      />
    );
  }

  const status = statusQ.data ?? {};
  const panel = asRecord(asRecord(result).executive_panel);
  const waterfall = asList(asRecord(result).waterfall);
  const summary = asRecord(asRecord(result).summary);
  const confidence = asRecord(asRecord(result).confidence);
  const veto = asRecord(asRecord(result).veto);
  const quality = asRecord(asRecord(result).quality);
  const decisions = asList(asRecord(historyQ.data).decisions);
  const policies = asRecord(policiesQ.data);

  return (
    <div className="grid gap-3 lg:grid-cols-12">
      <div className="space-y-3 lg:col-span-8">
        <Panel
          title="Mission"
          action={
            <Badge tone="neutral" className="font-mono text-[10px]">
              {str(status.version, "decision-intelligence-v1")}
            </Badge>
          }
        >
          <div className="flex items-start gap-3">
            <Scale className="mt-0.5 h-4 w-4 shrink-0 text-[var(--fg-subtle)]" />
            <div className="space-y-2">
              <p className="text-[13px] leading-relaxed text-[var(--fg)]">
                {str(
                  asRecord(status.policies).mission,
                  "Final institutional decision layer before execution.",
                )}
              </p>
              <p className="text-[11px] text-[var(--fg-subtle)]">
                {str(status.disclaimer, "")}
              </p>
              <div className="flex flex-wrap gap-2">
                <Badge tone="success">may reject</Badge>
                <Badge tone="warning">never force-execute</Badge>
                <Badge tone="neutral">Risk/Safety never bypassed</Badge>
              </div>
            </div>
          </div>
        </Panel>

        <Panel title="Executive decision panel">
          <div className="mb-3 flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={evaluateM.isPending}
              onClick={() =>
                evaluateM.mutate({
                  ...baseBody,
                  risk_engine_passed: null,
                  safety_engine_passed: null,
                })
              }
            >
              Evaluate (fail-closed)
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={evaluateM.isPending}
              onClick={() =>
                evaluateM.mutate({
                  ...baseBody,
                  risk_engine_passed: true,
                  safety_engine_passed: true,
                })
              }
            >
              Simulate Risk+Safety ALLOW
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={evaluateM.isPending}
              onClick={() =>
                evaluateM.mutate({
                  ...baseBody,
                  risk_engine_passed: true,
                  safety_engine_passed: true,
                  operator_action: "reject",
                  operator: "desk",
                  operator_reason: "Operator veto",
                })
              }
            >
              Operator reject
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={evaluateM.isPending}
              onClick={() =>
                evaluateM.mutate({
                  ...baseBody,
                  risk_engine_passed: true,
                  safety_engine_passed: true,
                  operator_action: "force_approve",
                  operator: "desk",
                })
              }
            >
              Attempt force-approve (blocked)
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={!replayId || replayM.isPending}
              onClick={() => replayM.mutate(replayId)}
            >
              Replay audit
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={policyM.isPending}
              onClick={() => policyM.mutate()}
            >
              Refresh policies
            </Button>
          </div>

          {!result ? (
            <DeskEmpty
              icon={Shield}
              title="No decision yet"
              description="Run evaluate to produce an auditable APPROVE / REJECT / HOLD. Center never places orders."
            />
          ) : (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  tone={
                    str(panel.decision) === "APPROVE"
                      ? "success"
                      : str(panel.decision) === "REJECT"
                        ? "danger"
                        : "warning"
                  }
                >
                  {str(panel.decision)}
                </Badge>
                <Badge tone="neutral">
                  confidence {str(panel.confidence)}
                </Badge>
                <Badge tone="accent" className="font-mono">
                  audit {str(panel.audit_id).slice(0, 8)}
                </Badge>
                <Badge
                  tone={panel.allow_execution_path ? "success" : "neutral"}
                >
                  path={String(Boolean(panel.allow_execution_path))}
                </Badge>
              </div>
              <p className="text-[12px] text-[var(--fg-muted)]">
                {str(summary.headline)}
              </p>
              <div className="grid gap-1 sm:grid-cols-2">
                {waterfall.map((row, i) => {
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
                      <div className="flex justify-between gap-2">
                        <span className="font-mono text-[10px] uppercase">
                          {str(r.name)}
                        </span>
                        <Badge tone={r.passed ? "success" : "danger"}>
                          {r.passed ? "pass" : "block"}
                        </Badge>
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
          <Panel title="Explainable AI decision summary">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  Why approved
                </h3>
                <ul className="list-inside list-disc text-[12px] text-[var(--fg-muted)]">
                  {asList(summary.why_approved)
                    .map(String)
                    .slice(0, 6)
                    .map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                </ul>
              </div>
              <div>
                <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  Why rejected
                </h3>
                <ul className="list-inside list-disc text-[12px] text-[var(--fg-muted)]">
                  {asList(summary.why_rejected).length === 0 ? (
                    <li>No blocking reasons.</li>
                  ) : (
                    asList(summary.why_rejected)
                      .map(String)
                      .slice(0, 6)
                      .map((x) => <li key={x}>{x}</li>)
                  )}
                </ul>
              </div>
            </div>
            <p className="mt-3 text-[11px] text-[var(--fg-subtle)]">
              {str(summary.disclaimer)}
            </p>
          </Panel>
        ) : null}
      </div>

      <div className="space-y-3 lg:col-span-4">
        <Panel title="Capabilities (10)">
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
          <div className="mt-2 border-t border-[var(--border)] pt-2">
            <p className="mb-1 text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
              Hard-locked off
            </p>
            {["force_execution", "bypass_risk", "bypass_safety"].map((k) => (
              <div
                key={k}
                className="flex items-center justify-between py-1 text-[12px]"
              >
                <span className="text-[var(--fg-muted)]">
                  {k.replace(/_/g, " ")}
                </span>
                <Badge tone="danger">OFF</Badge>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Confidence breakdown">
          <pre className="overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(confidence, null, 2)}
          </pre>
        </Panel>
        <Panel title="Trade veto">
          <pre className="overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(veto, null, 2)}
          </pre>
        </Panel>
        <Panel title="Decision quality">
          <pre className="overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(quality, null, 2)}
          </pre>
        </Panel>
        <Panel title="Decision history">
          <div className="max-h-48 space-y-1 overflow-auto">
            {decisions.length === 0 ? (
              <p className="text-[12px] text-[var(--fg-subtle)]">No audits yet.</p>
            ) : (
              decisions.map((row, i) => {
                const r = asRecord(row);
                return (
                  <button
                    key={`${str(r.audit_id)}-${i}`}
                    type="button"
                    className="flex w-full items-center justify-between border border-[var(--border)] px-2 py-1 text-left text-[11px]"
                    onClick={() => {
                      setReplayId(str(r.audit_id));
                      setResult(r);
                    }}
                  >
                    <span className="font-mono">
                      {str(r.audit_id).slice(0, 8)} · {str(r.decision)}
                    </span>
                    <Badge tone="neutral">audit</Badge>
                  </button>
                );
              })
            )}
          </div>
        </Panel>
        <Panel title="Configurable policies">
          <pre className="max-h-40 overflow-auto font-mono text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(policies, null, 2)}
          </pre>
        </Panel>
      </div>
    </div>
  );
}

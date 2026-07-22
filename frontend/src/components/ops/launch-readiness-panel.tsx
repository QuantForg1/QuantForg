"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteOpsApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

/**
 * OWNER Launch Readiness — live checklist with WHY / HOW TO RESOLVE.
 * Promote uses official Ops state machine only (never flips EXECUTION_ENABLED).
 */
export function LaunchReadinessPanel({ className }: { className?: string }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["ite-ops-launch-readiness"],
    queryFn: iteOpsApi.launchReadiness,
    retry: false,
    refetchInterval: 15_000,
  });

  const promote = useMutation({
    mutationFn: () =>
      iteOpsApi.promoteLaunch({
        reason: "OWNER launch readiness promotion",
        confirmed: true,
        activate_auto_trading: true,
      }),
    onSuccess: (raw) => {
      const d = asRecord(raw);
      void qc.invalidateQueries({ queryKey: ["ite-ops-launch-readiness"] });
      void qc.invalidateQueries({ queryKey: ["ite-ops-auto-trading"] });
      void qc.invalidateQueries({ queryKey: ["ite-ops-control-center"] });
      if (d.ok) {
        toast.success(str(d.message, "LIVE armed"));
      } else {
        toast.error(str(d.message, "Promotion refused — see blockers"));
      }
    },
    onError: (err) => {
      const detail = err instanceof ApiError ? asRecord(err.details) : {};
      const msg =
        err instanceof ApiError
          ? str(detail.message || err.message, "Promote failed")
          : "Promote failed";
      toast.error(msg);
    },
  });

  if (q.isLoading && !q.data) return <DeskSkeleton rows={5} />;
  if (q.isError) {
    return (
      <DeskError message="Launch Readiness unavailable — OWNER/ADMIN required." />
    );
  }

  const d = asRecord(q.data);
  const items = asList(d.items).map(asRecord);
  const blockers = asList(d.blockers).map(asRecord);
  const plan = asList(d.promotion_plan).map(String);
  const verification = asRecord(d.verification);
  const ready = Boolean(d.ready_for_promotion);

  return (
    <section
      className={cn(
        "border border-[var(--border)] bg-[var(--surface)] px-3 py-3",
        className,
      )}
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Launch Readiness
          </h2>
          <Badge tone={ready ? "success" : "warning"}>
            {ready ? "READY TO PROMOTE" : "BLOCKED"}
          </Badge>
          <Badge tone={d.ready_for_gate_enabled ? "success" : "neutral"}>
            Gate {d.ready_for_gate_enabled ? "Enabled" : "Disabled"}
          </Badge>
        </div>
        <Button
          size="sm"
          disabled={!ready || promote.isPending}
          onClick={() => {
            if (
              !window.confirm(
                "Promote SHADOW → CANARY → LIVE via official Ops state machine? Risk/Safety are never bypassed. EXECUTION_ENABLED must already be true in Railway.",
              )
            ) {
              return;
            }
            promote.mutate();
          }}
        >
          {promote.isPending ? "Promoting…" : "Promote to LIVE"}
        </Button>
      </div>

      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4 text-xs">
        {(
          [
            ["Ops", str(verification.ops_mode, "—")],
            ["Gate", str(verification.gate, "—")],
            ["Execution", verification.execution_enabled ? "ON" : "OFF"],
            ["Auto Trading", str(verification.auto_trading, "—")],
            ["Gateway", str(verification.gateway, "—")],
            ["Broker", str(verification.broker, "—")],
            ["Risk", str(verification.risk, "—")],
            ["Safety", str(verification.safety, "—")],
          ] as const
        ).map(([label, value]) => (
          <div
            key={label}
            className="border border-[var(--border)] bg-[var(--bg)]/40 px-2 py-1.5"
          >
            <p className="text-[9px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              {label}
            </p>
            <p className="font-mono text-[11px] text-[var(--fg)]">{value}</p>
          </div>
        ))}
      </div>

      <div className="space-y-2">
        {items.map((item) => {
          const passed = Boolean(item.passed);
          return (
            <div
              key={str(item.key)}
              className="border border-[var(--border)] px-2.5 py-2 text-xs"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium text-[var(--fg)]">
                  {str(item.label)}
                </span>
                <span className="flex items-center gap-2">
                  <span className="font-mono text-[var(--fg-muted)]">
                    {str(item.value)}
                  </span>
                  <Badge tone={passed ? "success" : "warning"}>
                    {passed ? "PASS" : "FAIL"}
                  </Badge>
                </span>
              </div>
              {!passed ? (
                <div className="mt-1.5 space-y-0.5 text-[var(--fg-muted)]">
                  <p>
                    <span className="text-[var(--fg-subtle)]">WHY: </span>
                    {str(item.why)}
                  </p>
                  <p>
                    <span className="text-[var(--fg-subtle)]">HOW: </span>
                    {str(item.how_to_resolve)}
                  </p>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      {blockers.length === 0 && plan.length > 0 ? (
        <div className="mt-3 text-xs text-[var(--fg-muted)]">
          <p className="mb-1 font-medium text-[var(--fg-subtle)]">Promotion plan</p>
          <ol className="list-decimal space-y-0.5 pl-4">
            {plan.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
      ) : null}

      <p className="mt-3 text-[10px] text-[var(--fg-subtle)]">
        Never bypasses Risk/Safety. Never flips EXECUTION_ENABLED. Never fabricates
        trades. Valid signals only: Decision → Risk → Safety → Execution; otherwise
        NO TRADE.
      </p>
    </section>
  );
}

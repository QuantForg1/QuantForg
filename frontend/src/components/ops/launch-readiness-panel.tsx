"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteOpsApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

/** Preferred display order for the Launch Lock Inspector. */
const LOCK_ORDER = [
  "gateway",
  "broker",
  "mt5_login",
  "market_open",
  "trading_allowed",
  "symbol_ready",
  "execution_enabled",
  "ops_mode",
  "kill_switch",
  "emergency_stop",
  "safety_lock",
  "risk_lock",
  "daily_loss_lock",
  "demo_certification",
  "owner_authorization",
  "auto_trading_run_state",
] as const;

const LABEL_OVERRIDE: Record<string, string> = {
  execution_enabled: "EXECUTION_ENABLED",
  ops_mode: "Ops Mode",
  kill_switch: "Kill Switch",
  emergency_stop: "Emergency Stop",
  safety_lock: "Safety Lock",
  risk_lock: "Risk Lock",
  daily_loss_lock: "Daily Loss",
  demo_certification: "Demo Certification",
  owner_authorization: "OWNER Authorization",
  mt5_login: "MT5 Login",
  market_open: "Market Open",
  trading_allowed: "Trading Allowed",
  symbol_ready: "Symbol",
  auto_trading_run_state: "Auto Trading",
};

function resolutionLines(raw: string): string[] {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

/**
 * Launch Lock Inspector — every execution prerequisite with WHY / Resolution.
 * Never shows only "Gate Disabled" without explaining locks.
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
        toast.error(str(d.message, "Promotion refused — see Launch Lock Inspector"));
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

  if (q.isLoading && !q.data) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError message="Launch Lock Inspector unavailable — OWNER/ADMIN required." />
    );
  }

  const d = asRecord(q.data);
  const byKey = new Map(
    asList(d.items)
      .map(asRecord)
      .map((item) => [str(item.key), item] as const),
  );
  const orderedKeys = new Set<string>(LOCK_ORDER as unknown as string[]);
  const ordered = [
    ...LOCK_ORDER.map((key) => byKey.get(key)).filter(
      (item): item is Record<string, unknown> => item != null,
    ),
    ...asList(d.items)
      .map(asRecord)
      .filter((item) => !orderedKeys.has(str(item.key))),
  ];

  const failed = ordered.filter((item) => !item.passed);
  const ready = Boolean(d.ready_for_promotion);
  const gateEnabled = Boolean(d.ready_for_gate_enabled);
  const execReady = ready && gateEnabled;
  const allPass = failed.length === 0 && ordered.length > 0;

  return (
    <section
      className={cn(
        "border border-[var(--border)] bg-[var(--surface)] px-3 py-3",
        className,
      )}
      aria-label="Launch Lock Inspector"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Launch Lock Inspector
          </h2>
          <p className="mt-0.5 text-xs text-[var(--fg-muted)]">
            Every execution prerequisite — never only “Gate Disabled”.
          </p>
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

      {allPass || execReady ? (
        <div className="mb-3 border border-[var(--success)]/40 bg-[var(--success)]/10 px-3 py-2.5">
          <p className="text-sm font-medium text-[var(--success)]">Launch Ready</p>
          <p className="mt-1 text-xs text-[var(--fg)]">Gate Enabled</p>
          <p className="text-xs text-[var(--fg)]">Execution Ready</p>
        </div>
      ) : (
        <div className="mb-3 border border-[var(--warning)]/35 bg-[var(--warning)]/8 px-3 py-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="warning">
              Gate {gateEnabled ? "Enabled" : "Disabled"}
            </Badge>
            <span className="text-xs text-[var(--fg-muted)]">
              {failed.length} lock{failed.length === 1 ? "" : "s"} blocking launch
            </span>
          </div>
          {failed[0] ? (
            <p className="mt-1.5 text-xs text-[var(--warning)]">
              Primary lock:{" "}
              <span className="font-medium text-[var(--fg)]">
                {LABEL_OVERRIDE[str(failed[0].key)] || str(failed[0].label)}
              </span>{" "}
              = {str(failed[0].value)}
            </p>
          ) : null}
        </div>
      )}

      <div className="space-y-2">
        {ordered.map((item) => {
          const key = str(item.key);
          const passed = Boolean(item.passed);
          const label = LABEL_OVERRIDE[key] || str(item.label);
          const steps = resolutionLines(str(item.how_to_resolve));
          return (
            <article
              key={key}
              className={cn(
                "border px-3 py-2.5",
                passed
                  ? "border-[var(--border)] bg-[var(--bg)]/25"
                  : "border-[var(--warning)]/40 bg-[var(--warning)]/5",
              )}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="flex items-start gap-2">
                  {passed ? (
                    <Check
                      className="mt-0.5 h-4 w-4 shrink-0 text-[var(--success)]"
                      aria-hidden
                    />
                  ) : (
                    <X
                      className="mt-0.5 h-4 w-4 shrink-0 text-[var(--warning)]"
                      aria-hidden
                    />
                  )}
                  <div>
                    <p
                      className={cn(
                        "text-sm font-medium",
                        passed ? "text-[var(--fg)]" : "text-[var(--fg)]",
                      )}
                    >
                      {passed ? "✓" : "✘"} {label}
                    </p>
                    <p className="mt-1 text-[11px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                      Current
                    </p>
                    <p className="font-mono text-xs text-[var(--fg)]">
                      {str(item.value, "—")}
                    </p>
                  </div>
                </div>
                <Badge tone={passed ? "success" : "warning"}>
                  {passed ? "PASS" : "LOCK"}
                </Badge>
              </div>

              {!passed ? (
                <div className="mt-2 border-t border-[var(--border)] pt-2 text-xs">
                  <p className="text-[11px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                    Why
                  </p>
                  <p className="mt-0.5 text-[var(--fg-muted)]">{str(item.why)}</p>
                  <p className="mt-2 text-[11px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                    Resolution
                  </p>
                  {steps.length > 0 ? (
                    <ul className="mt-0.5 list-none space-y-0.5 text-[var(--fg)]">
                      {steps.map((step) => (
                        <li key={`${key}-${step}`} className="font-mono text-[11px]">
                          {step}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-0.5 text-[var(--fg-muted)]">See OWNER Ops controls</p>
                  )}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>

      <p className="mt-3 text-[10px] text-[var(--fg-subtle)]">
        Never bypasses Risk/Safety. Never flips EXECUTION_ENABLED. Never fabricates
        trades. Valid signals: Decision → Risk → Safety → Execution; otherwise NO TRADE.
      </p>
    </section>
  );
}

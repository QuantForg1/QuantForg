"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

type Props = {
  className?: string;
  /** Prefer auto-trading payload when parent already loaded it. */
  executionState?: Record<string, unknown> | null;
  compact?: boolean;
};

/**
 * Shared authoritative execution snapshot.
 * Never shows only "Gate Disabled" — always surfaces primary lock + inspector link.
 */
export function ExecutionStateStrip({
  className,
  executionState,
  compact = false,
}: Props) {
  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 15_000,
    enabled: executionState == null,
  });
  const launchQ = useQuery({
    queryKey: ["ite-ops-launch-readiness"],
    queryFn: iteOpsApi.launchReadiness,
    retry: false,
    refetchInterval: 15_000,
  });

  const raw = executionState ?? asRecord(asRecord(autoQ.data).execution_state);
  const fromRoot = asRecord(autoQ.data);
  const opsMode = str(raw.ops_mode || fromRoot.ops_mode, "—");
  const gate = str(raw.gate_status || fromRoot.status, "—");
  const execOn = Boolean(
    raw.execution_enabled ?? fromRoot.execution_enabled ?? false,
  );
  const gateway = Boolean(raw.gateway_connected);
  const broker = Boolean(raw.broker_connected);
  const primary = str(raw.primary_blocker || fromRoot.primary_blocker, "");
  const kill = Boolean(raw.kill_switch_armed ?? fromRoot.emergency_stop);

  const launch = asRecord(launchQ.data);
  const launchItems = asList(launch.items).map(asRecord);
  const firstLock = launchItems.find((item) => !item.passed);
  const lockCount = launchItems.filter((item) => !item.passed).length;
  const launchReady = Boolean(launch.ready_for_promotion) && Boolean(launch.ready_for_gate_enabled);

  if (autoQ.isError && executionState == null) {
    return (
      <div
        className={cn(
          "border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs text-[var(--fg-muted)]",
          className,
        )}
      >
        Execution state unavailable — OWNER/ADMIN required for ITE ops.
      </div>
    );
  }

  const gateDisabled = gate.toLowerCase() !== "enabled";

  return (
    <section
      className={cn(
        "border border-[var(--border)] bg-[var(--surface)] px-3 py-2.5",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Execution state
        </p>
        <Button asChild size="sm" variant="ghost">
          <Link href="/auto-trading">Launch Lock Inspector</Link>
        </Button>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Badge tone={opsMode === "LIVE" || opsMode === "CANARY" ? "success" : "warning"}>
          Ops {opsMode}
        </Badge>
        <Badge tone={gateDisabled ? "warning" : "success"}>
          Gate {gate}
        </Badge>
        <Badge tone={execOn ? "danger" : "neutral"}>
          EXECUTION_ENABLED={execOn ? "true" : "false"}
        </Badge>
        <Badge tone={kill ? "danger" : "neutral"}>
          {kill ? "KILL ARMED" : "Kill clear"}
        </Badge>
        {!compact ? (
          <>
            <Badge tone={gateway ? "success" : "neutral"}>
              Gateway {gateway ? "CONNECTED" : "OFFLINE"}
            </Badge>
            <Badge tone={broker ? "success" : "neutral"}>
              Broker {broker ? "CONNECTED" : "OFF"}
            </Badge>
          </>
        ) : null}
      </div>

      {launchReady ? (
        <div className="mt-2 text-xs text-[var(--success)]">
          <p className="font-medium">Launch Ready</p>
          <p>Gate Enabled · Execution Ready</p>
        </div>
      ) : gateDisabled || lockCount > 0 ? (
        <div className="mt-2 space-y-1 text-xs text-[var(--warning)]">
          <p className="font-medium text-[var(--fg)]">
            Gate Disabled — {lockCount || "see"} launch lock
            {lockCount === 1 ? "" : "s"}
          </p>
          {firstLock ? (
            <>
              <p>
                ✘ {str(firstLock.label)} · Current: {str(firstLock.value)}
              </p>
              <p className="text-[var(--fg-muted)]">
                Why: {str(firstLock.why)}
              </p>
              <p className="whitespace-pre-line font-mono text-[11px] text-[var(--fg)]">
                Resolution:{"\n"}
                {str(firstLock.how_to_resolve)}
              </p>
            </>
          ) : primary ? (
            <p>
              Primary blocker: {primary}. Open Launch Lock Inspector for full WHY /
              Resolution on every lock.
            </p>
          ) : (
            <p>
              Open Launch Lock Inspector for every prerequisite with WHY and
              Resolution.
            </p>
          )}
        </div>
      ) : (
        <p className="mt-2 text-xs text-[var(--success)]">
          Gate Enabled — signals may enter Decision → Risk → Safety → Execution.
        </p>
      )}
    </section>
  );
}

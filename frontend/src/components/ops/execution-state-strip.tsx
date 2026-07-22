"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

type Props = {
  className?: string;
  /** Prefer auto-trading payload when parent already loaded it. */
  executionState?: Record<string, unknown> | null;
  compact?: boolean;
};

/**
 * Shared authoritative execution snapshot for Auto Trading / Monitoring /
 * Broker / Gateway. Never invents LIVE — reads ops_mode + EXECUTION_ENABLED
 * + gate primary_blocker from ITE ops.
 */
export function ExecutionStateStrip({
  className,
  executionState,
  compact = false,
}: Props) {
  const q = useQuery({
    queryKey: ["ite-ops-auto-trading"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 15_000,
    enabled: executionState == null,
  });

  const raw = executionState ?? asRecord(asRecord(q.data).execution_state);
  const fromRoot = asRecord(q.data);
  const opsMode = str(raw.ops_mode || fromRoot.ops_mode, "—");
  const gate = str(raw.gate_status || fromRoot.status, "—");
  const execOn = Boolean(
    raw.execution_enabled ?? fromRoot.execution_enabled ?? false,
  );
  const gateway = Boolean(raw.gateway_connected);
  const broker = Boolean(raw.broker_connected);
  const primary = str(
    raw.primary_blocker || fromRoot.primary_blocker,
    "",
  );
  const category = str(
    raw.blocking_category || fromRoot.blocking_category,
    "",
  );
  const kill = Boolean(raw.kill_switch_armed ?? fromRoot.emergency_stop);

  if (q.isError && executionState == null) {
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
          <Link href="/ops">Promote / certify</Link>
        </Button>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Badge tone={opsMode === "LIVE" || opsMode === "CANARY" ? "success" : "warning"}>
          Ops {opsMode}
        </Badge>
        <Badge tone={gate.toLowerCase() === "enabled" ? "success" : "warning"}>
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
      {primary ? (
        <p className="mt-2 text-xs text-[var(--warning)]">
          <span className="font-medium text-[var(--fg-subtle)]">
            Gate blocked
            {category ? ` · ${category}` : ""}:{" "}
          </span>
          {primary}
        </p>
      ) : gate.toLowerCase() === "enabled" ? (
        <p className="mt-2 text-xs text-[var(--success)]">
          Gate Enabled — signals may enter Decision → Risk → Safety → Execution.
        </p>
      ) : null}
    </section>
  );
}

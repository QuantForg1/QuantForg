"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatRelativeTime } from "@/lib/utils";
import { str } from "@/lib/desk";

function tone(
  value: string,
): "success" | "warning" | "danger" | "neutral" {
  const v = value.toLowerCase();
  if (["running", "connected", "ready", "healthy", "authorized"].some((x) => v.includes(x)))
    return "success";
  if (["paused", "reconnecting", "connecting", "degraded"].some((x) => v.includes(x)))
    return "warning";
  if (["error", "stopped", "blocked", "disconnected", "failed"].some((x) => v.includes(x)))
    return "danger";
  return "neutral";
}

function Row({
  label,
  value,
  badge,
}: {
  label: string;
  value: string;
  badge?: string;
}) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 border-b border-[var(--border)] py-2 last:border-b-0">
      <p className="text-xs text-[var(--fg-muted)]">{label}</p>
      <div className="flex min-w-0 items-center gap-2">
        {badge ? <Badge tone={tone(badge)}>{badge}</Badge> : null}
        <p className="truncate text-sm text-[var(--fg)]">{value}</p>
      </div>
    </div>
  );
}

export function RobotActivityPanel({
  robotState,
  brokerLabel,
  tradingAuthLabel,
  tradingAuthDetail,
  lastHeartbeat,
  lastSignalLabel,
  lastExecutionLabel,
  lastExecutionResult,
  omsLabel,
  lastSyncLabel,
  recentError,
  componentsHealthy,
}: {
  robotState: string;
  brokerLabel: string;
  tradingAuthLabel: string;
  tradingAuthDetail?: string;
  lastHeartbeat: string | null;
  lastSignalLabel: string;
  lastExecutionLabel: string;
  lastExecutionResult: string;
  omsLabel: string;
  lastSyncLabel: string;
  recentError: string | null;
  componentsHealthy?: boolean | null;
}) {
  return (
    <section
      aria-labelledby="robot-activity"
      className="space-y-3 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-[var(--shadow-card)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="robot-activity" className="text-sm font-medium text-[var(--fg)]">
              Robot Activity
            </h2>
            <Badge tone={tone(robotState)}>{robotState}</Badge>
          </div>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">
            Process health, broker connection, and trading authorization are shown
            separately. A healthy robot does not imply LIVE orders may submit.
          </p>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/ai-robot">Robot desk</Link>
        </Button>
      </div>

      <div className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg)]/30 px-3">
        <Row label="Robot operational status" value={robotState} badge={robotState} />
        <Row
          label="Last heartbeat / activity"
          value={
            lastHeartbeat
              ? formatRelativeTime(lastHeartbeat)
              : "No heartbeat reported"
          }
        />
        <Row label="Broker connection" value={brokerLabel} badge={brokerLabel} />
        <Row
          label="Trading authorization"
          value={tradingAuthDetail || tradingAuthLabel}
          badge={tradingAuthLabel}
        />
        <Row label="Last generated signal" value={lastSignalLabel} />
        <Row label="Last execution attempt" value={lastExecutionLabel} />
        <Row label="Last execution result" value={lastExecutionResult} />
        <Row label="OMS / processing" value={omsLabel} badge={omsLabel} />
        <Row label="Account synchronization" value={lastSyncLabel} />
        <Row
          label="Trading components plane"
          value={
            componentsHealthy == null
              ? "Not observed"
              : componentsHealthy
                ? "Healthy"
                : "Degraded"
          }
          badge={
            componentsHealthy == null
              ? undefined
              : componentsHealthy
                ? "Healthy"
                : "Degraded"
          }
        />
      </div>

      {recentError ? (
        <p className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--danger-soft)_35%,var(--bg))] px-3 py-2 text-xs text-[var(--fg)]">
          Recent operational note: {str(recentError)}
        </p>
      ) : null}
    </section>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { Radar } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { institutionalObservabilityApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[var(--border)] bg-[var(--bg)]/40 px-2.5 py-2">
      <p className="text-[9px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p className="mt-1 font-mono text-sm tabular text-[var(--fg)]">{value}</p>
    </div>
  );
}

function fmt(v: unknown, d = 2): string {
  const n = num(v);
  return Number.isFinite(n) ? formatNumber(n, d) : "—";
}

function fmtPct(v: unknown): string {
  const n = num(v);
  return Number.isFinite(n) ? `${formatNumber(n * 100, 1)}%` : "—";
}

function toneFor(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "healthy") return "success";
  if (status === "degraded" || status === "unknown") return "warning";
  if (status === "down") return "danger";
  return "neutral";
}

/**
 * Institutional Observability desk — monitoring only.
 * Never modifies trading behaviour.
 */
export function InstitutionalObservabilityWorkspace() {
  const q = useQuery({
    queryKey: ["institutional-observability"],
    queryFn: () => institutionalObservabilityApi.dashboard(),
    retry: false,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });

  if (q.isLoading && !q.data) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message="Observability platform unavailable."
        onRetry={() => void q.refetch()}
      />
    );
  }

  const d = asRecord(q.data);
  const health = asRecord(d.health);
  const comps = asRecord(health.components);
  const counts = asRecord(health.counts);
  const lat = asRecord(asRecord(d.latencies).latencies_ms);
  const resources = asRecord(d.resources);
  const errors = asRecord(asRecord(d.errors).totals);
  const uptime = asRecord(d.uptime);
  const dep = asList(asRecord(d.dependency).nodes).map(asRecord);
  const alerts = asList(asRecord(d.alerts).alerts).map(asRecord);
  const recs = asList(d.recommendations).map(String);
  const summary = asRecord(d.evidence_summary);

  if (str(d.status) === "unavailable") {
    return (
      <DeskEmpty
        icon={Radar}
        title="No observability snapshot"
        description="Health probes returned unavailable. Refresh once API/journal dependencies are reachable."
      />
    );
  }

  const componentKeys = [
    "api",
    "gateway",
    "broker",
    "mt5_session",
    "execution_queue",
    "journal_writer",
    "evidence_lab",
    "warehouse",
    "governance",
    "performance_iq",
    "replay_engine",
    "operations_center",
  ] as const;

  const latencyKeys = [
    "api",
    "gateway",
    "broker",
    "decision",
    "risk",
    "safety",
    "execution",
    "journal",
    "dashboard",
  ] as const;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Institutional Observability
          </span>
          <Badge tone="neutral">v{str(d.version, "1.0.1")}</Badge>
          <Badge tone={toneFor(str(health.overall, "unknown"))}>
            {str(health.overall, "unknown")}
          </Badge>
          <Badge tone="neutral">
            alerts={str(summary.alert_count ?? asRecord(d.alerts).count, "0")}
          </Badge>
        </div>
        <Button size="sm" variant="outline" onClick={() => void q.refetch()}>
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-6">
        <Stat label="Healthy" value={str(counts.healthy, "0")} />
        <Stat label="Degraded" value={str(counts.degraded, "0")} />
        <Stat label="Down" value={str(counts.down, "0")} />
        <Stat label="Unknown" value={str(counts.unknown, "0")} />
        <Stat
          label="Uptime"
          value={`${fmt(uptime.current_uptime_seconds, 0)}s`}
        />
        <Stat label="24h ratio" value={fmtPct(uptime.uptime_24h_ratio)} />
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Live component status
        </h3>
        <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-4">
          {componentKeys.map((key) => {
            const c = asRecord(comps[key]);
            return (
              <div
                key={key}
                className="border border-[var(--border)] bg-[var(--bg)]/40 px-2.5 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                    {key.replaceAll("_", " ")}
                  </p>
                  <Badge tone={toneFor(str(c.status, "unknown"))}>
                    {str(c.status, "—")}
                  </Badge>
                </div>
                <p className="mt-1 truncate text-[11px] text-[var(--fg-subtle)]">
                  {str(c.detail, "")}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Latency (ms)
        </h3>
        <div className="mt-2 grid grid-cols-3 gap-2 md:grid-cols-5 lg:grid-cols-9">
          {latencyKeys.map((key) => (
            <Stat key={key} label={key} value={fmt(lat[key], 1)} />
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Resources
          </h3>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <Stat label="CPU %" value={fmt(resources.cpu_percent, 1)} />
            <Stat label="Memory %" value={fmt(resources.memory_percent, 1)} />
            <Stat label="Memory MB" value={fmt(resources.memory_used_mb, 0)} />
            <Stat label="Disk %" value={fmt(resources.disk_percent, 1)} />
            <Stat label="Open conns" value={str(resources.open_connections, "—")} />
            <Stat label="Queue depth" value={str(resources.queue_depth, "—")} />
          </div>
        </section>
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Error analytics
          </h3>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <Stat label="Warnings" value={str(errors.warnings, "0")} />
            <Stat label="Errors" value={str(errors.errors, "0")} />
            <Stat label="Critical" value={str(errors.critical_events, "0")} />
            <Stat label="Timeouts" value={str(errors.timeouts, "0")} />
            <Stat label="Reconnects" value={str(errors.reconnects, "0")} />
            <Stat label="Failures" value={str(errors.failures, "0")} />
          </div>
        </section>
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Dependency map
        </h3>
        <ol className="mt-2 space-y-1">
          {dep.map((node, i) => (
            <li
              key={str(node.id)}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--bg)]/40 px-2.5 py-1.5 text-[12px]"
            >
              <span className="font-mono text-[var(--fg-subtle)]">{i + 1}</span>
              <span className="font-semibold">{str(node.id)}</span>
              <Badge tone={toneFor(str(node.status, "unknown"))}>
                {str(node.status, "—")}
              </Badge>
              {i < dep.length - 1 ? (
                <span className="text-[var(--fg-subtle)]">↓</span>
              ) : null}
            </li>
          ))}
        </ol>
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Alert summary
        </h3>
        {alerts.length === 0 ? (
          <p className="mt-2 text-[12px] text-[var(--fg-subtle)]">No active alerts</p>
        ) : (
          <ul className="mt-2 space-y-1 text-[12px]">
            {alerts.map((a) => (
              <li
                key={str(a.id)}
                className="border border-[var(--border)] bg-[var(--bg)]/40 px-2.5 py-1.5"
              >
                <Badge
                  tone={
                    str(a.severity) === "critical"
                      ? "danger"
                      : str(a.severity) === "warning"
                        ? "warning"
                        : "neutral"
                  }
                >
                  {str(a.severity, "info")}
                </Badge>{" "}
                {str(a.message)}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Uptime windows
        </h3>
        <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
          <Stat label="Current (s)" value={fmt(uptime.current_uptime_seconds, 0)} />
          <Stat label="24h" value={fmtPct(uptime.uptime_24h_ratio)} />
          <Stat label="7d" value={fmtPct(uptime.uptime_7d_ratio)} />
          <Stat label="30d" value={fmtPct(uptime.uptime_30d_ratio)} />
        </div>
        <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
          {str(uptime.note, "")}
        </p>
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Recommendations
        </h3>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-[12px]">
          {recs.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

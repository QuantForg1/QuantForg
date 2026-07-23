"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteReliabilityApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "border border-[var(--border)] bg-[var(--surface)]",
        className,
      )}
    >
      <header className="border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="border border-[var(--border)]/70 bg-[var(--bg)] px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg text-[var(--fg)]">{value}</div>
      {hint ? (
        <div className="mt-0.5 text-[10px] text-[var(--fg-muted)]">{hint}</div>
      ) : null}
    </div>
  );
}

function severityTone(sev: string): "neutral" | "warning" | "danger" | "success" {
  const s = sev.toUpperCase();
  if (s === "CRITICAL" || s === "ERROR") return "danger";
  if (s === "WARNING") return "warning";
  if (s === "INFO") return "success";
  return "neutral";
}

export function ProductionReliabilityWorkspace() {
  const dash = useQuery({
    queryKey: ["production-reliability-dash"],
    queryFn: iteReliabilityApi.dashboard,
    retry: false,
    refetchInterval: 15_000,
  });
  const network = useQuery({
    queryKey: ["production-reliability-network"],
    queryFn: iteReliabilityApi.network,
    retry: false,
    refetchInterval: 15_000,
  });

  if (dash.isLoading || network.isLoading) return <DeskSkeleton rows={4} />;
  if (dash.isError && network.isError) {
    return (
      <DeskError message="Reliability dashboard unavailable (OWNER/ADMIN · /ite/reliability/*)." />
    );
  }

  const d = asRecord(dash.data);
  const nRoot = asRecord(network.data);
  const net = asRecord(nRoot.network ?? asRecord(d.network));
  const incidents = asList(
    nRoot.incidents ?? asList(d.network_incidents),
  ).map(asRecord);
  const reconnects = asList(
    nRoot.reconnect_log ?? asList(d.reconnect_log),
  ).map(asRecord);
  const last = asRecord(net.last_network_incident);

  return (
    <div className="space-y-3">
      <Panel title="Network reliability">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <Metric
            label="Gateway uptime"
            value={`${num(net.gateway_uptime_pct, 100).toFixed(2)}%`}
            hint={net.gateway_currently_up ? "UP" : "DOWN"}
          />
          <Metric
            label="DNS failures (24h)"
            value={str(net.dns_failures_24h, "0")}
          />
          <Metric
            label="Reconnect count"
            value={str(net.reconnect_count, "0")}
          />
          <Metric
            label="Avg reconnect time"
            value={`${num(net.average_reconnect_time_ms, 0).toFixed(0)} ms`}
          />
          <Metric
            label="MT5 connection uptime"
            value={`${num(net.mt5_connection_uptime_pct, 100).toFixed(2)}%`}
            hint={net.mt5_currently_up ? "UP" : "DOWN"}
          />
          <Metric
            label="Last network incident"
            value={
              last.timestamp
                ? str(last.timestamp).slice(11, 19)
                : "None"
            }
            hint={last.severity ? `${str(last.severity)} · ${str(last.kind)}` : "—"}
          />
        </div>
      </Panel>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Network incidents">
          {incidents.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">
              No network incidents recorded this process lifetime.
            </p>
          ) : (
            <div className="max-h-72 space-y-1 overflow-auto">
              {[...incidents].reverse().map((i) => (
                <div
                  key={str(i.id)}
                  className="border-b border-[var(--border)]/50 py-1.5 text-sm last:border-0"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={severityTone(str(i.severity))}>
                      {str(i.severity)}
                    </Badge>
                    <span className="font-mono text-[11px] text-[var(--fg-subtle)]">
                      {str(i.timestamp).slice(11, 19)}
                    </span>
                    <span className="text-[11px] uppercase tracking-wide text-[var(--fg-muted)]">
                      {str(i.kind)} · {str(i.component)}
                    </span>
                    <span className="text-[11px] text-[var(--fg-muted)]">
                      {str(i.recovery_status)} · retries {str(i.retry_count, "0")} ·{" "}
                      {num(i.duration_ms, 0).toFixed(0)} ms
                    </span>
                  </div>
                  <div className="mt-0.5 truncate font-mono text-[11px] text-[var(--fg)]">
                    {str(i.error)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Reconnect log (every attempt)">
          {reconnects.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">
              No reconnect attempts logged yet.
            </p>
          ) : (
            <div className="max-h-72 space-y-1 overflow-auto font-mono text-[11px]">
              {[...reconnects].reverse().map((e) => (
                <div
                  key={str(e.id)}
                  className="border-b border-[var(--border)]/50 py-1 last:border-0"
                >
                  <span className="text-[var(--fg-subtle)]">
                    {str(e.at).slice(11, 19)}
                  </span>{" "}
                  <span className="uppercase">{str(e.component)}</span> #{str(e.attempt)}{" "}
                  {e.success === true
                    ? "ok"
                    : e.success === false
                      ? "fail"
                      : "…"}{" "}
                  — {str(e.detail)}
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Classification">
        <p className="text-sm text-[var(--fg-muted)]">
          INFO — single recovered DNS/timeout. WARNING — repeated failures in 15m
          or unrecovered transport loss. CRITICAL — clustered failures (≥4) or
          sustained unrecovered repeats. Every reconnect attempt is logged; none
          are silent.
        </p>
      </Panel>
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { opsApi } from "@/lib/api/endpoints";
import { asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";

const NA = "Not available";

function cell(label: string, value: string) {
  return (
    <div
      key={label}
      className="rounded border border-[var(--border)]/70 bg-[var(--surface-2)]/40 px-2.5 py-2"
    >
      <p className="text-[9px] uppercase tracking-wide text-[var(--fg-subtle)]">{label}</p>
      <p className="mt-1 font-mono text-sm tabular-nums text-[var(--fg)]">{value}</p>
    </div>
  );
}

function fmt(v: unknown, digits = 1, suffix = ""): string {
  const n = num(v, NaN);
  if (!Number.isFinite(n)) return NA;
  return `${formatNumber(n, digits)}${suffix}`;
}

/** RC1 ops telemetry strip — live audits + infrastructure probes only. */
export function Rc1TelemetryPanel() {
  const q = useQuery({
    queryKey: ["ops-rc1-telemetry"],
    queryFn: opsApi.rc1Telemetry,
    retry: false,
    refetchInterval: 30_000,
  });

  const t = asRecord(q.data);
  const alertRows = Array.isArray(t.alerts)
    ? t.alerts.map(asRecord).filter((a) => str(a.message))
    : [];

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">RC1 Execution Telemetry</CardTitle>
        <p className="text-[11px] text-[var(--fg-muted)]">
          Source: execution_audits (24h) + live Gateway/Railway/Cloudflare/MT5 probes ·{" "}
          {str(t.collected_at, "pending")}
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {q.isLoading ? (
          <p className="text-[11px] text-[var(--fg-muted)]">Loading telemetry…</p>
        ) : q.isError ? (
          <p className="text-[11px] text-[var(--danger)]">
            Telemetry unavailable — admin role required or probe failed.
          </p>
        ) : (
          <>
            <div className="grid gap-2 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
              {cell("Execution Success %", fmt(t.execution_success_pct, 1, "%"))}
              {cell("Execution Reject %", fmt(t.execution_reject_pct, 1, "%"))}
              {cell("Risk Reject %", fmt(t.risk_reject_pct, 1, "%"))}
              {cell("Avg Broker Latency", fmt(t.avg_broker_latency_ms, 1, " ms"))}
              {cell("Avg Gateway Latency", fmt(t.avg_gateway_latency_ms, 1, " ms"))}
              {cell("Avg Validation Time", fmt(t.avg_validation_time_ms, 1, " ms"))}
              {cell("Daily Orders", fmt(t.daily_orders, 0))}
              {cell("Daily Volume", fmt(t.daily_volume, 2))}
              {cell(
                "Daily P/L",
                t.daily_pnl == null ? NA : fmt(t.daily_pnl, 2),
              )}
              {cell("Gateway", str(t.gateway_availability, NA))}
              {cell("Railway", str(t.railway_availability, NA))}
              {cell("Cloudflare", str(t.cloudflare_availability, NA))}
              {cell("MT5", str(t.mt5_availability, NA))}
              {cell("System Health Score", fmt(t.system_health_score, 1))}
              {cell("Audit rows (24h)", fmt(t.audit_rows_24h, 0))}
              {cell("Request chains (24h)", fmt(t.unique_request_chains_24h, 0))}
            </div>
            <div>
              <p className="mb-1.5 text-[9px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Alerts
              </p>
              {alertRows.length === 0 ? (
                <p className="text-[11px] text-[var(--fg-muted)]">No active telemetry alerts.</p>
              ) : (
                <ul className="space-y-1">
                  {alertRows.map((a) => (
                    <li
                      key={`${str(a.code)}-${str(a.message)}`}
                      className="rounded border border-[var(--border)]/70 bg-[var(--surface-2)]/40 px-2.5 py-2 text-[11px]"
                    >
                      <span className="font-mono uppercase text-[var(--fg-subtle)]">
                        {str(a.severity, "info")}
                      </span>
                      <span className="ml-2 text-[var(--fg)]">{str(a.message)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

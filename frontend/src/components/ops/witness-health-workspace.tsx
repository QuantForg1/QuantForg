"use client";

import { useQuery } from "@tanstack/react-query";
import { HeartPulse } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteOpsApi } from "@/lib/api/endpoints";
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

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-[var(--border)]/50 py-1.5 last:border-0">
      <span className="text-[11px] uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
        {label}
      </span>
      <span
        className={cn(
          "max-w-[70%] truncate text-right font-mono text-[12px]",
          tone === "bad"
            ? "text-[var(--warning)]"
            : tone === "ok"
              ? "text-[var(--success)]"
              : "text-[var(--fg)]",
        )}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

export function WitnessHealthWorkspace() {
  const q = useQuery({
    queryKey: ["ite-ops-witness-health"],
    queryFn: iteOpsApi.witnessHealth,
    retry: false,
    refetchInterval: 15_000,
  });

  if (q.isLoading && !q.data) return <DeskSkeleton rows={5} />;
  if (q.error && !q.data) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Witness Health unavailable (OWNER/ADMIN · /ite/ops/witness-health)."
        }
      />
    );
  }

  const root = asRecord(q.data);
  const health = asRecord(root.health);
  const auth = str(root.authentication ?? health.authentication, "UNKNOWN");
  const authLabel = str(health.authentication_label, "");
  const continuity = asRecord(
    root.heartbeat_continuity ?? health.heartbeat_continuity,
  );
  const trading = asRecord(
    root.trading_execution_health ?? health.trading_execution_health,
  );
  const lastErr = asRecord(
    root.last_authentication_error ?? health.last_authentication_error,
  );
  const isolation = asRecord(root.acceptance_isolation);
  const incidents = asList(
    root.auth_incidents ?? health.auth_incidents_recent,
  ).map(asRecord);
  const authFailed = auth === "FAILED" || Boolean(authLabel);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <HeartPulse className="h-4 w-4 text-[var(--fg-subtle)]" />
        <span className="text-[12px] font-medium text-[var(--fg)]">
          Witness Health
        </span>
        <Badge tone="neutral">READ-ONLY</Badge>
        <Badge tone={authFailed ? "warning" : "success"}>
          {authFailed ? "AUTH WATCH" : "AUTH OK"}
        </Badge>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel
          title="Authentication"
          action={
            <Badge tone={authFailed ? "danger" : "success"}>
              {authFailed ? str(authLabel, "Witness Authentication Failed") : auth}
            </Badge>
          }
        >
          {authFailed ? (
            <p className="mb-3 font-mono text-[16px] text-[var(--warning)]">
              Witness Authentication Failed
            </p>
          ) : (
            <p className="mb-3 font-mono text-[16px] text-[var(--success)]">OK</p>
          )}
          <Row
            label="Last successful heartbeat"
            value={str(
              root.last_successful_heartbeat ?? health.last_successful_heartbeat,
              "—",
            )}
          />
          <Row
            label="Last authentication error"
            value={
              lastErr.utc_timestamp
                ? `${str(lastErr.http_status, "401")} · ${str(lastErr.endpoint, "—")} · ${str(lastErr.error, "—").slice(0, 80)}`
                : "None"
            }
            tone={lastErr.utc_timestamp ? "bad" : "ok"}
          />
          <Row
            label="Recovery time"
            value={str(root.recovery_time ?? health.recovery_time, "—")}
            tone={
              str(root.recovery_time ?? health.recovery_time) ? "ok" : undefined
            }
          />
          <Row
            label="Retry count (open)"
            value={str(lastErr.retry_count ?? asRecord(health.open_auth_incident).retry_count, "0")}
          />
        </Panel>

        <Panel title="Heartbeat continuity">
          <Row label="Status" value={str(continuity.status, "—")} />
          <Row
            label="Expected interval"
            value={
              continuity.expected_interval_sec != null
                ? `${str(continuity.expected_interval_sec)} s`
                : "—"
            }
          />
          <Row
            label="Last gap"
            value={
              continuity.last_gap_sec != null
                ? `${str(continuity.last_gap_sec)} s`
                : "—"
            }
          />
          <Row
            label="Consecutive OK polls"
            value={str(continuity.consecutive_ok, "0")}
          />
        </Panel>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Trading execution health (separate)">
          <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
            {str(
              trading.note,
              "From successful witness polls only — auth failures do not update this.",
            )}
          </p>
          <Row label="Ops mode" value={str(trading.ops_mode, "—")} />
          <Row label="Cycle outcome" value={str(trading.last_cycle_outcome, "—")} />
          <Row label="Session" value={str(trading.last_session, "—")} />
          <Row label="MT5 ticket" value={str(trading.mt5_ticket, "—")} />
          <Row label="Observed at" value={str(trading.observed_at, "—")} />
        </Panel>

        <Panel title="Production Acceptance isolation">
          <p className="font-mono text-[13px] text-[var(--fg)]">
            Witness auth affects Acceptance:{" "}
            {isolation.witness_auth_affects_production_acceptance === true
              ? "YES"
              : "NO"}
          </p>
          <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
            {str(
              isolation.reason,
              "Production Acceptance uses OMS/broker/MT5/Deal evidence only.",
            )}
          </p>
        </Panel>
      </div>

      <Panel title="Authentication incident history">
        {incidents.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">No auth incidents recorded.</p>
        ) : (
          <div className="max-h-64 space-y-1 overflow-auto font-mono text-[11px]">
            {incidents.map((i, idx) => (
              <div
                key={str(i.id, String(idx))}
                className="border-b border-[var(--border)]/50 py-1.5 last:border-0"
              >
                <span className="text-[var(--fg-subtle)]">
                  {str(i.utc_timestamp).slice(0, 19)}
                </span>{" "}
                <Badge
                  tone={
                    str(i.recovery_status) === "RECOVERED" ? "success" : "warning"
                  }
                >
                  {str(i.recovery_status, "ONGOING")}
                </Badge>{" "}
                HTTP {str(i.http_status, "—")} · {str(i.endpoint)} · retries{" "}
                {str(i.retry_count, "0")}
                {i.recovered_at ? (
                  <span className="text-[var(--success)]">
                    {" "}
                    · recovered {str(i.recovered_at).slice(0, 19)}
                  </span>
                ) : null}
                <div className="truncate text-[var(--fg-muted)]">{str(i.error)}</div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}

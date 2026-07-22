"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Scale } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { auditGovernanceApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";

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

/**
 * Institutional Audit Trail & Governance desk — governance only.
 * Never modifies strategy / risk / safety / execution / Performance IQ /
 * Evidence Lab / Trading Operations Center.
 */
export function AuditGovernanceWorkspace() {
  const [category, setCategory] = useState<string>("");
  const [severity, setSeverity] = useState<string>("");
  const [q, setQ] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");

  const dashQ = useQuery({
    queryKey: ["audit-governance-dashboard"],
    queryFn: () => auditGovernanceApi.dashboard(),
    retry: false,
    staleTime: 15_000,
  });

  const eventsQ = useQuery({
    queryKey: ["audit-governance-events", category, severity, q, since, until],
    queryFn: () =>
      auditGovernanceApi.events({
        limit: 200,
        category: category || undefined,
        severity: severity || undefined,
        q: q || undefined,
        since: since || undefined,
        until: until || undefined,
      }),
    retry: false,
    staleTime: 10_000,
  });

  const reportsQ = useQuery({
    queryKey: ["audit-governance-reports"],
    queryFn: () => auditGovernanceApi.reports(),
    retry: false,
    staleTime: 20_000,
  });

  const loading = dashQ.isLoading && !dashQ.data;
  if (loading) return <DeskSkeleton rows={8} />;
  if (dashQ.isError) {
    return (
      <DeskError
        message="Audit Governance unavailable."
        onRetry={() => void dashQ.refetch()}
      />
    );
  }

  const d = asRecord(dashQ.data);
  const counts = asRecord(d.counts);
  const security = asRecord(d.security);
  const timeline = asList(asRecord(d.timeline).steps).map(asRecord);
  const critical = asList(d.critical_events).map(asRecord);
  const warnings = asList(d.warnings).map(asRecord);
  const events = asList(asRecord(eventsQ.data).items).map(asRecord);
  const recs = asList(asRecord(reportsQ.data).recommendations).map(String);
  const categories = asList(asRecord(d.filters).categories).map(String);

  const empty = num(counts.total_events) === 0;

  if (empty) {
    return (
      <DeskEmpty
        icon={Scale}
        title="No governance audit events"
        description="POST institutional ops events to /audit-governance/events, or seed a local report via scripts/audit_governance.py --demo. The ledger stays empty rather than fabricating history."
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Audit Trail & Governance
          </span>
          <Badge tone="neutral">v{str(d.version, "1.0.1")}</Badge>
          <Badge tone={security.append_only ? "success" : "danger"}>
            append-only
          </Badge>
          <Badge tone={security.immutable ? "success" : "danger"}>immutable</Badge>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            void dashQ.refetch();
            void eventsQ.refetch();
            void reportsQ.refetch();
          }}
        >
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-6">
        <Stat label="Events" value={str(counts.total_events, "0")} />
        <Stat label="Critical" value={str(counts.critical, "0")} />
        <Stat label="Warnings" value={str(counts.warnings, "0")} />
        <Stat label="Config changes" value={str(counts.config_changes, "0")} />
        <Stat label="Trade versions" value={str(counts.trade_version_tags, "0")} />
        <Stat
          label="Rejected mutations"
          value={str(security.rejected_mutations, "0")}
        />
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Filters · search · date range
        </h3>
        <div className="mt-2 flex flex-wrap gap-2">
          <select
            className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[12px]"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[12px]"
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
          >
            <option value="">All severities</option>
            <option value="info">info</option>
            <option value="warning">warning</option>
            <option value="critical">critical</option>
          </select>
          <input
            className="min-w-[160px] flex-1 border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[12px]"
            placeholder="Search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <input
            type="datetime-local"
            className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[12px]"
            value={since}
            onChange={(e) => setSince(e.target.value)}
            aria-label="Since"
          />
          <input
            type="datetime-local"
            className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[12px]"
            value={until}
            onChange={(e) => setUntil(e.target.value)}
            aria-label="Until"
          />
        </div>
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Forensic timeline
        </h3>
        <ol className="mt-2 space-y-1">
          {timeline.map((step, i) => (
            <li
              key={`${str(step.event_id)}-${i}`}
              className="border border-[var(--border)] bg-[var(--bg)]/40 px-2.5 py-1.5 text-[12px]"
            >
              <span className="font-mono text-[var(--fg-subtle)]">
                {str(step.timestamp, "—")}
              </span>
              <span className="mx-2 text-[var(--fg-subtle)]">↓</span>
              <span className="font-semibold">{str(step.action, "—")}</span>
              <span className="ml-2 text-[var(--fg-subtle)]">
                {str(step.previous_state, "")}
                {step.previous_state || step.new_state ? " → " : ""}
                {str(step.new_state, "")}
              </span>
            </li>
          ))}
        </ol>
      </section>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Critical events
          </h3>
          <ul className="mt-2 max-h-40 space-y-1 overflow-auto text-[12px]">
            {critical.length === 0 ? (
              <li className="text-[var(--fg-subtle)]">None</li>
            ) : (
              critical.map((e) => (
                <li key={str(e.event_id)} className="font-mono">
                  {str(e.timestamp)} · {str(e.action)} · {str(e.actor)}
                </li>
              ))
            )}
          </ul>
        </section>
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Warnings
          </h3>
          <ul className="mt-2 max-h-40 space-y-1 overflow-auto text-[12px]">
            {warnings.length === 0 ? (
              <li className="text-[var(--fg-subtle)]">None</li>
            ) : (
              warnings.map((e) => (
                <li key={str(e.event_id)} className="font-mono">
                  {str(e.timestamp)} · {str(e.action)} · {str(e.actor)}
                </li>
              ))
            )}
          </ul>
        </section>
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Recent / filtered events
        </h3>
        <div className="mt-2 max-h-56 overflow-auto">
          <table className="w-full text-left text-[11px]">
            <thead className="text-[var(--fg-subtle)]">
              <tr>
                <th className="py-1 pr-2">Time</th>
                <th className="py-1 pr-2">Category</th>
                <th className="py-1 pr-2">Action</th>
                <th className="py-1 pr-2">Actor</th>
                <th className="py-1">Result</th>
              </tr>
            </thead>
            <tbody>
              {events
                .slice()
                .reverse()
                .slice(0, 60)
                .map((e) => (
                  <tr
                    key={str(e.event_id)}
                    className="border-t border-[var(--border)]"
                  >
                    <td className="py-1 pr-2 font-mono">{str(e.timestamp, "—")}</td>
                    <td className="py-1 pr-2">{str(e.category, "—")}</td>
                    <td className="py-1 pr-2">{str(e.action, "—")}</td>
                    <td className="py-1 pr-2">{str(e.actor, "—")}</td>
                    <td className="py-1">{str(e.result, "—")}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
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

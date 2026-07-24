"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { icpApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/institutional-control-plane", label: "Dashboard" },
  { href: "/institutional-control-plane/timeline", label: "Timeline" },
  { href: "/institutional-control-plane/health", label: "Health" },
  { href: "/institutional-control-plane/dependencies", label: "Dependencies" },
  { href: "/institutional-control-plane/evidence", label: "Evidence" },
  { href: "/institutional-control-plane/reports", label: "Reports" },
] as const;

export function IcpNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/institutional-control-plane"
            ? pathname === link.href
            : pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "px-3 py-1.5 text-[12px] uppercase tracking-[0.1em]",
              active
                ? "border border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--fg)]"
                : "text-[var(--fg-muted)] hover:text-[var(--fg)]",
            )}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

function IsolationBadges() {
  return (
    <div className="flex flex-wrap gap-2">
      <Badge tone="neutral">CONTROL PLANE</Badge>
      <Badge tone="success">READ-ONLY</Badge>
      <Badge tone="warning">NEVER MODIFIES PRODUCTION</Badge>
    </div>
  );
}

function severityTone(sev: string): "danger" | "warning" | "neutral" | "success" {
  if (sev === "Critical") return "danger";
  if (sev === "High") return "warning";
  if (sev === "Medium") return "neutral";
  return "success";
}

export function IcpDashboardWorkspace() {
  const q = useQuery({
    queryKey: ["icp", "dashboard"],
    queryFn: () => icpApi.dashboard(),
    refetchInterval: 60_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "ICP unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const health = asRecord(root.health);
  const alerts = asList(root.alerts).map(asRecord);

  return (
    <div className="space-y-4">
      <IcpNav />
      <IsolationBadges />
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Unified executive view across ICC, IDW, CVF, ISE, IEP, ISLM, IRAP, EQS,
        RES, IRDP, AQS, AQC and QKG. Aggregation only — never modifies
        production.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard
          label="Overall"
          value={str(health.overall_platform_health, "—")}
        />
        <MetricCard label="Trading" value={str(health.trading_health, "—")} />
        <MetricCard
          label="Execution"
          value={str(health.execution_health, "—")}
        />
        <MetricCard
          label="Reliability"
          value={str(health.reliability_health, "—")}
        />
        <MetricCard label="Risk" value={str(health.risk_health, "—")} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard
          label="Validation"
          value={str(health.validation_health, "—")}
        />
        <MetricCard
          label="Research"
          value={str(health.research_health, "—")}
        />
        <MetricCard
          label="Simulation"
          value={str(health.simulation_health, "—")}
        />
        <MetricCard
          label="Experiment"
          value={str(health.experiment_health, "—")}
        />
        <MetricCard label="Release" value={str(health.release_health, "—")} />
      </div>
      <OpsPanel title="Executive alerts">
        <ul className="space-y-2">
          {alerts.slice(0, 12).map((a, i) => (
            <li
              key={`${str(a.kind)}-${i}`}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge tone={severityTone(str(a.severity))}>
                {str(a.severity)}
              </Badge>
              <span className="font-medium">{str(a.kind)}</span>
              <span className="text-[var(--fg-muted)]">{str(a.detail)}</span>
              <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                {str(a.source_subsystem)} ·{" "}
                {str(asRecord(a.evidence_link).subsystem)}
              </span>
            </li>
          ))}
          {!alerts.length ? (
            <li className="text-[12px] text-[var(--fg-muted)]">
              No executive alerts in current snapshot.
            </li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IcpTimelineWorkspace() {
  const q = useQuery({
    queryKey: ["icp", "timeline"],
    queryFn: () => icpApi.timeline(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Timeline unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const timeline = asList(asRecord(q.data).timeline).map(asRecord);

  return (
    <div className="space-y-4">
      <IcpNav />
      <IsolationBadges />
      <OpsPanel title="Global timeline">
        <ul className="space-y-2">
          {timeline.map((ev, i) => (
            <li
              key={`${str(ev.kind)}-${i}`}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge tone="neutral">{str(ev.kind)}</Badge>
              <span className="font-medium">{str(ev.title)}</span>
              <span className="text-[var(--fg-muted)]">{str(ev.status)}</span>
              <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                {str(ev.source_subsystem)} · {str(ev.at)}
              </span>
            </li>
          ))}
          {!timeline.length ? (
            <li className="text-[var(--fg-muted)]">No timeline events.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IcpHealthWorkspace() {
  const q = useQuery({
    queryKey: ["icp", "health"],
    queryFn: () => icpApi.health(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Health unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const health = asRecord(asRecord(q.data).health);
  const avail = asRecord(health.subsystem_availability);
  const entries = Object.entries(avail);

  return (
    <div className="space-y-4">
      <IcpNav />
      <IsolationBadges />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {(
          [
            ["Overall", "overall_platform_health"],
            ["Trading", "trading_health"],
            ["Execution", "execution_health"],
            ["Reliability", "reliability_health"],
            ["Validation", "validation_health"],
            ["Research", "research_health"],
            ["Simulation", "simulation_health"],
            ["Experiment", "experiment_health"],
            ["Risk", "risk_health"],
            ["Release", "release_health"],
          ] as const
        ).map(([label, key]) => (
          <MetricCard key={key} label={label} value={str(health[key], "—")} />
        ))}
      </div>
      <OpsPanel title="Subsystem availability">
        <ul className="flex flex-wrap gap-2 text-[12px]">
          {entries.map(([k, v]) => (
            <li key={k}>
              <Badge tone={v ? "success" : "warning"}>
                {k.toUpperCase()} · {v ? "up" : "gap"}
              </Badge>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IcpDependenciesWorkspace() {
  const q = useQuery({
    queryKey: ["icp", "dependencies"],
    queryFn: () => icpApi.dependencies(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Dependencies unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const deps = asRecord(asRecord(q.data).dependencies);
  const nodes = asList(deps.nodes).map(asRecord);
  const edges = asList(deps.edges).map(asRecord);

  return (
    <div className="space-y-4">
      <IcpNav />
      <IsolationBadges />
      <div className="grid gap-3 sm:grid-cols-2">
        <MetricCard label="Nodes" value={str(deps.node_count, "—")} />
        <MetricCard label="Edges" value={str(deps.edge_count, "—")} />
      </div>
      <OpsPanel title="Subsystem nodes">
        <ul className="flex flex-wrap gap-2">
          {nodes.map((n) => (
            <Badge
              key={str(n.id)}
              tone={n.available ? "success" : "warning"}
            >
              {str(n.label)}
            </Badge>
          ))}
        </ul>
      </OpsPanel>
      <OpsPanel title="Dependency edges">
        <ul className="max-h-80 space-y-1 overflow-auto text-[11px] font-mono text-[var(--fg-muted)]">
          {edges.map((e, i) => (
            <li key={i}>
              {str(e.from)} → {str(e.to)}
              {e.active ? "" : " (inactive)"}
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IcpEvidenceWorkspace() {
  const q = useQuery({
    queryKey: ["icp", "evidence"],
    queryFn: () => icpApi.evidence(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Evidence unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const evidence = asRecord(asRecord(q.data).evidence);
  const packs = asList(evidence.packs).map(asRecord);
  const integrity = asRecord(evidence.integrity);

  return (
    <div className="space-y-4">
      <IcpNav />
      <IsolationBadges />
      <OpsPanel title="Evidence integrity">
        <p className="text-[12px] text-[var(--fg-muted)]">
          subsystems listed:{" "}
          {str(integrity.all_subsystems_listed)} · unique ids:{" "}
          {str(integrity.unique_subsystem_ids)}
        </p>
      </OpsPanel>
      <OpsPanel title="Evidence center">
        <ul className="space-y-2 text-[12px]">
          {packs.map((p) => (
            <li
              key={str(p.subsystem)}
              className="border border-[var(--border)]/60 px-3 py-2"
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone={p.present ? "success" : "warning"}>
                  {str(p.subsystem).toUpperCase()}
                </Badge>
                <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                  {str(p.evidence_ref)}
                </span>
              </div>
              <p className="mt-1 text-[var(--fg-muted)]">
                {asList(p.summary_keys)
                  .map((k) => str(k))
                  .join(", ") || "no keys"}
              </p>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IcpReportsWorkspace() {
  const q = useQuery({
    queryKey: ["icp", "reports"],
    queryFn: () => icpApi.reports(20),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Reports unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const reports = asList(asRecord(q.data).reports).map(asRecord);

  return (
    <div className="space-y-4">
      <IcpNav />
      <IsolationBadges />
      <OpsPanel title="Executive reports">
        <ul className="space-y-2 text-[12px]">
          {reports.map((r) => (
            <li
              key={str(r.report_id)}
              className="border border-[var(--border)]/60 px-3 py-2"
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone="neutral">{str(r.kind)}</Badge>
                <span className="font-mono text-[11px]">
                  {str(r.report_id)}
                </span>
              </div>
              <p className="mt-1 text-[var(--fg-muted)]">{str(r.title)}</p>
            </li>
          ))}
          {!reports.length ? (
            <li className="text-[var(--fg-muted)]">No reports yet.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

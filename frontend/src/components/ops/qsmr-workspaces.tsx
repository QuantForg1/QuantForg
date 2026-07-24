"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { qsmrApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/quantforg-strategy-marketplace", label: "Registry" },
  { href: "/quantforg-strategy-marketplace/explorer", label: "Explorer" },
  { href: "/quantforg-strategy-marketplace/comparison", label: "Comparison" },
  { href: "/quantforg-strategy-marketplace/evidence", label: "Evidence" },
  { href: "/quantforg-strategy-marketplace/reports", label: "Reports" },
] as const;

export function QsmrNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/quantforg-strategy-marketplace"
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
      <Badge tone="neutral">STRATEGY REGISTRY</Badge>
      <Badge tone="success">READ-ONLY</Badge>
      <Badge tone="warning">NEVER DEPLOYS</Badge>
    </div>
  );
}

export function QsmrRegistryWorkspace() {
  const q = useQuery({
    queryKey: ["qsmr", "dashboard"],
    queryFn: () => qsmrApi.dashboard(),
    refetchInterval: 60_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "QSMR unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const registry = asList(root.registry).map(asRecord);
  const stats = asRecord(root.stats);

  return (
    <div className="space-y-4">
      <QsmrNav />
      <IsolationBadges />
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Centralized registry for every QuantForg strategy. Discovery and
        comparison only — never modifies or deploys strategies.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Strategies" value={str(stats.strategy_count, "0")} />
        <MetricCard label="Active" value={str(stats.active, "0")} />
        <MetricCard label="Research" value={str(stats.research, "0")} />
        <MetricCard label="Retired" value={str(stats.retired, "0")} />
      </div>
      <OpsPanel title="Strategy registry">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12px]">
            <thead className="text-[var(--fg-muted)]">
              <tr className="border-b border-[var(--border)]">
                <th className="py-2 pr-3 font-medium">ID</th>
                <th className="py-2 pr-3 font-medium">Name</th>
                <th className="py-2 pr-3 font-medium">Owner</th>
                <th className="py-2 pr-3 font-medium">Version</th>
                <th className="py-2 pr-3 font-medium">Lifecycle</th>
                <th className="py-2 pr-3 font-medium">Certification</th>
                <th className="py-2 font-medium">Score</th>
              </tr>
            </thead>
            <tbody>
              {registry.map((row) => (
                <tr
                  key={str(row.strategy_id)}
                  className="border-b border-[var(--border)]/50"
                >
                  <td className="py-2 pr-3 font-mono text-[11px]">
                    {str(row.strategy_id)}
                  </td>
                  <td className="py-2 pr-3">{str(row.strategy_name)}</td>
                  <td className="py-2 pr-3">{str(row.owner)}</td>
                  <td className="py-2 pr-3">{str(row.version)}</td>
                  <td className="py-2 pr-3">{str(row.lifecycle)}</td>
                  <td className="py-2 pr-3">
                    {str(row.certification_status)}
                  </td>
                  <td className="py-2">
                    {str(
                      asRecord(row.scores).overall_strategy_score,
                      "—",
                    )}
                  </td>
                </tr>
              ))}
              {!registry.length ? (
                <tr>
                  <td colSpan={7} className="py-4 text-[var(--fg-muted)]">
                    No strategies registered.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </OpsPanel>
    </div>
  );
}

export function QsmrExplorerWorkspace() {
  const [qText, setQText] = useState("");
  const [status, setStatus] = useState("");
  const searchQ = useQuery({
    queryKey: ["qsmr", "search", qText, status],
    queryFn: () =>
      qsmrApi.search({
        q: qText || undefined,
        status: status || undefined,
        sort_by: "overall_strategy_score",
        sort_dir: "desc",
        group_by: "lifecycle",
      }),
  });
  if (searchQ.isLoading) return <DeskSkeleton rows={6} />;
  if (searchQ.isError) {
    return (
      <DeskError
        message={
          searchQ.error instanceof Error
            ? searchQ.error.message
            : "Explorer unavailable"
        }
        onRetry={() => void searchQ.refetch()}
      />
    );
  }
  const root = asRecord(searchQ.data);
  const results = asList(root.results).map(asRecord);
  const groups = asRecord(root.groups);

  return (
    <div className="space-y-4">
      <QsmrNav />
      <IsolationBadges />
      <OpsPanel title="Strategy explorer">
        <div className="mb-3 flex flex-wrap gap-2">
          <input
            className="border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1.5 text-[12px] text-[var(--fg)]"
            placeholder="Search…"
            value={qText}
            onChange={(e) => setQText(e.target.value)}
          />
          <select
            className="border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1.5 text-[12px] text-[var(--fg)]"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="Active">Active</option>
            <option value="Research">Research</option>
            <option value="Retired">Retired</option>
          </select>
        </div>
        <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
          {str(root.count)} results · sort{" "}
          {str(asRecord(root.sort).by)} {str(asRecord(root.sort).dir)}
        </p>
        <ul className="space-y-2 text-[12px]">
          {results.map((r) => (
            <li
              key={str(r.strategy_id)}
              className="flex flex-wrap gap-2 border border-[var(--border)]/60 px-3 py-2"
            >
              <span className="font-mono text-[11px]">
                {str(r.strategy_id)}
              </span>
              <span>{str(r.strategy_name)}</span>
              <Badge tone="neutral">{str(r.lifecycle)}</Badge>
              <span className="text-[var(--fg-muted)]">
                score{" "}
                {str(asRecord(r.scores).overall_strategy_score, "—")}
              </span>
            </li>
          ))}
        </ul>
        {Object.keys(groups).length ? (
          <div className="mt-4">
            <p className="mb-2 text-[11px] uppercase tracking-[0.1em] text-[var(--fg-muted)]">
              Grouped by lifecycle
            </p>
            <ul className="space-y-1 text-[11px] text-[var(--fg-muted)]">
              {Object.entries(groups).map(([k, v]) => (
                <li key={k}>
                  {k}: {asList(v).length}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </OpsPanel>
    </div>
  );
}

export function QsmrComparisonWorkspace() {
  const q = useQuery({
    queryKey: ["qsmr", "compare"],
    queryFn: () => qsmrApi.compare(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Comparison unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const strategies = asList(root.strategies).map(asRecord);

  return (
    <div className="space-y-4">
      <QsmrNav />
      <IsolationBadges />
      <OpsPanel title="Comparison workspace">
        <ul className="space-y-3">
          {strategies.map((s) => {
            const health = asRecord(s.health);
            const cert = asRecord(s.certification);
            return (
              <li
                key={str(s.strategy_id)}
                className="border border-[var(--border)]/60 px-3 py-2 text-[12px]"
              >
                <div className="mb-1 flex flex-wrap gap-2">
                  <Badge tone="neutral">#{str(s.rank)}</Badge>
                  <span className="font-medium">{str(s.strategy_name)}</span>
                  <span className="font-mono text-[11px]">
                    {str(s.strategy_id)}
                  </span>
                </div>
                <div className="flex flex-wrap gap-3 text-[var(--fg-muted)]">
                  <span>
                    overall {str(health.overall_strategy_score, "—")}
                  </span>
                  <span>risk {str(health.risk_score, "—")}</span>
                  <span>validation {str(health.validation_score, "—")}</span>
                  <span>execution {str(health.execution_score, "—")}</span>
                  <span>
                    cert {str(cert.status)} (
                    {str(cert.score, "—")})
                  </span>
                </div>
              </li>
            );
          })}
          {!strategies.length ? (
            <li className="text-[var(--fg-muted)]">Nothing to compare.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function QsmrEvidenceWorkspace() {
  const q = useQuery({
    queryKey: ["qsmr", "evidence"],
    queryFn: () => qsmrApi.evidence(),
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
  const evidence = asRecord(asRecord(q.data).evidence_viewer);

  return (
    <div className="space-y-4">
      <QsmrNav />
      <IsolationBadges />
      <p className="text-[11px] text-[var(--fg-muted)]">
        Strategy: {str(evidence.strategy_id, "—")}
      </p>
      <OpsPanel title="Evidence viewer">
        <pre className="max-h-96 overflow-auto text-[11px] text-[var(--fg-muted)]">
          {JSON.stringify(evidence, null, 2)}
        </pre>
      </OpsPanel>
    </div>
  );
}

export function QsmrReportsWorkspace() {
  const q = useQuery({
    queryKey: ["qsmr", "reports"],
    queryFn: () => qsmrApi.reports(20),
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
      <QsmrNav />
      <IsolationBadges />
      <OpsPanel title="Registry reports">
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

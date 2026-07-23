"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { qkgApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/quant-knowledge-graph", label: "Explorer" },
  { href: "/quant-knowledge-graph/relationships", label: "Relationships" },
  { href: "/quant-knowledge-graph/evidence", label: "Evidence Chains" },
  { href: "/quant-knowledge-graph/root-cause", label: "Root Cause" },
] as const;

export function QkgNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/quant-knowledge-graph"
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

export function QkgExplorerWorkspace() {
  const [q, setQ] = useState("");
  const [nodeType, setNodeType] = useState("");
  const dash = useQuery({
    queryKey: ["qkg", "dashboard"],
    queryFn: () => qkgApi.dashboard(),
    refetchInterval: 120_000,
  });
  const search = useQuery({
    queryKey: ["qkg", "search", q, nodeType],
    queryFn: () => qkgApi.search(q || undefined, nodeType || undefined),
    enabled: true,
  });

  if (dash.isLoading) return <DeskSkeleton rows={8} />;
  if (dash.isError) {
    return (
      <DeskError
        message={
          dash.error instanceof Error ? dash.error.message : "QKG unavailable"
        }
        onRetry={() => void dash.refetch()}
      />
    );
  }

  const root = asRecord(dash.data);
  const stats = asRecord(root.stats);
  const byType = asRecord(stats.by_type);
  const matches = asList(asRecord(search.data).matches).map(asRecord);

  return (
    <div className="space-y-4">
      <QkgNav />
      <div className="flex flex-wrap gap-2">
        <Badge tone="neutral">QUANT KNOWLEDGE GRAPH</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">KNOWLEDGE LAYER</Badge>
      </div>
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Connects trades, signals, regimes, research, recommendations,
        diagnostics, and alerts. Never modifies production. AQS/AQC may query
        via /qkg/ai.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Nodes" value={str(stats.node_count, "—")} />
        <MetricCard label="Edges" value={str(stats.edge_count, "—")} />
        <MetricCard
          label="Sources"
          value={String(Object.keys(asRecord(root.availability)).length || "—")}
        />
        <MetricCard label="Elapsed ms" value={str(root.elapsed_ms, "—")} />
      </div>

      <OpsPanel title="Nodes by type">
        <div className="flex flex-wrap gap-2">
          {Object.entries(byType).map(([k, v]) => (
            <Badge key={k} tone="neutral">
              {k}:{String(v)}
            </Badge>
          ))}
        </div>
      </OpsPanel>

      <OpsPanel title="Knowledge search">
        <div className="mb-3 flex flex-col gap-2 sm:flex-row">
          <input
            aria-label="Search graph"
            className="flex-1 border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px]"
            placeholder="Search nodes…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <input
            aria-label="Node type"
            className="border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px] sm:w-48"
            placeholder="Type filter"
            value={nodeType}
            onChange={(e) => setNodeType(e.target.value)}
          />
          <Button size="sm" variant="secondary" onClick={() => void search.refetch()}>
            Search
          </Button>
        </div>
        <ul className="space-y-2">
          {matches.slice(0, 25).map((n) => (
            <li
              key={str(n.id)}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge tone="neutral">{str(n.type)}</Badge>
              <span className="font-medium">{str(n.label)}</span>
              <span className="text-[var(--fg-muted)]">{str(n.id)}</span>
            </li>
          ))}
          {!matches.length ? (
            <li className="text-[12px] text-[var(--fg-muted)]">No matches.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

function NodeQueryPanel({
  title,
  fetcher,
}: {
  title: string;
  fetcher: (id: string) => Promise<Record<string, unknown>>;
}) {
  const [nodeId, setNodeId] = useState("strategy:production");
  const [active, setActive] = useState("strategy:production");
  const q = useQuery({
    queryKey: ["qkg", title, active],
    queryFn: () => fetcher(active),
    enabled: Boolean(active),
  });

  return (
    <div className="space-y-4">
      <QkgNav />
      <OpsPanel title={title}>
        <div className="mb-3 flex flex-col gap-2 sm:flex-row">
          <input
            aria-label="Node id"
            className="flex-1 border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px]"
            value={nodeId}
            onChange={(e) => setNodeId(e.target.value)}
          />
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setActive(nodeId.trim())}
          >
            Load
          </Button>
        </div>
        {q.isLoading ? <DeskSkeleton rows={4} /> : null}
        {q.isError ? (
          <DeskError
            message={q.error instanceof Error ? q.error.message : "Unavailable"}
            onRetry={() => void q.refetch()}
          />
        ) : null}
        {q.data ? (
          <pre className="max-h-[480px] overflow-auto whitespace-pre-wrap text-[11px] text-[var(--fg-muted)]">
            {JSON.stringify(q.data, null, 2)}
          </pre>
        ) : null}
      </OpsPanel>
    </div>
  );
}

export function QkgRelationshipsWorkspace() {
  return (
    <NodeQueryPanel
      title="Relationship viewer"
      fetcher={(id) => qkgApi.relationships(id)}
    />
  );
}

export function QkgEvidenceWorkspace() {
  return (
    <NodeQueryPanel
      title="Evidence chain viewer"
      fetcher={(id) => qkgApi.evidence(id)}
    />
  );
}

export function QkgRootCauseWorkspace() {
  return (
    <NodeQueryPanel
      title="Root cause explorer"
      fetcher={(id) => qkgApi.rootCause(id)}
    />
  );
}

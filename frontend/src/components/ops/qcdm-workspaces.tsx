"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { qcdmApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/quantforg-canonical-data", label: "Schema Explorer" },
  { href: "/quantforg-canonical-data/models", label: "Model Browser" },
  {
    href: "/quantforg-canonical-data/relationships",
    label: "Relationships",
  },
  { href: "/quantforg-canonical-data/timeline", label: "Version Timeline" },
] as const;

export function QcdmNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/quantforg-canonical-data"
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
      <Badge tone="neutral">CANONICAL DATA MODEL</Badge>
      <Badge tone="success">READ-ONLY</Badge>
      <Badge tone="neutral">ENTERPRISE CONTRACT</Badge>
    </div>
  );
}

export function QcdmSchemaExplorerWorkspace() {
  const q = useQuery({
    queryKey: ["qcdm", "dashboard"],
    queryFn: () => qcdmApi.dashboard(),
    refetchInterval: 120_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "QCDM unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const gov = asRecord(root.governance);
  const consistency = asRecord(root.schema_consistency);
  const compatibility = asRecord(root.compatibility);
  const references = asRecord(root.reference_validation);
  const names = asList(root.model_names).map((n) => str(n));

  return (
    <div className="space-y-4">
      <QcdmNav />
      <IsolationBadges />
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Enterprise-wide data contract. Schema metadata only — never executes
        trades or modifies production.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Version" value={str(root.schema_version, "—")} />
        <MetricCard label="Models" value={str(root.model_count, "—")} />
        <MetricCard
          label="Consistency"
          value={consistency.ok === true ? "OK" : "ISSUES"}
        />
        <MetricCard
          label="Compatible"
          value={compatibility.ok === true ? "OK" : "BREAKING"}
        />
      </div>
      <OpsPanel title="Schema Explorer">
        <div className="flex flex-wrap gap-2">
          {names.map((name) => (
            <Link
              key={name}
              href={`/quantforg-canonical-data/models?model=${encodeURIComponent(name)}`}
              className="border border-[var(--border)] px-2 py-1 font-mono text-[11px] text-[var(--fg)] hover:border-[var(--border-strong)]"
            >
              {name}
            </Link>
          ))}
        </div>
      </OpsPanel>
      <div className="grid gap-3 lg:grid-cols-3">
        <OpsPanel title="Governance">
          <ul className="space-y-1 text-[12px] text-[var(--fg-muted)]">
            <li>
              Compatibility rules:{" "}
              {asList(gov.compatibility_rules).length}
            </li>
            <li>
              Deprecation rules: {asList(gov.deprecation_rules).length}
            </li>
            <li>Migration rules: {asList(gov.migration_rules).length}</li>
          </ul>
        </OpsPanel>
        <OpsPanel title="Validation">
          <ul className="space-y-1 text-[12px] text-[var(--fg-muted)]">
            <li>Schema: {consistency.ok === true ? "pass" : "fail"}</li>
            <li>
              Compatibility: {compatibility.ok === true ? "pass" : "fail"}
            </li>
            <li>
              References: {references.ok === true ? "pass" : "fail"}
            </li>
          </ul>
        </OpsPanel>
        <OpsPanel title="Isolation">
          <p className="text-[12px] text-[var(--fg-muted)]">
            Contract is advisory and read-only. QCDM never migrates production
            stores.
          </p>
        </OpsPanel>
      </div>
    </div>
  );
}

export function QcdmModelBrowserWorkspace() {
  const [selected, setSelected] = useState("Strategy");
  const list = useQuery({
    queryKey: ["qcdm", "models"],
    queryFn: () => qcdmApi.models(),
  });
  const detail = useQuery({
    queryKey: ["qcdm", "model", selected],
    queryFn: () => qcdmApi.model(selected),
    enabled: Boolean(selected),
  });

  if (list.isLoading) return <DeskSkeleton rows={8} />;
  if (list.isError) {
    return (
      <DeskError
        message={
          list.error instanceof Error ? list.error.message : "Models unavailable"
        }
        onRetry={() => void list.refetch()}
      />
    );
  }

  const models = asList(asRecord(list.data).models).map(asRecord);
  const schema = asRecord(detail.data);
  const fields = asList(schema.fields).map(asRecord);
  const rules = asList(schema.validation_rules).map(asRecord);

  return (
    <div className="space-y-4">
      <QcdmNav />
      <IsolationBadges />
      <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
        <OpsPanel title="Models">
          <div className="max-h-[480px] space-y-1 overflow-y-auto">
            {models.map((m) => (
              <button
                key={str(m.model)}
                type="button"
                onClick={() => setSelected(str(m.model))}
                className={cn(
                  "block w-full px-2 py-1.5 text-left font-mono text-[12px]",
                  selected === str(m.model)
                    ? "border border-[var(--border-strong)] bg-[var(--surface-2)]"
                    : "text-[var(--fg-muted)] hover:text-[var(--fg)]",
                )}
              >
                {str(m.model)}
              </button>
            ))}
          </div>
        </OpsPanel>
        <div className="space-y-3">
          <OpsPanel title={`${selected} fields`}>
            {detail.isLoading ? (
              <DeskSkeleton rows={4} />
            ) : (
              <div className="max-h-[320px] overflow-y-auto">
                <table className="w-full text-left text-[11px]">
                  <thead className="text-[var(--fg-muted)]">
                    <tr>
                      <th className="py-1">Name</th>
                      <th>Type</th>
                      <th>Required</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fields.map((f) => (
                      <tr
                        key={str(f.name)}
                        className="border-t border-[var(--border)] font-mono text-[var(--fg)]"
                      >
                        <td className="py-1">{str(f.name)}</td>
                        <td>{str(f.type)}</td>
                        <td>{f.required === true ? "yes" : "no"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </OpsPanel>
          <OpsPanel title="Validation rules">
            <ul className="space-y-1 text-[12px] text-[var(--fg-muted)]">
              {rules.length === 0 ? (
                <li>No rules.</li>
              ) : (
                rules.map((r) => (
                  <li key={str(r.rule)} className="font-mono">
                    {str(r.rule)} · {str(r.field)} · {str(r.assert)}
                  </li>
                ))
              )}
            </ul>
          </OpsPanel>
        </div>
      </div>
    </div>
  );
}

export function QcdmRelationshipWorkspace() {
  const q = useQuery({
    queryKey: ["qcdm", "relationships"],
    queryFn: () => qcdmApi.relationships(),
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Relationships unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const edges = asList(root.edges).map(asRecord);
  const nodes = asList(root.nodes).map(asRecord);

  return (
    <div className="space-y-4">
      <QcdmNav />
      <IsolationBadges />
      <div className="grid gap-3 sm:grid-cols-2">
        <MetricCard label="Nodes" value={str(root.node_count, "—")} />
        <MetricCard label="Edges" value={str(root.edge_count, "—")} />
      </div>
      <OpsPanel title="Relationship Explorer">
        <div className="mb-3 flex flex-wrap gap-1">
          {nodes.map((n) => (
            <span
              key={str(n.id)}
              className="border border-[var(--border)] px-2 py-0.5 font-mono text-[10px] text-[var(--fg-muted)]"
            >
              {str(n.label)}
            </span>
          ))}
        </div>
        <div className="max-h-[480px] space-y-1 overflow-y-auto font-mono text-[11px]">
          {edges.map((e) => (
            <div
              key={str(e.id)}
              className="border-b border-[var(--border)] py-1.5 text-[var(--fg)]"
            >
              {str(e.from)} → {str(e.to)}{" "}
              <span className="text-[var(--fg-muted)]">
                via {str(e.via)} · {str(e.cardinality)}
              </span>
            </div>
          ))}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QcdmTimelineWorkspace() {
  const q = useQuery({
    queryKey: ["qcdm", "timeline"],
    queryFn: () => qcdmApi.timeline(),
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
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
  const root = asRecord(q.data);
  const timeline = asList(root.timeline).map(asRecord);

  return (
    <div className="space-y-4">
      <QcdmNav />
      <IsolationBadges />
      <MetricCard
        label="Current"
        value={str(root.current_version, "—")}
      />
      <OpsPanel title="Version Timeline">
        <ol className="relative max-h-[520px] space-y-3 overflow-y-auto border-l border-[var(--border)] pl-4">
          {timeline.map((v) => (
            <li key={str(v.version)} className="relative">
              <span className="absolute -left-[21px] top-1 h-2 w-2 rounded-full bg-[var(--fg-muted)]" />
              <div className="font-mono text-[12px] text-[var(--fg)]">
                {str(v.version)} · {str(v.status)}
              </div>
              <div className="text-[11px] text-[var(--fg-subtle)]">
                {str(v.timestamp)}
              </div>
              <div className="text-[12px] text-[var(--fg-muted)]">
                {str(v.notes)}
              </div>
              <div className="mt-1 text-[10px] text-[var(--fg-subtle)]">
                models:{" "}
                {asList(v.models_added)
                  .map((m) => str(m))
                  .join(", ")}
              </div>
            </li>
          ))}
        </ol>
      </OpsPanel>
    </div>
  );
}

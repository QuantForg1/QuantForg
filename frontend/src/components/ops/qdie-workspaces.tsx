"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { qdieApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/quantforg-decision-intelligence", label: "Decision Center" },
  {
    href: "/quantforg-decision-intelligence/recommendations",
    label: "Recommendations",
  },
  {
    href: "/quantforg-decision-intelligence/evidence",
    label: "Evidence Graph",
  },
  {
    href: "/quantforg-decision-intelligence/tradeoffs",
    label: "Trade-offs",
  },
  {
    href: "/quantforg-decision-intelligence/executive",
    label: "Executive",
  },
] as const;

export function QdieNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/quantforg-decision-intelligence"
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
      <Badge tone="neutral">DECISION INTELLIGENCE</Badge>
      <Badge tone="success">ADVISORY ONLY</Badge>
      <Badge tone="warning">HUMAN APPROVAL REQUIRED</Badge>
      <Badge tone="neutral">NO AUTO ACTIONS</Badge>
    </div>
  );
}

function priorityTone(
  p: string,
): "danger" | "warning" | "neutral" | "success" {
  if (p === "P0") return "danger";
  if (p === "P1") return "warning";
  if (p === "P2") return "neutral";
  return "success";
}

export function QdieDecisionCenterWorkspace() {
  const q = useQuery({
    queryKey: ["qdie", "dashboard"],
    queryFn: () => qdieApi.dashboard(),
    refetchInterval: 60_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "QDIE unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const scores = asRecord(root.scores);
  const recs = asList(root.recommendations).map(asRecord);

  return (
    <div className="space-y-4">
      <QdieNav />
      <IsolationBadges />
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Explainable institutional recommendations from subsystem evidence —
        never executes, allocates, approves, or modifies production.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Overall"
          value={str(scores.overall_decision_score, "—")}
        />
        <MetricCard label="Confidence" value={str(scores.confidence, "—")} />
        <MetricCard
          label="Evidence"
          value={str(scores.evidence_quality, "—")}
        />
        <MetricCard
          label="Validation"
          value={str(scores.validation_strength, "—")}
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Research"
          value={str(scores.research_quality, "—")}
        />
        <MetricCard
          label="Simulation"
          value={str(scores.simulation_consistency, "—")}
        />
        <MetricCard
          label="Portfolio"
          value={str(scores.portfolio_impact, "—")}
        />
        <MetricCard
          label="Operational"
          value={str(scores.operational_readiness, "—")}
        />
      </div>
      <OpsPanel title="Decision Center">
        <div className="max-h-[360px] space-y-2 overflow-y-auto">
          {recs.slice(0, 8).map((r) => (
            <div
              key={str(r.decision_id)}
              className="border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={priorityTone(str(r.priority))}>
                  {str(r.priority)}
                </Badge>
                <span className="text-[11px] text-[var(--fg-muted)]">
                  {str(r.decision_category)}
                </span>
                <Badge tone="warning">
                  {str(r.human_approval_status, "pending")}
                </Badge>
              </div>
              <div className="mt-1 text-[13px] text-[var(--fg)]">
                {str(r.title)}
              </div>
              <div className="mt-1 font-mono text-[10px] text-[var(--fg-subtle)]">
                conf {str(r.confidence_score)} · evidence{" "}
                {str(r.evidence_score)}
              </div>
            </div>
          ))}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QdieRecommendationsWorkspace() {
  const [focus, setFocus] = useState<string>("");
  const q = useQuery({
    queryKey: ["qdie", "recommendations"],
    queryFn: () => qdieApi.recommendations(),
    refetchInterval: 60_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Recommendations unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const recs = asList(asRecord(q.data).recommendations).map(asRecord);
  const selected =
    recs.find((r) => str(r.decision_id) === focus) || recs[0] || null;
  const exp = asRecord(selected?.explainability);

  return (
    <div className="space-y-4">
      <QdieNav />
      <IsolationBadges />
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <OpsPanel title="Recommendation Explorer">
          <div className="max-h-[480px] space-y-2 overflow-y-auto">
            {recs.map((r) => (
              <button
                key={str(r.decision_id)}
                type="button"
                onClick={() => setFocus(str(r.decision_id))}
                className={cn(
                  "block w-full border px-3 py-2 text-left",
                  focus === str(r.decision_id) ||
                    (!focus && selected && str(selected.decision_id) === str(r.decision_id))
                    ? "border-[var(--border-strong)] bg-[var(--surface-2)]"
                    : "border-[var(--border)] bg-[var(--surface-1)]",
                )}
              >
                <div className="flex gap-2">
                  <Badge tone={priorityTone(str(r.priority))}>
                    {str(r.priority)}
                  </Badge>
                  <span className="text-[11px] text-[var(--fg-muted)]">
                    {str(r.decision_category)}
                  </span>
                </div>
                <div className="mt-1 text-[12px] text-[var(--fg)]">
                  {str(r.title)}
                </div>
              </button>
            ))}
          </div>
        </OpsPanel>
        <OpsPanel title="Explainability">
          {selected ? (
            <div className="space-y-2 text-[12px] text-[var(--fg-muted)]">
              <div>
                <span className="text-[var(--fg-subtle)]">Why · </span>
                {str(exp.why)}
              </div>
              <div>
                <span className="text-[var(--fg-subtle)]">Risk · </span>
                {str(selected.risk_assessment)}
              </div>
              <div>
                <span className="text-[var(--fg-subtle)]">Actions · </span>
                {asList(selected.recommended_next_actions)
                  .map((a) => str(a))
                  .join(" · ")}
              </div>
              <div>
                <span className="text-[var(--fg-subtle)]">Alternatives · </span>
                {asList(exp.alternative_options)
                  .map((a) => str(a))
                  .join(" · ")}
              </div>
              <div>
                <span className="text-[var(--fg-subtle)]">Trade-offs · </span>
                {asList(exp.trade_offs)
                  .map((a) => str(a))
                  .join(" · ")}
              </div>
              <div>
                <span className="text-[var(--fg-subtle)]">Limitations · </span>
                {asList(exp.known_limitations)
                  .map((a) => str(a))
                  .join(" · ")}
              </div>
              <div className="font-mono text-[10px] text-[var(--fg-subtle)]">
                {str(selected.decision_id)} · approval{" "}
                {str(selected.human_approval_status)}
              </div>
            </div>
          ) : (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No recommendations.
            </p>
          )}
        </OpsPanel>
      </div>
    </div>
  );
}

export function QdieEvidenceWorkspace() {
  const q = useQuery({
    queryKey: ["qdie", "evidence"],
    queryFn: () => qdieApi.evidence(),
    refetchInterval: 60_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
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
  const graph = asRecord(asRecord(q.data).evidence_graph);
  const nodes = asList(graph.nodes).map(asRecord);
  const edges = asList(graph.edges).map(asRecord);

  return (
    <div className="space-y-4">
      <QdieNav />
      <IsolationBadges />
      <div className="grid gap-3 sm:grid-cols-2">
        <MetricCard label="Nodes" value={str(graph.node_count, "—")} />
        <MetricCard label="Edges" value={str(graph.edge_count, "—")} />
      </div>
      <OpsPanel title="Evidence Graph">
        <div className="mb-3 flex flex-wrap gap-1">
          {nodes
            .filter((n) => str(n.type) === "source")
            .map((n) => (
              <span
                key={str(n.id)}
                className="border border-[var(--border)] px-2 py-0.5 font-mono text-[10px] text-[var(--fg-muted)]"
              >
                {str(n.id)}
                {n.available === true ? "" : " · offline"}
              </span>
            ))}
        </div>
        <div className="max-h-[420px] space-y-1 overflow-y-auto font-mono text-[11px]">
          {edges.map((e, i) => (
            <div
              key={`${str(e.from)}-${str(e.to)}-${i}`}
              className="border-b border-[var(--border)] py-1.5 text-[var(--fg)]"
            >
              {str(e.from)} —{str(e.relation)}→ {str(e.to)}
            </div>
          ))}
          {edges.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No evidence edges yet.
            </p>
          ) : null}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QdieTradeoffWorkspace() {
  const q = useQuery({
    queryKey: ["qdie", "tradeoffs"],
    queryFn: () => qdieApi.tradeoffs(),
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Trade-offs unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const rows = asList(asRecord(q.data).tradeoffs).map(asRecord);

  return (
    <div className="space-y-4">
      <QdieNav />
      <IsolationBadges />
      <OpsPanel title="Trade-off Viewer">
        <div className="max-h-[520px] space-y-3 overflow-y-auto">
          {rows.map((r) => (
            <div
              key={str(r.decision_id)}
              className="border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2"
            >
              <div className="text-[13px] text-[var(--fg)]">{str(r.title)}</div>
              <div className="mt-1 text-[11px] text-[var(--fg-muted)]">
                {str(r.category)} · confidence {str(r.confidence_level)}
              </div>
              <div className="mt-2 text-[12px] text-[var(--fg-muted)]">
                <span className="text-[var(--fg-subtle)]">Alternatives · </span>
                {asList(r.alternatives)
                  .map((a) => str(a))
                  .join(" · ")}
              </div>
              <div className="mt-1 text-[12px] text-[var(--fg-muted)]">
                <span className="text-[var(--fg-subtle)]">Trade-offs · </span>
                {asList(r.trade_offs)
                  .map((a) => str(a))
                  .join(" · ")}
              </div>
            </div>
          ))}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QdieExecutiveWorkspace() {
  const brief = useQuery({
    queryKey: ["qdie", "brief"],
    queryFn: () => qdieApi.brief(),
  });
  const scores = useQuery({
    queryKey: ["qdie", "scores"],
    queryFn: () => qdieApi.scores(),
  });
  const history = useQuery({
    queryKey: ["qdie", "history"],
    queryFn: () => qdieApi.history(30),
  });

  if (brief.isLoading || scores.isLoading) return <DeskSkeleton rows={8} />;
  if (brief.isError) {
    return (
      <DeskError
        message={
          brief.error instanceof Error ? brief.error.message : "Brief unavailable"
        }
        onRetry={() => void brief.refetch()}
      />
    );
  }

  const exec = asRecord(asRecord(brief.data).executive_decision_brief);
  const sc = asRecord(asRecord(scores.data).scores);
  const hist = asList(asRecord(history.data).history).map(asRecord);

  return (
    <div className="space-y-4">
      <QdieNav />
      <IsolationBadges />
      <OpsPanel title="Executive Decision Dashboard">
        <div className="text-[14px] text-[var(--fg)]">{str(exec.headline)}</div>
        <div className="mt-2 grid gap-3 sm:grid-cols-3">
          <MetricCard
            label="Overall"
            value={str(exec.overall_decision_score ?? sc.overall_decision_score, "—")}
          />
          <MetricCard label="P0" value={str(exec.p0_count, "0")} />
          <MetricCard label="P1" value={str(exec.p1_count, "0")} />
        </div>
        <ul className="mt-3 space-y-1 text-[12px] text-[var(--fg-muted)]">
          {asList(exec.key_messages).map((m, i) => (
            <li key={i}>· {str(m)}</li>
          ))}
        </ul>
      </OpsPanel>
      <OpsPanel title="Decision History">
        <div className="max-h-[320px] space-y-1 overflow-y-auto font-mono text-[11px]">
          {hist.map((h) => (
            <div
              key={`${str(h.decision_id)}-${str(h.created_at)}`}
              className="border-b border-[var(--border)] py-1.5 text-[var(--fg)]"
            >
              {str(h.created_at)} · {str(h.priority)} · {str(h.title)}
            </div>
          ))}
          {hist.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">No history yet.</p>
          ) : null}
        </div>
      </OpsPanel>
    </div>
  );
}

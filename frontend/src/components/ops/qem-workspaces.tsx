"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { qemApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/quantforg-event-mesh", label: "Explorer" },
  { href: "/quantforg-event-mesh/stream", label: "Live Stream" },
  { href: "/quantforg-event-mesh/timeline", label: "Timeline" },
  { href: "/quantforg-event-mesh/correlation", label: "Correlation" },
] as const;

export function QemNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/quantforg-event-mesh"
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
      <Badge tone="neutral">EVENT MESH</Badge>
      <Badge tone="success">READ-ONLY</Badge>
      <Badge tone="neutral">IMMUTABLE</Badge>
      <Badge tone="warning">NO PRODUCTION MUTATION</Badge>
    </div>
  );
}

function severityTone(
  s: string,
): "danger" | "warning" | "neutral" | "success" {
  const v = s.toLowerCase();
  if (v === "critical" || v === "danger" || v === "error") return "danger";
  if (v === "warning" || v === "p1" || v === "p0") return "warning";
  if (v === "info" || v === "success") return "success";
  return "neutral";
}

export function QemExplorerWorkspace() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const dash = useQuery({
    queryKey: ["qem", "dashboard"],
    queryFn: () => qemApi.dashboard(),
    refetchInterval: 45_000,
  });
  const search = useQuery({
    queryKey: ["qem", "search", q, category],
    queryFn: () =>
      qemApi.search({
        q: q || undefined,
        category: category || undefined,
        limit: 80,
      }),
    enabled: Boolean(q || category),
  });

  if (dash.isLoading) return <DeskSkeleton rows={8} />;
  if (dash.isError) {
    return (
      <DeskError
        message={
          dash.error instanceof Error ? dash.error.message : "QEM unavailable"
        }
        onRetry={() => void dash.refetch()}
      />
    );
  }

  const root = asRecord(dash.data);
  const stats = asRecord(root.stats);
  const events = (
    search.data ? asList(asRecord(search.data).results) : asList(root.events)
  ).map(asRecord);

  return (
    <div className="space-y-4">
      <QemNav />
      <IsolationBadges />
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Institutional event backbone. Distributes immutable observations —
        never executes trades or modifies production.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Events" value={str(stats.event_count, "—")} />
        <MetricCard label="Sources" value={str(stats.source_count, "—")} />
        <MetricCard
          label="Subscribers"
          value={str(stats.subscriber_count, "—")}
        />
        <MetricCard
          label="Derived"
          value={str(stats.derived_this_run, "—")}
        />
      </div>
      <OpsPanel title="Search">
        <div className="flex flex-wrap gap-2">
          <input
            className="min-w-[180px] flex-1 border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1.5 text-[12px] text-[var(--fg)]"
            placeholder="Strategy · release · correlation · type"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <input
            className="w-[140px] border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1.5 text-[12px] text-[var(--fg)]"
            placeholder="Category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          />
        </div>
      </OpsPanel>
      <OpsPanel title="Event Explorer">
        <div className="max-h-[420px] space-y-2 overflow-y-auto">
          {events.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No events observed yet.
            </p>
          ) : (
            events.map((ev) => (
              <div
                key={str(ev.id)}
                className="border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[12px] text-[var(--fg)]">
                    {str(ev.event_type)}
                  </span>
                  <Badge tone={severityTone(str(ev.severity))}>
                    {str(ev.severity, "info")}
                  </Badge>
                  <span className="text-[11px] text-[var(--fg-muted)]">
                    {str(ev.producer)} · {str(ev.category)}
                  </span>
                </div>
                <div className="mt-1 font-mono text-[10px] text-[var(--fg-subtle)]">
                  {str(ev.timestamp)} · corr {str(ev.correlation_id, "—")}
                  {ev.strategy_id ? ` · strategy ${str(ev.strategy_id)}` : ""}
                </div>
              </div>
            ))
          )}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QemStreamWorkspace() {
  const q = useQuery({
    queryKey: ["qem", "stream"],
    queryFn: () => qemApi.stream(80),
    refetchInterval: 15_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Stream unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const stream = asList(asRecord(q.data).stream).map(asRecord);
  return (
    <div className="space-y-4">
      <QemNav />
      <IsolationBadges />
      <OpsPanel title="Live Event Stream">
        <div className="max-h-[520px] space-y-1 overflow-y-auto font-mono text-[11px]">
          {stream.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              Stream empty — waiting for subsystem events.
            </p>
          ) : (
            stream.map((ev) => (
              <div
                key={str(ev.id)}
                className="flex flex-wrap gap-x-3 border-b border-[var(--border)] py-1.5 text-[var(--fg)]"
              >
                <span className="text-[var(--fg-subtle)]">
                  {str(ev.timestamp)}
                </span>
                <span>{str(ev.event_type)}</span>
                <span className="text-[var(--fg-muted)]">
                  {str(ev.producer)}
                </span>
                <Badge tone={severityTone(str(ev.severity))}>
                  {str(ev.severity, "info")}
                </Badge>
              </div>
            ))
          )}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QemTimelineWorkspace() {
  const q = useQuery({
    queryKey: ["qem", "timeline"],
    queryFn: () => qemApi.timeline(100),
    refetchInterval: 45_000,
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
  const timeline = asList(asRecord(q.data).timeline).map(asRecord);
  return (
    <div className="space-y-4">
      <QemNav />
      <IsolationBadges />
      <OpsPanel title="Event Timeline">
        <ol className="relative max-h-[520px] space-y-3 overflow-y-auto border-l border-[var(--border)] pl-4">
          {timeline.length === 0 ? (
            <li className="text-[12px] text-[var(--fg-muted)]">
              No chronological history yet.
            </li>
          ) : (
            timeline.map((ev) => (
              <li key={str(ev.id)} className="relative">
                <span className="absolute -left-[21px] top-1 h-2 w-2 rounded-full bg-[var(--fg-muted)]" />
                <div className="text-[11px] text-[var(--fg-subtle)]">
                  {str(ev.timestamp)}
                </div>
                <div className="font-mono text-[12px] text-[var(--fg)]">
                  {str(ev.event_type)}
                </div>
                <div className="text-[11px] text-[var(--fg-muted)]">
                  {str(ev.producer)} · {str(ev.category)}
                  {ev.strategy_id ? ` · ${str(ev.strategy_id)}` : ""}
                  {ev.release_id ? ` · release ${str(ev.release_id)}` : ""}
                </div>
              </li>
            ))
          )}
        </ol>
      </OpsPanel>
    </div>
  );
}

export function QemCorrelationWorkspace() {
  const searchParams = useSearchParams();
  const focus = searchParams.get("id") || "";
  const [correlationId, setCorrelationId] = useState(focus);
  const groups = useQuery({
    queryKey: ["qem", "correlation", "groups"],
    queryFn: () => qemApi.correlation(),
    refetchInterval: 60_000,
  });
  const detail = useQuery({
    queryKey: ["qem", "correlation", correlationId],
    queryFn: () => qemApi.correlation(correlationId),
    enabled: Boolean(correlationId),
  });

  if (groups.isLoading) return <DeskSkeleton rows={8} />;
  if (groups.isError) {
    return (
      <DeskError
        message={
          groups.error instanceof Error
            ? groups.error.message
            : "Correlation unavailable"
        }
        onRetry={() => void groups.refetch()}
      />
    );
  }

  const groupRows = asList(asRecord(groups.data).groups).map(asRecord);
  const detailEvents = asList(asRecord(detail.data).events).map(asRecord);

  return (
    <div className="space-y-4">
      <QemNav />
      <IsolationBadges />
      <OpsPanel title="Correlation Viewer">
        <div className="mb-3 flex flex-wrap gap-2">
          <input
            className="min-w-[220px] flex-1 border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1.5 font-mono text-[12px] text-[var(--fg)]"
            placeholder="Correlation ID"
            value={correlationId}
            onChange={(e) => setCorrelationId(e.target.value)}
          />
        </div>
        {correlationId && detailEvents.length > 0 ? (
          <div className="mb-4 max-h-[280px] space-y-1 overflow-y-auto">
            {detailEvents.map((ev) => (
              <div
                key={str(ev.id)}
                className="border border-[var(--border)] px-2 py-1.5 font-mono text-[11px]"
              >
                {str(ev.timestamp)} · {str(ev.event_type)} ·{" "}
                {str(ev.producer)}
              </div>
            ))}
          </div>
        ) : null}
        <div className="max-h-[360px] space-y-2 overflow-y-auto">
          {groupRows.map((g) => (
            <button
              key={str(g.correlation_id)}
              type="button"
              className="block w-full border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-left hover:border-[var(--border-strong)]"
              onClick={() => setCorrelationId(str(g.correlation_id))}
            >
              <div className="font-mono text-[12px] text-[var(--fg)]">
                {str(g.correlation_id)}
              </div>
              <div className="text-[11px] text-[var(--fg-muted)]">
                {str(g.count)} events ·{" "}
                {asList(g.producers)
                  .map((p) => str(p))
                  .join(", ")}
              </div>
            </button>
          ))}
          {groupRows.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No correlation groups yet.
            </p>
          ) : null}
        </div>
      </OpsPanel>
    </div>
  );
}

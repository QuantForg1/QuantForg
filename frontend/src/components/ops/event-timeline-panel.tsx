"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { executionApi, iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { Activity } from "lucide-react";
import { cn } from "@/lib/utils";

type TimelineEvent = {
  id: string;
  at: string;
  title: string;
  detail: string;
  href?: string;
  tone: "ok" | "warn" | "off" | "neutral";
};

function pickTime(row: Record<string, unknown>): string {
  return str(
    row.at ||
      row.timestamp ||
      row.created_at ||
      row.ts ||
      row.time ||
      row.as_of ||
      "",
  );
}

function classify(row: Record<string, unknown>): TimelineEvent {
  const title = str(
    row.event ||
      row.action ||
      row.type ||
      row.stage ||
      row.message ||
      row.outcome ||
      "Event",
  );
  const detail = str(
    row.detail ||
      row.reason ||
      row.symbol ||
      row.request_id ||
      row.status ||
      "",
  );
  const lower = `${title} ${detail}`.toLowerCase();
  let tone: TimelineEvent["tone"] = "neutral";
  if (/accept|connected|approved|recovered|filled|closed|success|ok/.test(lower)) {
    tone = "ok";
  } else if (/reject|fail|error|timeout|disconnect|kill/.test(lower)) {
    tone = "off";
  } else if (/retry|degraded|warn|pending|risk|scan/.test(lower)) {
    tone = "warn";
  }
  const id = str(row.id || row.request_id || `${pickTime(row)}:${title}`);
  return {
    id,
    at: pickTime(row) || new Date().toISOString(),
    title,
    detail,
    href: row.request_id
      ? `/execution/diagnostics?request_id=${encodeURIComponent(String(row.request_id))}`
      : undefined,
    tone,
  };
}

/** LIVE institutional event timeline from execution journal + ITE audit. */
export function EventTimelinePanel() {
  const [selected, setSelected] = useState<string | null>(null);
  const journalQ = useQuery({
    queryKey: ["execution-journal", "mission-timeline"],
    queryFn: () => executionApi.journal(80),
    staleTime: 12_000,
    refetchInterval: 20_000,
    retry: false,
  });
  const auditQ = useQuery({
    queryKey: ["ite-ops-audit", "mission-timeline"],
    queryFn: () => iteOpsApi.audit(60),
    staleTime: 12_000,
    refetchInterval: 20_000,
    retry: false,
  });

  const events = useMemo(() => {
    const journalRows = asList(
      asRecord(journalQ.data).items ||
        asRecord(journalQ.data).events ||
        asRecord(journalQ.data).journal ||
        journalQ.data,
    ).map(asRecord);
    const auditRows = asList(
      asRecord(auditQ.data).items ||
        asRecord(auditQ.data).events ||
        asRecord(auditQ.data).audit ||
        auditQ.data,
    ).map(asRecord);
    return [...journalRows, ...auditRows]
      .map(classify)
      .filter((e) => e.title && e.title !== "Event")
      .sort((a, b) => Date.parse(b.at) - Date.parse(a.at))
      .slice(0, 80);
  }, [auditQ.data, journalQ.data]);

  if ((journalQ.isLoading || auditQ.isLoading) && events.length === 0) {
    return <DeskSkeleton rows={6} />;
  }
  if (journalQ.isError && auditQ.isError) {
    return (
      <DeskError
        message="Unable to load live event timeline."
        onRetry={() => {
          void journalQ.refetch();
          void auditQ.refetch();
        }}
      />
    );
  }
  if (events.length === 0) {
    return (
      <DeskEmpty
        icon={Activity}
        title="No live events yet"
        description="Execution journal and ITE audit events appear here as the platform runs."
      />
    );
  }

  const active = events.find((e) => e.id === selected) ?? events[0];

  return (
    <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
      <ol className="max-h-[28rem] space-y-0 overflow-y-auto border border-[var(--border)] bg-[var(--surface)]">
        {events.map((e) => (
          <li key={e.id}>
            <button
              type="button"
              onClick={() => setSelected(e.id)}
              className={cn(
                "flex w-full items-start gap-3 border-b border-[var(--border)] px-3 py-2.5 text-left transition-colors",
                active?.id === e.id
                  ? "bg-[var(--accent-soft)]"
                  : "hover:bg-[var(--surface-2)]",
              )}
            >
              <time className="w-20 shrink-0 font-mono text-[10px] text-[var(--fg-subtle)]">
                {e.at.includes("T") ? e.at.slice(11, 19) : e.at.slice(0, 8)}
              </time>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-[12px] font-medium text-[var(--fg)]">
                    {e.title}
                  </span>
                  <Badge
                    tone={
                      e.tone === "ok"
                        ? "success"
                        : e.tone === "off"
                          ? "danger"
                          : e.tone === "warn"
                            ? "warning"
                            : "neutral"
                    }
                    className="h-4 px-1 text-[9px]"
                  >
                    {e.tone}
                  </Badge>
                </div>
                {e.detail ? (
                  <p className="truncate text-[11px] text-[var(--fg-muted)]">{e.detail}</p>
                ) : null}
              </div>
            </button>
          </li>
        ))}
      </ol>
      <aside className="border border-[var(--border)] bg-[var(--surface)] p-4">
        <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Event detail
        </p>
        <h3 className="mt-2 text-sm font-semibold text-[var(--fg)]">{active?.title}</h3>
        <p className="mt-1 font-mono text-[11px] text-[var(--fg-muted)]">{active?.at}</p>
        <p className="mt-3 text-[12px] text-[var(--fg-muted)]">
          {active?.detail || "No additional detail from LIVE feed."}
        </p>
        {active?.href ? (
          <Button asChild size="sm" variant="outline" className="mt-4">
            <Link href={active.href}>Open diagnostics</Link>
          </Button>
        ) : null}
      </aside>
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { executionApi, iteOpsApi } from "@/lib/api/endpoints";
import {
  classifyProtectedFailure,
  protectedFailureCopy,
} from "@/lib/auth/protected-request";
import { mergeTimelineEvents } from "@/lib/ops/mission-timeline";
import { useAuth } from "@/providers/auth-provider";
import { Activity } from "lucide-react";
import { cn } from "@/lib/utils";

/** LIVE institutional event timeline from execution journal + ITE audit. */
export function EventTimelinePanel() {
  const { opsReady, authPhase } = useAuth();
  const [selected, setSelected] = useState<string | null>(null);
  const journalQ = useQuery({
    queryKey: ["execution-journal", "mission-timeline"],
    queryFn: () => executionApi.journal(80),
    enabled: opsReady,
    staleTime: 25_000,
    refetchInterval: opsReady ? 45_000 : false,
    retry: false,
  });
  const auditQ = useQuery({
    queryKey: ["ite-ops-audit", "mission-timeline"],
    queryFn: () => iteOpsApi.audit(60),
    enabled: opsReady,
    staleTime: 25_000,
    refetchInterval: opsReady ? 45_000 : false,
    retry: false,
  });

  const events = useMemo(
    () => mergeTimelineEvents(journalQ.data, auditQ.data),
    [auditQ.data, journalQ.data],
  );

  const journalKind = classifyProtectedFailure({
    authPhase,
    opsReady,
    error: journalQ.error,
  });
  const auditKind = classifyProtectedFailure({
    authPhase,
    opsReady,
    error: auditQ.error,
  });
  const authBlocked =
    journalKind === "AUTH_BOOTSTRAP_PENDING" ||
    journalKind === "AUTH_REQUIRED" ||
    journalKind === "AUTH_EXPIRED" ||
    journalKind === "FORBIDDEN" ||
    auditKind === "AUTH_BOOTSTRAP_PENDING" ||
    auditKind === "AUTH_REQUIRED" ||
    auditKind === "AUTH_EXPIRED" ||
    auditKind === "FORBIDDEN";
  const feedKind =
    journalKind !== "OK"
      ? journalKind
      : auditKind !== "OK"
        ? auditKind
        : "OK";
  const copy = protectedFailureCopy(feedKind === "OK" ? "SERVER_ERROR" : feedKind, "Timeline");

  if (!opsReady && (authPhase === "AUTH_LOADING" || authPhase === "AUTH_TIMEOUT")) {
    return (
      <div className="space-y-2 border border-[var(--border)] bg-[var(--surface)] p-4">
        <p className="text-[12px] text-[var(--fg-muted)]">Authenticating…</p>
        <DeskSkeleton rows={4} />
      </div>
    );
  }

  if ((journalQ.isLoading || auditQ.isLoading) && events.length === 0 && opsReady) {
    return <DeskSkeleton rows={6} />;
  }

  if (authBlocked && events.length === 0) {
    return (
      <div className="space-y-2 border border-[var(--border)] bg-[var(--surface)] p-4">
        <span className="text-[12px] font-medium text-[var(--fg)]">{copy.title}</span>
        <p className="text-[12px] text-[var(--fg-muted)]">{copy.detail}</p>
      </div>
    );
  }

  const bothFailed = journalQ.isError && auditQ.isError;
  const timelineDegraded = journalQ.isError || auditQ.isError;

  if (bothFailed && events.length === 0) {
    const unavailable = protectedFailureCopy(
      feedKind === "OK" ? "SERVER_ERROR" : feedKind,
      "Timeline",
    );
    return (
      <div className="space-y-2 border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="warning" className="h-5 px-1.5 text-[10px]">
            DEGRADED
          </Badge>
          <span className="text-[12px] font-medium text-[var(--fg)]">
            {unavailable.title}
          </span>
        </div>
        <p className="text-[12px] text-[var(--fg-muted)]">{unavailable.detail}</p>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            void journalQ.refetch();
            void auditQ.refetch();
          }}
        >
          Retry timeline
        </Button>
      </div>
    );
  }
  if (events.length === 0) {
    return (
      <div className="space-y-2">
        {timelineDegraded ? (
          <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
            <Badge tone="warning" className="h-5 px-1.5 text-[10px]">
              DEGRADED
            </Badge>
            <span className="text-[11px] text-[var(--fg-muted)]">
              Partial timeline feed error — Gateway/Broker/MT5 status is independent
            </span>
          </div>
        ) : null}
        <DeskEmpty
          icon={Activity}
          title="No events yet"
          description="Execution journal and ITE audit events appear here as the platform runs."
        />
      </div>
    );
  }

  const active = events.find((e) => e.id === selected) ?? events[0];

  return (
    <div className="space-y-2">
      {timelineDegraded ? (
        <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
          <Badge tone="warning" className="h-5 px-1.5 text-[10px]">
            DEGRADED
          </Badge>
          <span className="text-[11px] text-[var(--fg-muted)]">
            {journalQ.isError && auditQ.isError
              ? "Timeline feeds delayed — connectivity cards use trading-components"
              : journalQ.isError
                ? "Execution journal feed degraded"
                : "ITE audit feed degraded"}
          </span>
        </div>
      ) : null}
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
    </div>
  );
}

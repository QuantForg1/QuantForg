"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ListOrdered } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { executionApi, iteOpsApi } from "@/lib/api/endpoints";
import {
  buildExecutionTimelineModel,
  formatDurationMs,
  loadTimelineStore,
  saveTimelineStore,
  type TimelineStatus,
} from "@/lib/execution-timeline";
import { cn } from "@/lib/utils";

function statusTone(
  status: TimelineStatus,
): "success" | "warning" | "danger" | "neutral" | "accent" {
  if (status === "SUCCESS" || status === "PASS") return "success";
  if (status === "BLOCKED") return "warning";
  if (status === "FAILED") return "danger";
  return "neutral";
}

export function ExecutionTimelineWorkspace() {
  const [store, setStore] = useState(() => loadTimelineStore());
  const [filterSession, setFilterSession] = useState("all");
  const [filterDate, setFilterDate] = useState("");
  const [filterSignalId, setFilterSignalId] = useState("");

  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading", "exec-timeline"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 8_000,
  });
  const journalQ = useQuery({
    queryKey: ["execution-journal", "exec-timeline"],
    queryFn: () => executionApi.journal(100),
    retry: false,
    refetchInterval: 12_000,
  });

  const model = useMemo(
    () =>
      buildExecutionTimelineModel({
        autoTrading: autoQ.data,
        journal: journalQ.data,
        store,
        filterSession,
        filterDate,
        filterSignalId,
      }),
    [
      autoQ.data,
      journalQ.data,
      store,
      filterSession,
      filterDate,
      filterSignalId,
    ],
  );

  useEffect(() => {
    if (!autoQ.data) return;
    const next = model.storePatch;
    if (
      next.seenCycleKeys.length === store.seenCycleKeys.length &&
      next.events.length === store.events.length
    ) {
      return;
    }
    saveTimelineStore(next);
    setStore(next);
  }, [autoQ.data, model.storePatch, store.seenCycleKeys.length, store.events.length]);

  if (autoQ.isLoading && !autoQ.data) {
    return <DeskSkeleton rows={6} />;
  }
  if (autoQ.error && !autoQ.data) {
    return (
      <DeskError
        message={
          autoQ.error instanceof Error
            ? autoQ.error.message
            : "Execution Timeline unavailable"
        }
      />
    );
  }

  const rows = model.filtered;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <ListOrdered className="h-4 w-4 text-[var(--fg-subtle)]" />
        <span className="text-[12px] font-medium text-[var(--fg)]">
          Execution Timeline
        </span>
        <Badge tone="neutral">READ-ONLY</Badge>
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {rows.length} events
        </span>
      </div>

      {model.blocker ? (
        <section className="border border-[var(--warning)] bg-[var(--surface)] ring-1 ring-[var(--warning)]/30">
          <header className="border-b border-[var(--border)] px-3 py-2">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Blocking stage
            </h2>
          </header>
          <div className="p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={statusTone(model.blocker.status)}>
                {model.blocker.status}
              </Badge>
              <span className="font-mono text-[14px] text-[var(--fg)]">
                {model.blocker.stage}
              </span>
            </div>
            <p className="mt-2 font-mono text-[13px] text-[var(--warning)]">
              {model.blocker.reason}
            </p>
          </div>
        </section>
      ) : null}

      <section className="border border-[var(--border)] bg-[var(--surface)]">
        <header className="border-b border-[var(--border)] px-3 py-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Filters
          </h2>
        </header>
        <div className="flex flex-wrap gap-3 p-3">
          <label className="flex flex-col gap-1 text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
            Session
            <select
              className="min-w-[10rem] border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 font-mono text-[12px] text-[var(--fg)]"
              value={filterSession}
              onChange={(e) => setFilterSession(e.target.value)}
            >
              <option value="all">All</option>
              {model.sessions.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
            Date (UTC)
            <input
              type="date"
              className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 font-mono text-[12px] text-[var(--fg)]"
              value={filterDate}
              onChange={(e) => setFilterDate(e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
            Signal ID
            <input
              type="text"
              placeholder="filter…"
              className="min-w-[12rem] border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 font-mono text-[12px] text-[var(--fg)]"
              value={filterSignalId}
              onChange={(e) => setFilterSignalId(e.target.value)}
            />
          </label>
          <button
            type="button"
            className="self-end border border-[var(--border)] px-3 py-1.5 text-[11px] uppercase tracking-wide text-[var(--fg-muted)]"
            onClick={() => {
              setFilterSession("all");
              setFilterDate("");
              setFilterSignalId("");
            }}
          >
            Clear
          </button>
        </div>
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)]">
        <header className="border-b border-[var(--border)] px-3 py-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Chronological events
          </h2>
        </header>
        <div className="p-3">
          {rows.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">
              No timeline events yet. Events append when live cycles are observed.
            </p>
          ) : (
            <ul className="space-y-0">
              <li className="mb-1 hidden grid-cols-[9.5rem_6rem_1fr_5.5rem_5.5rem] gap-2 text-[9px] uppercase tracking-[0.1em] text-[var(--fg-subtle)] md:grid">
                <span>UTC</span>
                <span>Δ prev</span>
                <span>Stage</span>
                <span>Session</span>
                <span className="text-right">Status</span>
              </li>
              {[...rows].reverse().map((ev) => (
                <li
                  key={ev.id}
                  className={cn(
                    "grid gap-1 border-b border-[var(--border)]/50 py-2 last:border-0 md:grid-cols-[9.5rem_6rem_1fr_5.5rem_5.5rem] md:items-center md:gap-2",
                    ev.blocking && "bg-[var(--warning)]/5",
                  )}
                >
                  <span className="font-mono text-[11px] text-[var(--fg-subtle)]">
                    {ev.utcTimestamp.replace("T", " ").slice(0, 19)}
                  </span>
                  <span className="font-mono text-[11px] text-[var(--fg-muted)]">
                    {formatDurationMs(ev.durationSincePrevMs)}
                  </span>
                  <div className="min-w-0">
                    <div className="text-[12px] font-medium text-[var(--fg)]">
                      {ev.stage}
                      {ev.blocking ? (
                        <span className="ml-2 text-[10px] uppercase text-[var(--warning)]">
                          blocker
                        </span>
                      ) : null}
                    </div>
                    <div
                      className="truncate font-mono text-[11px] text-[var(--fg-muted)]"
                      title={ev.detail}
                    >
                      {ev.detail}
                      {ev.signalId !== "—" ? ` · sig ${ev.signalId.slice(0, 8)}` : ""}
                    </div>
                  </div>
                  <span className="font-mono text-[11px] text-[var(--fg-muted)]">
                    {ev.session}
                  </span>
                  <div className="md:text-right">
                    <Badge tone={statusTone(ev.status)}>{ev.status}</Badge>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}

"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { executionApi, iteOpsApi } from "@/lib/api/endpoints";
import {
  buildOperationsRunbookModel,
  type RunbookState,
} from "@/lib/operations-runbook";
import { cn } from "@/lib/utils";

function toneFor(state: RunbookState): "success" | "warning" | "danger" | "neutral" | "accent" {
  if (state === "EXECUTED" || state === "READY") return "success";
  if (state === "WAITING" || state === "EXECUTING") return "warning";
  if (state === "BLOCKED" || state === "FAILED") return "danger";
  return "neutral";
}

export function OperationsRunbookWorkspace() {
  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading", "ops-runbook"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 8_000,
  });
  const journalQ = useQuery({
    queryKey: ["execution-journal", "ops-runbook"],
    queryFn: () => executionApi.journal(50),
    retry: false,
    refetchInterval: 12_000,
  });
  const auditsQ = useQuery({
    queryKey: ["execution-audits", "ops-runbook"],
    queryFn: () => executionApi.audits(50),
    retry: false,
    refetchInterval: 20_000,
  });

  const model = useMemo(
    () =>
      buildOperationsRunbookModel({
        autoTrading: autoQ.data,
        journal: journalQ.data,
        audits: auditsQ.data,
      }),
    [autoQ.data, journalQ.data, auditsQ.data],
  );

  if (autoQ.isLoading && !autoQ.data) {
    return <DeskSkeleton rows={6} />;
  }
  if (autoQ.error && !autoQ.data) {
    return (
      <DeskError
        message={
          autoQ.error instanceof Error
            ? autoQ.error.message
            : "Operations Runbook unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <BookOpen className="h-4 w-4 text-[var(--fg-subtle)]" />
        <span className="text-[12px] font-medium text-[var(--fg)]">
          Operations Runbook
        </span>
        <Badge tone="neutral">READ-ONLY</Badge>
        <Badge tone={toneFor(model.activeState)}>{model.activeState}</Badge>
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {model.session} · {model.observedAt.replace("T", " ").slice(0, 19)} UTC
        </span>
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)] ring-1 ring-[var(--border)]">
        <header className="border-b border-[var(--border)] px-3 py-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Active state
          </h2>
        </header>
        <div className="space-y-3 p-3">
          <p className="font-mono text-[20px] text-[var(--fg)]">
            {model.active.state}
          </p>
          <div>
            <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Current condition
            </p>
            <p className="mt-1 text-[13px] text-[var(--fg)]">
              {model.active.currentCondition}
            </p>
          </div>
          {model.active.blockingReason ? (
            <div>
              <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Blocking reason
              </p>
              <p className="mt-1 font-mono text-[13px] text-[var(--warning)]">
                {model.active.blockingReason}
              </p>
            </div>
          ) : null}
          <div>
            <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Evidence
            </p>
            <ul className="mt-1 space-y-0.5">
              {model.active.evidence.map((e) => (
                <li key={e} className="font-mono text-[12px] text-[var(--fg)]">
                  {e}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Recommended operator action
            </p>
            <p className="mt-1 text-[13px] text-[var(--fg-muted)]">
              {model.active.operatorAction}
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
        {model.entries.map((entry) => {
          const active = entry.state === model.activeState;
          return (
            <section
              key={entry.state}
              className={cn(
                "border bg-[var(--surface)]",
                active
                  ? "border-[var(--fg-subtle)] ring-1 ring-[var(--fg-subtle)]/40"
                  : "border-[var(--border)]",
              )}
            >
              <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
                <h2 className="font-mono text-[13px] font-semibold text-[var(--fg)]">
                  {entry.state}
                </h2>
                {active ? <Badge tone="accent">NOW</Badge> : null}
              </header>
              <div className="space-y-2 p-3 text-[12px]">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                    Condition
                  </p>
                  <p className="mt-0.5 text-[var(--fg-muted)]">
                    {entry.currentCondition}
                  </p>
                </div>
                {entry.blockingReason ? (
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                      Blocking reason
                    </p>
                    <p className="mt-0.5 font-mono text-[var(--warning)]">
                      {entry.blockingReason}
                    </p>
                  </div>
                ) : null}
                <div>
                  <p className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                    Evidence
                  </p>
                  <ul className="mt-0.5 space-y-0.5 font-mono text-[11px] text-[var(--fg)]">
                    {entry.evidence.map((e) => (
                      <li key={e}>{e}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                    Operator action
                  </p>
                  <p className="mt-0.5 text-[var(--fg-muted)]">
                    {entry.operatorAction}
                  </p>
                </div>
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

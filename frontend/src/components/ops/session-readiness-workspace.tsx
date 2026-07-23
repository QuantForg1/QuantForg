"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarClock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteOpsApi } from "@/lib/api/endpoints";
import {
  buildSessionReadinessModel,
  loadSessionReadinessStore,
  pct,
  saveSessionReadinessStore,
} from "@/lib/session-readiness";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
  action,
  highlight,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <section
      className={cn(
        "border bg-[var(--surface)]",
        highlight
          ? "border-[var(--success)] ring-1 ring-[var(--success)]/40"
          : "border-[var(--border)]",
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[var(--border)]/70 bg-[var(--bg)] px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg text-[var(--fg)]">{value}</div>
    </div>
  );
}

export function SessionReadinessWorkspace() {
  const [store, setStore] = useState(() => loadSessionReadinessStore());
  const [nowTick, setNowTick] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNowTick(Date.now()), 1_000);
    return () => window.clearInterval(id);
  }, []);

  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading", "session-readiness"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 8_000,
  });

  const model = useMemo(
    () =>
      buildSessionReadinessModel({
        autoTrading: autoQ.data,
        store,
        now: new Date(nowTick),
      }),
    [autoQ.data, store, nowTick],
  );

  useEffect(() => {
    if (!autoQ.data) return;
    const next = model.storePatch;
    const prevKey = JSON.stringify(store);
    const nextKey = JSON.stringify(next);
    if (prevKey === nextKey) return;
    saveSessionReadinessStore(next);
    setStore(next);
  }, [autoQ.data, model.storePatch, store]);

  if (autoQ.isLoading && !autoQ.data) {
    return <DeskSkeleton rows={5} />;
  }
  if (autoQ.error && !autoQ.data) {
    return (
      <DeskError
        message={
          autoQ.error instanceof Error
            ? autoQ.error.message
            : "Session Readiness unavailable (OWNER/ADMIN · /ite/ops/auto-trading)."
        }
      />
    );
  }

  const allowed = model.sessionStatus === "Allowed";
  const m = model.metrics;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <CalendarClock className="h-4 w-4 text-[var(--fg-subtle)]" />
        <span className="text-[12px] font-medium text-[var(--fg)]">
          Session Readiness
        </span>
        <Badge tone="neutral">READ-ONLY</Badge>
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {model.observedAt.replace("T", " ").slice(0, 19)} UTC
        </span>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Current Session">
          <p className="font-mono text-[20px] text-[var(--fg)]">
            {model.currentSession}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Session Status
            </span>
            <Badge tone={allowed ? "success" : "warning"}>
              {model.sessionStatus}
            </Badge>
          </div>
          {!allowed && model.blockReason ? (
            <div className="mt-3 border border-[var(--border)] bg-[var(--bg)]/40 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Block reason
              </p>
              <p className="mt-1 font-mono text-[14px] text-[var(--warning)]">
                {model.blockReason}
              </p>
            </div>
          ) : null}
        </Panel>

        <Panel title="Next Allowed Session">
          <p className="font-mono text-[20px] text-[var(--fg)]">
            {model.nextAllowedSession}
          </p>
          <p className="mt-2 text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Estimated time
          </p>
          <p className="font-mono text-[16px] text-[var(--fg-muted)]">
            {model.etaLabel}
          </p>
        </Panel>
      </div>

      <Panel
        title="Execution Window"
        highlight={model.executionWindowOpen}
        action={
          model.executionWindowOpen ? (
            <Badge tone="success">OPEN</Badge>
          ) : (
            <Badge tone="neutral">CLOSED</Badge>
          )
        }
      >
        {model.executionWindowOpen ? (
          <div className="space-y-3">
            <p className="font-mono text-[18px] tracking-wide text-[var(--success)]">
              Execution Window Open
            </p>
            {model.windowOpenedAt ? (
              <p className="font-mono text-[11px] text-[var(--fg-subtle)]">
                Opened {model.windowOpenedAt.replace("T", " ").slice(0, 19)} UTC
              </p>
            ) : null}
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <Metric label="Signals generated" value={String(m.signalsGenerated)} />
              <Metric label="Decisions" value={String(m.decisions)} />
              <Metric
                label="Risk pass rate"
                value={pct(m.riskPass, m.riskTotal)}
              />
              <Metric
                label="Safety pass rate"
                value={pct(m.safetyPass, m.safetyTotal)}
              />
              <Metric label="OMS forwards" value={String(m.omsForwards)} />
              <Metric label="MT5 tickets" value={String(m.mt5Tickets)} />
            </div>
            <p className="text-[11px] text-[var(--fg-muted)]">
              Metrics accumulate from observed live cycles while this allowed
              session is open. Observation only — never places or modifies trades.
            </p>
          </div>
        ) : (
          <p className="text-sm text-[var(--fg-muted)]">
            Execution window closed. Counters start automatically when the
            session becomes Allowed.
          </p>
        )}
      </Panel>
    </div>
  );
}

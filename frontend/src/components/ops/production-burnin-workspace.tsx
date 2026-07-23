"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Flame } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import {
  executionApi,
  iteOpsApi,
  iteReliabilityApi,
  mt5Api,
} from "@/lib/api/endpoints";
import {
  buildBurnInModel,
  loadBurnInStore,
  saveBurnInStore,
} from "@/lib/production-burnin";
import { saveFirstExecutionEvidence } from "@/lib/first-execution-evidence";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
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

export function ProductionBurnInWorkspace() {
  const [store, setStore] = useState(() => loadBurnInStore());
  const [nowTick, setNowTick] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNowTick(Date.now()), 1_000);
    return () => window.clearInterval(id);
  }, []);

  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading", "burnin"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 8_000,
  });
  const mt5Q = useQuery({
    queryKey: ["mt5-status", "burnin"],
    queryFn: mt5Api.status,
    retry: false,
    refetchInterval: 12_000,
  });
  const relQ = useQuery({
    queryKey: ["ite-rel-dash", "burnin"],
    queryFn: iteReliabilityApi.dashboard,
    retry: false,
    refetchInterval: 20_000,
  });
  const witnessQ = useQuery({
    queryKey: ["ite-ops-witness-health", "burnin"],
    queryFn: iteOpsApi.witnessHealth,
    retry: false,
    refetchInterval: 15_000,
  });
  const journalQ = useQuery({
    queryKey: ["execution-journal", "burnin"],
    queryFn: () => executionApi.journal(100),
    retry: false,
    refetchInterval: 12_000,
  });
  const auditsQ = useQuery({
    queryKey: ["execution-audits", "burnin"],
    queryFn: () => executionApi.audits(100),
    retry: false,
    refetchInterval: 20_000,
  });

  const model = useMemo(
    () =>
      buildBurnInModel({
        autoTrading: autoQ.data,
        mt5Status: mt5Q.data,
        reliabilityDash: relQ.data,
        witnessHealth: witnessQ.data,
        journal: journalQ.data,
        audits: auditsQ.data,
        store,
        now: new Date(nowTick),
      }),
    [
      autoQ.data,
      mt5Q.data,
      relQ.data,
      witnessQ.data,
      journalQ.data,
      auditsQ.data,
      store,
      nowTick,
    ],
  );

  useEffect(() => {
    if (!autoQ.data) return;
    const next = model.storePatch;
    const prev = JSON.stringify({
      c: store.counters,
      r: store.rejectionCounts,
      s: store.seenCycleKeys.length,
      g: store.gatewayUpHits,
    });
    const nxt = JSON.stringify({
      c: next.counters,
      r: next.rejectionCounts,
      s: next.seenCycleKeys.length,
      g: next.gatewayUpHits,
    });
    if (prev !== nxt) {
      saveBurnInStore(next);
      setStore(next);
    }
    if (model.evidenceStorePatch.record) {
      saveFirstExecutionEvidence(model.evidenceStorePatch);
    }
  }, [autoQ.data, model.storePatch, model.evidenceStorePatch, store]);

  if (autoQ.isLoading && !autoQ.data) {
    return <DeskSkeleton rows={8} />;
  }
  if (autoQ.error && !autoQ.data) {
    return (
      <DeskError
        message={
          autoQ.error instanceof Error
            ? autoQ.error.message
            : "Production Burn-in Monitor unavailable"
        }
      />
    );
  }

  const statusTone =
    model.status === "STABLE"
      ? "success"
      : model.status === "INVESTIGATION REQUIRED"
        ? "danger"
        : "warning";
  const c = model.counters;
  const fe = model.firstExecution;
  const u = model.uptime;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <Flame className="h-4 w-4 text-[var(--fg-subtle)]" />
        <span className="text-[12px] font-medium text-[var(--fg)]">
          Production Burn-in Monitor
        </span>
        <Badge tone="neutral">READ-ONLY</Badge>
        <Badge tone="neutral">
          {model.opsMode} · {model.runState}
        </Badge>
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {model.observedAt.replace("T", " ").slice(0, 19)} UTC
        </span>
      </div>

      <Panel title="Burn-in Status">
        <p
          className={cn(
            "font-mono text-[22px] tracking-wide",
            model.status === "STABLE"
              ? "text-[var(--success)]"
              : model.status === "INVESTIGATION REQUIRED"
                ? "text-[var(--fg)]"
                : "text-[var(--warning)]",
          )}
        >
          {model.statusEmoji} {model.status}
        </p>
        <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
          Derived only from observed evidence. No manual override.
        </p>
        <Badge tone={statusTone} className="mt-2">
          {model.status}
        </Badge>
      </Panel>

      <Panel title="System Uptime">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Process uptime" value={u.processUptimeLabel} />
          <Metric
            label="Gateway uptime"
            value={
              u.gatewayUptimePct != null
                ? `${u.gatewayUptimePct.toFixed(1)}%`
                : u.gatewayUp
                  ? "UP"
                  : "—"
            }
          />
          <Metric label="Broker uptime" value={u.brokerUptimeLabel} />
          <Metric label="Witness uptime" value={u.witnessUptimeLabel} />
        </div>
      </Panel>

      <Panel title="Live Cycles">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          <Metric label="Snapshots" value={String(c.snapshots)} />
          <Metric label="Signals" value={String(c.signals)} />
          <Metric label="Decisions" value={String(c.decisions)} />
          <Metric label="Risk evaluations" value={String(c.riskEvaluations)} />
          <Metric label="Safety evaluations" value={String(c.safetyEvaluations)} />
          <Metric label="Session blocks" value={String(c.sessionBlocks)} />
          <Metric label="OMS forwards" value={String(c.omsForwards)} />
          <Metric label="MT5 executions" value={String(c.mt5Executions)} />
        </div>
      </Panel>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Blocker Analysis">
          {model.blockers.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">
              No rejection reasons recorded yet.
            </p>
          ) : (
            <ol className="space-y-2">
              {model.blockers.map((b, i) => (
                <li
                  key={b.reason}
                  className="border-b border-[var(--border)]/50 pb-2 last:border-0"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-mono text-[12px] text-[var(--fg-subtle)]">
                      {i + 1}.
                    </span>
                    <span className="flex-1 font-mono text-[13px] text-[var(--fg)]">
                      {b.reason}
                    </span>
                    <span className="font-mono text-[13px] text-[var(--warning)]">
                      ({b.pct}%)
                    </span>
                  </div>
                  <div className="mt-1 text-[10px] text-[var(--fg-muted)]">
                    n={b.count}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Panel>

        <Panel
          title="First Execution Watch"
          action={
            fe?.locked ? (
              <Badge tone="success">FROZEN</Badge>
            ) : (
              <Badge tone="neutral">PENDING</Badge>
            )
          }
        >
          {!fe ? (
            <p className="text-sm text-[var(--fg-muted)]">
              Waiting for first real live execution. Record freezes permanently
              when OMS + broker accept + MT5 ticket + Deal ID are observed.
            </p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2">
              {(
                [
                  ["UTC timestamp", fe.utcTimestamp],
                  ["Session", fe.session],
                  ["Signal ID", fe.signalId],
                  ["Quality", fe.quality],
                  ["Confluence", fe.confluence],
                  ["OMS Request", fe.omsRequest],
                  ["Broker Response", fe.brokerResponse],
                  ["MT5 Ticket", fe.mt5Ticket],
                  ["Deal ID", fe.dealId],
                  ["Latency", fe.latency],
                ] as const
              ).map(([label, value]) => (
                <div
                  key={label}
                  className="border border-[var(--border)] bg-[var(--bg)]/35 px-2.5 py-2"
                >
                  <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                    {label}
                  </div>
                  <div className="mt-0.5 truncate font-mono text-[12px] text-[var(--fg)]">
                    {value}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

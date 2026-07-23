"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Timer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { executionApi, iteOpsApi, mt5Api } from "@/lib/api/endpoints";
import {
  buildAcceptanceCountdownModel,
  loadAcceptanceStore,
  saveAcceptanceStore,
  type EvidenceItem,
  type ProductionStateRow,
} from "@/lib/production-acceptance-countdown";
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

function StateRow({ row }: { row: ProductionStateRow }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[var(--border)]/50 py-1.5 last:border-0">
      <span className="text-[12px] text-[var(--fg)]">{row.label}</span>
      <div className="flex items-center gap-2">
        <span className="font-mono text-[11px] text-[var(--fg-muted)]">
          {row.value}
        </span>
        <Badge tone={row.ok ? "success" : "warning"}>
          {row.ok ? "OK" : "WATCH"}
        </Badge>
      </div>
    </div>
  );
}

function EvidenceRow({ item }: { item: EvidenceItem }) {
  return (
    <div className="grid grid-cols-[1fr_auto_auto] items-center gap-3 border-b border-[var(--border)]/50 py-1.5 last:border-0">
      <span className="text-[12px] text-[var(--fg)]">{item.label}</span>
      <span
        className={cn(
          "font-mono text-[12px]",
          item.done ? "text-[var(--success)]" : "text-[var(--fg-muted)]",
        )}
        aria-hidden
      >
        {item.mark}
      </span>
      <span className="min-w-[4.5rem] text-right font-mono text-[11px] text-[var(--fg-muted)]">
        {item.done ? "OK" : "Waiting"}
      </span>
    </div>
  );
}

export function ProductionAcceptanceCountdownWorkspace() {
  const [store, setStore] = useState(() => loadAcceptanceStore());
  const [nowTick, setNowTick] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNowTick(Date.now()), 1_000);
    return () => window.clearInterval(id);
  }, []);

  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading", "pac"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 8_000,
  });
  const centerQ = useQuery({
    queryKey: ["ite-ops-center", "pac"],
    queryFn: iteOpsApi.controlCenter,
    retry: false,
    refetchInterval: 12_000,
  });
  const mt5Q = useQuery({
    queryKey: ["mt5-status", "pac"],
    queryFn: mt5Api.status,
    retry: false,
    refetchInterval: 10_000,
  });
  const journalQ = useQuery({
    queryKey: ["execution-journal", "pac"],
    queryFn: () => executionApi.journal(100),
    retry: false,
    refetchInterval: 10_000,
  });
  const auditsQ = useQuery({
    queryKey: ["execution-audits", "pac"],
    queryFn: () => executionApi.audits(100),
    retry: false,
    refetchInterval: 15_000,
  });

  const model = useMemo(
    () =>
      buildAcceptanceCountdownModel({
        autoTrading: autoQ.data,
        controlCenter: centerQ.data,
        mt5Status: mt5Q.data,
        journal: journalQ.data,
        audits: auditsQ.data,
        store,
        now: new Date(nowTick),
      }),
    [
      autoQ.data,
      centerQ.data,
      mt5Q.data,
      journalQ.data,
      auditsQ.data,
      store,
      nowTick,
    ],
  );

  useEffect(() => {
    if (!autoQ.data) return;
    const next = model.storePatch;
    const prevKey = JSON.stringify({
      t: store.firstExecution?.mt5Ticket,
      h: store.history,
    });
    const nextKey = JSON.stringify({
      t: next.firstExecution?.mt5Ticket,
      h: next.history,
    });
    if (prevKey === nextKey) return;
    saveAcceptanceStore(next);
    setStore(next);
  }, [autoQ.data, model.storePatch, store.firstExecution?.mt5Ticket, store.history]);

  if (autoQ.isLoading && !autoQ.data) {
    return <DeskSkeleton rows={8} />;
  }
  if (autoQ.error && !autoQ.data) {
    return (
      <DeskError
        message={
          autoQ.error instanceof Error
            ? autoQ.error.message
            : "Production Acceptance Countdown unavailable"
        }
      />
    );
  }

  const accepted = model.status === "PRODUCTION ACCEPTED";
  const trade = model.firstTrade;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <Timer className="h-4 w-4 text-[var(--fg-subtle)]" />
        <span className="text-[12px] font-medium text-[var(--fg)]">
          Production Acceptance Countdown
        </span>
        <Badge tone="neutral">READ-ONLY</Badge>
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {model.observedAt.replace("T", " ").slice(0, 19)} UTC
        </span>
      </div>

      <Panel title="Overall Status">
        <p
          className={cn(
            "font-mono text-[22px] tracking-wide",
            accepted ? "text-[var(--success)]" : "text-[var(--warning)]",
          )}
        >
          {model.statusEmoji} {model.status}
        </p>
        <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
          Status flips to accepted only when a real MT5 ticket is observed. No
          manual override.
        </p>
      </Panel>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel title="Current Production State">
          {model.productionState.map((row) => (
            <StateRow key={row.label} row={row} />
          ))}
        </Panel>

        <Panel title="Current Blocker">
          <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Active blocker
          </p>
          <p
            className={cn(
              "mt-2 font-mono text-[16px]",
              model.blocker === "Ready for execution"
                ? "text-[var(--success)]"
                : "text-[var(--warning)]",
            )}
          >
            {model.blocker}
          </p>
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel title="Execution Evidence Checklist">
          {model.evidence.map((item) => (
            <EvidenceRow key={item.label} item={item} />
          ))}
        </Panel>

        <Panel title="Next Expected Opportunity">
          <div className="space-y-3">
            <div>
              <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Current Session
              </p>
              <p className="font-mono text-[15px] text-[var(--fg)]">
                {model.opportunity.currentSession}
              </p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Next Allowed Session
              </p>
              <p className="font-mono text-[15px] text-[var(--fg)]">
                {model.opportunity.nextAllowedSession}
              </p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Estimated Time Until Next Allowed Session
              </p>
              <p className="font-mono text-[20px] text-[var(--fg)]">
                {model.opportunity.etaLabel}
              </p>
            </div>
          </div>
        </Panel>
      </div>

      <Panel
        title="First Successful Trade"
        action={
          trade ? (
            <Badge tone="success">CAPTURED</Badge>
          ) : (
            <Badge tone="neutral">PENDING</Badge>
          )
        }
      >
        {trade ? (
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {(
              [
                ["UTC Timestamp", trade.utcTime],
                ["Signal ID", trade.signalId],
                ["Quality", trade.quality],
                ["Confluence", trade.confluence],
                ["Decision ID", trade.decisionId],
                ["Risk Result", trade.riskResult],
                ["Safety Result", trade.safetyResult],
                ["OMS Request ID", trade.omsRequest],
                ["Broker Request ID", trade.brokerRequestId],
                ["Broker Response", trade.brokerResponse],
                ["MT5 Ticket", trade.mt5Ticket],
                ["Deal ID", trade.dealId],
                ["Entry Price", trade.entryPrice],
                ["Stop Loss", trade.stopLoss],
                ["Take Profit", trade.takeProfit],
                ["Execution Latency", trade.latency],
                ["Journal ID", trade.journalId],
                ["Audit ID", trade.auditId],
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
        ) : (
          <p className="text-sm text-[var(--fg-muted)]">
            Waiting for first eligible live execution. Evidence saves
            automatically when an MT5 ticket is confirmed.
          </p>
        )}
      </Panel>
    </div>
  );
}

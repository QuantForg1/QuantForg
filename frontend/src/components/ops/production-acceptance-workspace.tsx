"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { executionApi, iteOpsApi, mt5Api } from "@/lib/api/endpoints";
import {
  buildProductionAcceptanceModel,
  loadAcceptanceStore,
  saveAcceptanceStore,
  type PassFail,
  type PipelineStage,
  type StageState,
} from "@/lib/production-acceptance";
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

function StatusRow({ item }: { item: PassFail }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[var(--border)]/50 py-2 last:border-0">
      <span className="text-[12px] text-[var(--fg)]">{item.label}</span>
      <div className="flex items-center gap-2">
        <span className="max-w-[12rem] truncate font-mono text-[11px] text-[var(--fg-muted)]">
          {item.detail}
        </span>
        <Badge tone={item.passed ? "success" : "danger"}>
          {item.passed ? "PASS" : "FAIL"}
        </Badge>
      </div>
    </div>
  );
}

function stageTone(state: StageState): "success" | "warning" | "danger" | "neutral" | "accent" {
  if (state === "PASS") return "success";
  if (state === "WAITING") return "neutral";
  if (state === "BLOCKED") return "warning";
  return "danger";
}

function PipelineRow({ stage }: { stage: PipelineStage }) {
  return (
    <li className="grid grid-cols-[7rem_1fr_auto] items-center gap-3 border-b border-[var(--border)]/50 py-2 last:border-0">
      <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--fg)]">
        {stage.label}
      </span>
      <div className="min-w-0">
        <p className="truncate font-mono text-[11px] text-[var(--fg-muted)]" title={stage.detail}>
          {stage.detail}
        </p>
        <p className="font-mono text-[10px] text-[var(--fg-subtle)]">
          {stage.at.replace("T", " ").slice(0, 19)} UTC
        </p>
      </div>
      <Badge tone={stageTone(stage.state)}>{stage.state}</Badge>
    </li>
  );
}

export function ProductionAcceptanceWorkspace() {
  const [store, setStore] = useState(() => loadAcceptanceStore());

  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading", "pa"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 8_000,
  });
  const centerQ = useQuery({
    queryKey: ["ite-ops-center", "pa"],
    queryFn: iteOpsApi.controlCenter,
    retry: false,
    refetchInterval: 12_000,
  });
  const mt5Q = useQuery({
    queryKey: ["mt5-status", "pa"],
    queryFn: mt5Api.status,
    retry: false,
    refetchInterval: 10_000,
  });
  const journalQ = useQuery({
    queryKey: ["execution-journal", "pa"],
    queryFn: () => executionApi.journal(100),
    retry: false,
    refetchInterval: 10_000,
  });
  const auditsQ = useQuery({
    queryKey: ["execution-audits", "pa"],
    queryFn: () => executionApi.audits(100),
    retry: false,
    refetchInterval: 15_000,
  });

  const model = useMemo(
    () =>
      buildProductionAcceptanceModel({
        autoTrading: autoQ.data,
        controlCenter: centerQ.data,
        mt5Status: mt5Q.data,
        journal: journalQ.data,
        audits: auditsQ.data,
        store,
      }),
    [autoQ.data, centerQ.data, mt5Q.data, journalQ.data, auditsQ.data, store],
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
            : "Production Acceptance unavailable"
        }
      />
    );
  }

  const accepted = model.certification === "PRODUCTION ACCEPTED";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <BadgeCheck className="h-4 w-4 text-[var(--fg-subtle)]" />
        <span className="text-[12px] font-medium text-[var(--fg)]">
          Production Acceptance
        </span>
        <Badge tone={accepted ? "success" : "warning"}>{model.certification}</Badge>
        <Badge tone="neutral">READ-ONLY</Badge>
        <span className="ml-auto text-[11px] text-[var(--fg-subtle)]">
          Observes live evidence · never mutates trading engines
        </span>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel title="System Status">
          {model.system.map((item) => (
            <StatusRow key={item.label} item={item} />
          ))}
        </Panel>

        <Panel title="Execution Readiness">
          <ol>
            {model.pipeline.map((stage) => (
              <PipelineRow key={stage.id} stage={stage} />
            ))}
          </ol>
        </Panel>
      </div>

      <Panel title="Current Rejection">
        {model.rejection ? (
          <div className="space-y-2">
            <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Current Status
            </p>
            <p className="font-mono text-[18px] text-[var(--fg)]">{model.rejection.status}</p>
            <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Reason
            </p>
            <p className="font-mono text-[14px] text-[var(--warning)]">
              {model.rejection.reason}
            </p>
          </div>
        ) : (
          <p className="text-sm text-[var(--fg-muted)]">
            No active rejection — awaiting next cycle or fill evidence.
          </p>
        )}
      </Panel>

      <Panel
        title="First Execution Evidence"
        action={
          model.firstExecution ? (
            <Badge tone="success">CAPTURED</Badge>
          ) : (
            <Badge tone="neutral">PENDING</Badge>
          )
        }
      >
        {model.firstExecution ? (
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {(
              [
                ["Signal ID", model.firstExecution.signalId],
                ["UTC Time", model.firstExecution.utcTime],
                ["Session", model.firstExecution.session],
                ["Quality", model.firstExecution.quality],
                ["Confluence", model.firstExecution.confluence],
                ["Risk Result", model.firstExecution.riskResult],
                ["Safety Result", model.firstExecution.safetyResult],
                ["OMS Request", model.firstExecution.omsRequest],
                ["Broker Response", model.firstExecution.brokerResponse],
                ["MT5 Ticket", model.firstExecution.mt5Ticket],
                ["Deal ID", model.firstExecution.dealId],
                ["Entry Price", model.firstExecution.entryPrice],
                ["SL", model.firstExecution.stopLoss],
                ["TP", model.firstExecution.takeProfit],
                ["Latency", model.firstExecution.latency],
                ["Journal ID", model.firstExecution.journalId],
                ["Audit ID", model.firstExecution.auditId],
              ] as const
            ).map(([label, value]) => (
              <div
                key={label}
                className="border border-[var(--border)] bg-[var(--bg)]/35 px-2.5 py-2"
              >
                <p className="text-[9px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  {label}
                </p>
                <p className="mt-1 truncate font-mono text-[12px] text-[var(--fg)]" title={value}>
                  {value}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[var(--fg-muted)]">
            No fill observed yet. The first real MT5 ticket will be captured permanently in this
            browser store (and shown here). Never fabricated.
          </p>
        )}
      </Panel>

      <Panel
        title="Production Certification"
        action={
          <Badge tone={accepted ? "success" : "warning"}>{model.certification}</Badge>
        }
      >
        <div className="mb-3 border border-[var(--border)] bg-[var(--bg)]/40 px-3 py-3">
          <p
            className={cn(
              "font-mono text-[20px] tracking-tight",
              accepted ? "text-[var(--success)]" : "text-[var(--warning)]",
            )}
          >
            {model.certification}
          </p>
          <p className="mt-1 text-[12px] text-[var(--fg-muted)]">
            Based solely on observed evidence
            {accepted
              ? " — first MT5 fill captured."
              : " — awaiting first legitimate production fill."}
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {model.certItems.map((item) => (
            <StatusRow key={item.label} item={item} />
          ))}
        </div>
      </Panel>

      <Panel title="History">
        <ol className="space-y-2">
          {model.history.map((h) => (
            <li
              key={h.id}
              className="grid grid-cols-[1fr_auto] gap-3 border-b border-[var(--border)]/50 py-2 last:border-0"
            >
              <div>
                <p className="text-[12px] text-[var(--fg)]">{h.label}</p>
                <p className="font-mono text-[11px] text-[var(--fg-subtle)]">
                  {h.at ? h.at.replace("T", " ").slice(0, 19) + " UTC" : "—"}
                </p>
              </div>
              <Badge tone={h.done ? "success" : "neutral"}>
                {h.done ? "DONE" : "PENDING"}
              </Badge>
            </li>
          ))}
        </ol>
      </Panel>

      <Panel title="Operator note">
        <div className="flex gap-2 text-[12px] text-[var(--fg-muted)]">
          <Shield className="mt-0.5 h-4 w-4 shrink-0 text-[var(--fg-subtle)]" />
          <p>
            Read-only certification desk. Does not change Risk, Safety, sessions, thresholds, OMS,
            or MT5. First-fill evidence is stored locally when observed from live Auto Trading /
            journal APIs.
          </p>
        </div>
      </Panel>
    </div>
  );
}

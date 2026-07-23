"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { BadgeCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { executionApi, iteOpsApi } from "@/lib/api/endpoints";
import { runAutomaticAcceptanceEngine } from "@/lib/automatic-production-acceptance";
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

export function AutomaticProductionAcceptanceWorkspace() {
  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading", "auto-accept"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 8_000,
  });
  const journalQ = useQuery({
    queryKey: ["execution-journal", "auto-accept"],
    queryFn: () => executionApi.journal(100),
    retry: false,
    refetchInterval: 10_000,
  });
  const auditsQ = useQuery({
    queryKey: ["execution-audits", "auto-accept"],
    queryFn: () => executionApi.audits(100),
    retry: false,
    refetchInterval: 15_000,
  });

  const model = useMemo(
    () =>
      runAutomaticAcceptanceEngine({
        autoTrading: autoQ.data,
        journal: journalQ.data,
        audits: auditsQ.data,
      }),
    [autoQ.data, journalQ.data, auditsQ.data],
  );

  if (autoQ.isLoading && !autoQ.data) {
    return <DeskSkeleton rows={6} />;
  }
  if (autoQ.error && !autoQ.data && model.status !== "PRODUCTION ACCEPTED") {
    return (
      <DeskError
        message={
          autoQ.error instanceof Error
            ? autoQ.error.message
            : "Automatic Production Acceptance unavailable"
        }
      />
    );
  }

  const accepted = model.status === "PRODUCTION ACCEPTED";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <BadgeCheck className="h-4 w-4 text-[var(--fg-subtle)]" />
        <span className="text-[12px] font-medium text-[var(--fg)]">
          Automatic Production Acceptance Engine
        </span>
        <Badge tone="neutral">READ-ONLY</Badge>
        <Badge tone="neutral">NO MANUAL OVERRIDE</Badge>
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {model.observedAt.replace("T", " ").slice(0, 19)} UTC
        </span>
      </div>

      <Panel title="Status">
        <p
          className={cn(
            "font-mono text-[22px] tracking-wide",
            accepted ? "text-[var(--success)]" : "text-[var(--warning)]",
          )}
        >
          {accepted ? "✅ PRODUCTION ACCEPTED" : "WAITING"}
        </p>
        <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
          Accepted only when every required evidence item is observed. Missing
          evidence is never inferred.
        </p>
      </Panel>

      <Panel title="Execution Evidence">
        <ul className="space-y-1">
          {model.checklist.map((item) => (
            <li
              key={item.id}
              className="grid grid-cols-[1.5rem_1fr_auto] items-center gap-2 border-b border-[var(--border)]/50 py-1.5 last:border-0"
            >
              <span
                className={cn(
                  "font-mono text-[14px]",
                  item.present ? "text-[var(--success)]" : "text-[var(--fg-muted)]",
                )}
              >
                {item.mark}
              </span>
              <span className="text-[13px] text-[var(--fg)]">{item.label}</span>
              <span className="max-w-[14rem] truncate font-mono text-[11px] text-[var(--fg-muted)]">
                {item.present ? item.detail : "Waiting"}
              </span>
            </li>
          ))}
        </ul>
        {!accepted && model.missing.length > 0 ? (
          <div className="mt-3 border border-[var(--border)] bg-[var(--bg)]/40 px-3 py-2">
            <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Still missing
            </p>
            <p className="mt-1 font-mono text-[12px] text-[var(--warning)]">
              {model.missing.join(" · ")}
            </p>
          </div>
        ) : null}
      </Panel>

      <Panel
        title="Acceptance Report"
        action={
          model.report ? (
            <Badge tone="success">IMMUTABLE</Badge>
          ) : (
            <Badge tone="neutral">NOT GENERATED</Badge>
          )
        }
      >
        {!model.report ? (
          <p className="text-sm text-[var(--fg-muted)]">
            Report generates automatically when all evidence is observed, then
            freezes permanently.
          </p>
        ) : (
          <div className="space-y-3">
            <p className="font-mono text-[12px] text-[var(--fg)]">
              Generated {model.report.generatedAtUtc.replace("T", " ").slice(0, 19)}{" "}
              UTC · immutable
            </p>
            <pre className="max-h-80 overflow-auto border border-[var(--border)] bg-[var(--bg)] p-3 font-mono text-[10px] text-[var(--fg-muted)]">
              {JSON.stringify(model.report, null, 2)}
            </pre>
          </div>
        )}
      </Panel>
    </div>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Lock, FileLock2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { executionApi, iteOpsApi } from "@/lib/api/endpoints";
import {
  EVIDENCE_FIELD_LABELS,
  loadFirstExecutionEvidence,
  reconcileFirstExecutionEvidence,
  saveFirstExecutionEvidence,
  type FirstExecutionEvidenceRecord,
} from "@/lib/first-execution-evidence";
import { cn } from "@/lib/utils";

export function FirstExecutionEvidenceWorkspace() {
  const [record, setRecord] = useState<FirstExecutionEvidenceRecord | null>(
    () => loadFirstExecutionEvidence().record,
  );

  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading", "fee"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 8_000,
  });
  const journalQ = useQuery({
    queryKey: ["execution-journal", "fee"],
    queryFn: () => executionApi.journal(100),
    retry: false,
    refetchInterval: 10_000,
  });
  const auditsQ = useQuery({
    queryKey: ["execution-audits", "fee"],
    queryFn: () => executionApi.audits(100),
    retry: false,
    refetchInterval: 15_000,
  });

  const reconciled = useMemo(
    () =>
      reconcileFirstExecutionEvidence({
        autoTrading: autoQ.data,
        journal: journalQ.data,
        audits: auditsQ.data,
        existing: record,
      }),
    [autoQ.data, journalQ.data, auditsQ.data, record],
  );

  useEffect(() => {
    if (!autoQ.data) return;
    const next = reconciled.storePatch.record;
    if (!next) return;
    if (record?.locked) return;
    saveFirstExecutionEvidence({ record: next });
    setRecord(next);
  }, [autoQ.data, reconciled.storePatch.record, record?.locked]);

  if (autoQ.isLoading && !autoQ.data && !record) {
    return <DeskSkeleton rows={4} />;
  }
  if (autoQ.error && !autoQ.data && !record) {
    return (
      <DeskError
        message={
          autoQ.error instanceof Error
            ? autoQ.error.message
            : "First Execution Evidence unavailable"
        }
      />
    );
  }

  const locked = reconciled.record ?? record;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <FileLock2 className="h-4 w-4 text-[var(--fg-subtle)]" />
        <span className="text-[12px] font-medium text-[var(--fg)]">
          First Execution Evidence
        </span>
        <Badge tone="neutral">READ-ONLY</Badge>
        {locked ? (
          <Badge tone="success">
            <Lock className="mr-1 h-3 w-3" />
            LOCKED
          </Badge>
        ) : (
          <Badge tone="warning">PENDING</Badge>
        )}
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)]">
        <header className="border-b border-[var(--border)] px-3 py-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Immutable record
          </h2>
        </header>
        <div className="p-3">
          {!locked ? (
            <p className="text-sm text-[var(--fg-muted)]">
              No successful live execution recorded.
            </p>
          ) : (
            <div className="space-y-3">
              <p className="text-[11px] text-[var(--fg-muted)]">
                Locked at {locked.lockedAt.replace("T", " ").slice(0, 19)} UTC ·
                never overwritten
              </p>
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {EVIDENCE_FIELD_LABELS.map(({ key, label }) => {
                  if (key === "locked" || key === "lockedAt" || key === "source") {
                    return null;
                  }
                  const value = String(locked[key] ?? "—");
                  return (
                    <div
                      key={key}
                      className={cn(
                        "border border-[var(--border)] bg-[var(--bg)]/35 px-2.5 py-2",
                      )}
                    >
                      <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                        {label}
                      </div>
                      <div className="mt-0.5 truncate font-mono text-[12px] text-[var(--fg)]">
                        {value}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

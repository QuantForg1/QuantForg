"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ClipboardCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { executionApi, iteOpsApi, portfolioApi } from "@/lib/api/endpoints";
import {
  buildPatPdfBytes,
  downloadBytes,
  downloadJson,
  runProductionAcceptanceTest,
} from "@/lib/production-acceptance-test";
import { cn } from "@/lib/utils";

const GROUPS = [
  "Market",
  "Decision",
  "Risk",
  "Safety",
  "Execution",
  "Trade",
  "Audit",
] as const;

export function ProductionAcceptanceTestWorkspace() {
  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading", "pat"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 8_000,
  });
  const journalQ = useQuery({
    queryKey: ["execution-journal", "pat"],
    queryFn: () => executionApi.journal(100),
    retry: false,
    refetchInterval: 10_000,
  });
  const auditsQ = useQuery({
    queryKey: ["execution-audits", "pat"],
    queryFn: () => executionApi.audits(100),
    retry: false,
    refetchInterval: 15_000,
  });
  const positionsQ = useQuery({
    queryKey: ["positions", "pat"],
    queryFn: () => portfolioApi.positions(),
    retry: false,
    refetchInterval: 12_000,
  });

  const model = useMemo(
    () =>
      runProductionAcceptanceTest({
        autoTrading: autoQ.data,
        journal: journalQ.data,
        audits: auditsQ.data,
        positions: positionsQ.data,
      }),
    [autoQ.data, journalQ.data, auditsQ.data, positionsQ.data],
  );

  if (autoQ.isLoading && !autoQ.data) {
    return <DeskSkeleton rows={8} />;
  }
  if (autoQ.error && !autoQ.data && model.status !== "PRODUCTION ACCEPTED") {
    return (
      <DeskError
        message={
          autoQ.error instanceof Error
            ? autoQ.error.message
            : "Production Acceptance Test unavailable"
        }
      />
    );
  }

  const accepted = model.status === "PRODUCTION ACCEPTED";

  const exportPayload = {
    title: "Production Acceptance Report",
    status: model.status,
    statusLabel: model.statusLabel,
    generatedAtUtc: model.report?.generatedAtUtc ?? new Date().toISOString(),
    utcTimestamp: model.summary.utcTimestamp,
    signalId: model.summary.signalId,
    mt5Ticket: model.summary.mt5Ticket,
    dealId: model.summary.dealId,
    executionLatency: model.summary.executionLatency,
    checklist: model.checklist,
    overall: accepted ? "PASS" : "FAIL",
    missing: model.missing,
    immutable: Boolean(model.report?.immutable),
    note: "Evidence only. No manual approval.",
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <ClipboardCheck className="h-4 w-4 text-[var(--fg-subtle)]" />
        <span className="text-[12px] font-medium text-[var(--fg)]">
          Production Acceptance Test (PAT)
        </span>
        <Badge tone="neutral">READ-ONLY</Badge>
        <Badge tone="neutral">NO MANUAL APPROVAL</Badge>
        <div className="ml-auto flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              downloadJson(
                `production-acceptance-report-${Date.now()}.json`,
                exportPayload,
              )
            }
          >
            Export JSON
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              const bytes = buildPatPdfBytes({
                statusLabel: model.statusLabel,
                generatedAtUtc: exportPayload.generatedAtUtc,
                utcTimestamp: model.summary.utcTimestamp,
                signalId: model.summary.signalId,
                mt5Ticket: model.summary.mt5Ticket,
                dealId: model.summary.dealId,
                executionLatency: model.summary.executionLatency,
                checklist: model.checklist,
                overall: exportPayload.overall,
              });
              downloadBytes(
                `production-acceptance-report-${Date.now()}.pdf`,
                bytes,
                "application/pdf",
              );
            }}
          >
            Export PDF
          </Button>
        </div>
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)]">
        <header className="border-b border-[var(--border)] px-3 py-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Result
          </h2>
        </header>
        <div className="p-3">
          <p
            className={cn(
              "font-mono text-[22px] tracking-wide",
              accepted ? "text-[var(--success)]" : "text-[var(--warning)]",
            )}
          >
            {accepted ? "✅ PRODUCTION ACCEPTED" : "⏳ WAITING"}
          </p>
          {!accepted && model.missing.length > 0 ? (
            <div className="mt-3 border border-[var(--border)] bg-[var(--bg)]/40 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Missing evidence
              </p>
              <p className="mt-1 font-mono text-[12px] text-[var(--warning)]">
                {model.missing.join(" · ")}
              </p>
            </div>
          ) : null}
          {model.report ? (
            <p className="mt-2 font-mono text-[11px] text-[var(--fg-muted)]">
              Report frozen {model.report.generatedAtUtc.replace("T", " ").slice(0, 19)}{" "}
              UTC · immutable
            </p>
          ) : null}
        </div>
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)]">
        <header className="border-b border-[var(--border)] px-3 py-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Test checklist
          </h2>
        </header>
        <div className="space-y-4 p-3">
          {GROUPS.map((group) => {
            const rows = model.checklist.filter((c) => c.group === group);
            if (!rows.length) return null;
            return (
              <div key={group}>
                <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  {group}
                </h3>
                <ul>
                  {rows.map((c) => (
                    <li
                      key={c.id}
                      className="grid grid-cols-[1.5rem_1fr_auto_auto] items-center gap-2 border-b border-[var(--border)]/40 py-1.5 last:border-0"
                    >
                      <span
                        className={cn(
                          "font-mono text-[14px]",
                          c.pass
                            ? "text-[var(--success)]"
                            : "text-[var(--fg-muted)]",
                        )}
                      >
                        {c.mark}
                      </span>
                      <span className="text-[13px] text-[var(--fg)]">{c.label}</span>
                      <Badge tone={c.pass ? "success" : "neutral"}>
                        {c.result}
                      </Badge>
                      <span className="max-w-[10rem] truncate font-mono text-[10px] text-[var(--fg-muted)]">
                        {c.pass ? c.detail : "□"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

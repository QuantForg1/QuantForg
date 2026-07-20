"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Activity } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { executionApi } from "@/lib/api/endpoints";
import { asList, asRecord } from "@/lib/desk";
import {
  journalToDiagnostics,
  type ExecutionDiagnosticRow,
} from "@/lib/execution/humanize";
import { cn } from "@/lib/utils";

function StageCell({
  label,
  stage,
}: {
  label: string;
  stage: { status: string; reason: string; latency_ms?: number };
}) {
  const tone =
    stage.status === "ok"
      ? "success"
      : stage.status === "failed" || stage.status === "blocked"
        ? "danger"
        : "neutral";
  return (
    <div className="min-w-[8rem] space-y-0.5">
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--fg-subtle)]">
          {label}
        </span>
        <Badge tone={tone} className="text-[10px]">
          {stage.status}
        </Badge>
      </div>
      <p className="line-clamp-2 text-xs text-[var(--fg-muted)]" title={stage.reason}>
        {stage.reason}
      </p>
      {typeof stage.latency_ms === "number" ? (
        <p className="text-[10px] text-[var(--fg-subtle)]">{stage.latency_ms.toFixed(0)} ms</p>
      ) : null}
    </div>
  );
}

/**
 * Full execution diagnostics — Validation → Risk → Gateway → MT5 check/send.
 * Sourced from live execution journal only (no mocks).
 */
export function ExecutionDiagnosticsPanel({ dense = false }: { dense?: boolean }) {
  const [selected, setSelected] = useState<ExecutionDiagnosticRow | null>(null);
  const q = useQuery({
    queryKey: ["execution-journal", "diagnostics"],
    queryFn: () => executionApi.journal(80),
    staleTime: 4_000,
    refetchInterval: 8_000,
    retry: false,
  });

  const rows = useMemo(() => {
    const raw = asList(asRecord(q.data).items ?? q.data).map(asRecord);
    return journalToDiagnostics(raw);
  }, [q.data]);

  if (q.isLoading) return <DeskSkeleton />;
  if (q.isError) {
    return (
      <DeskError
        message="Diagnostics unavailable — could not load the execution journal."
        onRetry={() => void q.refetch()}
      />
    );
  }

  const tableRows = rows.map((r) => [
    <span key="t" className="whitespace-nowrap text-xs">
      {r.timestamp ? new Date(r.timestamp).toLocaleString() : "—"}
    </span>,
    <span key="s">{r.symbol || "—"}</span>,
    <span key="a" className="uppercase">
      {r.action} {r.side}
    </span>,
    <Badge
      key="o"
      tone={
        r.outcome === "success"
          ? "success"
          : r.outcome === "rejected" || r.outcome === "failed"
            ? "danger"
            : "warning"
      }
    >
      {r.outcome || "—"}
    </Badge>,
    <span key="tk" className="font-mono text-xs">
      {r.ticket ?? "—"} / {r.deal ?? "—"}
    </span>,
    <span key="l" className="text-xs">
      {r.latency_ms != null ? `${r.latency_ms.toFixed(0)} ms` : "—"}
    </span>,
    <span key="rc" className="font-mono text-xs">
      {r.retcode ?? "—"}
    </span>,
    <Button key="d" type="button" size="sm" variant="ghost" onClick={() => setSelected(r)}>
      Details
    </Button>,
  ]);

  return (
    <section
      id="bw-execution-diagnostics"
      className={cn(
        "scroll-mt-24 space-y-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)]/90 p-5 shadow-[var(--shadow-card)]",
        dense && "p-3",
      )}
      aria-label="Execution diagnostics"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-medium tracking-wide text-[var(--fg)]">
            Execution Diagnostics
          </h2>
          <p className="mt-0.5 text-xs text-[var(--fg-subtle)]">
            Every submit: Validation · Risk · Gateway · MT5 order_check · order_send
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone="neutral">{rows.length} runs</Badge>
          <Button type="button" variant="outline" size="sm" onClick={() => void q.refetch()}>
            Refresh
          </Button>
          <Button type="button" variant="ghost" size="sm" asChild>
            <Link href="/terminal">Open Terminal</Link>
          </Button>
        </div>
      </div>

      {rows.length === 0 ? (
        <DeskEmpty
          icon={Activity}
          title="No executions yet"
          description="Submit a live BUY/SELL from Terminal — each attempt appears here with full stage audit."
          actionLabel="Open Terminal"
          actionHref="/terminal"
        />
      ) : (
        <DeskTable
          columns={[
            "Time",
            "Symbol",
            "Action",
            "Outcome",
            "Ticket / Deal",
            "Latency",
            "Retcode",
            "",
          ]}
          rows={tableRows}
        />
      )}

      {selected ? (
        <div className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--bg)]/40 p-4">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-sm font-medium text-[var(--fg)]">
                {selected.symbol} · {selected.action} {selected.side}
              </p>
              <p className="text-xs text-[var(--fg-subtle)]">
                {selected.request_id} · {selected.comment || "—"}
              </p>
            </div>
            <Button type="button" size="sm" variant="ghost" onClick={() => setSelected(null)}>
              Close
            </Button>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <StageCell label="Validation" stage={selected.validation} />
            <StageCell label="Risk" stage={selected.risk} />
            <StageCell label="Gateway" stage={selected.gateway} />
            <StageCell label="MT5 order_check" stage={selected.order_check} />
            <StageCell label="MT5 order_send" stage={selected.order_send} />
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--fg-subtle)]">
                Request payload
              </p>
              <pre className="max-h-48 overflow-auto rounded-lg bg-[var(--surface-2)] p-2 text-[11px] text-[var(--fg-muted)]">
                {JSON.stringify(selected.request_payload ?? {}, null, 2)}
              </pre>
            </div>
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--fg-subtle)]">
                Response payload
              </p>
              <pre className="max-h-48 overflow-auto rounded-lg bg-[var(--surface-2)] p-2 text-[11px] text-[var(--fg-muted)]">
                {JSON.stringify(selected.response_payload ?? {}, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

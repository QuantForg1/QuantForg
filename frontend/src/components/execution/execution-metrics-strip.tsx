"use client";

import { memo } from "react";
import { cn, formatNumber } from "@/lib/utils";

export type ExecutionTimingMetrics = {
  signalMs: number | null;
  riskMs: number | null;
  orderCheckMs: number | null;
  brokerFillMs: number | null;
  totalMs: number | null;
  slippage: string | null;
  spread: string | null;
  source: "live" | "none";
};

export const EMPTY_EXECUTION_METRICS: ExecutionTimingMetrics = {
  signalMs: null,
  riskMs: null,
  orderCheckMs: null,
  brokerFillMs: null,
  totalMs: null,
  slippage: null,
  spread: null,
  source: "none",
};

function fmtMs(v: number | null): string {
  if (v == null || !Number.isFinite(v)) return "Not available";
  return `${formatNumber(v, 1)} ms`;
}

/** Real execution timings only — never invents latency or slippage. */
export const ExecutionMetricsStrip = memo(function ExecutionMetricsStrip({
  metrics,
  className,
}: {
  metrics: ExecutionTimingMetrics;
  className?: string;
}) {
  const rows: [string, string][] = [
    ["Signal Time", fmtMs(metrics.signalMs)],
    ["Risk Time", fmtMs(metrics.riskMs)],
    ["Order Check Time", fmtMs(metrics.orderCheckMs)],
    ["Broker Fill Time", fmtMs(metrics.brokerFillMs)],
    ["Total Execution Time", fmtMs(metrics.totalMs)],
    ["Slippage", metrics.slippage?.trim() || "Not available"],
    ["Spread", metrics.spread?.trim() || "Not available"],
  ];

  return (
    <section
      className={cn(
        "rounded-md border border-[var(--border)] bg-[var(--bg)]/50 px-2.5 py-2",
        className,
      )}
      aria-label="Execution metrics"
    >
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Execution metrics
        </p>
        <span className="text-[9px] text-[var(--fg-subtle)]">
          {metrics.source === "live" ? "Last live submit" : "Awaiting live fill"}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 sm:grid-cols-4">
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <div className="text-[9px] uppercase tracking-wide text-[var(--fg-subtle)]">
              {label}
            </div>
            <div className="truncate font-mono text-[10px] tabular text-[var(--fg)]">
              {value}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
});

/** Map institutional pipeline stages + client marks → display metrics. */
export function metricsFromPipelineResult(
  result: Record<string, unknown>,
  client: {
    signalMs?: number;
    riskMs?: number;
    orderCheckMs?: number;
    totalMs?: number;
    spread?: string;
  },
): ExecutionTimingMetrics {
  const stages = Array.isArray(result.stages) ? result.stages : [];
  const byStage = new Map<string, number>();
  for (const raw of stages) {
    if (!raw || typeof raw !== "object") continue;
    const s = raw as Record<string, unknown>;
    const name = String(s.stage ?? "").toLowerCase();
    const elapsed = Number(s.elapsed_ms);
    if (name && Number.isFinite(elapsed)) byStage.set(name, elapsed);
  }

  const find = (...keys: string[]) => {
    for (const k of keys) {
      const v = byStage.get(k);
      if (v != null) return v;
    }
    return null;
  };

  const exec = (result.execution ?? result) as Record<string, unknown>;
  const slippageRaw =
    exec.slippage ?? result.slippage ?? exec.slippage_points ?? null;
  const spreadRaw = client.spread ?? exec.spread ?? result.spread ?? null;

  const totalFromServer = Number(result.latency_ms);
  const brokerFill =
    find("broker_fill", "broker_acceptance", "broker_submission") ??
    (Number.isFinite(Number(exec.latency_ms)) ? Number(exec.latency_ms) : null);

  return {
    signalMs: client.signalMs ?? find("draft", "signal") ?? null,
    riskMs: client.riskMs ?? find("risk_check", "risk") ?? null,
    orderCheckMs:
      client.orderCheckMs ??
      find("execution_check", "validation", "order_check") ??
      null,
    brokerFillMs: brokerFill,
    totalMs:
      client.totalMs ??
      (Number.isFinite(totalFromServer) ? totalFromServer : null),
    slippage:
      slippageRaw != null && String(slippageRaw).trim()
        ? String(slippageRaw)
        : null,
    spread:
      spreadRaw != null && String(spreadRaw).trim() ? String(spreadRaw) : null,
    source: "live",
  };
}

"use client";

import { memo } from "react";
import { cn, formatNumber } from "@/lib/utils";

export type ExecutionTimingMetrics = {
  signalMs: number | null;
  riskMs: number | null;
  safetyMs: number | null;
  orderCheckMs: number | null;
  brokerFillMs: number | null;
  totalMs: number | null;
  slippage: string | null;
  spread: string | null;
  fillStatus: string | null;
  source: "live" | "none";
  requestId?: string;
};

export const EMPTY_EXECUTION_METRICS: ExecutionTimingMetrics = {
  signalMs: null,
  riskMs: null,
  safetyMs: null,
  orderCheckMs: null,
  brokerFillMs: null,
  totalMs: null,
  slippage: null,
  spread: null,
  fillStatus: null,
  source: "none",
};

function fmtMs(v: number | null, hasHistory: boolean): string {
  if (v == null || !Number.isFinite(v)) {
    return hasHistory ? "—" : "Awaiting fill";
  }
  return `${formatNumber(v, 1)} ms`;
}

function fmtText(v: string | null, hasHistory: boolean, empty = "—"): string {
  const t = v?.trim();
  if (t) return t;
  return hasHistory ? empty : "Awaiting fill";
}

/** Real execution timings only — never invents latency or slippage. */
export const ExecutionMetricsStrip = memo(function ExecutionMetricsStrip({
  metrics,
  className,
  dense = false,
}: {
  metrics: ExecutionTimingMetrics;
  className?: string;
  dense?: boolean;
}) {
  const hasHistory = metrics.source === "live";
  const rows: [string, string][] = [
    ["Signal Time", fmtMs(metrics.signalMs, hasHistory)],
    ["Risk Time", fmtMs(metrics.riskMs, hasHistory)],
    ["Safety Time", fmtMs(metrics.safetyMs, hasHistory)],
    ["Order Check", fmtMs(metrics.orderCheckMs, hasHistory)],
    ["Broker Fill Time", fmtMs(metrics.brokerFillMs, hasHistory)],
    ["Total Execution Time", fmtMs(metrics.totalMs, hasHistory)],
    ["Spread", fmtText(metrics.spread, hasHistory)],
    ["Slippage", fmtText(metrics.slippage, hasHistory, "0")],
    [
      "Fill Status",
      fmtText(metrics.fillStatus, hasHistory, hasHistory ? "Filled" : "Awaiting fill"),
    ],
  ];

  return (
    <section
      className={cn(
        "border border-[var(--border)] bg-[var(--surface)]",
        dense ? "px-2.5 py-2" : "px-3 py-3",
        className,
      )}
      aria-label="Execution metrics"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Last successful execution
        </p>
        <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
          {hasHistory
            ? metrics.requestId
              ? metrics.requestId.slice(0, 28)
              : "Live history"
            : "No fills yet"}
        </span>
      </div>
      <div
        className={cn(
          "grid gap-x-4 gap-y-2",
          dense ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-2 sm:grid-cols-3 lg:grid-cols-5",
        )}
      >
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0 border-l border-[var(--border)] pl-2">
            <div className="text-[9px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              {label}
            </div>
            <div className="truncate font-mono text-[12px] tabular text-[var(--fg)]">
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
    safetyMs?: number;
    orderCheckMs?: number;
    brokerFillMs?: number;
    totalMs?: number;
    spread?: string;
    slippage?: string;
  },
): ExecutionTimingMetrics {
  const stages = Array.isArray(result.stages) ? result.stages : [];
  const byStage = new Map<string, number>();
  for (const raw of stages) {
    if (!raw || typeof raw !== "object") continue;
    const s = raw as Record<string, unknown>;
    const name = String(s.stage ?? "")
      .toLowerCase()
      .replace(/\s+/g, "_");
    const elapsed = Number(s.elapsed_ms);
    if (name && Number.isFinite(elapsed)) byStage.set(name, elapsed);
  }

  const find = (...keys: string[]) => {
    for (const k of keys) {
      const v = byStage.get(k);
      if (v != null) return v;
      for (const [name, elapsed] of byStage) {
        if (name.includes(k)) return elapsed;
      }
    }
    return null;
  };

  const exec = (result.execution ?? result) as Record<string, unknown>;
  const slippageRaw =
    client.slippage ??
    exec.slippage ??
    result.slippage ??
    exec.slippage_points ??
    null;
  const spreadRaw = client.spread ?? exec.spread ?? result.spread ?? null;

  const totalFromServer = Number(result.latency_ms);
  const brokerFill =
    client.brokerFillMs ??
    find("broker_fill", "broker_acceptance", "broker_submission") ??
    (Number.isFinite(Number(exec.latency_ms)) ? Number(exec.latency_ms) : null);

  const outcome = String(result.outcome ?? exec.outcome ?? "").toLowerCase();
  const filled = outcome === "success" || outcome === "filled";

  return {
    signalMs: client.signalMs ?? find("draft", "signal") ?? null,
    riskMs: client.riskMs ?? find("risk_check", "risk") ?? null,
    safetyMs: client.safetyMs ?? find("safety", "execution_check") ?? null,
    orderCheckMs:
      client.orderCheckMs ??
      find("validation", "order_check") ??
      null,
    brokerFillMs: brokerFill,
    totalMs:
      client.totalMs ??
      (Number.isFinite(totalFromServer) ? totalFromServer : null),
    slippage:
      slippageRaw != null && String(slippageRaw).trim()
        ? String(slippageRaw)
        : filled
          ? "0"
          : null,
    spread:
      spreadRaw != null && String(spreadRaw).trim() ? String(spreadRaw) : null,
    fillStatus: filled ? "Filled" : outcome || null,
    source: "live",
    requestId: String(result.request_id ?? ""),
  };
}

import type { ExecutionTimingMetrics } from "@/components/execution/execution-metrics-strip";
import { EMPTY_EXECUTION_METRICS } from "@/components/execution/execution-metrics-strip";

const KEY = "qf.exec.metrics.v1";

/** Persist last live execution timings for Monitoring desk (never invents). */
export function saveLastExecutionMetrics(metrics: ExecutionTimingMetrics): void {
  if (typeof window === "undefined") return;
  if (metrics.source !== "live") return;
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ ...metrics, savedAt: Date.now() }));
  } catch {
    /* ignore */
  }
}

export function loadLastExecutionMetrics(): ExecutionTimingMetrics {
  if (typeof window === "undefined") return EMPTY_EXECUTION_METRICS;
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return EMPTY_EXECUTION_METRICS;
    const parsed = JSON.parse(raw) as ExecutionTimingMetrics;
    if (parsed?.source !== "live") return EMPTY_EXECUTION_METRICS;
    return {
      signalMs: parsed.signalMs ?? null,
      riskMs: parsed.riskMs ?? null,
      orderCheckMs: parsed.orderCheckMs ?? null,
      brokerFillMs: parsed.brokerFillMs ?? null,
      totalMs: parsed.totalMs ?? null,
      slippage: parsed.slippage ?? null,
      spread: parsed.spread ?? null,
      source: "live",
    };
  } catch {
    return EMPTY_EXECUTION_METRICS;
  }
}

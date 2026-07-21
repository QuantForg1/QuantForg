/** Derive live execution timing metrics from journal + audits (never invent). */

import {
  EMPTY_EXECUTION_METRICS,
  type ExecutionTimingMetrics,
} from "@/components/execution/execution-metrics-strip";
import { asList, asRecord, num, str } from "@/lib/desk";

function stageElapsed(
  stages: Record<string, unknown>[],
  ...names: string[]
): number | null {
  const want = names.map((n) => n.toLowerCase().replace(/\s+/g, "_"));
  for (const s of stages) {
    const name = str(s.stage).toLowerCase().replace(/\s+/g, "_");
    if (!want.some((w) => name === w || name.includes(w))) continue;
    const elapsed = num(s.elapsed_ms ?? s.latency_ms);
    if (Number.isFinite(elapsed)) return elapsed;
  }
  return null;
}

function safetySpread(audits: Record<string, unknown>[]): string | null {
  const safety = audits.find((a) => str(a.stage).toLowerCase() === "safety");
  if (!safety) return null;
  const calc = asRecord(asRecord(safety.payload_out).calculated_risk);
  const fromCalc = str(calc.spread);
  if (fromCalc) return fromCalc;
  const direct = str(safety.spread);
  return direct || null;
}

export type LatestExecutionSnapshot = {
  requestId: string;
  metrics: ExecutionTimingMetrics;
  symbol: string;
  side: string;
  volume: string;
  price: string;
  ticket: string;
  deal: string;
  at: string;
};

/**
 * Prefer the latest successful journal fill. Fall back to last live sessionStorage
 * metrics only when journal has no success row.
 */
export function latestSuccessfulExecution(params: {
  journalItems: unknown;
  auditItems?: unknown;
  sessionFallback?: ExecutionTimingMetrics;
}): LatestExecutionSnapshot | null {
  const rows = asList(
    asRecord(params.journalItems).items ?? params.journalItems,
  )
    .map(asRecord)
    .filter((r) => {
      const result = str(r.execution_result || r.outcome).toLowerCase();
      return result === "success" || result === "filled" || result === "done";
    });

  if (rows.length === 0) {
    const fb = params.sessionFallback;
    if (fb && fb.source === "live" && fb.totalMs != null) {
      return {
        requestId: fb.requestId ?? "",
        metrics: {
          ...EMPTY_EXECUTION_METRICS,
          ...fb,
          fillStatus: fb.fillStatus ?? "Filled",
          source: "live",
        },
        symbol: "XAUUSD",
        side: "",
        volume: "",
        price: "",
        ticket: "",
        deal: "",
        at: "",
      };
    }
    return null;
  }

  rows.sort((a, b) => {
    const ta = Date.parse(str(a.timestamp || a.submitted_at || a.created_at));
    const tb = Date.parse(str(b.timestamp || b.submitted_at || b.created_at));
    return (Number.isFinite(tb) ? tb : 0) - (Number.isFinite(ta) ? ta : 0);
  });

  const latest = rows[0]!;
  const requestId = str(latest.request_id);
  const allAudits = asList(
    asRecord(params.auditItems).items ?? params.auditItems,
  ).map(asRecord);
  const audits = allAudits.filter(
    (a) => !requestId || str(a.request_id) === requestId,
  );

  const submitAudit = audits.find((a) => str(a.stage).toLowerCase() === "submit");
  const stagesFromJournal = asList(latest.stages).map(asRecord);
  const stagesFromSubmit = asList(
    asRecord(submitAudit?.payload_out).stages,
  ).map(asRecord);
  const stages = stagesFromJournal.length ? stagesFromJournal : stagesFromSubmit;

  const total =
    num(latest.latency_ms) ||
    num(submitAudit?.latency_ms) ||
    null;
  const gateway =
    num(submitAudit?.gateway_latency_ms) ||
    stageElapsed(
      stages,
      "broker_submission",
      "broker_fill",
      "broker_acceptance",
    );

  const spread = safetySpread(audits) || str(latest.spread) || null;
  const slippageRaw = latest.slippage ?? submitAudit?.slippage;

  const metrics: ExecutionTimingMetrics = {
    signalMs: stageElapsed(stages, "draft", "signal"),
    riskMs:
      stageElapsed(stages, "risk_check", "risk") ??
      (audits.some((a) => str(a.stage) === "risk") ? num(asRecord(audits.find((a) => str(a.stage) === "risk")).railway_processing_ms) || 0 : null),
    safetyMs:
      stageElapsed(stages, "safety", "execution_check") ??
      (audits.some((a) => str(a.stage) === "safety") ? 0 : null),
    orderCheckMs: stageElapsed(stages, "validation", "order_check"),
    brokerFillMs: gateway,
    totalMs: Number.isFinite(total as number) ? (total as number) : null,
    slippage:
      slippageRaw != null && String(slippageRaw).trim()
        ? String(slippageRaw)
        : "0",
    spread: spread || "—",
    fillStatus: "Filled",
    source: "live",
    requestId,
  };

  return {
    requestId,
    metrics,
    symbol: str(latest.symbol, "XAUUSD"),
    side: str(latest.side),
    volume: str(latest.volume),
    price: str(latest.price),
    ticket: str(latest.ticket ?? latest.order_id ?? latest.order_ticket),
    deal: str(latest.deal_ticket ?? latest.deal_id),
    at: str(latest.timestamp || latest.submitted_at || latest.created_at),
  };
}

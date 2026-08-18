/**
 * Classify conditions that may halt a new entry vs advisory noise.
 *
 * Advisory must not immediately halt a trade:
 *   UI/telemetry stale, duplicate health probe, optional enrichment miss,
 *   non-authoritative analytics unavailable.
 *
 * Hard block — fail closed:
 *   MT5 disconnected, Gateway unavailable, stale quote, invalid symbol,
 *   risk limit exceeded, Safety failure, min-lot risk violation,
 *   reconciliation unknown.
 */

export type HaltClass = "advisory" | "hard_block" | "unclassified";

function norm(text: string): string {
  return String(text || "")
    .toLowerCase()
    .replace(/[_/:.,()[\]-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const HARD_NEEDLES = [
  "mt5 disconnected",
  "mt5 unavailable",
  "broker unavailable",
  "gateway unavailable",
  "gateway disconnected",
  "stale quote",
  "stale market data",
  "market data stale",
  "quote missing",
  "quote malformed",
  "invalid symbol",
  "symbol identity invalid",
  "symbol not tradable",
  "risk limit exceeded",
  "portfolio risk exceeded",
  "portfolio risk limit",
  "daily loss exceeded",
  "safety failure",
  "safety blocked",
  "safety block",
  "below min lot",
  "min lot constraint",
  "minimum lot causes risk",
  "min lot risk",
  "reconciliation required",
  "reconciliation unknown",
  "unknown order reconciliation",
  "stale heartbeat gateway",
  "stale heartbeat mt5",
  "stale heartbeat oms",
] as const;

const ADVISORY_NEEDLES = [
  "ui telemetry stale",
  "telemetry stale",
  "ops telemetry",
  "ops telemetry delayed",
  "duplicate health probe",
  "duplicate health",
  "optional enrichment",
  "enrichment unavailable",
  "non authoritative analytics",
  "analytics unavailable",
  "execution quality analytics",
  "platform probe",
  "railway self probe",
  "stale heartbeat execution",
  "stale heartbeat decision",
  "stale heartbeat pme",
  "connected cached",
] as const;

export function classifyHaltCondition(reason: string): HaltClass {
  const hay = norm(reason);
  if (!hay) return "unclassified";
  for (const needle of HARD_NEEDLES) {
    if (hay.includes(needle)) return "hard_block";
  }
  for (const needle of ADVISORY_NEEDLES) {
    if (hay.includes(needle)) return "advisory";
  }
  return "unclassified";
}

export function doesNotHaltNewEntry(reason: string): boolean {
  return classifyHaltCondition(reason) === "advisory";
}

export function haltsNewEntry(reason: string): boolean {
  return classifyHaltCondition(reason) === "hard_block";
}

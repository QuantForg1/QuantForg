/** Immutable First Execution Evidence — write-once recorder.

Read-only observation of live fills. Never mutates Strategy, Risk, Safety,
OMS, or MT5 execution. Once a complete successful execution is locked,
the record is never overwritten.
*/
import { asList, asRecord, bool, str } from "@/lib/desk";

const STORAGE_KEY = "quantforg.first_execution_evidence.v1";
/** Legacy acceptance blob — read for one-time migration only. */
const LEGACY_ACCEPTANCE_KEY = "quantforg.production_acceptance.v1";

export type FirstExecutionEvidenceRecord = {
  /** Always true once persisted — immutable lock. */
  locked: true;
  lockedAt: string;
  utcTimestamp: string;
  session: string;
  signalId: string;
  quality: string;
  confluence: string;
  decisionId: string;
  riskResult: string;
  safetyResult: string;
  omsRequestId: string;
  brokerRequestId: string;
  brokerResponse: string;
  mt5Ticket: string;
  dealId: string;
  entryPrice: string;
  stopLoss: string;
  takeProfit: string;
  executionLatency: string;
  journalId: string;
  auditId: string;
  source: "live_cycle" | "journal" | "migrated";
};

export type EvidenceStore = {
  record: FirstExecutionEvidenceRecord | null;
};

function present(value: string | null | undefined): boolean {
  const v = (value ?? "").trim();
  return v !== "" && v !== "—";
}

/** Broker accepted = retcode 0 or explicit accept/fill wording. */
export function isBrokerAccepted(brokerResponse: string): boolean {
  const r = brokerResponse.trim().toLowerCase();
  if (!present(r)) return false;
  if (r === "0" || r === "10009" || r === "done" || r === "accepted" || r === "filled") {
    return true;
  }
  // MT5 TRADE_RETCODE_DONE = 10009; also accept numeric 0
  const n = Number(r);
  return Number.isFinite(n) && (n === 0 || n === 10009);
}

/** Gate for lock + PRODUCTION ACCEPTED. */
export function isCompleteSuccessfulExecution(
  ev: Pick<
    FirstExecutionEvidenceRecord,
    "omsRequestId" | "brokerResponse" | "mt5Ticket" | "dealId"
  >,
): boolean {
  return (
    present(ev.omsRequestId) &&
    isBrokerAccepted(ev.brokerResponse) &&
    present(ev.mt5Ticket) &&
    present(ev.dealId)
  );
}

export function loadFirstExecutionEvidence(): EvidenceStore {
  if (typeof window === "undefined") return { record: null };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as EvidenceStore;
      if (parsed?.record?.locked && isCompleteSuccessfulExecution(parsed.record)) {
        return { record: parsed.record };
      }
      if (parsed?.record?.locked) {
        // Locked incomplete should not happen; still never overwrite
        return { record: parsed.record };
      }
    }
  } catch {
    /* fall through */
  }
  // One-time migrate from legacy acceptance store if complete
  try {
    const legacyRaw = window.localStorage.getItem(LEGACY_ACCEPTANCE_KEY);
    if (!legacyRaw) return { record: null };
    const legacy = JSON.parse(legacyRaw) as {
      firstExecution?: Record<string, unknown> | null;
    };
    const fe = legacy.firstExecution;
    if (!fe) return { record: null };
    const migrated = normalizeLegacy(fe);
    if (migrated && isCompleteSuccessfulExecution(migrated)) {
      const store: EvidenceStore = { record: migrated };
      saveFirstExecutionEvidence(store);
      return store;
    }
  } catch {
    /* ignore */
  }
  return { record: null };
}

function normalizeLegacy(
  fe: Record<string, unknown>,
): FirstExecutionEvidenceRecord | null {
  const ticket = str(fe.mt5Ticket ?? fe.mt5_ticket, "—");
  const deal = str(fe.dealId ?? fe.deal_id, "—");
  const oms = str(fe.omsRequest ?? fe.omsRequestId ?? fe.oms_request_id, "—");
  const broker = str(fe.brokerResponse ?? fe.broker_response, "—");
  if (!present(ticket)) return null;
  return {
    locked: true,
    lockedAt: str(fe.capturedAt ?? fe.lockedAt, new Date().toISOString()),
    utcTimestamp: str(fe.utcTime ?? fe.utcTimestamp, "—"),
    session: str(fe.session, "—"),
    signalId: str(fe.signalId ?? fe.signal_id, "—"),
    quality: str(fe.quality, "—"),
    confluence: str(fe.confluence, "—"),
    decisionId: str(fe.decisionId ?? fe.decision_id ?? fe.trace_id, "—"),
    riskResult: str(fe.riskResult ?? fe.risk_result, "—"),
    safetyResult: str(fe.safetyResult ?? fe.safety_result, "—"),
    omsRequestId: oms,
    brokerRequestId: str(
      fe.brokerRequestId ?? fe.broker_request_id ?? fe.request_id,
      "—",
    ),
    brokerResponse: broker,
    mt5Ticket: ticket,
    dealId: deal,
    entryPrice: str(fe.entryPrice ?? fe.entry_price, "—"),
    stopLoss: str(fe.stopLoss ?? fe.stop_loss, "—"),
    takeProfit: str(fe.takeProfit ?? fe.take_profit, "—"),
    executionLatency: str(fe.latency ?? fe.executionLatency, "—"),
    journalId: str(fe.journalId ?? fe.journal_id, "—"),
    auditId: str(fe.auditId ?? fe.audit_id, "—"),
    source: "migrated",
  };
}

/**
 * Persist only when empty. If a locked record exists, it is returned unchanged.
 */
export function saveFirstExecutionEvidence(store: EvidenceStore): EvidenceStore {
  if (typeof window === "undefined") return store;
  try {
    const existing = window.localStorage.getItem(STORAGE_KEY);
    if (existing) {
      const parsed = JSON.parse(existing) as EvidenceStore;
      if (parsed?.record?.locked) {
        return { record: parsed.record };
      }
    }
    if (!store.record?.locked) return { record: null };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
    return store;
  } catch {
    return store;
  }
}

/**
 * Attempt to lock candidate evidence. Never overwrites an existing lock.
 * Incomplete candidates are ignored (do not lock partial fills).
 */
export function lockFirstExecutionIfEligible(
  candidate: Omit<FirstExecutionEvidenceRecord, "locked" | "lockedAt"> | null,
  existing: FirstExecutionEvidenceRecord | null,
): FirstExecutionEvidenceRecord | null {
  if (existing?.locked) return existing;
  if (!candidate) return null;
  if (!isCompleteSuccessfulExecution(candidate)) return null;
  const locked: FirstExecutionEvidenceRecord = {
    ...candidate,
    locked: true,
    lockedAt: new Date().toISOString(),
  };
  return locked;
}

function parseQuality(reasons: string[]): string {
  for (const r of reasons) {
    const m = r.match(/Trade quality\s+(\d+)/i);
    if (m?.[1]) return m[1];
  }
  return "—";
}

function parseConfluence(reasons: string[]): string {
  for (const r of reasons) {
    const m = r.match(/Confluence\s+(\d+)/i);
    if (m?.[1]) return m[1];
  }
  return "—";
}

function findJournalFill(
  journalItems: Record<string, unknown>[],
  ticketHint?: string,
): Record<string, unknown> | null {
  if (ticketHint && present(ticketHint)) {
    const byTicket = journalItems.find((j) => {
      const t = str(j.ticket ?? j.mt5_ticket, "");
      return t === ticketHint;
    });
    if (byTicket) return byTicket;
  }
  return (
    journalItems.find((j) => {
      const ticket = j.ticket ?? j.mt5_ticket;
      const deal = j.deal ?? j.deal_id;
      const result = str(j.execution_result || j.outcome || j.status).toLowerCase();
      return (
        (ticket != null && deal != null) ||
        result.includes("fill") ||
        result.includes("success")
      );
    }) ?? null
  );
}

/** Build a candidate from live cycle + journal/audits (observation only). */
export function observeFirstExecutionCandidate(input: {
  autoTrading: unknown;
  journal: unknown;
  audits: unknown;
}): Omit<FirstExecutionEvidenceRecord, "locked" | "lockedAt"> | null {
  const auto = asRecord(input.autoTrading);
  const orch = asRecord(auto.orchestrator);
  const last = asRecord(orch.last_cycle);
  const diag = asRecord(last.market_context_diagnostics);
  const journalItems = asList(
    asRecord(input.journal).items ??
      asRecord(input.journal).entries ??
      input.journal,
  ).map(asRecord);
  const auditItems = asList(
    asRecord(input.audits).items ??
      asRecord(input.audits).audits ??
      input.audits,
  ).map(asRecord);

  const reasons = asList(last.decision_reasons).map(String);
  const safetyReasons = asList(last.safety_failed_reasons).map(String);
  const outcome = str(last.cycle_outcome, "").toLowerCase();
  const nowIso = new Date().toISOString();
  const cycleAt = str(
    last.observed_at || diag.server_time,
    nowIso,
  );

  const cycleTicket =
    last.mt5_ticket != null ? String(last.mt5_ticket) : "";
  const fill = findJournalFill(journalItems, cycleTicket || undefined);

  // Prefer journal when it has deal + ticket (complete fill path)
  if (fill) {
    const ticket = str(fill.ticket ?? fill.mt5_ticket, cycleTicket || "—");
    const deal = str(fill.deal ?? fill.deal_id, "—");
    const oms = str(
      fill.request_id || fill.oms_request_id || last.oms_message || last.trace_id,
      "—",
    );
    const brokerReq = str(
      fill.broker_request_id || fill.request_id || fill.client_order_id,
      "—",
    );
    const brokerResp = str(
      fill.retcode ?? fill.broker_retcode ?? last.broker_retcode,
      "—",
    );
    const requestId = str(fill.request_id, "");
    const audit =
      auditItems.find((a) => str(a.request_id) === requestId) ??
      auditItems.find((a) => str(a.ticket ?? a.mt5_ticket) === ticket);

    return {
      utcTimestamp: str(
        fill.timestamp || fill.submitted_at || fill.created_at,
        cycleAt,
      ),
      session: str(fill.session || diag.trading_session, "—"),
      signalId: str(fill.signal_id || last.signal_id, "—"),
      quality: str(fill.quality, parseQuality(reasons)),
      confluence: str(fill.confluence, parseConfluence(reasons)),
      decisionId: str(
        fill.decision_id || last.decision_id || last.trace_id,
        "—",
      ),
      riskResult: str(
        fill.risk_result,
        outcome.includes("risk") ? "FAIL" : "PASS",
      ),
      safetyResult: str(
        fill.safety_result,
        safetyReasons.length || outcome.includes("safety") ? "BLOCK" : "PASS",
      ),
      omsRequestId: oms,
      brokerRequestId: brokerReq,
      brokerResponse: brokerResp,
      mt5Ticket: ticket,
      dealId: deal,
      entryPrice: str(fill.price ?? fill.fill_price ?? fill.entry, "—"),
      stopLoss: str(fill.stop_loss ?? fill.sl, "—"),
      takeProfit: str(fill.take_profit ?? fill.tp, "—"),
      executionLatency:
        fill.latency_ms != null
          ? `${str(fill.latency_ms)} ms`
          : last.latency_ms != null
            ? `${str(last.latency_ms)} ms`
            : "—",
      journalId: str(fill.id || fill.request_id, "—"),
      auditId: str(audit?.id, "—"),
      source: "journal",
    };
  }

  // Live cycle only — usually incomplete without deal; still observe
  if (last.mt5_ticket != null && bool(last.forwarded_to_oms)) {
    return {
      utcTimestamp: cycleAt,
      session: str(diag.trading_session || last.session, "—"),
      signalId: str(last.signal_id, "—"),
      quality: parseQuality(reasons),
      confluence: parseConfluence(reasons),
      decisionId: str(last.decision_id || last.trace_id, "—"),
      riskResult: outcome.includes("risk") ? "FAIL" : "PASS",
      safetyResult:
        safetyReasons.length || outcome.includes("safety") ? "BLOCK" : "PASS",
      omsRequestId: str(last.oms_message || last.trace_id, "—"),
      brokerRequestId: str(last.broker_request_id || last.trace_id, "—"),
      brokerResponse:
        last.broker_retcode != null ? String(last.broker_retcode) : "—",
      mt5Ticket: String(last.mt5_ticket),
      dealId: str(last.deal_id || last.deal, "—"),
      entryPrice: str(last.entry_price || last.price, "—"),
      stopLoss: str(last.stop_loss || last.sl, "—"),
      takeProfit: str(last.take_profit || last.tp, "—"),
      executionLatency:
        last.latency_ms != null ? `${str(last.latency_ms)} ms` : "—",
      journalId: str(last.trace_id, "—"),
      auditId: str(last.trace_id, "—"),
      source: "live_cycle",
    };
  }

  return null;
}

export function reconcileFirstExecutionEvidence(input: {
  autoTrading: unknown;
  journal: unknown;
  audits: unknown;
  existing: FirstExecutionEvidenceRecord | null;
}): {
  record: FirstExecutionEvidenceRecord | null;
  storePatch: EvidenceStore;
} {
  const candidate = observeFirstExecutionCandidate(input);
  const locked = lockFirstExecutionIfEligible(candidate, input.existing);
  const storePatch: EvidenceStore = { record: locked };
  return { record: locked, storePatch };
}

export const EVIDENCE_FIELD_LABELS: { key: keyof FirstExecutionEvidenceRecord; label: string }[] = [
  { key: "utcTimestamp", label: "UTC Timestamp" },
  { key: "session", label: "Session" },
  { key: "signalId", label: "Signal ID" },
  { key: "quality", label: "Quality" },
  { key: "confluence", label: "Confluence" },
  { key: "decisionId", label: "Decision ID" },
  { key: "riskResult", label: "Risk Result" },
  { key: "safetyResult", label: "Safety Result" },
  { key: "omsRequestId", label: "OMS Request ID" },
  { key: "brokerRequestId", label: "Broker Request ID" },
  { key: "brokerResponse", label: "Broker Response" },
  { key: "mt5Ticket", label: "MT5 Ticket" },
  { key: "dealId", label: "Deal ID" },
  { key: "entryPrice", label: "Entry Price" },
  { key: "stopLoss", label: "Stop Loss" },
  { key: "takeProfit", label: "Take Profit" },
  { key: "executionLatency", label: "Execution Latency" },
  { key: "journalId", label: "Journal ID" },
  { key: "auditId", label: "Audit ID" },
];

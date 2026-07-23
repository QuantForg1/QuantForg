/** Automatic Production Acceptance Engine — evidence-only, write-once.

Never mutates Strategy, Risk, Safety, OMS, MT5, or session rules.
Never infers missing evidence. No manual override.
*/
import { asList, asRecord, bool, str } from "@/lib/desk";
import {
  type FirstExecutionEvidenceRecord,
  isBrokerAccepted,
  loadFirstExecutionEvidence,
  observeFirstExecutionCandidate,
  saveFirstExecutionEvidence,
} from "@/lib/first-execution-evidence";

const REPORT_KEY = "quantforg.automatic_acceptance_report.v1";

export type AcceptanceStatus = "WAITING" | "PRODUCTION ACCEPTED";

export type EvidenceItem = {
  id: string;
  label: string;
  present: boolean;
  mark: "✓" | "⏳";
  detail: string;
};

export type AcceptanceReport = {
  /** Immutable once generated */
  immutable: true;
  status: "PRODUCTION ACCEPTED";
  generatedAtUtc: string;
  evidence: {
    signalId: string;
    decisionId: string;
    decisionPass: boolean;
    riskPass: boolean;
    safetyPass: boolean;
    omsForward: boolean;
    omsRequestId: string;
    brokerAccepted: boolean;
    brokerResponse: string;
    mt5Ticket: string;
    dealId: string;
    journalId: string;
    session: string;
    quality: string;
    confluence: string;
    latency: string;
    snapshotPresent: boolean;
    utcTimestamp: string;
  };
  checklist: EvidenceItem[];
};

export type ObservedEvidence = {
  snapshot: boolean;
  signalGenerated: boolean;
  decisionPass: boolean;
  riskPass: boolean;
  safetyPass: boolean;
  omsForward: boolean;
  brokerAccepted: boolean;
  mt5Ticket: boolean;
  dealId: boolean;
  journalEntry: boolean;
  /** Raw observed fields — empty string means not observed */
  fields: {
    signalId: string;
    decisionId: string;
    riskResult: string;
    safetyResult: string;
    omsRequestId: string;
    brokerResponse: string;
    mt5Ticket: string;
    dealId: string;
    journalId: string;
    session: string;
    quality: string;
    confluence: string;
    latency: string;
    utcTimestamp: string;
    snapshotPresent: boolean;
  };
};

function present(value: string | null | undefined): boolean {
  const v = (value ?? "").trim();
  return v !== "" && v !== "—";
}

function isPass(result: string): boolean {
  const r = result.trim().toUpperCase();
  return r === "PASS" || r === "OK" || r === "CLEAR" || r === "SUCCESS";
}

/** Full gate — every required item must be observed, never inferred. */
export function allRequiredEvidencePresent(obs: ObservedEvidence): boolean {
  return (
    obs.signalGenerated &&
    obs.decisionPass &&
    obs.riskPass &&
    obs.safetyPass &&
    obs.omsForward &&
    obs.brokerAccepted &&
    obs.mt5Ticket &&
    obs.dealId &&
    obs.journalEntry
  );
}

export function buildChecklist(obs: ObservedEvidence): EvidenceItem[] {
  const row = (
    id: string,
    label: string,
    ok: boolean,
    detail: string,
  ): EvidenceItem => ({
    id,
    label,
    present: ok,
    mark: ok ? "✓" : "⏳",
    detail: ok ? detail || "observed" : "Waiting",
  });

  return [
    row("snapshot", "Snapshot", obs.snapshot, "present"),
    row(
      "signal",
      "Signal generated",
      obs.signalGenerated,
      obs.fields.signalId,
    ),
    row(
      "decision",
      "Decision PASS",
      obs.decisionPass,
      obs.fields.decisionId || "PASS",
    ),
    row("risk", "Risk PASS", obs.riskPass, obs.fields.riskResult || "PASS"),
    row(
      "safety",
      "Safety PASS",
      obs.safetyPass,
      obs.fields.safetyResult || "PASS",
    ),
    row(
      "oms",
      "OMS Forward",
      obs.omsForward,
      obs.fields.omsRequestId,
    ),
    row(
      "broker",
      "Broker Accepted",
      obs.brokerAccepted,
      obs.fields.brokerResponse,
    ),
    row("mt5", "MT5 Ticket", obs.mt5Ticket, obs.fields.mt5Ticket),
    row("deal", "Deal ID", obs.dealId, obs.fields.dealId),
    row("journal", "Journal Entry", obs.journalEntry, obs.fields.journalId),
  ];
}

export function missingEvidenceLabels(checklist: EvidenceItem[]): string[] {
  return checklist.filter((i) => !i.present).map((i) => i.label);
}

export function loadAcceptanceReport(): AcceptanceReport | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(REPORT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AcceptanceReport;
    if (parsed?.immutable && parsed.status === "PRODUCTION ACCEPTED") {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Persist report only once. Existing immutable report is never overwritten.
 */
export function freezeAcceptanceReport(
  report: AcceptanceReport,
): AcceptanceReport {
  if (typeof window === "undefined") return report;
  const existing = loadAcceptanceReport();
  if (existing?.immutable) return existing;
  try {
    window.localStorage.setItem(REPORT_KEY, JSON.stringify(report));
  } catch {
    /* quota */
  }
  return report;
}

export function observeAcceptanceEvidence(input: {
  autoTrading: unknown;
  journal: unknown;
  audits: unknown;
}): ObservedEvidence {
  const auto = asRecord(input.autoTrading);
  const orch = asRecord(auto.orchestrator);
  const last = asRecord(orch.last_cycle);
  const diag = asRecord(last.market_context_diagnostics);
  const candidate = observeFirstExecutionCandidate(input);

  const journalItems = asList(
    asRecord(input.journal).items ??
      asRecord(input.journal).entries ??
      input.journal,
  ).map(asRecord);

  const outcome = str(last.cycle_outcome, "").toLowerCase();
  const safetyReasons = asList(last.safety_failed_reasons).map(String);
  const decisionReasons = asList(last.decision_reasons).map(String);

  const signalId = str(
    candidate?.signalId || last.signal_id,
    "",
  );
  const decisionId = str(
    candidate?.decisionId || last.decision_id || last.trace_id,
    "",
  );

  // Never infer PASS — only use explicit observed results from candidate/journal
  let riskResult = str(candidate?.riskResult, "");
  let safetyResult = str(candidate?.safetyResult, "");
  if (!present(riskResult) && present(str(last.risk_result, ""))) {
    riskResult = str(last.risk_result);
  }
  if (!present(safetyResult) && present(str(last.safety_result, ""))) {
    safetyResult = str(last.safety_result);
  }
  // Explicit fails from cycle (observed blockers) — still not inventing PASS
  if (
    !present(riskResult) &&
    (outcome.includes("risk") ||
      decisionReasons.some((r) => /risk\s*reject/i.test(r)))
  ) {
    riskResult = "FAIL";
  }
  if (
    !present(safetyResult) &&
    (safetyReasons.length > 0 ||
      outcome.includes("safety") ||
      outcome === "safety_blocked")
  ) {
    safetyResult = "BLOCK";
  }

  const omsRequestId = str(
    candidate?.omsRequestId || last.oms_message || "",
    "",
  );
  // OMS forward: only observed flag or observed request id with ticket — never invent
  const omsObserved =
    bool(last.forwarded_to_oms) === true ||
    (present(omsRequestId) &&
      present(
        str(
          candidate?.mt5Ticket ??
            (last.mt5_ticket != null ? String(last.mt5_ticket) : ""),
          "",
        ),
      ));

  const brokerResponse = str(
    candidate?.brokerResponse ??
      (last.broker_retcode != null ? String(last.broker_retcode) : ""),
    "",
  );
  const brokerOk = isBrokerAccepted(brokerResponse);

  const mt5Ticket = str(
    candidate?.mt5Ticket ??
      (last.mt5_ticket != null ? String(last.mt5_ticket) : ""),
    "",
  );
  const dealId = str(candidate?.dealId, "");
  const journalId = str(candidate?.journalId, "");

  const journalHit =
    present(journalId) ||
    (present(mt5Ticket) &&
      journalItems.some(
        (j) => str(j.ticket ?? j.mt5_ticket) === mt5Ticket,
      ));

  const snapshot =
    bool(last.snapshot_present) || str(diag.snapshot) === "OK";

  // Decision PASS: only when an explicit decision_action is observed as a trade path,
  // or a complete fill candidate recorded decision — never invent from silence
  const decisionAction = str(last.decision_action, "");
  const decisionPass =
    (present(decisionAction) &&
      !/reject|block|abort|deny/i.test(decisionAction)) ||
    (present(decisionId) && present(mt5Ticket) && present(dealId));

  const riskPass = present(riskResult) && isPass(riskResult);
  const safetyPass = present(safetyResult) && isPass(safetyResult);

  return {
    snapshot,
    signalGenerated: present(signalId),
    decisionPass,
    riskPass,
    safetyPass,
    omsForward: omsObserved,
    brokerAccepted: brokerOk,
    mt5Ticket: present(mt5Ticket),
    dealId: present(dealId),
    journalEntry: journalHit,
    fields: {
      signalId: present(signalId) ? signalId : "",
      decisionId: present(decisionId) ? decisionId : "",
      riskResult: present(riskResult) ? riskResult : "",
      safetyResult: present(safetyResult) ? safetyResult : "",
      omsRequestId: present(omsRequestId) ? omsRequestId : "",
      brokerResponse: present(brokerResponse) ? brokerResponse : "",
      mt5Ticket: present(mt5Ticket) ? mt5Ticket : "",
      dealId: present(dealId) ? dealId : "",
      journalId: present(journalId)
        ? journalId
        : journalHit && present(mt5Ticket)
          ? `ticket:${mt5Ticket}`
          : "",
      session: str(candidate?.session || diag.trading_session, ""),
      quality: str(candidate?.quality, ""),
      confluence: str(candidate?.confluence, ""),
      latency: str(candidate?.executionLatency, ""),
      utcTimestamp: str(
        candidate?.utcTimestamp || last.observed_at,
        "",
      ),
      snapshotPresent: snapshot,
    },
  };
}

export type AutoAcceptanceModel = {
  status: AcceptanceStatus;
  statusLabel: string;
  checklist: EvidenceItem[];
  missing: string[];
  report: AcceptanceReport | null;
  observedAt: string;
};

export function runAutomaticAcceptanceEngine(input: {
  autoTrading: unknown;
  journal: unknown;
  audits: unknown;
}): AutoAcceptanceModel {
  const frozen = loadAcceptanceReport();
  if (frozen?.immutable) {
    return {
      status: "PRODUCTION ACCEPTED",
      statusLabel: "✅ PRODUCTION ACCEPTED",
      checklist: frozen.checklist,
      missing: [],
      report: frozen,
      observedAt: frozen.generatedAtUtc,
    };
  }

  const obs = observeAcceptanceEvidence(input);
  const checklist = buildChecklist(obs);
  const missing = missingEvidenceLabels(checklist);

  if (!allRequiredEvidencePresent(obs)) {
    return {
      status: "WAITING",
      statusLabel: "WAITING",
      checklist,
      missing,
      report: null,
      observedAt: obs.fields.utcTimestamp || new Date().toISOString(),
    };
  }

  // All evidence observed — freeze report + first-execution record
  const generatedAtUtc = new Date().toISOString();
  const report: AcceptanceReport = {
    immutable: true,
    status: "PRODUCTION ACCEPTED",
    generatedAtUtc,
    evidence: {
      signalId: obs.fields.signalId,
      decisionId: obs.fields.decisionId,
      decisionPass: true,
      riskPass: true,
      safetyPass: true,
      omsForward: true,
      omsRequestId: obs.fields.omsRequestId,
      brokerAccepted: true,
      brokerResponse: obs.fields.brokerResponse,
      mt5Ticket: obs.fields.mt5Ticket,
      dealId: obs.fields.dealId,
      journalId: obs.fields.journalId,
      session: obs.fields.session,
      quality: obs.fields.quality,
      confluence: obs.fields.confluence,
      latency: obs.fields.latency,
      snapshotPresent: obs.snapshot,
      utcTimestamp: obs.fields.utcTimestamp || generatedAtUtc,
    },
    checklist,
  };

  const lockedReport = freezeAcceptanceReport(report);

  // Also lock first-execution evidence when complete (never overwrite if already locked)
  const existing = loadFirstExecutionEvidence().record;
  if (!existing?.locked) {
    const candidate = observeFirstExecutionCandidate(input);
    if (candidate) {
      const locked: FirstExecutionEvidenceRecord = {
        ...candidate,
        locked: true,
        lockedAt: generatedAtUtc,
        signalId: obs.fields.signalId || candidate.signalId,
        decisionId: obs.fields.decisionId || candidate.decisionId,
        riskResult: "PASS",
        safetyResult: "PASS",
        omsRequestId: obs.fields.omsRequestId || candidate.omsRequestId,
        brokerResponse: obs.fields.brokerResponse || candidate.brokerResponse,
        mt5Ticket: obs.fields.mt5Ticket || candidate.mt5Ticket,
        dealId: obs.fields.dealId || candidate.dealId,
        journalId: obs.fields.journalId || candidate.journalId,
      };
      saveFirstExecutionEvidence({ record: locked });
    }
  }

  return {
    status: "PRODUCTION ACCEPTED",
    statusLabel: "✅ PRODUCTION ACCEPTED",
    checklist: lockedReport.checklist,
    missing: [],
    report: lockedReport,
    observedAt: lockedReport.generatedAtUtc,
  };
}

/** Operations Runbook — read-only operator guidance by execution state.

Never mutates Strategy, Risk, Safety, OMS, or MT5. Guidance only.
*/
import { asList, asRecord, bool, str } from "@/lib/desk";
import {
  loadAcceptanceReport,
  observeAcceptanceEvidence,
  type ObservedEvidence,
} from "@/lib/automatic-production-acceptance";

export type RunbookState =
  | "WAITING"
  | "READY"
  | "BLOCKED"
  | "EXECUTING"
  | "EXECUTED"
  | "FAILED";

export type RunbookEntry = {
  state: RunbookState;
  currentCondition: string;
  blockingReason: string | null;
  evidence: string[];
  operatorAction: string;
};

export type OperationsRunbookModel = {
  activeState: RunbookState;
  entries: RunbookEntry[];
  active: RunbookEntry;
  observedAt: string;
  session: string;
};

const STATIC_GUIDANCE: Record<
  RunbookState,
  Pick<RunbookEntry, "currentCondition" | "operatorAction">
> = {
  WAITING: {
    currentCondition:
      "Production is live but not yet in an eligible execution window or awaiting signal.",
    operatorAction: "Continue monitoring until an allowed session.",
  },
  READY: {
    currentCondition:
      "Allowed session with Risk and Safety clear — system ready for eligible flow.",
    operatorAction: "Observe OMS forwarding.",
  },
  BLOCKED: {
    currentCondition: "An observed gate blocked progression this cycle.",
    operatorAction:
      "Do not override. Confirm blocker is expected (session/risk/safety). Keep monitoring.",
  },
  EXECUTING: {
    currentCondition: "OMS forward observed; broker/MT5 path in progress.",
    operatorAction:
      "Watch broker response and MT5 ticket. Do not resubmit or bypass OMS.",
  },
  EXECUTED: {
    currentCondition: "End-to-end fill evidence observed.",
    operatorAction:
      "Archive First Execution Evidence. Mark Production Accepted (automatic engine).",
  },
  FAILED: {
    currentCondition: "Observed hard failure on risk, broker, or execution path.",
    operatorAction:
      "Investigate failure evidence only. Do not change Strategy/Risk/Safety/OMS/MT5 from this desk.",
  },
};

function present(v: string | null | undefined): boolean {
  const s = (v ?? "").trim();
  return s !== "" && s !== "—";
}

export function deriveRunbookState(input: {
  autoTrading: unknown;
  obs: ObservedEvidence;
  accepted: boolean;
}): RunbookState {
  if (input.accepted) return "EXECUTED";

  const auto = asRecord(input.autoTrading);
  const orch = asRecord(auto.orchestrator);
  const last = asRecord(orch.last_cycle);
  const outcome = str(last.cycle_outcome, "").toLowerCase();
  const safetyReasons = asList(last.safety_failed_reasons).map(String);
  const obs = input.obs;

  if (obs.mt5Ticket && obs.dealId && obs.omsForward && obs.brokerAccepted) {
    return "EXECUTED";
  }

  if (obs.omsForward && !obs.mt5Ticket) {
    return "EXECUTING";
  }

  const brokerFail =
    present(obs.fields.brokerResponse) && !obs.brokerAccepted;
  const riskFail = present(obs.fields.riskResult) && !obs.riskPass;
  const hardFail =
    brokerFail ||
    riskFail ||
    outcome.includes("risk") ||
    (last.broker_retcode != null &&
      Number(last.broker_retcode) !== 0 &&
      Number(last.broker_retcode) !== 10009);

  if (hardFail && !obs.mt5Ticket) {
    return "FAILED";
  }

  const sessionBlocked =
    outcome === "safety_blocked" ||
    safetyReasons.some((r) => /session/i.test(r)) ||
    bool(asRecord(last.market_context_diagnostics).session_allowed) === false;

  if (sessionBlocked || (present(obs.fields.safetyResult) && !obs.safetyPass)) {
    // Session / safety block while waiting for eligibility
    if (sessionBlocked) return "WAITING";
    return "BLOCKED";
  }

  if (
    obs.snapshot &&
    bool(asRecord(last.market_context_diagnostics).session_allowed) &&
    obs.riskPass &&
    obs.safetyPass
  ) {
    return "READY";
  }

  if (obs.signalGenerated && obs.decisionPass && (!obs.riskPass || !obs.safetyPass)) {
    return "BLOCKED";
  }

  return "WAITING";
}

function evidenceForState(
  state: RunbookState,
  obs: ObservedEvidence,
  last: Record<string, unknown>,
): { evidence: string[]; blockingReason: string | null } {
  const safetyReasons = asList(last.safety_failed_reasons).map(String);
  const detail = str(last.detail || last.abort_reason, "");
  const session = str(
    asRecord(last.market_context_diagnostics).trading_session ||
      obs.fields.session,
    "—",
  );

  switch (state) {
    case "WAITING": {
      const reasons = [
        ...safetyReasons,
        detail && /session/i.test(detail) ? detail : "",
      ].filter(Boolean);
      const evidence =
        reasons.length > 0
          ? reasons
          : [
              obs.snapshot ? "Snapshot present" : "Awaiting snapshot",
              `Session: ${session}`,
            ];
      return {
        evidence,
        blockingReason: reasons[0] || null,
      };
    }
    case "READY":
      return {
        evidence: [
          "Allowed session",
          obs.riskPass ? "Risk PASS" : "Risk observed clear",
          obs.safetyPass ? "Safety PASS" : "Safety observed clear",
        ],
        blockingReason: null,
      };
    case "BLOCKED":
      return {
        evidence: [
          ...safetyReasons,
          present(obs.fields.riskResult) ? `Risk: ${obs.fields.riskResult}` : "",
          present(obs.fields.safetyResult)
            ? `Safety: ${obs.fields.safetyResult}`
            : "",
          detail,
        ].filter(Boolean),
        blockingReason:
          safetyReasons[0] ||
          detail ||
          obs.fields.riskResult ||
          obs.fields.safetyResult ||
          "Blocked",
      };
    case "EXECUTING":
      return {
        evidence: [
          obs.omsForward ? "OMS Forward" : "",
          present(obs.fields.omsRequestId)
            ? `OMS Request: ${obs.fields.omsRequestId}`
            : "",
          present(obs.fields.brokerResponse)
            ? `Broker: ${obs.fields.brokerResponse}`
            : "Awaiting broker response",
        ].filter(Boolean),
        blockingReason: null,
      };
    case "EXECUTED":
      return {
        evidence: [
          "OMS Forward",
          "Broker Accepted",
          present(obs.fields.mt5Ticket)
            ? `MT5 Ticket: ${obs.fields.mt5Ticket}`
            : "MT5 Ticket",
          present(obs.fields.dealId) ? `Deal ID: ${obs.fields.dealId}` : "Deal ID",
        ],
        blockingReason: null,
      };
    case "FAILED":
      return {
        evidence: [
          present(obs.fields.brokerResponse)
            ? `Broker: ${obs.fields.brokerResponse}`
            : "",
          present(obs.fields.riskResult) ? `Risk: ${obs.fields.riskResult}` : "",
          detail,
          str(last.cycle_outcome, ""),
        ].filter(Boolean),
        blockingReason:
          detail ||
          obs.fields.brokerResponse ||
          obs.fields.riskResult ||
          "Execution failed",
      };
  }
}

export function buildOperationsRunbookModel(input: {
  autoTrading: unknown;
  journal: unknown;
  audits: unknown;
}): OperationsRunbookModel {
  const obs = observeAcceptanceEvidence(input);
  const accepted = loadAcceptanceReport()?.immutable === true;
  const activeState = deriveRunbookState({
    autoTrading: input.autoTrading,
    obs,
    accepted,
  });

  const auto = asRecord(input.autoTrading);
  const last = asRecord(asRecord(auto.orchestrator).last_cycle);
  const diag = asRecord(last.market_context_diagnostics);
  const session = str(diag.trading_session || obs.fields.session, "—");
  const observedAt = str(
    last.observed_at || obs.fields.utcTimestamp,
    new Date().toISOString(),
  );

  const states: RunbookState[] = [
    "WAITING",
    "READY",
    "BLOCKED",
    "EXECUTING",
    "EXECUTED",
    "FAILED",
  ];

  const entries: RunbookEntry[] = states.map((state) => {
    const guide = STATIC_GUIDANCE[state];
    const live =
      state === activeState
        ? evidenceForState(state, obs, last)
        : { evidence: [] as string[], blockingReason: null as string | null };

    // Template examples for non-active states (operator education)
    const templateEvidence: Record<RunbookState, string[]> = {
      WAITING: ["Session 'tokyo' not allowed"],
      READY: ["Allowed session", "Risk PASS", "Safety PASS"],
      BLOCKED: ["Safety or risk rejection observed"],
      EXECUTING: ["OMS Forward", "Awaiting broker / MT5"],
      EXECUTED: ["OMS Forward", "Broker Accepted", "MT5 Ticket", "Deal ID"],
      FAILED: ["Broker reject or risk FAIL"],
    };

    return {
      state,
      currentCondition: guide.currentCondition,
      blockingReason:
        state === activeState ? live.blockingReason : null,
      evidence:
        state === activeState && live.evidence.length
          ? live.evidence
          : templateEvidence[state],
      operatorAction: guide.operatorAction,
    };
  });

  const active = entries.find((e) => e.state === activeState) ?? entries[0];

  return {
    activeState,
    entries,
    active,
    observedAt,
    session,
  };
}

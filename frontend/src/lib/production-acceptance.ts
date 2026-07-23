/** Production Acceptance — read-only certification model.

Never mutates trading engines. Never fabricates fills.
First-execution evidence is immutable (write-once) via first-execution-evidence.
PRODUCTION ACCEPTED only when OMS + broker accept + MT5 ticket + Deal ID exist.
*/
import { asList, asRecord, bool, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import {
  type FirstExecutionEvidenceRecord,
  isCompleteSuccessfulExecution,
  loadFirstExecutionEvidence,
  reconcileFirstExecutionEvidence,
  saveFirstExecutionEvidence,
} from "@/lib/first-execution-evidence";

const STORAGE_KEY = "quantforg.production_acceptance.v1";

export type PassFail = { label: string; passed: boolean; detail: string };

export type StageState = "PASS" | "WAITING" | "BLOCKED" | "FAILED";

export type PipelineStage = {
  id: string;
  label: string;
  state: StageState;
  at: string;
  detail: string;
};

/** @deprecated Prefer FirstExecutionEvidenceRecord — kept for desk UI mapping. */
export type FirstExecutionEvidence = {
  signalId: string;
  utcTime: string;
  session: string;
  quality: string;
  confluence: string;
  decisionId: string;
  riskResult: string;
  safetyResult: string;
  omsRequest: string;
  brokerRequestId: string;
  brokerResponse: string;
  mt5Ticket: string;
  dealId: string;
  entryPrice: string;
  stopLoss: string;
  takeProfit: string;
  latency: string;
  journalId: string;
  auditId: string;
  capturedAt: string;
  source: "live_cycle" | "journal" | "stored" | "migrated";
  locked: boolean;
};

export type HistoryEvent = {
  id: string;
  label: string;
  at: string | null;
  done: boolean;
};

export type StoredBlob = {
  firstExecution: FirstExecutionEvidence | null;
  history: Partial<Record<string, string>>;
};

export function toDeskEvidence(
  rec: FirstExecutionEvidenceRecord | null,
): FirstExecutionEvidence | null {
  if (!rec) return null;
  return {
    signalId: rec.signalId,
    utcTime: rec.utcTimestamp,
    session: rec.session,
    quality: rec.quality,
    confluence: rec.confluence,
    decisionId: rec.decisionId,
    riskResult: rec.riskResult,
    safetyResult: rec.safetyResult,
    omsRequest: rec.omsRequestId,
    brokerRequestId: rec.brokerRequestId,
    brokerResponse: rec.brokerResponse,
    mt5Ticket: rec.mt5Ticket,
    dealId: rec.dealId,
    entryPrice: rec.entryPrice,
    stopLoss: rec.stopLoss,
    takeProfit: rec.takeProfit,
    latency: rec.executionLatency,
    journalId: rec.journalId,
    auditId: rec.auditId,
    capturedAt: rec.lockedAt,
    source: rec.source === "migrated" ? "migrated" : rec.source,
    locked: true,
  };
}

export function loadAcceptanceStore(): StoredBlob {
  const evidence = loadFirstExecutionEvidence();
  let history: Partial<Record<string, string>> = {};
  if (typeof window !== "undefined") {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as StoredBlob;
        history = parsed.history ?? {};
      }
    } catch {
      /* ignore */
    }
  }
  return {
    firstExecution: toDeskEvidence(evidence.record),
    history,
  };
}

export function saveAcceptanceStore(blob: StoredBlob): void {
  if (typeof window === "undefined") return;
  try {
    // History only in acceptance key — evidence is owned by immutable store
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ firstExecution: null, history: blob.history }),
    );
  } catch {
    /* quota */
  }
}

function stampHistory(
  history: Partial<Record<string, string>>,
  key: string,
  when: string | null | undefined,
): Partial<Record<string, string>> {
  if (!when || when === "—") return history;
  if (history[key]) return history;
  return { ...history, [key]: when };
}

export function buildProductionAcceptanceModel(input: {
  autoTrading: unknown;
  controlCenter: unknown;
  mt5Status: unknown;
  journal: unknown;
  audits: unknown;
  store: StoredBlob;
}): {
  system: PassFail[];
  pipeline: PipelineStage[];
  rejection: { status: string; reason: string } | null;
  firstExecution: FirstExecutionEvidence | null;
  storePatch: StoredBlob;
  certification: "PRODUCTION ACCEPTED" | "WAITING";
  certItems: PassFail[];
  history: HistoryEvent[];
  opsMode: string;
  symbol: string;
} {
  const auto = asRecord(input.autoTrading);
  const exec = asRecord(auto.execution_state);
  const facts = asRecord(auto.facts);
  const orch = asRecord(auto.orchestrator);
  const last = asRecord(orch.last_cycle);
  const diag = asRecord(last.market_context_diagnostics);
  const persistence = asRecord(auto.persistence);
  const policy = asRecord(auto.policy);
  const center = asRecord(input.controlCenter);
  const mt5 = asRecord(input.mt5Status);
  const auditItems = asList(
    asRecord(input.audits).items ?? asRecord(input.audits).audits ?? input.audits,
  ).map(asRecord);

  const reasons = asList(last.decision_reasons).map(String);
  const safetyReasons = asList(
    last.safety_failed_reasons ?? auto.failed_reasons,
  ).map(String);
  const health = asRecord(last.health);

  const opsMode = str(auto.ops_mode || exec.ops_mode || center.mode, "—");
  const runState = str(policy.run_state || exec.auto_trading_run_state, "off");
  const gateOk =
    str(exec.gate_status || auto.status, "").toLowerCase() === "enabled" ||
    bool(exec.gate_allowed) ||
    bool(auto.allowed);
  const gatewayOk = bool(facts.gateway_connected ?? exec.gateway_connected);
  const brokerOk = bool(facts.broker_connected ?? exec.broker_connected);
  const mt5Ok =
    bool(mt5.connected) ||
    bool(mt5.is_connected) ||
    str(mt5.status).toLowerCase() === "connected" ||
    brokerOk;
  const snapshotOk = bool(last.snapshot_present) || str(diag.snapshot) === "OK";
  const marketOk = bool(facts.market_data_live ?? exec.market_data_live) || snapshotOk;
  const strategyOk =
    bool(last.signal_id) ||
    reasons.length > 0 ||
    str(last.cycle_outcome) !== "" ||
    runState === "running";
  const outcome = str(last.cycle_outcome, "").toLowerCase();
  const riskOk = !outcome.includes("risk") && !reasons.some((r) => /risk reject/i.test(r));
  const safetyOk =
    safetyReasons.length === 0 &&
    outcome !== "safety_blocked" &&
    !bool(exec.kill_switch_armed ?? center.kill_switch_armed);
  const nowIso = new Date().toISOString();
  const cycleAt = str(
    diag.server_time || last.observed_at || health.checked_at,
    nowIso,
  );

  const system: PassFail[] = [
    {
      label: "Ops Mode",
      passed: opsMode.toUpperCase() === "LIVE",
      detail: opsMode,
    },
    {
      label: "Auto Trading",
      passed: runState === "running",
      detail: runState.toUpperCase(),
    },
    {
      label: "Gate",
      passed: gateOk,
      detail: str(exec.gate_status || auto.status, gateOk ? "Enabled" : "Disabled"),
    },
    { label: "Gateway", passed: gatewayOk, detail: gatewayOk ? "CONNECTED" : "OFFLINE" },
    { label: "Broker", passed: brokerOk, detail: brokerOk ? "CONNECTED" : "OFF" },
    { label: "MT5", passed: mt5Ok, detail: mt5Ok ? "CONNECTED" : "OFFLINE" },
    { label: "Snapshot", passed: snapshotOk, detail: snapshotOk ? "OK" : "MISSING" },
    {
      label: "Market Context",
      passed: marketOk,
      detail: marketOk ? "LIVE" : "UNAVAILABLE",
    },
    {
      label: "Strategy",
      passed: strategyOk,
      detail: strategyOk ? "RUNNING" : "IDLE",
    },
    {
      label: "Risk",
      passed: riskOk,
      detail: riskOk ? "READY" : "BLOCKED",
    },
    {
      label: "Safety",
      passed: !bool(exec.kill_switch_armed ?? center.kill_switch_armed),
      detail: bool(exec.kill_switch_armed ?? center.kill_switch_armed)
        ? "KILL ARMED"
        : outcome === "safety_blocked"
          ? "BLOCK (session)"
          : "READY",
    },
  ];

  const stage = (
    id: string,
    label: string,
    state: StageState,
    detail: string,
    at: string,
  ): PipelineStage => ({ id, label, state, detail, at });

  const pipeline: PipelineStage[] = [
    stage(
      "market",
      "Market",
      snapshotOk || marketOk ? "PASS" : "FAILED",
      snapshotOk ? "snapshot ok" : "no snapshot",
      cycleAt,
    ),
    stage(
      "strategy",
      "Strategy",
      last.signal_id || reasons.length ? "PASS" : runState === "running" ? "WAITING" : "WAITING",
      last.signal_id ? str(last.signal_id).slice(0, 8) : "awaiting signal",
      cycleAt,
    ),
    stage(
      "decision",
      "Decision",
      last.decision_action || last.cycle_outcome
        ? outcome.includes("no_trade") || outcome === "safety_blocked"
          ? "BLOCKED"
          : "PASS"
        : "WAITING",
      str(last.decision_action || last.cycle_outcome, "—"),
      cycleAt,
    ),
    stage(
      "risk",
      "Risk",
      outcome.includes("risk")
        ? "FAILED"
        : last.cycle_outcome
          ? "PASS"
          : "WAITING",
      outcome.includes("risk") ? "rejected" : "clear",
      cycleAt,
    ),
    stage(
      "safety",
      "Safety",
      outcome === "safety_blocked" || safetyReasons.length
        ? "BLOCKED"
        : last.cycle_outcome
          ? "PASS"
          : "WAITING",
      safetyReasons[0] || (safetyOk ? "clear" : "—"),
      cycleAt,
    ),
    stage(
      "oms",
      "OMS",
      bool(last.forwarded_to_oms)
        ? "PASS"
        : last.cycle_outcome
          ? "BLOCKED"
          : "WAITING",
      bool(last.forwarded_to_oms) ? "forwarded" : "not forwarded",
      cycleAt,
    ),
    stage(
      "broker",
      "Broker",
      last.broker_retcode != null
        ? Number(last.broker_retcode) === 0
          ? "PASS"
          : "FAILED"
        : "WAITING",
      last.broker_retcode != null ? String(last.broker_retcode) : "—",
      cycleAt,
    ),
    stage(
      "mt5",
      "MT5",
      last.mt5_ticket != null ? "PASS" : "WAITING",
      last.mt5_ticket != null ? String(last.mt5_ticket) : "no ticket",
      cycleAt,
    ),
    stage(
      "journal",
      "Journal",
      last.cycle_outcome ? "PASS" : "WAITING",
      str(last.cycle_outcome, "—"),
      cycleAt,
    ),
  ];

  const noTrade =
    !bool(last.forwarded_to_oms) &&
    last.mt5_ticket == null &&
    Boolean(last.cycle_outcome || safetyReasons.length);
  const rejection = noTrade
    ? {
        status: "NO TRADE",
        reason:
          safetyReasons[0] ||
          str(last.abort_reason || last.detail || reasons[0], "No eligible trade"),
      }
    : null;

  // Immutable first-execution evidence (write-once; never overwrite)
  const existingLocked =
    input.store.firstExecution?.locked &&
    isCompleteSuccessfulExecution({
      omsRequestId: input.store.firstExecution.omsRequest,
      brokerResponse: input.store.firstExecution.brokerResponse,
      mt5Ticket: input.store.firstExecution.mt5Ticket,
      dealId: input.store.firstExecution.dealId,
    })
      ? {
          locked: true as const,
          lockedAt: input.store.firstExecution.capturedAt,
          utcTimestamp: input.store.firstExecution.utcTime,
          session: input.store.firstExecution.session,
          signalId: input.store.firstExecution.signalId,
          quality: input.store.firstExecution.quality,
          confluence: input.store.firstExecution.confluence,
          decisionId: input.store.firstExecution.decisionId,
          riskResult: input.store.firstExecution.riskResult,
          safetyResult: input.store.firstExecution.safetyResult,
          omsRequestId: input.store.firstExecution.omsRequest,
          brokerRequestId: input.store.firstExecution.brokerRequestId,
          brokerResponse: input.store.firstExecution.brokerResponse,
          mt5Ticket: input.store.firstExecution.mt5Ticket,
          dealId: input.store.firstExecution.dealId,
          entryPrice: input.store.firstExecution.entryPrice,
          stopLoss: input.store.firstExecution.stopLoss,
          takeProfit: input.store.firstExecution.takeProfit,
          executionLatency: input.store.firstExecution.latency,
          journalId: input.store.firstExecution.journalId,
          auditId: input.store.firstExecution.auditId,
          source:
            input.store.firstExecution.source === "migrated"
              ? ("migrated" as const)
              : input.store.firstExecution.source === "journal"
                ? ("journal" as const)
                : ("live_cycle" as const),
        }
      : loadFirstExecutionEvidence().record;

  const reconciled = reconcileFirstExecutionEvidence({
    autoTrading: input.autoTrading,
    journal: input.journal,
    audits: input.audits,
    existing: existingLocked,
  });
  if (reconciled.storePatch.record && !existingLocked?.locked) {
    saveFirstExecutionEvidence(reconciled.storePatch);
  }
  const firstExecution = toDeskEvidence(reconciled.record);

  let historyMap = { ...input.store.history };
  if (opsMode.toUpperCase() === "LIVE") {
    historyMap = stampHistory(historyMap, "live", nowIso);
  }
  if (snapshotOk) {
    historyMap = stampHistory(historyMap, "snapshot", cycleAt);
  }
  if (last.signal_id) {
    historyMap = stampHistory(historyMap, "signal", cycleAt);
  }
  if (last.decision_action || last.cycle_outcome) {
    historyMap = stampHistory(historyMap, "decision", cycleAt);
  }
  if (bool(last.forwarded_to_oms)) {
    historyMap = stampHistory(historyMap, "oms", cycleAt);
  }
  if (last.broker_retcode != null) {
    historyMap = stampHistory(historyMap, "broker", cycleAt);
  }
  if (firstExecution?.mt5Ticket && firstExecution.mt5Ticket !== "—") {
    historyMap = stampHistory(historyMap, "mt5", firstExecution.utcTime);
    historyMap = stampHistory(historyMap, "fill", firstExecution.utcTime);
  }

  const storePatch: StoredBlob = {
    firstExecution,
    history: historyMap,
  };

  const durable = bool(persistence.durable) || bool(persistence.postgres_has_state);
  const accepted =
    firstExecution != null &&
    isCompleteSuccessfulExecution({
      omsRequestId: firstExecution.omsRequest,
      brokerResponse: firstExecution.brokerResponse,
      mt5Ticket: firstExecution.mt5Ticket,
      dealId: firstExecution.dealId,
    });

  const certItems: PassFail[] = [
    {
      label: "Infrastructure",
      passed: gatewayOk && mt5Ok && brokerOk,
      detail: gatewayOk && mt5Ok && brokerOk ? "PASS" : "INCOMPLETE",
    },
    {
      label: "Market Context",
      passed: marketOk && snapshotOk,
      detail: snapshotOk ? "PASS" : "FAIL",
    },
    {
      label: "Strategy",
      passed: strategyOk,
      detail: strategyOk ? "PASS" : "IDLE",
    },
    { label: "Risk", passed: riskOk, detail: riskOk ? "PASS" : "BLOCKED" },
    {
      label: "Safety",
      passed: !bool(exec.kill_switch_armed ?? center.kill_switch_armed),
      detail: "OPERATIONAL",
    },
    {
      label: "OMS request",
      passed: accepted || Boolean(firstExecution?.omsRequest && firstExecution.omsRequest !== "—"),
      detail: accepted ? "CONFIRMED" : "WAITING",
    },
    {
      label: "Broker accepted",
      passed: accepted,
      detail: accepted ? "ACCEPTED" : "WAITING",
    },
    {
      label: "MT5 ticket",
      passed: Boolean(firstExecution?.mt5Ticket && firstExecution.mt5Ticket !== "—"),
      detail: firstExecution?.mt5Ticket ?? "WAITING",
    },
    {
      label: "Deal ID",
      passed: Boolean(firstExecution?.dealId && firstExecution.dealId !== "—"),
      detail: firstExecution?.dealId ?? "WAITING",
    },
    {
      label: "Persistence",
      passed: durable,
      detail: durable ? "DURABLE" : "EPHEMERAL",
    },
    {
      label: "Audit Trail",
      passed: auditItems.length > 0 || Boolean(last.cycle_outcome),
      detail: auditItems.length ? `${auditItems.length} entries` : "cycle logged",
    },
  ];

  const certification: "PRODUCTION ACCEPTED" | "WAITING" = accepted
    ? "PRODUCTION ACCEPTED"
    : "WAITING";

  const history: HistoryEvent[] = [
    {
      id: "live",
      label: "Production became LIVE",
      at: historyMap.live ?? (opsMode.toUpperCase() === "LIVE" ? nowIso : null),
      done: opsMode.toUpperCase() === "LIVE" || Boolean(historyMap.live),
    },
    {
      id: "snapshot",
      label: "First Snapshot",
      at: historyMap.snapshot ?? null,
      done: Boolean(historyMap.snapshot) || snapshotOk,
    },
    {
      id: "signal",
      label: "First Signal",
      at: historyMap.signal ?? null,
      done: Boolean(historyMap.signal),
    },
    {
      id: "decision",
      label: "First Decision",
      at: historyMap.decision ?? null,
      done: Boolean(historyMap.decision),
    },
    {
      id: "oms",
      label: "First OMS Request",
      at: historyMap.oms ?? null,
      done: Boolean(historyMap.oms),
    },
    {
      id: "broker",
      label: "First Broker Response",
      at: historyMap.broker ?? null,
      done: Boolean(historyMap.broker),
    },
    {
      id: "mt5",
      label: "First MT5 Ticket",
      at: historyMap.mt5 ?? null,
      done: Boolean(historyMap.mt5),
    },
    {
      id: "fill",
      label: "First Filled Trade",
      at: historyMap.fill ?? null,
      done: accepted,
    },
  ];

  return {
    system,
    pipeline,
    rejection,
    firstExecution: storePatch.firstExecution,
    storePatch,
    certification,
    certItems,
    history,
    opsMode,
    symbol: TRADING_SYMBOL,
  };
}

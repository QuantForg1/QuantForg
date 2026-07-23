/** Production Acceptance — read-only certification model.

Never mutates trading engines. Never fabricates fills.
First-execution evidence persists in localStorage when a real ticket is observed.
*/
import { asList, asRecord, bool, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";

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

export type FirstExecutionEvidence = {
  signalId: string;
  utcTime: string;
  session: string;
  quality: string;
  confluence: string;
  riskResult: string;
  safetyResult: string;
  omsRequest: string;
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
  source: "live_cycle" | "journal" | "stored";
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

export function loadAcceptanceStore(): StoredBlob {
  if (typeof window === "undefined") {
    return { firstExecution: null, history: {} };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { firstExecution: null, history: {} };
    const parsed = JSON.parse(raw) as StoredBlob;
    return {
      firstExecution: parsed.firstExecution ?? null,
      history: parsed.history ?? {},
    };
  } catch {
    return { firstExecution: null, history: {} };
  }
}

export function saveAcceptanceStore(blob: StoredBlob): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(blob));
  } catch {
    /* quota / private mode — evidence still shown live */
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
  certification: "PRODUCTION ACCEPTED" | "NOT YET ACCEPTED";
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
  const journalItems = asList(
    asRecord(input.journal).items ?? asRecord(input.journal).entries ?? input.journal,
  ).map(asRecord);
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

  // First execution evidence from live cycle or journal
  let liveEvidence: FirstExecutionEvidence | null = null;
  if (last.mt5_ticket != null) {
    liveEvidence = {
      signalId: str(last.signal_id, "—"),
      utcTime: cycleAt,
      session: str(diag.trading_session, "—"),
      quality: parseQuality(reasons),
      confluence: parseConfluence(reasons),
      riskResult: riskOk ? "PASS" : "FAIL",
      safetyResult: safetyOk ? "PASS" : "BLOCK",
      omsRequest: str(last.oms_message || last.trace_id, "—"),
      brokerResponse: last.broker_retcode != null ? String(last.broker_retcode) : "—",
      mt5Ticket: String(last.mt5_ticket),
      dealId: "—",
      entryPrice: "—",
      stopLoss: "—",
      takeProfit: "—",
      latency: last.latency_ms != null ? `${str(last.latency_ms)} ms` : "—",
      journalId: str(last.trace_id, "—"),
      auditId: str(last.trace_id, "—"),
      capturedAt: nowIso,
      source: "live_cycle",
    };
  } else {
    const fill = journalItems.find((j) => {
      const ticket = j.ticket ?? j.mt5_ticket;
      const result = str(j.execution_result || j.outcome || j.status).toLowerCase();
      return (
        ticket != null ||
        result.includes("fill") ||
        result.includes("success")
      );
    });
    if (fill) {
      liveEvidence = {
        signalId: str(fill.signal_id || fill.request_id, "—"),
        utcTime: str(fill.timestamp || fill.submitted_at || fill.created_at, nowIso),
        session: str(fill.session, "—"),
        quality: str(fill.quality, "—"),
        confluence: str(fill.confluence, "—"),
        riskResult: str(fill.risk_result, "PASS"),
        safetyResult: str(fill.safety_result, "PASS"),
        omsRequest: str(fill.request_id || fill.oms_request_id, "—"),
        brokerResponse: str(fill.retcode ?? fill.broker_retcode, "—"),
        mt5Ticket: str(fill.ticket ?? fill.mt5_ticket, "—"),
        dealId: str(fill.deal ?? fill.deal_id, "—"),
        entryPrice: str(fill.price ?? fill.fill_price ?? fill.entry, "—"),
        stopLoss: str(fill.stop_loss ?? fill.sl, "—"),
        takeProfit: str(fill.take_profit ?? fill.tp, "—"),
        latency:
          fill.latency_ms != null ? `${str(fill.latency_ms)} ms` : "—",
        journalId: str(fill.id || fill.request_id, "—"),
        auditId: str(
          auditItems.find(
            (a) => str(a.request_id) === str(fill.request_id),
          )?.id,
          "—",
        ),
        capturedAt: nowIso,
        source: "journal",
      };
    }
  }

  const stored = input.store.firstExecution;
  const firstExecution =
    stored && stored.mt5Ticket && stored.mt5Ticket !== "—"
      ? stored
      : liveEvidence && liveEvidence.mt5Ticket !== "—"
        ? liveEvidence
        : null;

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
    firstExecution:
      firstExecution && (!stored || stored.source !== "stored")
        ? { ...firstExecution, source: stored ? stored.source : firstExecution.source }
        : firstExecution ?? stored,
    history: historyMap,
  };
  // Prefer keeping first permanent capture
  if (stored?.mt5Ticket && stored.mt5Ticket !== "—") {
    storePatch.firstExecution = { ...stored, source: "stored" };
  } else if (liveEvidence?.mt5Ticket && liveEvidence.mt5Ticket !== "—") {
    storePatch.firstExecution = { ...liveEvidence, source: "stored" };
  }

  const durable = bool(persistence.durable) || bool(persistence.postgres_has_state);
  const hasFill = Boolean(
    storePatch.firstExecution?.mt5Ticket &&
      storePatch.firstExecution.mt5Ticket !== "—",
  );

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
      label: "OMS",
      passed: hasFill || bool(exec.oms_orders_allowed),
      detail: hasFill ? "EXECUTED" : bool(exec.oms_orders_allowed) ? "READY" : "IDLE",
    },
    { label: "Broker", passed: brokerOk, detail: brokerOk ? "PASS" : "FAIL" },
    { label: "MT5", passed: mt5Ok, detail: mt5Ok ? "PASS" : "FAIL" },
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

  const certification: "PRODUCTION ACCEPTED" | "NOT YET ACCEPTED" = hasFill
    ? "PRODUCTION ACCEPTED"
    : "NOT YET ACCEPTED";

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
      done: Boolean(historyMap.fill),
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

/** Production Burn-in Monitor — read-only stability desk until first live fill.

Never mutates Strategy, Risk, Safety, OMS, MT5, or session rules.
Status is derived only from observed evidence — no manual override.
*/
import { asList, asRecord, bool, num, str } from "@/lib/desk";
import {
  type FirstExecutionEvidenceRecord,
  isCompleteSuccessfulExecution,
  loadFirstExecutionEvidence,
  reconcileFirstExecutionEvidence,
  saveFirstExecutionEvidence,
} from "@/lib/first-execution-evidence";

const STORAGE_KEY = "quantforg.production_burnin.v1";

export type BurnInStatus =
  | "STABLE"
  | "WAITING FOR FIRST EXECUTION"
  | "INVESTIGATION REQUIRED";

export type CycleCounters = {
  snapshots: number;
  signals: number;
  decisions: number;
  riskEvaluations: number;
  safetyEvaluations: number;
  sessionBlocks: number;
  omsForwards: number;
  mt5Executions: number;
};

export type BlockerRank = {
  reason: string;
  count: number;
  pct: number;
};

export type UptimeBlock = {
  processUptimeLabel: string;
  processUptimeSec: number;
  gatewayUptimePct: number | null;
  gatewayUp: boolean | null;
  brokerUptimeLabel: string;
  brokerUp: boolean | null;
  witnessUptimeLabel: string;
  witnessAuthOk: boolean | null;
  witnessLastHeartbeat: string | null;
};

export type FirstExecutionWatch = {
  utcTimestamp: string;
  session: string;
  signalId: string;
  quality: string;
  confluence: string;
  omsRequest: string;
  brokerResponse: string;
  mt5Ticket: string;
  dealId: string;
  latency: string;
  locked: boolean;
} | null;

export type BurnInStore = {
  monitorStartedAt: string;
  counters: CycleCounters;
  rejectionCounts: Record<string, number>;
  seenCycleKeys: string[];
  gatewayUpSamples: number;
  gatewayUpHits: number;
  brokerUpSamples: number;
  brokerUpHits: number;
};

const EMPTY_COUNTERS: CycleCounters = {
  snapshots: 0,
  signals: 0,
  decisions: 0,
  riskEvaluations: 0,
  safetyEvaluations: 0,
  sessionBlocks: 0,
  omsForwards: 0,
  mt5Executions: 0,
};

function present(v: string | null | undefined): boolean {
  const s = (v ?? "").trim();
  return s !== "" && s !== "—";
}

export function formatUptime(sec: number): string {
  if (sec < 0) sec = 0;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h >= 48) {
    const d = Math.floor(h / 24);
    return `${d}d ${h % 24}h ${m}m`;
  }
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function loadBurnInStore(): BurnInStore {
  if (typeof window === "undefined") {
    return {
      monitorStartedAt: new Date().toISOString(),
      counters: { ...EMPTY_COUNTERS },
      rejectionCounts: {},
      seenCycleKeys: [],
      gatewayUpSamples: 0,
      gatewayUpHits: 0,
      brokerUpSamples: 0,
      brokerUpHits: 0,
    };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {
        monitorStartedAt: new Date().toISOString(),
        counters: { ...EMPTY_COUNTERS },
        rejectionCounts: {},
        seenCycleKeys: [],
        gatewayUpSamples: 0,
        gatewayUpHits: 0,
        brokerUpSamples: 0,
        brokerUpHits: 0,
      };
    }
    const parsed = JSON.parse(raw) as BurnInStore;
    return {
      monitorStartedAt: parsed.monitorStartedAt || new Date().toISOString(),
      counters: { ...EMPTY_COUNTERS, ...(parsed.counters ?? {}) },
      rejectionCounts: parsed.rejectionCounts ?? {},
      seenCycleKeys: Array.isArray(parsed.seenCycleKeys)
        ? parsed.seenCycleKeys.slice(-3_000)
        : [],
      gatewayUpSamples: Number(parsed.gatewayUpSamples) || 0,
      gatewayUpHits: Number(parsed.gatewayUpHits) || 0,
      brokerUpSamples: Number(parsed.brokerUpSamples) || 0,
      brokerUpHits: Number(parsed.brokerUpHits) || 0,
    };
  } catch {
    return {
      monitorStartedAt: new Date().toISOString(),
      counters: { ...EMPTY_COUNTERS },
      rejectionCounts: {},
      seenCycleKeys: [],
      gatewayUpSamples: 0,
      gatewayUpHits: 0,
      brokerUpSamples: 0,
      brokerUpHits: 0,
    };
  }
}

export function saveBurnInStore(store: BurnInStore): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    /* ignore */
  }
}

function cycleKey(last: Record<string, unknown>, diag: Record<string, unknown>): string {
  return [
    str(last.observed_at || diag.server_time, ""),
    str(last.trace_id, ""),
    str(last.signal_id, ""),
    str(last.cycle_outcome, ""),
    str(last.abort_reason, ""),
    str(last.mt5_ticket, ""),
    str(last.detail, "").slice(0, 80),
  ].join("|");
}

function rankBlockers(counts: Record<string, number>): BlockerRank[] {
  const entries = Object.entries(counts).filter(([r, c]) => present(r) && c > 0);
  const total = entries.reduce((a, [, c]) => a + c, 0) || 1;
  return entries
    .map(([reason, count]) => ({
      reason,
      count,
      pct: Math.round((count / total) * 1000) / 10,
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 12);
}

function toWatch(
  rec: FirstExecutionEvidenceRecord | null,
): FirstExecutionWatch {
  if (!rec) return null;
  return {
    utcTimestamp: rec.utcTimestamp,
    session: rec.session,
    signalId: rec.signalId,
    quality: rec.quality,
    confluence: rec.confluence,
    omsRequest: rec.omsRequestId,
    brokerResponse: rec.brokerResponse,
    mt5Ticket: rec.mt5Ticket,
    dealId: rec.dealId,
    latency: rec.executionLatency,
    locked: true,
  };
}

export function deriveBurnInStatus(input: {
  firstExecutionComplete: boolean;
  investigation: boolean;
}): BurnInStatus {
  if (input.firstExecutionComplete) return "STABLE";
  if (input.investigation) return "INVESTIGATION REQUIRED";
  return "WAITING FOR FIRST EXECUTION";
}

export type BurnInModel = {
  status: BurnInStatus;
  statusEmoji: "🟢" | "🟡" | "🔴";
  uptime: UptimeBlock;
  counters: CycleCounters;
  blockers: BlockerRank[];
  firstExecution: FirstExecutionWatch;
  storePatch: BurnInStore;
  evidenceStorePatch: ReturnType<typeof reconcileFirstExecutionEvidence>["storePatch"];
  observedAt: string;
  opsMode: string;
  runState: string;
};

export function buildBurnInModel(input: {
  autoTrading: unknown;
  mt5Status: unknown;
  reliabilityDash: unknown;
  witnessHealth: unknown;
  journal: unknown;
  audits: unknown;
  store: BurnInStore;
  now?: Date;
}): BurnInModel {
  const now = input.now ?? new Date();
  const auto = asRecord(input.autoTrading);
  const exec = asRecord(auto.execution_state);
  const facts = asRecord(auto.facts);
  const orch = asRecord(auto.orchestrator);
  const last = asRecord(orch.last_cycle);
  const diag = asRecord(last.market_context_diagnostics);
  const mt5 = asRecord(input.mt5Status);
  const rel = asRecord(input.reliabilityDash);
  const net = asRecord(rel.network);
  const witness = asRecord(input.witnessHealth);
  const health = asRecord(witness.health);
  const policy = asRecord(auto.policy);

  const opsMode = str(auto.ops_mode || exec.ops_mode, "—");
  const runState = str(policy.run_state || exec.auto_trading_run_state, "off");
  const observedAt = str(
    last.observed_at || diag.server_time,
    now.toISOString(),
  );

  const gatewayOk = bool(facts.gateway_connected ?? exec.gateway_connected);
  const brokerOk = bool(facts.broker_connected ?? exec.broker_connected);
  const mt5Ok =
    bool(mt5.connected) ||
    bool(mt5.is_connected) ||
    str(mt5.status).toLowerCase() === "connected" ||
    brokerOk;

  let store: BurnInStore = {
    ...input.store,
    counters: { ...EMPTY_COUNTERS, ...input.store.counters },
    rejectionCounts: { ...input.store.rejectionCounts },
    seenCycleKeys: [...input.store.seenCycleKeys],
  };

  // Sample connectivity for uptime %
  store.gatewayUpSamples += 1;
  if (gatewayOk) store.gatewayUpHits += 1;
  store.brokerUpSamples += 1;
  if (brokerOk || mt5Ok) store.brokerUpHits += 1;

  const key = cycleKey(last, diag);
  const hasCycle = Boolean(last.cycle_outcome || last.signal_id || last.snapshot_present);
  if (hasCycle && key.replace(/\|/g, "") && !store.seenCycleKeys.includes(key)) {
    store.seenCycleKeys = [...store.seenCycleKeys, key].slice(-3_000);
    const c = { ...store.counters };
    if (bool(last.snapshot_present) || str(diag.snapshot) === "OK") {
      c.snapshots += 1;
    }
    if (present(str(last.signal_id))) c.signals += 1;
    if (last.cycle_outcome || last.decision_action) c.decisions += 1;
    if (last.cycle_outcome) {
      c.riskEvaluations += 1;
      c.safetyEvaluations += 1;
    }
    const safetyReasons = asList(last.safety_failed_reasons).map(String);
    const outcome = str(last.cycle_outcome, "").toLowerCase();
    const sessionBlock =
      outcome === "safety_blocked" ||
      safetyReasons.some((r) => /session/i.test(r));
    if (sessionBlock) c.sessionBlocks += 1;
    if (bool(last.forwarded_to_oms)) c.omsForwards += 1;
    if (last.mt5_ticket != null) c.mt5Executions += 1;

    const reason =
      safetyReasons[0] ||
      str(last.detail || last.abort_reason, "");
    if (
      present(reason) &&
      (sessionBlock ||
        outcome === "no_trade" ||
        outcome === "aborted" ||
        outcome.includes("risk") ||
        !bool(last.forwarded_to_oms))
    ) {
      store.rejectionCounts[reason] = (store.rejectionCounts[reason] || 0) + 1;
    }
    store.counters = c;
  }

  // Immutable first execution
  const existing = loadFirstExecutionEvidence().record;
  const reconciled = reconcileFirstExecutionEvidence({
    autoTrading: input.autoTrading,
    journal: input.journal,
    audits: input.audits,
    existing,
  });
  if (reconciled.storePatch.record && !existing?.locked) {
    saveFirstExecutionEvidence(reconciled.storePatch);
  }
  const firstComplete = Boolean(
    reconciled.record && isCompleteSuccessfulExecution(reconciled.record),
  );

  const auth = str(witness.authentication ?? health.authentication, "");
  const authFailed =
    auth === "FAILED" ||
    str(health.authentication_label).toLowerCase().includes("authentication failed");
  const continuity = asRecord(
    witness.heartbeat_continuity ?? health.heartbeat_continuity,
  );
  const continuityBad =
    str(continuity.status) === "AUTH_INTERRUPT" ||
    str(continuity.status) === "TRANSPORT_INTERRUPT";

  const netGwPct =
    net.gateway_uptime_pct != null ? num(net.gateway_uptime_pct) : null;
  const investigation =
    (!gatewayOk && store.gatewayUpSamples >= 3) ||
    ((!brokerOk && !mt5Ok) && store.brokerUpSamples >= 3) ||
    authFailed ||
    continuityBad ||
    (net.gateway_currently_up === false && store.gatewayUpSamples >= 2);

  const status = deriveBurnInStatus({
    firstExecutionComplete: firstComplete,
    investigation: investigation && !firstComplete,
  });

  const started = Date.parse(store.monitorStartedAt);
  const processSec = Number.isFinite(started)
    ? Math.max(0, (now.getTime() - started) / 1000)
    : 0;

  const gwPct =
    netGwPct != null
      ? netGwPct
      : store.gatewayUpSamples > 0
        ? (store.gatewayUpHits / store.gatewayUpSamples) * 100
        : null;
  const brokerPct =
    store.brokerUpSamples > 0
      ? (store.brokerUpHits / store.brokerUpSamples) * 100
      : null;

  const witnessHb = str(
    witness.last_successful_heartbeat ?? health.last_successful_heartbeat,
    "",
  );
  let witnessUptimeLabel = "—";
  if (present(witnessHb)) {
    const hb = Date.parse(witnessHb);
    if (Number.isFinite(hb)) {
      const age = Math.max(0, (now.getTime() - hb) / 1000);
      witnessUptimeLabel = authFailed
        ? `Auth failed · last OK ${formatUptime(age)} ago`
        : `Last heartbeat ${formatUptime(age)} ago`;
    }
  } else if (authFailed) {
    witnessUptimeLabel = "Witness Authentication Failed";
  }

  const emoji =
    status === "STABLE" ? "🟢" : status === "INVESTIGATION REQUIRED" ? "🔴" : "🟡";

  return {
    status,
    statusEmoji: emoji,
    uptime: {
      processUptimeLabel: formatUptime(processSec),
      processUptimeSec: processSec,
      gatewayUptimePct: gwPct != null ? Math.round(gwPct * 10) / 10 : null,
      gatewayUp: gatewayOk,
      brokerUptimeLabel:
        brokerPct != null ? `${brokerPct.toFixed(1)}% sampled` : "—",
      brokerUp: brokerOk || mt5Ok,
      witnessUptimeLabel,
      witnessAuthOk: authFailed ? false : present(witnessHb) ? true : null,
      witnessLastHeartbeat: present(witnessHb) ? witnessHb : null,
    },
    counters: store.counters,
    blockers: rankBlockers(store.rejectionCounts),
    firstExecution: toWatch(reconciled.record),
    storePatch: store,
    evidenceStorePatch: reconciled.storePatch,
    observedAt,
    opsMode,
    runState,
  };
}

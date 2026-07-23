/** Production Acceptance Countdown — read-only operational desk model.

Never mutates Strategy, Risk, Safety, OMS, MT5, sessions, or the trading engine.
Status becomes PRODUCTION ACCEPTED only when a real MT5 ticket is observed —
no manual override.
*/
import { asList, asRecord, bool, str } from "@/lib/desk";
import {
  type FirstExecutionEvidence,
  loadAcceptanceStore,
  saveAcceptanceStore,
  type StoredBlob,
  buildProductionAcceptanceModel,
} from "@/lib/production-acceptance";

export type CountdownStatus =
  | "PRODUCTION ACCEPTED"
  | "WAITING FOR FIRST ELIGIBLE EXECUTION";

export type EvidenceItem = {
  label: string;
  done: boolean;
  mark: "✅" | "⏳";
  detail: string;
};

export type ProductionStateRow = {
  label: string;
  value: string;
  ok: boolean;
};

export type SessionOpportunity = {
  currentSession: string;
  nextAllowedSession: string;
  etaLabel: string;
  etaSeconds: number | null;
  sessionAllowed: boolean;
};

/** Mirror of control-plane defaults — display only; never mutates policy. */
export const DISPLAY_ALLOWED_SESSIONS = [
  "london",
  "new_york",
  "london_ny_overlap",
] as const;

type SessionOpen = {
  id: (typeof DISPLAY_ALLOWED_SESSIONS)[number];
  label: string;
  timeZone: string;
  startHourLocal: number;
  startMinuteLocal: number;
};

const SESSION_OPENS: SessionOpen[] = [
  {
    id: "london",
    label: "London",
    timeZone: "Europe/London",
    startHourLocal: 8,
    startMinuteLocal: 0,
  },
  {
    id: "new_york",
    label: "New York",
    timeZone: "America/New_York",
    startHourLocal: 8,
    startMinuteLocal: 0,
  },
  {
    id: "london_ny_overlap",
    label: "London/NY overlap",
    timeZone: "UTC",
    startHourLocal: 13,
    startMinuteLocal: 0,
  },
];

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** Convert a local wall-clock in `timeZone` to a UTC Date (DST-aware via Intl). */
export function zonedLocalToUtc(
  year: number,
  month: number,
  day: number,
  hour: number,
  minute: number,
  timeZone: string,
): Date {
  const utcGuess = new Date(Date.UTC(year, month - 1, day, hour, minute, 0));
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  const parts = fmt.formatToParts(utcGuess);
  const get = (type: string) =>
    Number(parts.find((p) => p.type === type)?.value ?? "0");
  let h = get("hour");
  if (h === 24) h = 0;
  const asUtc = Date.UTC(
    get("year"),
    get("month") - 1,
    get("day"),
    h,
    get("minute"),
    get("second"),
  );
  const diff = utcGuess.getTime() - asUtc;
  return new Date(utcGuess.getTime() + diff);
}

export function nextSessionOpenUtc(
  now: Date,
  open: SessionOpen,
): Date {
  const y = now.getUTCFullYear();
  const m = now.getUTCMonth() + 1;
  const d = now.getUTCDate();
  // Probe today and next 8 calendar days in UTC; pick first future open.
  for (let add = 0; add < 9; add++) {
    const probe = new Date(Date.UTC(y, m - 1, d + add, 12, 0, 0));
    const py = probe.getUTCFullYear();
    const pm = probe.getUTCMonth() + 1;
    const pd = probe.getUTCDate();
    // Skip weekends for FX (Sat/Sun UTC approximation of trading week)
    const dow = probe.getUTCDay();
    if (dow === 0 || dow === 6) continue;
    const candidate = zonedLocalToUtc(
      py,
      pm,
      pd,
      open.startHourLocal,
      open.startMinuteLocal,
      open.timeZone,
    );
    if (candidate.getTime() > now.getTime() + 1_000) {
      return candidate;
    }
  }
  return new Date(now.getTime() + 24 * 3600_000);
}

export function formatDuration(seconds: number): string {
  if (seconds < 0) seconds = 0;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 48) {
    const days = Math.floor(h / 24);
    return `~${days}d ${h % 24}h`;
  }
  return `${pad2(h)}:${pad2(m)}:${pad2(s)}`;
}

export function resolveSessionOpportunity(input: {
  currentSession: string;
  sessionAllowed: boolean;
  now?: Date;
}): SessionOpportunity {
  const now = input.now ?? new Date();
  const current = str(input.currentSession, "—").toLowerCase() || "—";
  if (input.sessionAllowed) {
    return {
      currentSession: current,
      nextAllowedSession: current,
      etaLabel: "Now (session allowed)",
      etaSeconds: 0,
      sessionAllowed: true,
    };
  }
  let best: { open: SessionOpen; at: Date } | null = null;
  for (const open of SESSION_OPENS) {
    const at = nextSessionOpenUtc(now, open);
    if (!best || at.getTime() < best.at.getTime()) {
      best = { open, at };
    }
  }
  if (!best) {
    return {
      currentSession: current,
      nextAllowedSession: "london",
      etaLabel: "Unknown",
      etaSeconds: null,
      sessionAllowed: false,
    };
  }
  const etaSeconds = Math.max(
    0,
    Math.round((best.at.getTime() - now.getTime()) / 1000),
  );
  return {
    currentSession: current,
    nextAllowedSession: best.open.id,
    etaLabel: formatDuration(etaSeconds),
    etaSeconds,
    sessionAllowed: false,
  };
}

function activeBlocker(input: {
  safetyReasons: string[];
  decisionReasons: string[];
  abortReason: string;
  detail: string;
  outcome: string;
  sessionAllowed: boolean;
  hasSignal: boolean;
  forwarded: boolean;
  hasTicket: boolean;
}): string {
  if (input.hasTicket) return "Ready for execution";
  const safety = input.safetyReasons[0];
  if (safety) return safety;
  const abort = input.abortReason;
  if (abort && abort !== "—" && abort.toUpperCase() !== "NONE") {
    // Prefer human detail when present
    if (input.detail && input.detail !== "—") return input.detail;
    return abort;
  }
  for (const r of input.decisionReasons) {
    if (/quality/i.test(r) && /below|fail|low/i.test(r)) {
      return r.match(/quality[^\n]*/i)?.[0] || "Quality below threshold";
    }
    if (/confluence/i.test(r) && /below|fail|low/i.test(r)) {
      return r.match(/confluence[^\n]*/i)?.[0] || "Confluence below threshold";
    }
    if (/spread/i.test(r)) {
      return r.match(/spread[^\n]*/i)?.[0] || "Spread too high";
    }
    if (/risk/i.test(r) && /reject/i.test(r)) return "Risk rejected";
    if (/safety/i.test(r) && /reject|block/i.test(r)) return "Safety rejected";
  }
  const outcome = input.outcome.toLowerCase();
  if (outcome.includes("risk")) return "Risk rejected";
  if (outcome.includes("safety")) return "Safety rejected";
  if (!input.sessionAllowed && /session/i.test(input.detail)) {
    return input.detail;
  }
  if (!input.hasSignal && !input.forwarded) {
    if (input.sessionAllowed) return "No signal";
  }
  if (input.sessionAllowed && !input.forwarded && !input.hasTicket) {
    return "Ready for execution";
  }
  if (input.detail && input.detail !== "—") return input.detail;
  return "Ready for execution";
}

export type CountdownModel = {
  status: CountdownStatus;
  statusEmoji: "🟢" | "🟡";
  productionState: ProductionStateRow[];
  blocker: string;
  evidence: EvidenceItem[];
  opportunity: SessionOpportunity;
  firstTrade: FirstExecutionEvidence | null;
  storePatch: StoredBlob;
  observedAt: string;
};

export function buildAcceptanceCountdownModel(input: {
  autoTrading: unknown;
  controlCenter: unknown;
  mt5Status: unknown;
  journal: unknown;
  audits: unknown;
  store: StoredBlob;
  now?: Date;
}): CountdownModel {
  const base = buildProductionAcceptanceModel(input);
  const auto = asRecord(input.autoTrading);
  const exec = asRecord(auto.execution_state);
  const facts = asRecord(auto.facts);
  const orch = asRecord(auto.orchestrator);
  const last = asRecord(orch.last_cycle);
  const diag = asRecord(last.market_context_diagnostics);
  const center = asRecord(input.controlCenter);
  const mt5 = asRecord(input.mt5Status);
  const persistence = asRecord(auto.persistence);
  const policy = asRecord(auto.policy);

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
  const decisionAlive =
    Boolean(last.cycle_outcome) ||
    Boolean(last.decision_action) ||
    runState === "running";
  const outcome = str(last.cycle_outcome, "").toLowerCase();
  const riskOk =
    !outcome.includes("risk") &&
    !asList(last.decision_reasons).some((r) => /risk reject/i.test(String(r)));
  const killArmed = bool(exec.kill_switch_armed ?? center.kill_switch_armed);
  const safetyReasons = asList(
    last.safety_failed_reasons ?? auto.failed_reasons,
  ).map(String);
  const sessionAllowed =
    bool(diag.session_allowed) ||
    str(diag.session_allowed).toLowerCase() === "true";
  const currentSession = str(
    diag.trading_session || last.session || diag.session,
    "—",
  );
  const durable =
    bool(persistence.durable) || bool(persistence.postgres_has_state);
  const marketOk =
    bool(facts.market_data_live ?? exec.market_data_live) || snapshotOk;
  const strategyOk =
    bool(last.signal_id) ||
    asList(last.decision_reasons).length > 0 ||
    Boolean(last.cycle_outcome) ||
    runState === "running";

  const firstTrade = base.firstExecution;
  const hasTicket = Boolean(
    firstTrade?.mt5Ticket && firstTrade.mt5Ticket !== "—",
  );
  const status: CountdownStatus = hasTicket
    ? "PRODUCTION ACCEPTED"
    : "WAITING FOR FIRST ELIGIBLE EXECUTION";

  const productionState: ProductionStateRow[] = [
    {
      label: "Ops Mode",
      value: opsMode.toUpperCase(),
      ok: opsMode.toUpperCase() === "LIVE",
    },
    {
      label: "Gate",
      value: gateOk ? "Enabled" : "Disabled",
      ok: gateOk,
    },
    {
      label: "Auto Trading",
      value: runState.toUpperCase(),
      ok: runState === "running",
    },
    {
      label: "Gateway",
      value: gatewayOk ? "CONNECTED" : "OFFLINE",
      ok: gatewayOk,
    },
    {
      label: "Broker",
      value: brokerOk ? "CONNECTED" : "OFF",
      ok: brokerOk,
    },
    {
      label: "MT5",
      value: mt5Ok ? "CONNECTED" : "OFFLINE",
      ok: mt5Ok,
    },
    {
      label: "Snapshot",
      value: snapshotOk ? "OK" : "MISSING",
      ok: snapshotOk,
    },
    {
      label: "Decision Engine",
      value: decisionAlive ? "ACTIVE" : "IDLE",
      ok: decisionAlive,
    },
    {
      label: "Risk",
      value: riskOk ? "READY" : "BLOCKED",
      ok: riskOk,
    },
    {
      label: "Safety",
      value: killArmed
        ? "KILL ARMED"
        : outcome === "safety_blocked"
          ? "BLOCK"
          : "READY",
      ok: !killArmed,
    },
  ];

  const blocker = hasTicket
    ? "Ready for execution"
    : activeBlocker({
        safetyReasons,
        decisionReasons: asList(last.decision_reasons).map(String),
        abortReason: str(last.abort_reason, ""),
        detail: str(last.detail || safetyReasons[0], "—"),
        outcome,
        sessionAllowed,
        hasSignal: Boolean(last.signal_id),
        forwarded: bool(last.forwarded_to_oms),
        hasTicket: bool(last.mt5_ticket) || hasTicket,
      });

  const mark = (done: boolean, waitingDetail: string): EvidenceItem["mark"] =>
    done ? "✅" : "⏳";

  const evidence: EvidenceItem[] = [
    {
      label: "Infrastructure",
      done: gatewayOk && brokerOk && mt5Ok,
      mark: mark(gatewayOk && brokerOk && mt5Ok, "Waiting"),
      detail: gatewayOk && brokerOk && mt5Ok ? "OK" : "Waiting",
    },
    {
      label: "Persistence",
      done: durable,
      mark: mark(durable, "Waiting"),
      detail: durable ? "OK" : "Waiting",
    },
    {
      label: "Market Context",
      done: marketOk && snapshotOk,
      mark: mark(marketOk && snapshotOk, "Waiting"),
      detail: snapshotOk ? "OK" : "Waiting",
    },
    {
      label: "Strategy",
      done: strategyOk,
      mark: mark(strategyOk, "Waiting"),
      detail: strategyOk ? "OK" : "Waiting",
    },
    {
      label: "Decision",
      done: decisionAlive,
      mark: mark(decisionAlive, "Waiting"),
      detail: decisionAlive ? "OK" : "Waiting",
    },
    {
      label: "Risk",
      done: riskOk && !killArmed,
      mark: mark(riskOk && !killArmed, "Waiting"),
      detail: riskOk ? "OK" : "Waiting",
    },
    {
      label: "Safety",
      done: !killArmed,
      mark: mark(!killArmed, "Waiting"),
      detail: !killArmed ? "OK" : "Waiting",
    },
    {
      label: "OMS Request",
      done: hasTicket || bool(last.forwarded_to_oms) || Boolean(base.history.find((h) => h.id === "oms")?.done),
      mark: hasTicket || bool(last.forwarded_to_oms) ? "✅" : "⏳",
      detail:
        hasTicket || bool(last.forwarded_to_oms) ? "OK" : "Waiting",
    },
    {
      label: "Broker Response",
      done:
        hasTicket ||
        last.broker_retcode != null ||
        Boolean(base.history.find((h) => h.id === "broker")?.done),
      mark:
        hasTicket || last.broker_retcode != null ? "✅" : "⏳",
      detail:
        hasTicket || last.broker_retcode != null ? "OK" : "Waiting",
    },
    {
      label: "MT5 Ticket",
      done: hasTicket,
      mark: hasTicket ? "✅" : "⏳",
      detail: hasTicket ? str(firstTrade?.mt5Ticket) : "Waiting",
    },
    {
      label: "Deal ID",
      done: Boolean(firstTrade?.dealId && firstTrade.dealId !== "—"),
      mark:
        firstTrade?.dealId && firstTrade.dealId !== "—" ? "✅" : "⏳",
      detail:
        firstTrade?.dealId && firstTrade.dealId !== "—"
          ? firstTrade.dealId
          : "Waiting",
    },
    {
      label: "Journal",
      done:
        hasTicket ||
        Boolean(firstTrade?.journalId && firstTrade.journalId !== "—"),
      mark: hasTicket ? "✅" : "⏳",
      detail: hasTicket ? "OK" : "Waiting",
    },
  ];

  // Normalize marks to ✅ / ⏳ Waiting wording for unfinished
  for (const item of evidence) {
    if (!item.done) {
      item.mark = "⏳";
      if (item.detail === "OK") item.detail = "Waiting";
    } else {
      item.mark = "✅";
    }
  }

  const opportunity = resolveSessionOpportunity({
    currentSession,
    sessionAllowed,
    now: input.now,
  });

  return {
    status,
    statusEmoji: status === "PRODUCTION ACCEPTED" ? "🟢" : "🟡",
    productionState,
    blocker,
    evidence,
    opportunity,
    firstTrade,
    storePatch: base.storePatch,
    observedAt: str(
      last.observed_at || diag.server_time,
      new Date().toISOString(),
    ),
  };
}

export { loadAcceptanceStore, saveAcceptanceStore };
export type { FirstExecutionEvidence, StoredBlob };

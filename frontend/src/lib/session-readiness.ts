/** Session Readiness — read-only operational panel.

Never mutates Strategy, Risk, Safety, OMS, MT5, sessions, or the trading engine.
Window metrics accumulate client-side while an allowed session is open.
*/
import { asList, asRecord, bool, str } from "@/lib/desk";
import {
  resolveSessionOpportunity,
  type SessionOpportunity,
} from "@/lib/production-acceptance-countdown";

const STORAGE_KEY = "quantforg.session_readiness.v1";

export type SessionStatus = "Allowed" | "Blocked";

export type WindowMetrics = {
  signalsGenerated: number;
  decisions: number;
  riskPass: number;
  riskTotal: number;
  safetyPass: number;
  safetyTotal: number;
  omsForwards: number;
  mt5Tickets: number;
};

export type SessionReadinessModel = {
  currentSession: string;
  sessionStatus: SessionStatus;
  blockReason: string | null;
  nextAllowedSession: string;
  etaLabel: string;
  executionWindowOpen: boolean;
  windowOpenedAt: string | null;
  metrics: WindowMetrics;
  opportunity: SessionOpportunity;
  observedAt: string;
  storePatch: SessionReadinessStore;
};

export type SessionReadinessStore = {
  /** Active allowed-window id, e.g. "london|2026-07-23" */
  activeWindowId: string | null;
  windowOpenedAt: string | null;
  metrics: WindowMetrics;
  seenCycleKeys: string[];
};

const EMPTY_METRICS: WindowMetrics = {
  signalsGenerated: 0,
  decisions: 0,
  riskPass: 0,
  riskTotal: 0,
  safetyPass: 0,
  safetyTotal: 0,
  omsForwards: 0,
  mt5Tickets: 0,
};

export function loadSessionReadinessStore(): SessionReadinessStore {
  if (typeof window === "undefined") {
    return {
      activeWindowId: null,
      windowOpenedAt: null,
      metrics: { ...EMPTY_METRICS },
      seenCycleKeys: [],
    };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {
        activeWindowId: null,
        windowOpenedAt: null,
        metrics: { ...EMPTY_METRICS },
        seenCycleKeys: [],
      };
    }
    const parsed = JSON.parse(raw) as SessionReadinessStore;
    return {
      activeWindowId: parsed.activeWindowId ?? null,
      windowOpenedAt: parsed.windowOpenedAt ?? null,
      metrics: { ...EMPTY_METRICS, ...(parsed.metrics ?? {}) },
      seenCycleKeys: Array.isArray(parsed.seenCycleKeys)
        ? parsed.seenCycleKeys.slice(-500)
        : [],
    };
  } catch {
    return {
      activeWindowId: null,
      windowOpenedAt: null,
      metrics: { ...EMPTY_METRICS },
      seenCycleKeys: [],
    };
  }
}

export function saveSessionReadinessStore(store: SessionReadinessStore): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    /* ignore quota */
  }
}

function utcDay(isoOrNow: string): string {
  const d = new Date(isoOrNow);
  if (Number.isNaN(d.getTime())) return new Date().toISOString().slice(0, 10);
  return d.toISOString().slice(0, 10);
}

function cycleKey(last: Record<string, unknown>, diag: Record<string, unknown>): string {
  return [
    str(last.observed_at || diag.server_time, ""),
    str(last.cycle_outcome, ""),
    str(last.signal_id, ""),
    str(last.mt5_ticket, ""),
    str(last.trace_id, ""),
    str(last.abort_reason, ""),
  ].join("|");
}

function applyCycleToMetrics(
  metrics: WindowMetrics,
  last: Record<string, unknown>,
): WindowMetrics {
  const next = { ...metrics };
  const outcome = str(last.cycle_outcome, "").toLowerCase();
  const safetyReasons = asList(last.safety_failed_reasons).map(String);
  const decisionReasons = asList(last.decision_reasons).map(String);
  const hasDecision = Boolean(last.cycle_outcome || last.decision_action);

  if (last.signal_id) next.signalsGenerated += 1;
  if (hasDecision) next.decisions += 1;

  if (hasDecision) {
    next.riskTotal += 1;
    const riskFail =
      outcome.includes("risk") ||
      decisionReasons.some((r) => /risk\s*reject/i.test(r));
    if (!riskFail) next.riskPass += 1;

    next.safetyTotal += 1;
    const safetyFail =
      outcome === "safety_blocked" ||
      safetyReasons.length > 0 ||
      outcome.includes("safety");
    if (!safetyFail) next.safetyPass += 1;
  }

  if (bool(last.forwarded_to_oms)) next.omsForwards += 1;
  if (last.mt5_ticket != null && str(last.mt5_ticket) !== "") {
    next.mt5Tickets += 1;
  }
  return next;
}

export function pct(pass: number, total: number): string {
  if (total <= 0) return "—";
  return `${((pass / total) * 100).toFixed(0)}%`;
}

export function buildSessionReadinessModel(input: {
  autoTrading: unknown;
  store: SessionReadinessStore;
  now?: Date;
}): SessionReadinessModel {
  const auto = asRecord(input.autoTrading);
  const orch = asRecord(auto.orchestrator);
  const last = asRecord(orch.last_cycle);
  const diag = asRecord(last.market_context_diagnostics);
  const now = input.now ?? new Date();
  const nowIso = now.toISOString();

  const currentSession = str(
    diag.trading_session || last.session || diag.session,
    "—",
  ).toLowerCase();
  const sessionAllowed =
    bool(diag.session_allowed) ||
    str(diag.session_allowed).toLowerCase() === "true";
  const sessionStatus: SessionStatus = sessionAllowed ? "Allowed" : "Blocked";

  const safetyReasons = asList(
    last.safety_failed_reasons ?? auto.failed_reasons,
  ).map(String);
  const blockReason = sessionAllowed
    ? null
    : safetyReasons[0] ||
      str(last.detail, "") ||
      (currentSession && currentSession !== "—"
        ? `Session '${currentSession}' not allowed`
        : "Session not allowed");

  const opportunity = resolveSessionOpportunity({
    currentSession,
    sessionAllowed,
    now,
  });

  let store: SessionReadinessStore = {
    activeWindowId: input.store.activeWindowId,
    windowOpenedAt: input.store.windowOpenedAt,
    metrics: { ...EMPTY_METRICS, ...input.store.metrics },
    seenCycleKeys: [...input.store.seenCycleKeys],
  };

  if (sessionAllowed) {
    const windowId = `${currentSession}|${utcDay(nowIso)}`;
    if (store.activeWindowId !== windowId) {
      // New execution window — reset counters
      store = {
        activeWindowId: windowId,
        windowOpenedAt: nowIso,
        metrics: { ...EMPTY_METRICS },
        seenCycleKeys: [],
      };
    }
    const key = cycleKey(last, diag);
    if (key.replace(/\|/g, "") && !store.seenCycleKeys.includes(key)) {
      // Only count when we have a real cycle observation
      if (last.cycle_outcome || last.signal_id || last.decision_action) {
        store = {
          ...store,
          metrics: applyCycleToMetrics(store.metrics, last),
          seenCycleKeys: [...store.seenCycleKeys, key].slice(-500),
        };
      }
    }
  } else {
    // Window closed — keep last metrics for display until next open resets
    store = {
      ...store,
      activeWindowId: null,
    };
  }

  return {
    currentSession: currentSession || "—",
    sessionStatus,
    blockReason,
    nextAllowedSession: opportunity.nextAllowedSession,
    etaLabel: opportunity.etaLabel,
    executionWindowOpen: sessionAllowed,
    windowOpenedAt: store.windowOpenedAt,
    metrics: store.metrics,
    opportunity,
    observedAt: str(last.observed_at || diag.server_time, nowIso),
    storePatch: store,
  };
}

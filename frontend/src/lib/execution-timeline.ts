/** Execution Timeline — read-only chronological cycle reconstruction.

Never mutates Strategy, Risk, Safety, OMS, or MT5. Observes live cycle + journal
only and appends immutable event rows client-side.
*/
import { asList, asRecord, bool, str } from "@/lib/desk";

const STORAGE_KEY = "quantforg.execution_timeline.v1";

export type TimelineStatus = "PASS" | "BLOCKED" | "FAILED" | "SUCCESS";

export type TimelineEvent = {
  id: string;
  stage: string;
  utcTimestamp: string;
  durationSincePrevMs: number | null;
  status: TimelineStatus;
  detail: string;
  session: string;
  signalId: string;
  dateKey: string;
  cycleKey: string;
  blocking: boolean;
};

export type TimelineStore = {
  events: TimelineEvent[];
  seenCycleKeys: string[];
};

export type TimelineBlocker = {
  stage: string;
  reason: string;
  status: TimelineStatus;
} | null;

export type ExecutionTimelineModel = {
  events: TimelineEvent[];
  filtered: TimelineEvent[];
  blocker: TimelineBlocker;
  sessions: string[];
  storePatch: TimelineStore;
  latestCycleKey: string | null;
};

function present(v: string | null | undefined): boolean {
  const s = (v ?? "").trim();
  return s !== "" && s !== "—";
}

function dateKeyFromIso(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toISOString().slice(0, 10);
}

function parseMs(iso: string): number | null {
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : null;
}

function withDurations(events: TimelineEvent[]): TimelineEvent[] {
  const out: TimelineEvent[] = [];
  let prevMs: number | null = null;
  for (const ev of events) {
    const ms = parseMs(ev.utcTimestamp);
    let duration: number | null = null;
    if (ms != null && prevMs != null) {
      duration = Math.max(0, ms - prevMs);
    }
    out.push({ ...ev, durationSincePrevMs: duration });
    if (ms != null) prevMs = ms;
  }
  return out;
}

export function formatDurationMs(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  const m = Math.floor(ms / 60_000);
  const s = Math.round((ms % 60_000) / 1000);
  return `${m}m ${s}s`;
}

export function loadTimelineStore(): TimelineStore {
  if (typeof window === "undefined") {
    return { events: [], seenCycleKeys: [] };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { events: [], seenCycleKeys: [] };
    const parsed = JSON.parse(raw) as TimelineStore;
    return {
      events: Array.isArray(parsed.events) ? parsed.events.slice(-5_000) : [],
      seenCycleKeys: Array.isArray(parsed.seenCycleKeys)
        ? parsed.seenCycleKeys.slice(-2_000)
        : [],
    };
  } catch {
    return { events: [], seenCycleKeys: [] };
  }
}

export function saveTimelineStore(store: TimelineStore): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        events: store.events.slice(-5_000),
        seenCycleKeys: store.seenCycleKeys.slice(-2_000),
      }),
    );
  } catch {
    /* ignore */
  }
}

function cycleFingerprint(last: Record<string, unknown>, diag: Record<string, unknown>): string {
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

function findJournalMatch(
  journal: unknown,
  ticket: string,
  signalId: string,
): Record<string, unknown> | null {
  const items = asList(
    asRecord(journal).items ?? asRecord(journal).entries ?? journal,
  ).map(asRecord);
  if (present(ticket)) {
    const byTicket = items.find(
      (j) => str(j.ticket ?? j.mt5_ticket) === ticket,
    );
    if (byTicket) return byTicket;
  }
  if (present(signalId)) {
    const bySig = items.find((j) => str(j.signal_id) === signalId);
    if (bySig) return bySig;
  }
  return null;
}

/** Build ordered stages for one live cycle observation. */
export function buildCycleEvents(input: {
  autoTrading: unknown;
  journal?: unknown;
  nowIso?: string;
}): { events: TimelineEvent[]; cycleKey: string | null; blocker: TimelineBlocker } {
  const auto = asRecord(input.autoTrading);
  const orch = asRecord(auto.orchestrator);
  const last = asRecord(orch.last_cycle);
  if (!last.cycle_outcome && !last.signal_id && !bool(last.snapshot_present)) {
    return { events: [], cycleKey: null, blocker: null };
  }

  const diag = asRecord(last.market_context_diagnostics);
  const nowIso = input.nowIso ?? new Date().toISOString();
  const baseAt = str(last.observed_at || diag.server_time, nowIso);
  const session = str(
    diag.trading_session || last.session || diag.session,
    "—",
  ).toLowerCase();
  const signalId = str(last.signal_id, "—");
  const cycleKey = cycleFingerprint(last, diag);
  const dateKey = dateKeyFromIso(baseAt);
  const outcome = str(last.cycle_outcome, "").toLowerCase();
  const safetyReasons = asList(last.safety_failed_reasons).map(String);
  const decisionReasons = asList(last.decision_reasons).map(String);
  const ticket =
    last.mt5_ticket != null ? String(last.mt5_ticket) : "";
  const fill = findJournalMatch(input.journal, ticket, signalId);
  const dealId = str(
    fill?.deal ?? fill?.deal_id ?? last.deal_id ?? last.deal,
    "—",
  );
  const latencyMs =
    last.latency_ms != null && Number.isFinite(Number(last.latency_ms))
      ? Number(last.latency_ms)
      : null;

  // Slight sequential offsets so duration-since-previous is meaningful within a cycle
  const stepMs = latencyMs != null && latencyMs > 0 ? Math.max(1, Math.round(latencyMs / 8)) : 0;
  let offset = 0;
  const stamp = (): string => {
    const t = parseMs(baseAt);
    if (t == null) return baseAt;
    const iso = new Date(t + offset).toISOString();
    offset += stepMs;
    return iso;
  };

  const events: TimelineEvent[] = [];
  const push = (
    stage: string,
    status: TimelineStatus,
    detail: string,
    blocking = false,
  ) => {
    events.push({
      id: `${cycleKey}:${stage}:${events.length}`,
      stage,
      utcTimestamp: stamp(),
      durationSincePrevMs: null,
      status,
      detail,
      session,
      signalId: present(signalId) ? signalId : "—",
      dateKey,
      cycleKey,
      blocking,
    });
  };

  // 1 Snapshot
  if (bool(last.snapshot_present) || str(diag.snapshot) === "OK") {
    push("Snapshot refreshed", "PASS", "snapshot ok");
  } else if (outcome === "no_snapshot") {
    push("Snapshot refreshed", "FAILED", "snapshot missing", true);
  }

  // 2 Signal
  if (present(signalId)) {
    push("Signal generated", "PASS", signalId);
  }

  // 3 Decision
  if (last.decision_action || last.cycle_outcome) {
    const ok =
      !outcome.includes("abort") ||
      outcome === "safety_blocked" ||
      outcome === "no_trade" ||
      outcome === "forwarded" ||
      outcome === "shadow";
    push(
      "Decision made",
      ok ? "PASS" : "FAILED",
      str(last.decision_action || last.cycle_outcome, "—"),
    );
  }

  // 4 Risk
  const riskFail =
    outcome.includes("risk") ||
    decisionReasons.some((r) => /risk\s*reject/i.test(r));
  if (last.cycle_outcome || riskFail) {
    push(
      "Risk evaluated",
      riskFail ? "FAILED" : "PASS",
      riskFail
        ? decisionReasons.find((r) => /risk/i.test(r)) || "Risk rejected"
        : "clear",
      riskFail,
    );
  }

  // 5 Safety
  const safetyFail =
    outcome === "safety_blocked" ||
    safetyReasons.length > 0 ||
    outcome.includes("safety");
  if (last.cycle_outcome || safetyFail) {
    const reason =
      safetyReasons[0] ||
      str(last.detail || last.abort_reason, "Safety blocked");
    push(
      "Safety evaluated",
      safetyFail ? "BLOCKED" : "PASS",
      safetyFail ? reason : "clear",
      safetyFail,
    );
  }

  // 6 Rejection OR OMS forwarded
  if (bool(last.forwarded_to_oms)) {
    push(
      "OMS forwarded",
      "PASS",
      str(last.oms_message || last.trace_id, "forwarded"),
    );
  } else if (
    safetyFail ||
    riskFail ||
    outcome === "no_trade" ||
    outcome === "safety_blocked" ||
    outcome === "aborted"
  ) {
    const reason =
      safetyReasons[0] ||
      str(
        last.detail || last.abort_reason || decisionReasons[0],
        "Rejected",
      );
    push("Rejection reason", "BLOCKED", reason, true);
  }

  // 7 Broker
  if (last.broker_retcode != null) {
    const code = Number(last.broker_retcode);
    const ok = code === 0 || code === 10009;
    push(
      "Broker response",
      ok ? "PASS" : "FAILED",
      String(last.broker_retcode),
      !ok,
    );
  }

  // 8 MT5 ticket
  if (present(ticket)) {
    push("MT5 ticket", "SUCCESS", ticket);
  }

  // 9 Deal ID
  if (present(dealId)) {
    push("Deal ID", "SUCCESS", dealId);
  }

  const timed = withDurations(events);
  const blocker =
    timed.find((e) => e.blocking) != null
      ? (() => {
          const b = timed.find((e) => e.blocking)!;
          return { stage: b.stage, reason: b.detail, status: b.status };
        })()
      : null;

  return { events: timed, cycleKey, blocker };
}

export function buildExecutionTimelineModel(input: {
  autoTrading: unknown;
  journal?: unknown;
  store: TimelineStore;
  filterSession?: string;
  filterDate?: string;
  filterSignalId?: string;
}): ExecutionTimelineModel {
  const built = buildCycleEvents({
    autoTrading: input.autoTrading,
    journal: input.journal,
  });

  let events = [...input.store.events];
  let seen = [...input.store.seenCycleKeys];

  if (built.cycleKey && !seen.includes(built.cycleKey) && built.events.length) {
    seen = [...seen, built.cycleKey].slice(-2_000);
    events = [...events, ...built.events].slice(-5_000);
  }

  const storePatch: TimelineStore = { events, seenCycleKeys: seen };

  const sess = (input.filterSession || "").trim().toLowerCase();
  const date = (input.filterDate || "").trim();
  const sig = (input.filterSignalId || "").trim().toLowerCase();

  const filtered = events.filter((e) => {
    if (sess && sess !== "all" && e.session !== sess) return false;
    if (date && e.dateKey !== date) return false;
    if (sig && !e.signalId.toLowerCase().includes(sig)) return false;
    return true;
  });

  // Prefer live blocker from current cycle; else last blocking event in filter
  let blocker = built.blocker;
  if (!blocker) {
    const lastBlock = [...filtered].reverse().find((e) => e.blocking);
    if (lastBlock) {
      blocker = {
        stage: lastBlock.stage,
        reason: lastBlock.detail,
        status: lastBlock.status,
      };
    }
  }

  const sessions = [
    ...new Set(events.map((e) => e.session).filter((s) => present(s))),
  ].sort();

  return {
    events,
    filtered: withDurations(
      // Recompute durations within filtered view chronologically
      [...filtered].sort(
        (a, b) =>
          (parseMs(a.utcTimestamp) ?? 0) - (parseMs(b.utcTimestamp) ?? 0),
      ),
    ),
    blocker,
    sessions,
    storePatch,
    latestCycleKey: built.cycleKey,
  };
}

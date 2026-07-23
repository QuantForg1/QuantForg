/** Derive Production Validation desk fields from live API payloads.

Never fabricates trades, tickets, or readiness. Empty → elegant "—" / FAIL.
*/
import { asList, asRecord, bool, num, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";

export type ValidationLight = {
  key: string;
  label: string;
  passed: boolean;
  detail: string;
};

function parseQuality(reasons: unknown[]): string {
  for (const r of reasons) {
    const s = String(r);
    const m = s.match(/Trade quality\s+(\d+)/i);
    if (m) return m[1] ?? "—";
    if (/quality/i.test(s)) return s;
  }
  return "—";
}

function parseConfluence(reasons: unknown[]): string {
  for (const r of reasons) {
    const s = String(r);
    const m = s.match(/Confluence\s+(\d+)/i);
    if (m) return m[1] ?? "—";
    if (/confluence/i.test(s)) return s;
  }
  return "—";
}

function todayUtcPrefix(): string {
  return new Date().toISOString().slice(0, 10);
}

function isToday(ts: unknown): boolean {
  const s = str(ts, "");
  if (!s || s === "—") return false;
  return s.startsWith(todayUtcPrefix());
}

export function buildProductionValidationModel(input: {
  autoTrading: unknown;
  controlCenter: unknown;
  launchReadiness: unknown;
  mt5Status: unknown;
  tick: unknown;
  journal: unknown;
  audits: unknown;
  analytics: unknown;
}) {
  const auto = asRecord(input.autoTrading);
  const execState = asRecord(auto.execution_state);
  const facts = asRecord(auto.facts);
  const orch = asRecord(auto.orchestrator);
  const last = asRecord(orch.last_cycle);
  const diag = asRecord(last.market_context_diagnostics);
  const persistence = asRecord(auto.persistence);
  const policy = asRecord(auto.policy);
  const center = asRecord(input.controlCenter);
  const lr = asRecord(input.launchReadiness);
  const lrVerify = asRecord(lr.verification);
  const mt5 = asRecord(input.mt5Status);
  const tick = asRecord(input.tick);
  const journalPayload = asRecord(input.journal);
  const journalItems = asList(journalPayload.items ?? journalPayload.entries ?? input.journal);
  const auditItems = asList(
    asRecord(input.audits).items ?? asRecord(input.audits).audits ?? input.audits,
  );
  const analytics = asRecord(input.analytics);
  const attempts = asList(auto.recent_execution_attempts);

  const reasons = asList(last.decision_reasons).map(String);
  const safetyReasons = asList(
    last.safety_failed_reasons ?? auto.failed_reasons,
  ).map(String);

  const opsMode = str(auto.ops_mode || execState.ops_mode || center.mode, "—");
  const runState = str(policy.run_state || execState.auto_trading_run_state, "off");
  const gatewayOk = bool(facts.gateway_connected ?? execState.gateway_connected);
  const brokerOk = bool(facts.broker_connected ?? execState.broker_connected);
  const marketLive = bool(facts.market_data_live ?? execState.market_data_live);
  const mt5Ok =
    bool(mt5.connected) ||
    bool(mt5.is_connected) ||
    str(mt5.status).toLowerCase() === "connected" ||
    brokerOk;
  const snapshotOk = bool(last.snapshot_present) || str(diag.snapshot) === "OK";
  const session = str(diag.trading_session || diag.session, "—");
  const sessionAllowed = bool(diag.session_allowed);
  const gateEnabled =
    str(execState.gate_status || auto.status, "").toLowerCase() === "enabled" ||
    bool(execState.gate_allowed) ||
    bool(auto.allowed);
  const omsAllowed = bool(execState.oms_orders_allowed ?? center.oms_orders_allowed);
  const killArmed = bool(execState.kill_switch_armed ?? center.kill_switch_armed);
  const durable = bool(persistence.durable);
  const liveMode = opsMode.toUpperCase() === "LIVE";

  const bid = str(tick.bid ?? diag.bid, "—");
  const ask = str(tick.ask ?? diag.ask, "—");
  const spread = str(tick.spread ?? diag.spread, "—");
  const lastTick = str(
    tick.time ?? tick.timestamp ?? diag.server_time,
    "—",
  );

  let snapshotAge = "—";
  const observed = str(last.latency_ms, "");
  if (diag.server_time && diag.server_time !== "—") {
    const t = Date.parse(String(diag.server_time));
    if (Number.isFinite(t)) {
      const ageSec = Math.max(0, Math.round((Date.now() - t) / 1000));
      snapshotAge = `${ageSec}s`;
    }
  } else if (observed && observed !== "—") {
    snapshotAge = `${observed}ms cycle`;
  }

  const quality = parseQuality(reasons);
  const confluence = parseConfluence(reasons);
  const trend =
    reasons.find((r) => /trend|aligned|BOS/i.test(r)) ??
    str(diag.trend, "—");
  const regime = str(diag.trading_session || diag.market_regime, session);

  const decision = str(last.decision_action || last.cycle_outcome, "—");
  const decisionReason =
    reasons[0] ||
    str(last.abort_reason || last.detail || safetyReasons[0], "—");
  const confidence =
    confluence !== "—"
      ? confluence
      : str(last.confidence, "—");

  const riskResult =
    str(last.cycle_outcome).toLowerCase() === "risk_blocked"
      ? "REJECT"
      : reasons.some((r) => /risk/i.test(r))
        ? "SEE REASONS"
        : gateEnabled && !killArmed
          ? "PASS / N/A"
          : "—";

  const safetyStatus = safetyReasons.length
    ? "BLOCKED"
    : str(auto.status || execState.gate_status, "—");
  const safetyBlock = safetyReasons.join("; ") || str(last.detail, "—");

  const forwarded = bool(last.forwarded_to_oms);
  const mt5Ticket = last.mt5_ticket != null ? str(last.mt5_ticket) : "—";
  const brokerRetcode =
    last.broker_retcode != null ? str(last.broker_retcode) : "—";
  const omsMessage = str(last.oms_message, "—");
  const latency = last.latency_ms != null ? `${str(last.latency_ms)} ms` : "—";

  const todayAttempts = attempts.filter((a) => {
    const r = asRecord(a);
    return isToday(r.created_at || r.timestamp || r.at);
  });
  const todayJournal = journalItems.filter((j) => {
    const r = asRecord(j);
    return isToday(r.created_at || r.timestamp || r.ts || r.time);
  });

  let signalsGenerated =
    num(analytics.signals_count, NaN) ||
    todayAttempts.length ||
    (last.signal_id ? 1 : 0);
  let signalsRejected = 0;
  let riskRejects = 0;
  let safetyRejects = 0;
  let omsRequests = 0;
  let brokerRequests = 0;
  let mt5Orders = 0;
  let filledTrades = 0;
  const latencies: number[] = [];

  for (const raw of [...todayAttempts, ...todayJournal]) {
    const r = asRecord(raw);
    const outcome = str(
      r.cycle_outcome || r.outcome || r.status || r.result,
      "",
    ).toLowerCase();
    const reason = str(r.abort_reason || r.reason || r.detail, "").toLowerCase();
    if (
      outcome.includes("no_trade") ||
      outcome.includes("reject") ||
      outcome.includes("blocked") ||
      outcome.includes("shadow")
    ) {
      signalsRejected += 1;
    }
    if (outcome.includes("risk") || reason.includes("risk")) riskRejects += 1;
    if (outcome.includes("safety") || reason.includes("session")) {
      safetyRejects += 1;
    }
    if (bool(r.forwarded_to_oms) || outcome.includes("forward")) omsRequests += 1;
    if (r.broker_retcode != null || r.retcode != null) brokerRequests += 1;
    if (r.mt5_ticket != null || r.ticket != null) {
      mt5Orders += 1;
      filledTrades += 1;
    }
    const lat = num(r.latency_ms ?? r.execution_latency_ms, NaN);
    if (Number.isFinite(lat)) latencies.push(lat);
  }

  // Prefer live last_cycle classification for today's rolling counters when journal empty
  if (todayAttempts.length === 0 && todayJournal.length === 0) {
    const outcome = str(last.cycle_outcome, "").toLowerCase();
    const abort = str(last.abort_reason, "").toLowerCase();
    if (last.signal_id || snapshotOk) signalsGenerated = Math.max(signalsGenerated, 1);
    if (outcome && outcome !== "forwarded") signalsRejected = Math.max(signalsRejected, 1);
    if (outcome.includes("risk") || abort.includes("risk")) riskRejects = 1;
    if (outcome.includes("safety") || abort.includes("safety") || abort.includes("session")) {
      safetyRejects = 1;
    }
    if (forwarded) omsRequests = 1;
    if (last.broker_retcode != null) brokerRequests = 1;
    if (last.mt5_ticket != null) {
      mt5Orders = 1;
      filledTrades = 1;
    }
    const lat = num(last.latency_ms, NaN);
    if (Number.isFinite(lat)) latencies.push(lat);
  }

  const avgLatency =
    latencies.length > 0
      ? `${Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)} ms`
      : latency !== "—"
        ? latency
        : "—";

  const winRate =
    filledTrades > 0
      ? str(analytics.win_rate ?? analytics.win_rate_pct, "—")
      : "—";

  const lastJournal = asRecord(journalItems[0] ?? attempts[0] ?? {});
  const lastTrade =
    journalItems.find((j) => {
      const r = asRecord(j);
      return r.ticket != null || r.mt5_ticket != null || str(r.kind).includes("fill");
    }) ?? null;
  const lastRejection =
    journalItems.find((j) => {
      const r = asRecord(j);
      const o = str(r.outcome || r.status || r.cycle_outcome, "").toLowerCase();
      return o.includes("reject") || o.includes("block") || o.includes("no_trade");
    }) ??
    (str(last.cycle_outcome).toLowerCase() !== "forwarded" ? last : null);

  const infraReady =
    gatewayOk && mt5Ok && brokerOk && (snapshotOk || marketLive);
  const tradingReady =
    liveMode && gateEnabled && (runState === "running" || bool(policy.enabled));
  const executionReady = omsAllowed && !killArmed && tradingReady;
  const productionReady = infraReady && tradingReady && executionReady && durable;

  const lights: ValidationLight[] = [
    {
      key: "infrastructure",
      label: "Infrastructure Ready",
      passed: infraReady,
      detail: infraReady
        ? "Gateway · MT5 · Broker · Snapshot"
        : [
            !gatewayOk ? "Gateway" : null,
            !mt5Ok ? "MT5" : null,
            !brokerOk ? "Broker" : null,
            !(snapshotOk || marketLive) ? "Snapshot" : null,
          ]
            .filter(Boolean)
            .join(", ") || "Incomplete",
    },
    {
      key: "trading",
      label: "Trading Ready",
      passed: tradingReady,
      detail: tradingReady
        ? `LIVE · Gate Enabled · ${runState}`
        : `${opsMode} · gate=${str(execState.gate_status || auto.status)} · run=${runState}`,
    },
    {
      key: "execution",
      label: "Execution Ready",
      passed: executionReady,
      detail: executionReady
        ? "OMS allowed · Safety clear"
        : killArmed
          ? "Kill switch armed"
          : !omsAllowed
            ? "OMS not allowed"
            : "Trading not ready",
    },
    {
      key: "production",
      label: "Production Ready",
      passed: productionReady,
      detail: productionReady
        ? "All validations PASS · durable persistence"
        : !durable
          ? "Persistence not durable"
          : "Waiting on infrastructure / trading / execution",
    },
  ];

  // Fill price / deal id from journal when present
  const tradeRec = asRecord(lastTrade);
  const fillPrice = str(
    tradeRec.fill_price ?? tradeRec.price ?? tradeRec.avg_price,
    "—",
  );
  const dealId = str(tradeRec.deal_id ?? tradeRec.deal ?? tradeRec.id, "—");

  return {
    system: {
      opsMode,
      autoTrading: runState.toUpperCase(),
      gateway: gatewayOk ? "CONNECTED" : "OFFLINE",
      mt5: mt5Ok ? "CONNECTED" : "OFFLINE",
      broker: brokerOk ? "CONNECTED" : "OFF",
      snapshot: snapshotOk ? "OK" : str(diag.snapshot, "MISSING"),
      session,
      sessionAllowed,
      durable,
      hydrateSource: str(persistence.hydrate_source, "—"),
      persistedMode: str(persistence.persisted_ops_mode, "—"),
    },
    market: {
      symbol: TRADING_SYMBOL,
      bid,
      ask,
      spread,
      lastTick,
      snapshotAge,
      marketLive,
    },
    strategy: {
      signalId: str(last.signal_id, "—"),
      quality,
      confluence,
      trend: typeof trend === "string" ? trend : str(trend),
      regime,
      session,
    },
    decision: {
      decision,
      reason: decisionReason,
      confidence,
      forwardedToOms: forwarded ? "YES" : "NO",
      abortReason: str(last.abort_reason, "—"),
      cycleOutcome: str(last.cycle_outcome, "—"),
      detail: str(last.detail, "—"),
      reasons,
    },
    risk: {
      positionSize: str(policy.risk_per_trade_pct, "—") + "% / trade",
      dailyRisk: str(policy.max_daily_loss_pct, "—") + "% max",
      exposure: str(policy.max_open_positions, "—") + " max open",
      result: riskResult,
    },
    safety: {
      status: safetyStatus,
      blockReason: safetyBlock,
      killSwitch: killArmed ? "ARMED" : "DISARMED",
    },
    execution: {
      omsRequest: omsMessage,
      brokerResponse: brokerRetcode,
      mt5Ticket,
      dealId,
      fillPrice,
      latency,
      forwarded,
    },
    journal: {
      lastEvent: str(
        lastJournal.action ?? lastJournal.kind ?? last.cycle_outcome,
        "—",
      ),
      lastTrade: lastTrade
        ? str(
            asRecord(lastTrade).ticket ??
              asRecord(lastTrade).mt5_ticket ??
              asRecord(lastTrade).id,
            "—",
          )
        : "—",
      lastRejection: lastRejection
        ? str(
            asRecord(lastRejection).abort_reason ??
              asRecord(lastRejection).detail ??
              asRecord(lastRejection).cycle_outcome ??
              last.abort_reason,
            "—",
          )
        : "—",
      timestamp: str(
        lastJournal.created_at ??
          lastJournal.timestamp ??
          last.observed_at ??
          diag.server_time,
        "—",
      ),
      auditCount: auditItems.length,
    },
    stats: {
      signalsGenerated,
      signalsRejected,
      riskRejects,
      safetyRejects,
      omsRequests,
      brokerRequests,
      mt5Orders,
      filledTrades,
      winRate,
      averageLatency: avgLatency,
    },
    lights,
    productionReady,
    lrOpsMode: str(lr.ops_mode || lrVerify.ops_mode, opsMode),
    modesAligned:
      str(lr.ops_mode || lrVerify.ops_mode, opsMode).toUpperCase() ===
      opsMode.toUpperCase(),
  };
}

export type ProductionValidationModel = ReturnType<
  typeof buildProductionValidationModel
>;

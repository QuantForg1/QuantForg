"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Pause,
  Play,
  ShieldAlert,
  Square,
  XCircle,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/execution/confirm-dialog";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import {
  executionApi,
  institutionalObservabilityApi,
  iteOpsApi,
  mt5Api,
  portfolioApi,
  strategyApi,
  platformApi,
  weltradeApi,
} from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import {
  AUTO_STRATEGY_MODULES,
  loadStrategyToggles,
  saveStrategyToggles,
  type StrategyModuleId,
  type StrategyToggleState,
} from "@/lib/auto-trading/strategy-modules";
import { latestSuccessfulExecution } from "@/lib/execution/ops-metrics";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn, formatNumber } from "@/lib/utils";
import { LaunchReadinessPanel } from "@/components/ops/launch-readiness-panel";
import {
  BiasMeter,
  ExecutionPipeline,
  HealthDot,
  JournalRow,
  MetricCard,
  OpsPanel,
  StatusPill,
  UtcClock,
  type PipelineStageState,
} from "@/components/ops/auto-trading-ops-ui";

type RunState = "off" | "running" | "paused" | "stopped";

function startOfUtcDay(d = new Date()): Date {
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
}

function toneRun(state: RunState): "success" | "warning" | "danger" | "neutral" {
  if (state === "running") return "success";
  if (state === "paused") return "warning";
  if (state === "stopped") return "danger";
  return "neutral";
}

/**
 * Institutional Auto Trading command center.
 * Controls run state via ITE ops; all closes/cancels go through executionApi
 * (Risk + Safety + gateway) — never direct MT5.
 */
export function AutoTradingWorkspace() {
  const qc = useQueryClient();
  const session = useTradingSession();
  const [toggles, setToggles] = useState<StrategyToggleState>(() => loadStrategyToggles());
  const [confirmEmergency, setConfirmEmergency] = useState(false);
  const [confirmCloseAll, setConfirmCloseAll] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [busyLabel, setBusyLabel] = useState<string | null>(null);
  const [autoPausedNote, setAutoPausedNote] = useState<string | null>(null);
  const [executeResult, setExecuteResult] = useState<Record<string, unknown> | null>(
    null,
  );

  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 10_000,
  });
  const centerQ = useQuery({
    queryKey: ["ite-ops-center"],
    queryFn: iteOpsApi.controlCenter,
    retry: false,
    refetchInterval: 15_000,
  });
  const signalsQ = useQuery({
    queryKey: ["strategy-signals", "auto-ws"],
    queryFn: strategyApi.signals,
    retry: false,
    refetchInterval: 12_000,
  });
  const journalQ = useQuery({
    queryKey: ["execution-journal", "auto-ws"],
    queryFn: () => executionApi.journal(60),
    retry: false,
    refetchInterval: 8_000,
  });
  const auditsQ = useQuery({
    queryKey: ["execution-audits", "auto-ws"],
    queryFn: () => executionApi.audits(80),
    retry: false,
    refetchInterval: 8_000,
  });
  const analyticsQ = useQuery({
    queryKey: ["execution-analytics", "auto-ws"],
    queryFn: () => executionApi.analytics(100),
    retry: false,
    refetchInterval: 20_000,
  });
  const optQ = useQuery({
    queryKey: ["execution-optimization", "auto-ws"],
    queryFn: () => executionApi.optimization(100),
    retry: false,
    refetchInterval: 30_000,
  });
  const positionsQ = useQuery({
    queryKey: ["portfolio-positions", "auto-ws"],
    queryFn: () => portfolioApi.positions(),
    retry: false,
    refetchInterval: 5_000,
  });
  const ordersQ = useQuery({
    queryKey: ["portfolio-orders", "auto-ws"],
    queryFn: () => portfolioApi.orders(),
    retry: false,
    refetchInterval: 8_000,
  });
  const mt5Q = useQuery({
    queryKey: ["mt5-status"],
    queryFn: () => mt5Api.status(),
    retry: false,
    refetchInterval: 10_000,
  });
  const healthQ = useQuery({
    queryKey: ["weltrade-health"],
    queryFn: () => weltradeApi.health(),
    retry: false,
    refetchInterval: 10_000,
  });
  const tickQ = useQuery({
    queryKey: ["mt5-tick", TRADING_SYMBOL],
    queryFn: () => mt5Api.tick(TRADING_SYMBOL),
    enabled: session.connected,
    staleTime: 2_000,
    refetchInterval: session.connected ? 3_000 : false,
    retry: false,
  });
  const auditLogQ = useQuery({
    queryKey: ["ite-ops-audit", "auto-ws"],
    queryFn: () => iteOpsApi.audit(40),
    retry: false,
    refetchInterval: 20_000,
  });
  const servicesHealthQ = useQuery({
    queryKey: ["ite-ops-services-health", "auto-ws"],
    queryFn: iteOpsApi.servicesHealth,
    retry: false,
    refetchInterval: 20_000,
  });
  const obsHealthQ = useQuery({
    queryKey: ["institutional-observability", "auto-ws"],
    queryFn: institutionalObservabilityApi.health,
    retry: false,
    refetchInterval: 30_000,
  });
  const obsResourcesQ = useQuery({
    queryKey: ["institutional-observability-resources", "auto-ws"],
    queryFn: institutionalObservabilityApi.resources,
    retry: false,
    refetchInterval: 30_000,
  });
  const apiHealthQ = useQuery({
    queryKey: ["system-health", "auto-ws"],
    queryFn: platformApi.health,
    retry: false,
    refetchInterval: 20_000,
  });

  const policy = asRecord(asRecord(autoQ.data).policy);
  const runState = ((): RunState => {
    const rs = str(policy.run_state).toLowerCase();
    if (rs === "running" || rs === "paused" || rs === "stopped" || rs === "off") {
      return rs;
    }
    return Boolean(policy.enabled) ? "running" : "off";
  })();
  const maxDailyLossPct = num(policy.max_daily_loss_pct, 3);
  const riskPerTradePct = num(policy.risk_per_trade_pct, 1);
  const maxOpen = num(policy.max_open_positions, 1);
  const tradingMode = str(policy.trading_mode, "swing").toLowerCase();
  const compoundingEnabled = Boolean(policy.compounding_enabled);
  const aiScalping = asRecord(asRecord(autoQ.data).ai_scalping);
  const aiScore = asRecord(aiScalping.ai_score);
  const gateStatus = str(asRecord(autoQ.data).status, "—");
  const failedReasons = asList(asRecord(autoQ.data).failed_reasons).map(String);
  const reasonGroups = asRecord(asRecord(autoQ.data).reason_groups);
  const primaryBlocker = str(asRecord(autoQ.data).primary_blocker, "");
  const blockingCategory = str(asRecord(autoQ.data).blocking_category, "");
  const executionState = asRecord(asRecord(autoQ.data).execution_state);
  const executionEnabled = Boolean(
    executionState.execution_enabled ?? asRecord(autoQ.data).execution_enabled,
  );
  const riskReasons = asList(reasonGroups.risk).map(String);
  const connectivityReasons = asList(reasonGroups.connectivity).map(String);
  const operatorReasons = [
    ...asList(reasonGroups.operator).map(String),
    ...asList(reasonGroups.configuration).map(String),
    ...asList(reasonGroups.safety).map(String),
  ];
  const liveFacts = asRecord(asRecord(autoQ.data).live);
  const gatewayLive = Boolean(
    executionState.gateway_connected ??
      liveFacts.gateway_connected ??
      asRecord(asRecord(autoQ.data).facts).gateway_connected,
  );
  const brokerLive = Boolean(
    executionState.broker_connected ??
      liveFacts.broker_connected ??
      asRecord(asRecord(autoQ.data).facts).broker_connected,
  );
  const killArmed = Boolean(
    executionState.kill_switch_armed ??
      asRecord(centerQ.data).kill_switch_armed ??
      asRecord(autoQ.data).emergency_stop,
  );
  const opsMode = str(
    executionState.ops_mode ||
      asRecord(autoQ.data).ops_mode ||
      asRecord(centerQ.data).execution_mode ||
      asRecord(centerQ.data).mode,
    "—",
  );

  // Keep Auto Trading gate in sync with the same session the Broker page uses.
  useEffect(() => {
    void qc.invalidateQueries({ queryKey: ["ite-ops-auto-trading"] });
  }, [qc, session.gatewayOnline, session.connected]);

  const positions = useMemo(
    () => asList(asRecord(positionsQ.data).items ?? positionsQ.data).map(asRecord),
    [positionsQ.data],
  );
  const orders = useMemo(() => {
    const raw = ordersQ.data
      ? asList(asRecord(ordersQ.data).items ?? ordersQ.data)
      : session.orders;
    return raw.map(asRecord);
  }, [ordersQ.data, session.orders]);

  const deals = session.historyDeals;
  const todayStart = startOfUtcDay();
  const todayDeals = useMemo(
    () =>
      deals.filter((d) => {
        const t = d.time instanceof Date ? d.time : new Date(String(d.time));
        return t >= todayStart;
      }),
    [deals, todayStart],
  );
  const todayPl = useMemo(
    () => todayDeals.reduce((s, d) => s + num(d.profit) + num(d.commission) + num(d.swap), 0),
    [todayDeals],
  );
  const floating = positions.reduce((s, p) => s + num(p.profit), 0);
  const accountSnap = asRecord(asRecord(healthQ.data).account);
  const equity = num(session.equity, num(accountSnap.equity));
  const balance = num(session.balance, num(accountSnap.balance, equity));
  const dailyDdPct =
    balance > 0 ? ((balance - (equity || balance)) / balance) * 100 : 0;
  const dailyLossPct = todayPl < 0 && balance > 0 ? (Math.abs(todayPl) / balance) * 100 : 0;
  const dailyRiskUsed = Math.max(dailyDdPct, dailyLossPct);
  const remainingCapacity = Math.max(0, maxDailyLossPct - dailyRiskUsed);
  const openExposure = positions.reduce(
    (s, p) => s + Math.abs(num(p.volume) * num(p.open_price ?? p.price_open) * 100) / Math.max(num(asRecord(mt5Q.data).leverage, 1000), 1),
    0,
  );

  const journalItems = asList(asRecord(journalQ.data).items ?? journalQ.data).map(asRecord);
  const latestFill = useMemo(
    () =>
      latestSuccessfulExecution({
        journalItems: journalQ.data,
        auditItems: auditsQ.data,
      }),
    [journalQ.data, auditsQ.data],
  );

  const lastTradeTime = latestFill?.at
    ? latestFill.at.replace("T", " ").slice(0, 19)
    : "—";
  const signals = asList(asRecord(signalsQ.data).items ?? signalsQ.data).map(asRecord);
  const lastSignalTime = (() => {
    const first = signals[0];
    if (!first) return "—";
    return str(first.created_at || first.timestamp || first.time, "—")
      .replace("T", " ")
      .slice(0, 19);
  })();

  const tick = asRecord(tickQ.data);
  const mid =
    Number.isFinite(num(tick.bid)) && Number.isFinite(num(tick.ask))
      ? (num(tick.bid) + num(tick.ask)) / 2
      : NaN;
  const marketOpen = session.connected && (tick.bid != null || tick.ask != null);

  const analytics = asRecord(asRecord(analyticsQ.data).metrics);
  const optTrends = asRecord(asRecord(asRecord(optQ.data).risk_trends).trends);
  const sessionOverall = asRecord(
    asRecord(asRecord(optQ.data).session_analytics).overall,
  );
  const pf =
    sessionOverall.profit_factor != null
      ? formatNumber(num(sessionOverall.profit_factor), 2)
      : "—";
  const expectancy =
    sessionOverall.expectancy != null
      ? formatNumber(num(sessionOverall.expectancy), 2)
      : "—";
  const avgR =
    optTrends.average_r != null
      ? formatNumber(num(optTrends.average_r), 2)
      : "—";
  const avgHold =
    analytics.order_duration_ms_avg != null
      ? `${formatNumber(num(analytics.order_duration_ms_avg) / 1000, 1)}s`
      : sessionOverall.avg_duration_seconds != null
        ? `${formatNumber(num(sessionOverall.avg_duration_seconds), 1)}s`
        : "—";
  const todayJournal = journalItems.filter((j) => {
    const t = Date.parse(str(j.timestamp || j.submitted_at));
    return Number.isFinite(t) && t >= todayStart.getTime();
  });
  const todayWins = todayJournal.filter((j) => {
    const r = str(j.execution_result || j.outcome).toLowerCase();
    return r === "success" || r === "filled";
  }).length;
  const todayFails = todayJournal.filter((j) => {
    const r = str(j.execution_result || j.outcome).toLowerCase();
    return r === "failed" || r === "rejected";
  }).length;
  const todayWinRate =
    todayWins + todayFails > 0
      ? `${formatNumber((todayWins / (todayWins + todayFails)) * 100, 0)}%`
      : "—";

  const pipelineStages = useMemo(() => {
    const journals = asList(asRecord(journalQ.data).items ?? journalQ.data).map(
      asRecord,
    );
    const audits = asList(asRecord(auditsQ.data).items ?? auditsQ.data).map(
      asRecord,
    );
    const submit = audits.find(
      (a) =>
        str(a.request_id) === (latestFill?.requestId || "") &&
        str(a.stage).toLowerCase() === "submit",
    );
    const fromPayload = asList(asRecord(submit?.payload_out).stages).map(asRecord);
    const fromJournal = asList(
      journals.find((j) => str(j.request_id) === latestFill?.requestId)?.stages,
    ).map(asRecord);
    const list = fromPayload.length ? fromPayload : fromJournal;
    const pick = (...names: string[]) => {
      for (const s of list) {
        const n = str(s.stage).toLowerCase().replace(/\s+/g, "_");
        if (names.some((x) => n.includes(x))) {
          const ms = num(s.elapsed_ms ?? s.latency_ms);
          return Number.isFinite(ms) ? `${formatNumber(ms, 0)} ms` : "ok";
        }
      }
      return "—";
    };
    return [
      { label: "AI Signal", dur: pick("draft", "signal") },
      { label: "Strategy Validation", dur: pick("validation") },
      { label: "Risk Engine", dur: pick("risk") },
      { label: "Safety Engine", dur: pick("safety", "execution_check") },
      { label: "Execution Queue", dur: pick("execution_check", "draft") },
      { label: "Broker", dur: pick("broker_submission", "broker") },
      {
        label: "Filled",
        dur:
          latestFill?.metrics.brokerFillMs != null
            ? `${formatNumber(latestFill.metrics.brokerFillMs, 0)} ms`
            : pick("broker_fill", "fill"),
      },
      { label: "Journal", dur: pick("journal") },
      { label: "Analytics", dur: pick("analytics") },
    ];
  }, [latestFill, auditsQ.data, journalQ.data]);

  const eventTimeline = useMemo(() => {
    const events: { at: string; label: string; detail: string }[] = [];
    if (latestFill) {
      const audits = asList(asRecord(auditsQ.data).items ?? auditsQ.data)
        .map(asRecord)
        .filter((a) => str(a.request_id) === latestFill.requestId)
        .sort(
          (a, b) =>
            Date.parse(str(a.created_at)) - Date.parse(str(b.created_at)),
        );
      for (const a of audits) {
        events.push({
          at: str(a.created_at).replace("T", " ").slice(11, 19) || "—",
          label: `${str(a.stage)} · ${str(a.outcome)}`,
          detail: str(a.message || a.retcode, ""),
        });
      }
      if (latestFill.metrics.fillStatus) {
        events.push({
          at: latestFill.at.replace("T", " ").slice(11, 19) || "—",
          label: "Broker Filled",
          detail: `ticket ${latestFill.ticket} · deal ${latestFill.deal}`,
        });
      }
    }
    const ops = asList(asRecord(auditLogQ.data).entries ?? asRecord(auditLogQ.data).items)
      .map(asRecord)
      .slice(0, 8);
    for (const e of ops) {
      events.push({
        at: str(e.created_at || e.timestamp)
          .replace("T", " ")
          .slice(11, 19),
        label: str(e.action || e.event),
        detail: str(e.reason || e.detail || e.message, "").slice(0, 80),
      });
    }
    return events.slice(0, 24);
  }, [latestFill, auditsQ.data, auditLogQ.data]);

  const invalidate = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ["ite-ops-auto-trading"] });
    void qc.invalidateQueries({ queryKey: ["ite-ops-center"] });
    void qc.invalidateQueries({ queryKey: ["portfolio-positions"] });
    void qc.invalidateQueries({ queryKey: ["execution-journal"] });
  }, [qc]);

  const setRunMut = useMutation({
    mutationFn: (next: RunState) =>
      iteOpsApi.updateAutoTrading({
        reason: `operator set run_state=${next}`,
        confirmed: true,
        run_state: next,
        enabled: next === "running" || next === "paused",
        max_open_positions: maxOpen || 1,
        risk_per_trade_pct: String(riskPerTradePct || 1),
        max_daily_loss_pct: String(maxDailyLossPct || 3),
        max_spread: str(policy.max_spread, "2.00"),
        allowed_symbols: ["XAUUSD"],
        allowed_sessions: asList(policy.allowed_sessions).map(String).length
          ? asList(policy.allowed_sessions).map(String)
          : ["london", "new_york", "london_ny_overlap"],
        news_filter_enabled: Boolean(policy.news_filter_enabled),
        trading_mode: tradingMode,
        compounding_enabled: compoundingEnabled,
      }),
    onSuccess: () => {
      toast.success("Auto Trading state updated");
      invalidate();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Failed to update Auto Trading"),
  });

  const setModeMut = useMutation({
    mutationFn: (mode: "swing" | "scalping") =>
      iteOpsApi.updateAutoTrading({
        reason: `operator set trading_mode=${mode}`,
        confirmed: true,
        trading_mode: mode,
        max_open_positions: mode === "scalping" ? Math.max(maxOpen || 1, 3) : maxOpen || 1,
        risk_per_trade_pct: String(riskPerTradePct || 1),
        max_daily_loss_pct: String(maxDailyLossPct || 3),
        max_spread: str(policy.max_spread, "2.00"),
        allowed_symbols: ["XAUUSD"],
        allowed_sessions: asList(policy.allowed_sessions).map(String).length
          ? asList(policy.allowed_sessions).map(String)
          : ["london", "new_york", "london_ny_overlap"],
        news_filter_enabled: Boolean(policy.news_filter_enabled),
        compounding_enabled: compoundingEnabled,
        run_state: runState === "off" ? undefined : runState,
        enabled: runState === "running" || runState === "paused" ? true : undefined,
      }),
    onSuccess: (_data, mode) => {
      toast.success(
        mode === "scalping" ? "AI Scalping Mode enabled" : "Swing Mode enabled",
      );
      invalidate();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Failed to set trading mode"),
  });

  const setCompoundMut = useMutation({
    mutationFn: (on: boolean) =>
      iteOpsApi.updateAutoTrading({
        reason: `operator set compounding_enabled=${on}`,
        confirmed: true,
        compounding_enabled: on,
        trading_mode: tradingMode,
        max_open_positions: maxOpen || 1,
        risk_per_trade_pct: String(riskPerTradePct || 1),
        max_daily_loss_pct: String(maxDailyLossPct || 3),
        max_spread: str(policy.max_spread, "2.00"),
        allowed_symbols: ["XAUUSD"],
        allowed_sessions: asList(policy.allowed_sessions).map(String).length
          ? asList(policy.allowed_sessions).map(String)
          : ["london", "new_york", "london_ny_overlap"],
        news_filter_enabled: Boolean(policy.news_filter_enabled),
      }),
    onSuccess: (_d, on) => {
      toast.success(on ? "Compounding Mode on" : "Compounding Mode off");
      invalidate();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Failed to update compounding"),
  });
  const emergencyMut = useMutation({
    mutationFn: () =>
      iteOpsApi.emergencyStop("workspace emergency stop", true),
    onSuccess: async () => {
      try {
        await iteOpsApi.armKill("workspace emergency stop", true);
      } catch {
        /* kill may already be armed */
      }
      toast.success("Emergency stop armed — auto trading stopped");
      invalidate();
      setConfirmEmergency(false);
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Emergency stop failed"),
  });

  const executeNowMut = useMutation({
    mutationFn: () => iteOpsApi.executeNow(),
    onMutate: () => {
      setBusyLabel("Execute Now running…");
      setExecuteResult(null);
    },
    onSuccess: (data) => {
      const payload = asRecord(data);
      setExecuteResult(payload);
      setBusyLabel(null);
      invalidate();
      if (payload.success === true) {
        toast.success(str(payload.message, "Order executed successfully."));
      } else {
        toast.error(str(payload.reason || payload.message, "Execution rejected"));
      }
    },
    onError: (e) => {
      setBusyLabel(null);
      const message =
        e instanceof ApiError ? e.message : "Execute Now failed";
      setExecuteResult({
        success: false,
        status: "REJECTED",
        reason: message,
      });
      toast.error(message);
    },
  });

  const closeAllMut = useMutation({
    mutationFn: async () => {
      setBusyLabel("Closing positions…");
      for (const row of positions) {
        const side = str(row.side).toLowerCase() === "buy" ? "sell" : "buy";
        await executionApi.manage({
          request_id: `at_close_${str(row.ticket)}_${Date.now()}`,
          action: "close",
          symbol: str(row.symbol, TRADING_SYMBOL),
          ticket: Number(str(row.ticket)) || null,
          side,
          order_type: "market",
          volume: str(row.volume, "0.01"),
          price: null,
          stop_loss: null,
          take_profit: null,
          slippage: 10,
          magic: 0,
          comment: "auto-workspace-close-all",
        });
      }
    },
    onSuccess: () => {
      toast.success("Close-all submitted through execution pipeline");
      setConfirmCloseAll(false);
      setBusyLabel(null);
      invalidate();
    },
    onError: (e) => {
      setBusyLabel(null);
      toast.error(e instanceof ApiError ? e.message : "Close-all failed");
    },
  });

  const cancelPendingMut = useMutation({
    mutationFn: async () => {
      setBusyLabel("Cancelling pending orders…");
      for (const o of orders) {
        const ticket = Number(str(o.ticket || o.order_ticket));
        if (!Number.isFinite(ticket) || ticket <= 0) continue;
        await executionApi.cancel({
          request_id: `at_cancel_${ticket}_${Date.now()}`,
          ticket,
          symbol: str(o.symbol, TRADING_SYMBOL),
        });
      }
    },
    onSuccess: () => {
      toast.success("Cancel pending submitted through execution pipeline");
      setConfirmCancel(false);
      setBusyLabel(null);
      invalidate();
    },
    onError: (e) => {
      setBusyLabel(null);
      toast.error(e instanceof ApiError ? e.message : "Cancel pending failed");
    },
  });

  // Auto-pause when daily risk limit reached (operator policy — still goes through ITE API)
  useEffect(() => {
    if (runState !== "running") return;
    if (!(dailyRiskUsed >= maxDailyLossPct && maxDailyLossPct > 0)) return;
    if (setRunMut.isPending) return;
    setAutoPausedNote(
      `Daily risk ${formatNumber(dailyRiskUsed, 2)}% reached limit ${formatNumber(maxDailyLossPct, 2)}% — auto paused.`,
    );
    setRunMut.mutate("paused");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fire once per breach while running
  }, [runState, dailyRiskUsed, maxDailyLossPct]);

  const toggleStrategy = (id: StrategyModuleId) => {
    setToggles((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      saveStrategyToggles(next);
      return next;
    });
  };

  const strategyStats = (id: StrategyModuleId) => {
    const label = AUTO_STRATEGY_MODULES.find((m) => m.id === id)?.label ?? id;
    const related = todayJournal.filter((j) =>
      str(j.comment || j.reason || j.strategy)
        .toLowerCase()
        .includes(id.split("_")[0] ?? ""),
    );
    const last = related[0] || signals.find((s) =>
      str(s.strategy || s.name || s.type).toLowerCase().includes(id.split("_")[0] ?? ""),
    );
    return {
      status: toggles[id] ? (runState === "running" ? "Armed" : "Enabled") : "Disabled",
      winRate: "—",
      lastSignal: last
        ? str(last.timestamp || last.created_at || last.time, "—")
            .replace("T", " ")
            .slice(0, 19)
        : "—",
      todayTrades: String(related.length || "—"),
      lastExecution: related[0]
        ? str(related[0].execution_result || related[0].outcome, "—")
        : "—",
      label,
    };
  };

  const signalRows = signals.slice(0, 20).map((s) => {
    const decision = str(s.decision || s.status || s.outcome, "").toLowerCase();
    let status = "No decision";
    if (!decision) {
      status =
        opsMode === "SHADOW"
          ? "Shadow hold"
          : opsMode === "CANARY" || opsMode === "LIVE"
            ? "Awaiting cycle"
            : "No decision";
    } else if (decision.includes("allow") || decision.includes("approv")) {
      status = "Approved";
    } else if (decision.includes("reject") || decision.includes("block")) {
      status = "Rejected";
    } else if (decision.includes("execut") || decision.includes("fill")) {
      status = "Executed";
    } else if (decision.includes("expir")) {
      status = "Expired";
    } else if (decision.includes("queue") || decision.includes("pending")) {
      status = opsMode === "SHADOW" ? "Shadow hold" : "Queued";
    } else {
      status = decision.charAt(0).toUpperCase() + decision.slice(1);
    }
    return [
      str(s.created_at || s.timestamp || s.time, "—").replace("T", " ").slice(0, 19),
      str(s.side || s.direction, "—").toUpperCase(),
      str(s.confidence || s.score, "—"),
      str(s.entry || s.entry_price, "—"),
      str(s.stop_loss || s.sl, "—"),
      str(s.take_profit || s.tp, "—"),
      str(s.risk_pct || riskPerTradePct, "—"),
      status,
    ];
  });

  if (autoQ.isLoading && !autoQ.data) {
    return <DeskSkeleton rows={8} />;
  }
  if (autoQ.isError) {
    return (
      <DeskError message="Auto Trading unavailable — OWNER/ADMIN required for ITE ops controls." />
    );
  }

  const orch = asRecord(asRecord(autoQ.data).orchestrator);
  const last = asRecord(orch.last_cycle);
  const diag = asRecord(last.market_context_diagnostics);
  const decisionReasons = asList(last.decision_reasons).map(String);
  const safetyCycleReasons = asList(
    last.safety_failed_reasons ?? failedReasons,
  ).map(String);

  const tradingSession = str(diag.trading_session || diag.session, "—");
  const sessionAllowed =
    diag.session_allowed === true ||
    diag.session_allowed === "true" ||
    str(diag.session_allowed).toLowerCase() === "true";

  const bidRaw = tick.bid ?? diag.bid;
  const askRaw = tick.ask ?? diag.ask;
  const bid = Number.isFinite(num(bidRaw))
    ? formatNumber(num(bidRaw), 3)
    : str(bidRaw, "—");
  const ask = Number.isFinite(num(askRaw))
    ? formatNumber(num(askRaw), 3)
    : str(askRaw, "—");
  const spreadRaw =
    tick.spread ??
    diag.spread ??
    (Number.isFinite(num(tick.bid)) && Number.isFinite(num(tick.ask))
      ? num(tick.ask) - num(tick.bid)
      : NaN);
  const spread = Number.isFinite(num(spreadRaw))
    ? formatNumber(num(spreadRaw), 2)
    : str(spreadRaw, "—");

  const atr =
    Number.isFinite(num(diag.atr))
      ? formatNumber(num(diag.atr), 2)
      : str(diag.atr, "—");
  const stopDistance =
    Number.isFinite(num(diag.stop_distance))
      ? formatNumber(num(diag.stop_distance), 2)
      : str(diag.stop_distance, "—");
  const riskBudget =
    Number.isFinite(num(diag.risk_budget))
      ? formatNumber(num(diag.risk_budget), 2)
      : str(diag.risk_budget, "—");
  const calculatedLots =
    Number.isFinite(num(diag.calculated_lots ?? diag.approved_lots))
      ? formatNumber(num(diag.calculated_lots ?? diag.approved_lots), 2)
      : str(diag.calculated_lots ?? diag.approved_lots, "—");
  const volatility = str(
    diag.volatility_level || diag.volatility || diag.regime_volatility,
    "—",
  );
  const trend = str(
    diag.trend ||
      decisionReasons.find((r) => /trend|aligned|BOS|CHOCH/i.test(r)),
    "—",
  );
  const marketRegime = str(
    aiScore.market_regime || diag.market_regime || diag.regime || tradingSession,
    "—",
  );
  const liquidity = str(
    aiScore.liquidity != null
      ? String(aiScore.liquidity)
      : diag.liquidity_level || diag.liquidity,
    "—",
  );

  const qualityMatch =
    decisionReasons.find((r) => /Trade quality/i.test(r)) ??
    str(last.detail, "");
  const qualityScore =
    aiScore.trade_quality != null
      ? String(aiScore.trade_quality)
      : (qualityMatch.match(/Trade quality\s+(\d+)/i)?.[1] ??
        (str(diag.trade_quality, "") !== "" ? str(diag.trade_quality) : "—"));
  const confluenceMatch =
    decisionReasons.find((r) => /Confluence/i.test(r)) ?? "";
  const confluenceScore =
    aiScore.confluence != null
      ? String(aiScore.confluence)
      : (confluenceMatch.match(/Confluence\s+(\d+)/i)?.[1] ??
        (str(diag.confluence, "") !== "" ? str(diag.confluence) : "—"));
  const confidence =
    aiScore.ai_confidence != null
      ? String(aiScore.ai_confidence)
      : (str(diag.confidence, "") !== ""
          ? str(diag.confidence)
          : str(last.confidence, "—"));
  const expectedRr = str(aiScore.expected_rr, str(diag.expected_rr, "—"));
  const expectedHold = str(aiScore.expected_hold_time, "—");
  const momentum = str(
    aiScore.momentum != null ? String(aiScore.momentum) : diag.momentum,
    "—",
  );
  const learning = asRecord(aiScalping.learning);
  const winRate =
    learning.win_rate != null ? `${String(learning.win_rate)}%` : "—";
  const lastLatency =
    Number.isFinite(num(last.latency_ms))
      ? `${formatNumber(num(last.latency_ms), 0)} ms`
      : "—";
  const profitProjection =
    expectedRr !== "—" && Number.isFinite(num(diag.risk_budget))
      ? formatNumber(num(diag.risk_budget) * num(expectedRr), 2)
      : "—";

  const decisionAction = str(last.decision_action, "").toUpperCase();
  const bias: "BUY" | "SELL" | "WAIT" =
    decisionAction === "BUY" || decisionAction === "LONG"
      ? "BUY"
      : decisionAction === "SELL" || decisionAction === "SHORT"
        ? "SELL"
        : aiScore.direction === "BUY" || aiScore.direction === "SELL"
          ? (aiScore.direction as "BUY" | "SELL")
          : "WAIT";
  const cycleOutcome = str(last.cycle_outcome, "").toLowerCase();
  const forwarded = Boolean(last.forwarded_to_oms);
  const hasTicket = last.mt5_ticket != null && str(last.mt5_ticket) !== "";
  const latencyMs =
    last.latency_ms != null && Number.isFinite(num(last.latency_ms))
      ? `${formatNumber(num(last.latency_ms), 0)} ms`
      : analytics.latency_ms_avg != null
        ? `${formatNumber(num(analytics.latency_ms_avg), 0)} ms`
        : "—";

  const stageOf = (
    ok: boolean,
    fail: boolean,
    running = false,
  ): PipelineStageState => {
    if (fail) return "failed";
    if (ok) return "success";
    if (running) return "running";
    return "waiting";
  };

  const livePipeline: {
    id: string;
    label: string;
    state: PipelineStageState;
    detail?: string;
  }[] = [
    {
      id: "market",
      label: "Market",
      state: stageOf(
        Boolean(last.snapshot_present) || str(diag.snapshot) === "OK" || marketOpen,
        cycleOutcome === "no_snapshot",
        Boolean(orch.running),
      ),
      detail: str(diag.ticks || diag.snapshot, ""),
    },
    {
      id: "strategy",
      label: "Strategy",
      state: stageOf(
        Boolean(last.signal_id) || decisionReasons.length > 0,
        /strategy|analyze/i.test(str(last.abort_reason)),
      ),
      detail: str(last.signal_id, ""),
    },
    {
      id: "decision",
      label: "Decision",
      state: stageOf(
        Boolean(last.decision_action) || cycleOutcome.includes("no_trade"),
        cycleOutcome.includes("decision") && cycleOutcome.includes("fail"),
      ),
      detail: str(last.decision_action || last.cycle_outcome, ""),
    },
    {
      id: "risk",
      label: "Risk",
      state: stageOf(
        cycleOutcome === "forwarded" ||
          cycleOutcome === "safety_blocked" ||
          (cycleOutcome.length > 0 && !cycleOutcome.includes("risk")),
        cycleOutcome.includes("risk") || riskReasons.length > 0,
      ),
      detail: riskReasons[0] || "",
    },
    {
      id: "safety",
      label: "Safety",
      state: stageOf(
        forwarded || hasTicket || cycleOutcome === "forwarded",
        cycleOutcome.includes("safety") || safetyCycleReasons.length > 0,
      ),
      detail: safetyCycleReasons[0] || str(last.detail, ""),
    },
    {
      id: "oms",
      label: "OMS",
      state: stageOf(
        forwarded,
        Boolean(str(last.oms_message)) && !forwarded && cycleOutcome.includes("oms"),
      ),
      detail: str(last.oms_message, ""),
    },
    {
      id: "broker",
      label: "Broker",
      state: stageOf(
        last.broker_retcode != null || hasTicket,
        last.broker_retcode != null && Number(last.broker_retcode) !== 0 && !hasTicket,
      ),
      detail:
        last.broker_retcode != null ? `retcode ${str(last.broker_retcode)}` : "",
    },
    {
      id: "mt5",
      label: "MT5",
      state: stageOf(hasTicket, false),
      detail: hasTicket ? `ticket ${str(last.mt5_ticket)}` : "",
    },
    {
      id: "journal",
      label: "Journal",
      state: stageOf(
        todayJournal.length > 0 || hasTicket || eventTimeline.length > 0,
        false,
      ),
      detail: todayJournal.length ? `${todayJournal.length} today` : "",
    },
  ];

  const journalTimeline = [
    ...todayJournal.slice(0, 24).map((j) => {
      const row = asRecord(j);
      return {
        time: str(row.timestamp || row.submitted_at || row.created_at, "—")
          .replace("T", " ")
          .slice(11, 19),
        type: str(row.action || row.kind || row.stage || "event", "event"),
        reason: str(
          row.reason || row.message || row.comment || row.detail,
          "",
        ).slice(0, 120),
        status: str(row.execution_result || row.outcome || row.status, "—"),
        latency:
          row.latency_ms != null || row.elapsed_ms != null
            ? `${formatNumber(num(row.latency_ms ?? row.elapsed_ms), 0)} ms`
            : "—",
      };
    }),
    ...(todayJournal.length === 0
      ? eventTimeline.slice(0, 16).map((e) => ({
          time: e.at || "—",
          type: e.label.split("·")[0]?.trim() || "event",
          reason: e.detail || e.label,
          status: /fail|block|reject/i.test(e.label) ? "blocked" : "info",
          latency: "—",
        }))
      : []),
  ];

  const obsRes = asRecord(obsResourcesQ.data);
  const obsHealth = asRecord(obsHealthQ.data);
  const obsComps = asRecord(obsHealth.components ?? obsHealth);
  const svcHealth = asRecord(servicesHealthQ.data);
  const apiHealth = asRecord(apiHealthQ.data);
  const apiDeps = asList(apiHealth.dependencies).map(asRecord);
  const findDep = (name: string) =>
    apiDeps.find((d) => str(d.name).toLowerCase().includes(name.toLowerCase()));

  const cpuPct =
    obsRes.cpu_percent != null
      ? `${formatNumber(num(obsRes.cpu_percent), 1)}%`
      : "—";
  const ramPct =
    obsRes.memory_percent != null
      ? `${formatNumber(num(obsRes.memory_percent), 1)}%`
      : obsRes.memory_used_mb != null
        ? `${formatNumber(num(obsRes.memory_used_mb), 0)} MB`
        : "—";

  const dbDep = findDep("postgres") || findDep("database") || findDep("supabase");
  const redisDep = findDep("redis");
  const dbOk =
    dbDep != null
      ? /ok|up|healthy|pass/i.test(str(dbDep.status))
      : asRecord(obsComps.warehouse).status
        ? /healthy|ok/i.test(str(asRecord(obsComps.warehouse).status))
        : null;
  const redisOk =
    redisDep != null
      ? /ok|up|healthy|pass/i.test(str(redisDep.status))
      : null;
  const apiOk =
    apiHealthQ.isError
      ? false
      : apiHealth.status != null
        ? /ok|up|healthy|pass/i.test(str(apiHealth.status))
        : apiHealthQ.isSuccess
          ? true
          : null;
  const gatewayHealthOk = gatewayLive;
  const mt5HealthOk = Boolean(
    brokerLive || session.connected || asRecord(mt5Q.data).connected,
  );
  const railwayOk =
    asRecord(svcHealth.railway).status != null
      ? /ok|up|healthy/i.test(str(asRecord(svcHealth.railway).status))
      : asRecord(obsComps.api).status
        ? /healthy|ok/i.test(str(asRecord(obsComps.api).status))
        : apiOk;

  const safetyBlocked =
    safetyCycleReasons.length > 0 || cycleOutcome.includes("safety");
  const safetyStatusLabel = safetyBlocked
    ? "BLOCK"
    : gateStatus.toLowerCase() === "enabled" && !killArmed
      ? "PASS"
      : str(gateStatus, "—").toUpperCase();
  const exactSafetyReason =
    safetyCycleReasons[0] ||
    primaryBlocker ||
    str(last.detail || last.abort_reason, "—");

  const riskStatusLabel = riskReasons.length
    ? "BLOCK"
    : cycleOutcome.includes("risk")
      ? "BLOCK"
      : "PASS";

  const signalsToday = todayWins + todayFails || todayJournal.length;
  const rejectedToday = todayFails;
  const executedToday = todayWins;
  const pnlToday = todayPl + floating;
  const mt5Connected = mt5HealthOk;
  const gateEnabled = gateStatus.toLowerCase() === "enabled";
  const forceFirst = asRecord(asRecord(autoQ.data).force_first_trade);
  const forceBanner = Boolean(forceFirst.banner);
  return (
    <div className="space-y-3">
      {forceBanner ? (
        <section
          role="status"
          className="border border-[var(--warning)] bg-[var(--warning)]/10 px-3 py-2.5"
        >
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--warning)]">
            TEST MODE
          </p>
          <p className="mt-1 text-sm font-medium text-[var(--fg)]">
            Forced Trade Enabled
          </p>
          <p className="mt-0.5 text-xs text-[var(--fg-muted)]">
            This bypasses signal filters for ONE trade only.
          </p>
        </section>
      ) : null}
      {/* Header */}
      <section className="border border-[var(--border)] bg-[var(--surface)]/90 px-3 py-2.5 backdrop-blur-[2px]">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--fg-subtle)]">
              Trading Operations Center
            </span>
            <StatusPill label={opsMode} ok={opsMode === "LIVE" || opsMode === "CANARY"} warn={opsMode === "SHADOW"} />
            <StatusPill label="Gateway" ok={gatewayLive} />
            <StatusPill label="Broker" ok={brokerLive || mt5Connected} />
            <StatusPill label="MT5" ok={mt5Connected} />
            <StatusPill
              label={`Auto ${runState}`}
              ok={runState === "running"}
              warn={runState === "paused"}
            />
            <StatusPill label={`Gate ${gateStatus}`} ok={gateEnabled} warn={!gateEnabled} />
            <Badge tone={killArmed ? "danger" : "neutral"}>
              {killArmed ? "KILL ARMED" : "Kill clear"}
            </Badge>
            <Badge tone={executionEnabled ? "danger" : "neutral"}>
              EXEC={executionEnabled ? "ON" : "OFF"}
            </Badge>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="font-mono text-[11px] tabular text-[var(--fg-muted)]">
              Latency {latencyMs}
            </span>
            <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-[var(--fg-muted)]">
              {tradingSession}
            </span>
            <span className="font-mono text-[11px] text-[var(--fg)]">{TRADING_SYMBOL}</span>
            <UtcClock />
            <Button asChild size="sm" variant="ghost">
              <Link href="/ops">ITE Ops</Link>
            </Button>
          </div>
        </div>
        {autoPausedNote ? (
          <p className="mt-2 text-xs text-[var(--warning)]">{autoPausedNote}</p>
        ) : null}
        {primaryBlocker ? (
          <p className="mt-2 text-xs text-[var(--fg-muted)]">
            Primary blocker:{" "}
            <span className="font-medium text-[var(--fg)]">{primaryBlocker}</span>
            {blockingCategory ? ` · ${blockingCategory}` : ""}
          </p>
        ) : null}
      </section>

      <LaunchReadinessPanel />

      {/* Controls */}
      <OpsPanel
        title="Operator controls"
        action={
          <Badge tone={toneRun(runState)}>{runState.toUpperCase()}</Badge>
        }
      >
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={setRunMut.isPending || runState === "running"}
            onClick={() => setRunMut.mutate("running")}
          >
            <Play className="h-4 w-4" />
            Start
          </Button>
          <Button
            variant="secondary"
            disabled={setRunMut.isPending || runState === "paused"}
            onClick={() => setRunMut.mutate("paused")}
          >
            <Pause className="h-4 w-4" />
            Pause
          </Button>
          <Button
            variant="ghost"
            disabled={setRunMut.isPending}
            onClick={() => setRunMut.mutate("stopped")}
          >
            <Square className="h-4 w-4" />
            Stop
          </Button>
          <Button
            variant="outline"
            disabled={executeNowMut.isPending}
            onClick={() => executeNowMut.mutate()}
          >
            <Zap className="h-4 w-4" />
            {executeNowMut.isPending ? "Executing…" : "Execute Now"}
          </Button>
          <Button variant="outline" onClick={() => setConfirmCloseAll(true)}>
            <XCircle className="h-4 w-4" />
            Close All
          </Button>
          <Button variant="outline" onClick={() => setConfirmCancel(true)}>
            Cancel Pending
          </Button>
          <Button variant="danger" onClick={() => setConfirmEmergency(true)}>
            <ShieldAlert className="h-4 w-4" />
            Emergency Stop
          </Button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Engine mode
          </span>
          <Button
            size="sm"
            variant={tradingMode === "scalping" ? "default" : "outline"}
            disabled={setModeMut.isPending}
            onClick={() => setModeMut.mutate("scalping")}
          >
            AI Scalping
          </Button>
          <Button
            size="sm"
            variant={tradingMode === "swing" ? "default" : "outline"}
            disabled={setModeMut.isPending}
            onClick={() => setModeMut.mutate("swing")}
          >
            Swing
          </Button>
          <Button
            size="sm"
            variant={compoundingEnabled ? "default" : "outline"}
            disabled={setCompoundMut.isPending}
            onClick={() => setCompoundMut.mutate(!compoundingEnabled)}
          >
            Compounding {compoundingEnabled ? "ON" : "OFF"}
          </Button>
          <span className="font-mono text-[10px] text-[var(--fg-muted)]">
            Max open {maxOpen} · Risk {riskPerTradePct}%
            {tradingMode === "scalping" ? " · H1→M1 (no H4)" : " · H4→M5"}
          </span>
        </div>
        {busyLabel ? (
          <p className="mt-2 text-xs text-[var(--accent)]">{busyLabel}</p>
        ) : null}
        {executeResult ? (
          <div className="mt-3 border border-[var(--border)] bg-[var(--bg)]/60 px-3 py-2.5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Execution Result
            </p>
            <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-3">
              <div>
                <dt className="text-[var(--fg-subtle)]">Market</dt>
                <dd className="font-mono text-[var(--fg)]">
                  {str(executeResult.market, TRADING_SYMBOL)}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Direction</dt>
                <dd className="font-mono text-[var(--fg)]">
                  {str(executeResult.direction, "—")}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Lot</dt>
                <dd className="font-mono text-[var(--fg)]">
                  {executeResult.lot == null ? "—" : String(executeResult.lot)}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Entry</dt>
                <dd className="font-mono text-[var(--fg)]">
                  {executeResult.entry == null ? "—" : String(executeResult.entry)}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">SL</dt>
                <dd className="font-mono text-[var(--fg)]">
                  {executeResult.sl == null ? "—" : String(executeResult.sl)}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">TP</dt>
                <dd className="font-mono text-[var(--fg)]">
                  {executeResult.tp == null ? "—" : String(executeResult.tp)}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Ticket</dt>
                <dd className="font-mono text-[var(--fg)]">
                  {str(executeResult.ticket, "—")}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Execution Time</dt>
                <dd className="font-mono text-[var(--fg)]">
                  {executeResult.execution_ms == null
                    ? "—"
                    : `${String(executeResult.execution_ms)} ms`}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Status</dt>
                <dd
                  className={cn(
                    "font-mono font-medium",
                    executeResult.success === true
                      ? "text-[var(--success)]"
                      : "text-[var(--danger)]",
                  )}
                >
                  {str(executeResult.status, executeResult.success === true ? "SUCCESS" : "REJECTED")}
                </dd>
              </div>
            </dl>
            {executeResult.success !== true ? (
              <p className="mt-2 text-xs text-[var(--danger)]">
                Reason:{" "}
                <span className="font-mono text-[var(--fg)]">
                  {str(executeResult.reason || executeResult.message, "—")}
                </span>
              </p>
            ) : (
              <p className="mt-2 text-xs text-[var(--fg-muted)]">
                {str(executeResult.message, "Order executed successfully.")}
              </p>
            )}
          </div>
        ) : null}
        <p className="mt-2 text-[10px] text-[var(--fg-subtle)]">
          Closes and cancels use the production execution pipeline — never a direct MT5 bypass.
        </p>
      </OpsPanel>

      {/* Live market */}
      <OpsPanel title="Live market">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">
          <MetricCard label="Bid" value={bid} large tone="buy" />
          <MetricCard label="Ask" value={ask} large tone="sell" />
          <MetricCard label="Spread" value={spread} large />
          <MetricCard label="ATR" value={atr} />
          <MetricCard label="Stop distance" value={stopDistance} />
          <MetricCard label="Risk budget" value={riskBudget} />
          <MetricCard label="Calculated lots" value={calculatedLots} />
          <MetricCard label="Volatility" value={volatility} />
          <MetricCard label="Trend" value={trend} />
          <MetricCard label="Regime" value={marketRegime} />
          <MetricCard label="Liquidity" value={liquidity} />
        </div>
        <p className="mt-2 font-mono text-[10px] text-[var(--fg-subtle)]">
          Mid {Number.isFinite(mid) ? formatNumber(mid, 3) : "—"} · Market{" "}
          {marketOpen ? "OPEN" : session.connected ? "QUIET" : "OFF"}
        </p>
      </OpsPanel>

      <div className="grid gap-3 xl:grid-cols-2">
        {/* AI strategy */}
        <OpsPanel
          title="AI strategy"
          action={
            <Badge tone={tradingMode === "scalping" ? "success" : "neutral"}>
              {tradingMode === "scalping" ? "SCALPING" : "SWING"}
            </Badge>
          }
        >
          <BiasMeter bias={bias} />
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
            <MetricCard label="AI Confidence" value={String(confidence)} tone="accent" />
            <MetricCard label="Trade Quality" value={String(qualityScore)} tone="accent" />
            <MetricCard label="Confluence" value={String(confluenceScore)} tone="accent" />
            <MetricCard label="Market Regime" value={marketRegime} />
            <MetricCard label="Momentum" value={momentum} />
            <MetricCard label="Liquidity" value={liquidity} />
            <MetricCard label="Expected RR" value={expectedRr} />
            <MetricCard label="Hold Time" value={expectedHold} />
            <MetricCard label="Session" value={tradingSession} />
            <MetricCard label="Current Risk %" value={`${formatNumber(riskPerTradePct, 2)}%`} />
            <MetricCard label="Current Lot" value={calculatedLots} />
            <MetricCard label="Execution Time" value={lastLatency} />
            <MetricCard label="Profit Projection" value={profitProjection} />
            <MetricCard label="Open Positions" value={String(positions.length)} />
            <MetricCard label="Win Rate" value={winRate} />
            <MetricCard
              label="Decision"
              value={str(last.decision_action || last.cycle_outcome, "—")}
            />
          </div>
          <p className="mt-3 text-[12px] text-[var(--fg-muted)]">
            Reason:{" "}
            <span className="text-[var(--fg)]">
              {str(aiScore.reject_reason, "") ||
                decisionReasons[0] ||
                exactSafetyReason ||
                "—"}
            </span>
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {AUTO_STRATEGY_MODULES.map((m) => {
              const st = strategyStats(m.id);
              const on = toggles[m.id];
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => toggleStrategy(m.id)}
                  className={cn(
                    "border px-3 py-2.5 text-left transition-colors duration-[var(--duration-os)]",
                    on
                      ? "border-[var(--accent)]/50 bg-[var(--accent-soft)]"
                      : "border-[var(--border)] opacity-70",
                  )}
                  aria-pressed={on}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-[var(--fg)]">{m.label}</span>
                    <Badge tone={on ? "success" : "neutral"}>{st.status}</Badge>
                  </div>
                  <p className="mt-1 text-[10px] text-[var(--fg-subtle)]">{m.hint}</p>
                </button>
              );
            })}
          </div>
        </OpsPanel>

        {/* Risk */}
        <OpsPanel title="Risk engine">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <MetricCard
              label="Today's Risk"
              value={`${formatNumber(dailyRiskUsed, 2)}%`}
              tone={dailyRiskUsed >= maxDailyLossPct ? "bad" : "neutral"}
            />
            <MetricCard label="Exposure" value={formatNumber(openExposure, 2)} />
            <MetricCard label="Open Positions" value={String(positions.length)} />
            <MetricCard
              label="Risk / Trade"
              value={`${formatNumber(riskPerTradePct, 2)}%`}
            />
            <MetricCard
              label="Daily Loss"
              value={`${formatNumber(dailyLossPct, 2)}%`}
              tone={dailyLossPct > 0 ? "warn" : "neutral"}
            />
            <MetricCard
              label="Risk Status"
              value={riskStatusLabel}
              tone={riskStatusLabel === "BLOCK" ? "bad" : "ok"}
            />
            <MetricCard
              label="Limit"
              value={`${formatNumber(maxDailyLossPct, 1)}%`}
            />
            <MetricCard label="Ops Mode" value={opsMode} />
          </div>
          {riskReasons.length > 0 ? (
            <ul className="mt-3 list-disc space-y-0.5 pl-4 text-[11px] text-[var(--danger)]">
              {riskReasons.slice(0, 4).map((r) => (
                <li key={`risk-${r}`}>{r}</li>
              ))}
            </ul>
          ) : null}
        </OpsPanel>
      </div>

      {/* Safety */}
      <OpsPanel
        title="Safety engine"
        action={
          <Badge tone={safetyBlocked || killArmed ? "danger" : "success"}>
            {safetyStatusLabel}
          </Badge>
        }
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <MetricCard
            label="Status"
            value={safetyStatusLabel}
            tone={safetyBlocked ? "bad" : "ok"}
          />
          <MetricCard
            label="Allowed Session"
            value={sessionAllowed ? "YES" : "NO"}
            tone={sessionAllowed ? "ok" : "warn"}
          />
          <MetricCard label="Session" value={tradingSession} />
          <MetricCard
            label="Emergency"
            value={killArmed ? "ARMED" : "CLEAR"}
            tone={killArmed ? "bad" : "ok"}
          />
        </div>
        <p className="mt-3 text-[12px] text-[var(--fg-muted)]">
          Exact reason:{" "}
          <span className="font-medium text-[var(--fg)]">{exactSafetyReason}</span>
        </p>
      </OpsPanel>

      {/* Performance */}
      <OpsPanel title="Performance · today">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
          <MetricCard label="Signals" value={String(signalsToday || "—")} />
          <MetricCard label="Rejected" value={String(rejectedToday || "—")} />
          <MetricCard label="Executed" value={String(executedToday || "—")} />
          <MetricCard label="Win Rate" value={todayWinRate} />
          <MetricCard
            label="PnL"
            value={formatNumber(pnlToday, 2)}
            tone={pnlToday >= 0 ? "ok" : "bad"}
          />
          <MetricCard label="Avg Latency" value={latencyMs} />
          <MetricCard
            label="Fill Rate"
            value={
              analytics.fill_rate != null
                ? `${formatNumber(num(analytics.fill_rate) * 100, 0)}%`
                : "—"
            }
          />
        </div>
      </OpsPanel>

      {/* Pipeline */}
      <OpsPanel title="Execution pipeline · last cycle">
        <ExecutionPipeline stages={livePipeline} />
        {!orch.last_cycle ? (
          <p className="mt-2 text-sm text-[var(--fg-muted)]">
            Pipeline stages update from the live orchestrator cycle — never fabricated.
          </p>
        ) : null}
      </OpsPanel>

      {/* Journal */}
      <OpsPanel title="Trade journal">
        {journalTimeline.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">
            Live journal and cycle events appear here.
          </p>
        ) : (
          <ul>
            <li className="mb-1 hidden grid-cols-[4.75rem_6.5rem_1fr_5.5rem_4.5rem] gap-2 text-[9px] uppercase tracking-[0.1em] text-[var(--fg-subtle)] md:grid">
              <span>Time</span>
              <span>Type</span>
              <span>Reason</span>
              <span>Status</span>
              <span className="text-right">Latency</span>
            </li>
            {journalTimeline.map((row, i) => (
              <JournalRow
                key={`${row.time}-${row.type}-${i}`}
                time={row.time}
                type={row.type}
                reason={row.reason}
                status={row.status}
                latency={row.latency}
              />
            ))}
          </ul>
        )}
      </OpsPanel>

      {/* Positions */}
      <OpsPanel title="Active positions">
        {positions.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">No open positions.</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {positions.map((p) => {
              const entry = num(p.open_price ?? p.price_open);
              const pnl = num(p.profit);
              const cur = Number.isFinite(mid)
                ? mid
                : num(p.current_price ?? p.price_current);
              return (
                <div
                  key={str(p.ticket)}
                  className="border border-[var(--border)] bg-[var(--bg)]/30 p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <Badge
                      tone={str(p.side).toLowerCase() === "buy" ? "success" : "danger"}
                    >
                      {str(p.side).toUpperCase()}
                    </Badge>
                    <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                      #{str(p.ticket)}
                    </span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-1 text-[11px]">
                    <span className="text-[var(--fg-subtle)]">Entry</span>
                    <span className="font-mono tabular text-right">
                      {formatNumber(entry, 3)}
                    </span>
                    <span className="text-[var(--fg-subtle)]">Current</span>
                    <span className="font-mono tabular text-right">
                      {Number.isFinite(cur) ? formatNumber(cur, 3) : "—"}
                    </span>
                    <span className="text-[var(--fg-subtle)]">PnL</span>
                    <span
                      className={cn(
                        "font-mono tabular text-right",
                        pnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
                      )}
                    >
                      {formatNumber(pnl, 2)}
                    </span>
                    <span className="text-[var(--fg-subtle)]">Volume</span>
                    <span className="font-mono tabular text-right">{str(p.volume)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </OpsPanel>

      {/* System health */}
      <OpsPanel title="System health">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <HealthDot label="CPU" ok={obsRes.cpu_percent != null ? num(obsRes.cpu_percent) < 90 : null} value={cpuPct} />
          <HealthDot label="RAM" ok={obsRes.memory_percent != null ? num(obsRes.memory_percent) < 90 : null} value={ramPct} />
          <HealthDot label="Gateway" ok={gatewayHealthOk} />
          <HealthDot
            label="Database"
            ok={dbOk}
            value={dbDep ? str(dbDep.status, "—") : undefined}
          />
          <HealthDot
            label="Redis"
            ok={redisOk}
            value={redisDep ? str(redisDep.status, "—") : undefined}
          />
          <HealthDot label="API" ok={apiOk} />
          <HealthDot label="Railway" ok={railwayOk} />
          <HealthDot label="MT5" ok={mt5HealthOk} />
        </div>
      </OpsPanel>

      <ConfirmDialog
        open={confirmEmergency}
        onOpenChange={setConfirmEmergency}
        title="Emergency Stop"
        description="This stops Auto Trading and arms the kill switch. Confirm to proceed. Open positions are not closed automatically — use Close All if required."
        confirmLabel="Confirm Emergency Stop"
        tone="danger"
        busy={emergencyMut.isPending}
        onConfirm={() => emergencyMut.mutate()}
      />
      <ConfirmDialog
        open={confirmCloseAll}
        onOpenChange={setConfirmCloseAll}
        title="Close all positions"
        description={`Submit market closes for ${positions.length} open position(s) through the execution pipeline.`}
        confirmLabel="Close all"
        tone="danger"
        busy={closeAllMut.isPending}
        onConfirm={() => closeAllMut.mutate()}
      />
      <ConfirmDialog
        open={confirmCancel}
        onOpenChange={setConfirmCancel}
        title="Cancel pending orders"
        description={`Cancel ${orders.length} pending order(s) through the execution pipeline.`}
        confirmLabel="Cancel pending"
        tone="danger"
        busy={cancelPendingMut.isPending}
        onConfirm={() => cancelPendingMut.mutate()}
      />
    </div>
  );

}

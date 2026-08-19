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
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps, iteOpsAccessDeniedMessage } from "@/lib/auth/ite-ops-access";
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
import { isGoldSymbol, TRADING_SYMBOL, WELTRADE_XAUUSD } from "@/lib/trading/gold-only";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn, formatNumber } from "@/lib/utils";
import { LaunchReadinessPanel } from "@/components/ops/launch-readiness-panel";
import {
  resolveTradingComponentsView,
} from "@/lib/trading/component-health";
import {
  autoTradingSurfaceCopy,
  classifyOpsFailure,
  resolveAutoTradingSurface,
  resolveTradingInfraState,
  type OpsQueryKind,
} from "@/lib/ops/auto-trading-surface";
import {
  readOpsTelemetry,
  rememberOpsTelemetry,
} from "@/lib/ops/ops-telemetry-cache";
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
  const auth = useAuth();
  const { user, opsReady, authPhase, loading: authLoading } = auth;
  const qc = useQueryClient();
  const session = useTradingSession();
  const [toggles, setToggles] = useState<StrategyToggleState>(() => loadStrategyToggles());
  const [confirmEmergency, setConfirmEmergency] = useState(false);
  const [confirmCloseAll, setConfirmCloseAll] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [busyLabel, setBusyLabel] = useState<string | null>(null);
  const [autoPausedNote] = useState<string | null>(null);
  const [executeResult, setExecuteResult] = useState<Record<string, unknown> | null>(
    null,
  );

  const opsEnabled = opsReady && canAccessIteOps(user);

  const componentsQ = useQuery({
    queryKey: ["trading-components-health"],
    queryFn: platformApi.tradingComponents,
    staleTime: 15_000,
    refetchInterval: 20_000,
    retry: 1,
  });
  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading"],
    queryFn: iteOpsApi.autoTrading,
    enabled: opsEnabled,
    retry: false,
    staleTime: 20_000,
    refetchInterval: opsEnabled ? 30_000 : false,
  });
  if (autoQ.isSuccess && autoQ.data) {
    rememberOpsTelemetry(autoQ.data);
  }
  const opsPayload = autoQ.data ?? readOpsTelemetry()?.payload ?? null;
  const coreSettled = autoQ.isFetched || autoQ.isError;
  const telemetryEnabled = opsEnabled && coreSettled;
  const centerQ = useQuery({
    queryKey: ["ite-ops-center"],
    queryFn: iteOpsApi.controlCenter,
    enabled: telemetryEnabled,
    retry: false,
    staleTime: 20_000,
    refetchInterval: telemetryEnabled ? 30_000 : false,
  });
  const signalsQ = useQuery({
    queryKey: ["strategy-signals", "auto-ws"],
    queryFn: strategyApi.signals,
    enabled: telemetryEnabled,
    retry: false,
    refetchInterval: telemetryEnabled ? 20_000 : false,
  });
  const journalQ = useQuery({
    queryKey: ["execution-journal", "auto-ws"],
    queryFn: () => executionApi.journal(60),
    enabled: telemetryEnabled,
    retry: false,
    refetchInterval: telemetryEnabled ? 15_000 : false,
  });
  const auditsQ = useQuery({
    queryKey: ["execution-audits", "auto-ws"],
    queryFn: () => executionApi.audits(80),
    enabled: telemetryEnabled,
    retry: false,
    refetchInterval: telemetryEnabled ? 15_000 : false,
  });
  const analyticsQ = useQuery({
    queryKey: ["execution-analytics", "auto-ws"],
    queryFn: () => executionApi.analytics(100),
    enabled: telemetryEnabled,
    retry: false,
    refetchInterval: telemetryEnabled ? 30_000 : false,
  });
  const positionsQ = useQuery({
    queryKey: ["portfolio-positions", "auto-ws"],
    queryFn: () => portfolioApi.positions(),
    enabled: telemetryEnabled,
    retry: false,
    refetchInterval: telemetryEnabled ? 12_000 : false,
  });
  const ordersQ = useQuery({
    queryKey: ["portfolio-orders", "auto-ws"],
    queryFn: () => portfolioApi.orders(),
    enabled: telemetryEnabled,
    retry: false,
    refetchInterval: telemetryEnabled ? 15_000 : false,
  });
  const mt5Q = useQuery({
    queryKey: ["mt5-status"],
    queryFn: () => mt5Api.status(),
    enabled: telemetryEnabled,
    retry: false,
    staleTime: 10_000,
    refetchInterval: telemetryEnabled ? 15_000 : false,
  });
  const healthQ = useQuery({
    queryKey: ["weltrade-health"],
    queryFn: () => weltradeApi.health(),
    enabled: telemetryEnabled,
    retry: false,
    staleTime: 15_000,
    refetchInterval: telemetryEnabled ? 20_000 : false,
  });
  const tickQ = useQuery({
    queryKey: ["mt5-tick", TRADING_SYMBOL],
    queryFn: () => mt5Api.tick(TRADING_SYMBOL),
    enabled: opsEnabled && session.connected,
    staleTime: 4_000,
    refetchInterval: opsEnabled && session.connected ? 5_000 : false,
    retry: false,
  });
  const auditLogQ = useQuery({
    queryKey: ["ite-ops-audit", "auto-ws"],
    queryFn: () => iteOpsApi.audit(40),
    enabled: telemetryEnabled,
    retry: false,
    refetchInterval: telemetryEnabled ? 30_000 : false,
  });
  const servicesHealthQ = useQuery({
    queryKey: ["ite-ops-services-health", "auto-ws"],
    queryFn: iteOpsApi.servicesHealth,
    enabled: telemetryEnabled,
    retry: false,
    refetchInterval: telemetryEnabled ? 30_000 : false,
  });
  const obsHealthQ = useQuery({
    queryKey: ["institutional-observability", "auto-ws"],
    queryFn: institutionalObservabilityApi.health,
    enabled: telemetryEnabled,
    retry: false,
    refetchInterval: telemetryEnabled ? 45_000 : false,
  });
  const obsResourcesQ = useQuery({
    queryKey: ["institutional-observability-resources", "auto-ws"],
    queryFn: institutionalObservabilityApi.resources,
    enabled: telemetryEnabled,
    retry: false,
    refetchInterval: telemetryEnabled ? 45_000 : false,
  });
  const apiHealthQ = useQuery({
    queryKey: ["system-health", "auto-ws"],
    queryFn: platformApi.health,
    enabled: telemetryEnabled,
    retry: false,
    refetchInterval: telemetryEnabled ? 30_000 : false,
  });

  const policy = asRecord(asRecord(opsPayload).policy);
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
  const aiScalping = asRecord(asRecord(opsPayload).ai_scalping);
  const aiScore = asRecord(aiScalping.ai_score);
  const gateStatus = str(asRecord(opsPayload).status, "—");
  const failedReasons = asList(asRecord(opsPayload).failed_reasons).map(String);
  const reasonGroups = asRecord(asRecord(opsPayload).reason_groups);
  const primaryBlocker = str(asRecord(opsPayload).primary_blocker, "");
  const blockingCategory = str(asRecord(opsPayload).blocking_category, "");
  const executionState = asRecord(asRecord(opsPayload).execution_state);
  const goldOnly = asRecord(
    asRecord(opsPayload).gold_only ?? executionState,
  );
  const goldOnlyMode = goldOnly.gold_only_mode !== false;
  const autonomousSymbol = str(
    goldOnly.canonical_symbol,
    WELTRADE_XAUUSD,
  );
  const executionEnabled = Boolean(
    executionState.execution_enabled ?? asRecord(opsPayload).execution_enabled,
  );
  const riskReasons = asList(reasonGroups.risk).map(String);
  const liveFacts = asRecord(asRecord(opsPayload).live);
  const gatewayLive = Boolean(
    executionState.gateway_connected ??
      liveFacts.gateway_connected ??
      asRecord(asRecord(opsPayload).facts).gateway_connected,
  );
  const brokerLive = Boolean(
    executionState.broker_connected ??
      liveFacts.broker_connected ??
      asRecord(asRecord(opsPayload).facts).broker_connected,
  );
  const killArmed = Boolean(
    executionState.kill_switch_armed ??
      asRecord(centerQ.data).kill_switch_armed ??
      asRecord(opsPayload).emergency_stop,
  );
  const opsMode = str(
    executionState.ops_mode ||
      asRecord(opsPayload).ops_mode ||
      asRecord(centerQ.data).execution_mode ||
      asRecord(centerQ.data).mode,
    "—",
  );

  const [opsWaitMs, setOpsWaitMs] = useState(0);
  useEffect(() => {
    if (!opsEnabled || opsPayload || autoQ.isError) {
      setOpsWaitMs(0);
      return;
    }
    const started = Date.now();
    setOpsWaitMs(0);
    const id = window.setInterval(() => setOpsWaitMs(Date.now() - started), 500);
    return () => window.clearInterval(id);
  }, [opsEnabled, opsPayload, autoQ.isError]);

  // Do not abort in-flight auto-trading when session planes flip on first load.

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
  // Only compute DD when both equity and balance are live (>0). Treating
  // equity=0 as valid previously produced a false 100% DD and auto-paused.
  const dailyDdPct =
    balance > 0 && equity > 0 ? Math.max(0, ((balance - equity) / balance) * 100) : 0;
  const dailyLossPct = todayPl < 0 && balance > 0 ? (Math.abs(todayPl) / balance) * 100 : 0;
  const dailyRiskUsed = Math.max(dailyDdPct, dailyLossPct);
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

  const signals = asList(asRecord(signalsQ.data).items ?? signalsQ.data).map(asRecord);

  const tick = asRecord(tickQ.data);
  const mid =
    Number.isFinite(num(tick.bid)) && Number.isFinite(num(tick.ask))
      ? (num(tick.bid) + num(tick.ask)) / 2
      : NaN;
  const marketOpen = session.connected && (tick.bid != null || tick.ask != null);

  const analytics = asRecord(asRecord(analyticsQ.data).metrics);
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
          : ["sydney", "tokyo", "london", "new_york", "london_ny_overlap"],
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
    mutationFn: (mode: "swing" | "scalping" | "alpha") =>
      iteOpsApi.updateAutoTrading({
        reason: `operator set trading_mode=${mode}`,
        confirmed: true,
        trading_mode: mode,
        alpha_engine_enabled: mode === "alpha",
        max_open_positions:
          mode === "scalping" || mode === "alpha"
            ? Math.max(maxOpen || 1, 3)
            : maxOpen || 1,
        risk_per_trade_pct: String(riskPerTradePct || 1),
        max_daily_loss_pct: String(maxDailyLossPct || 3),
        max_spread: str(policy.max_spread, "2.00"),
        allowed_symbols:
          mode === "alpha"
            ? ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "NAS100", "US30", "BTCUSD"]
            : ["XAUUSD"],
        allowed_sessions: asList(policy.allowed_sessions).map(String).length
          ? asList(policy.allowed_sessions).map(String)
          : ["sydney", "tokyo", "london", "new_york", "london_ny_overlap"],
        news_filter_enabled: Boolean(policy.news_filter_enabled),
        compounding_enabled: compoundingEnabled,
        run_state: runState === "off" ? undefined : runState,
        enabled: runState === "running" || runState === "paused" ? true : undefined,
      }),
    onSuccess: (_data, mode) => {
      toast.success(
        mode === "alpha"
          ? "Institutional Alpha enabled"
          : mode === "scalping"
            ? "AI Scalping Mode enabled"
            : "Swing Mode enabled",
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
          : ["sydney", "tokyo", "london", "new_york", "london_ny_overlap"],
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

  // Never auto-mutate run_state to PAUSED from the browser.
  // Daily-loss / kill locks are enforced by the ITE safety gate on the server.
  // False equity=0 DD previously forced PAUSED and required a manual Resume.

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

  const componentsView = resolveTradingComponentsView({
    payload: componentsQ.data,
    isSuccess: componentsQ.isSuccess,
    isError: componentsQ.isError,
    errorKind:
      componentsQ.error instanceof ApiError && componentsQ.error.code === "timeout"
        ? "timeout"
        : componentsQ.error instanceof ApiError && componentsQ.error.code === "network_error"
          ? "network"
          : componentsQ.isError
            ? "other"
            : null,
  });
  const tradingInfra = resolveTradingInfraState({
    gatewayOk: componentsView?.gateway.ok,
    mt5Ok: componentsView?.mt5.ok,
    omsOk: componentsView?.oms.ok,
  });
  const opsQueryKind: OpsQueryKind = !opsEnabled
    ? authLoading || authPhase === "AUTH_LOADING"
      ? "idle"
      : authPhase === "AUTH_REQUIRED"
        ? "unauthorized"
        : user && !canAccessIteOps(user)
          ? "forbidden"
          : "idle"
    : autoQ.isSuccess
      ? "success"
      : autoQ.isError
        ? classifyOpsFailure(
            autoQ.error instanceof ApiError
              ? { status: autoQ.error.status, code: autoQ.error.code }
              : null,
          )
        : autoQ.isLoading || autoQ.isFetching
          ? "loading"
          : "idle";
  const surface = resolveAutoTradingSurface({
    authPhase,
    opsQuery: opsQueryKind,
    hasOpsData: Boolean(opsPayload),
    tradingInfra,
    opsWaitMs,
    opsFresh: autoQ.isSuccess && Boolean(autoQ.data),
  });
  const surfaceCopy = autoTradingSurfaceCopy(surface);

  if (surface.surface === "AUTHENTICATING") {
    return (
      <div className="space-y-3">
        <p className="text-sm text-[var(--fg-muted)]">{surfaceCopy.detail}</p>
        <DeskSkeleton rows={8} />
      </div>
    );
  }
  if (surface.surface === "AUTH_REQUIRED") {
    return (
      <DeskError
        message={surfaceCopy.detail}
        onRetry={() => {
          void auth.refreshMe();
        }}
      />
    );
  }
  if (surface.surface === "UNAVAILABLE") {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(user, autoQ.error, "Auto Trading")}
        onRetry={() => {
          void qc.invalidateQueries({ queryKey: ["ite-ops-auto-trading"] });
        }}
      />
    );
  }
  if (surface.surface === "API_UNREACHABLE") {
    return (
      <div className="space-y-4" role="status">
        <div className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-[var(--space-3)]">
          <p className="text-sm font-medium text-[var(--fg)]">{surfaceCopy.title}</p>
          <p className="mt-1 text-sm text-[var(--fg-muted)]">{surfaceCopy.detail}</p>
          <p className="mt-2 font-mono text-[11px] text-[var(--fg-subtle)]">
            infra={tradingInfra} · gateway=
            {componentsView?.gateway.status || "UNKNOWN"} · mt5=
            {componentsView?.mt5.status || "UNKNOWN"} · oms=
            {componentsView?.oms.status || "UNKNOWN"}
          </p>
          <Button
            className="mt-3"
            size="sm"
            variant="secondary"
            onClick={() => {
              void qc.invalidateQueries({ queryKey: ["ite-ops-auto-trading"] });
            }}
          >
            Retry ops
          </Button>
        </div>
      </div>
    );
  }
  if (
    (surface.surface === "LOADING_OPS" || surface.surface === "DEGRADED") &&
    !opsPayload
  ) {
    return (
      <div className="space-y-4" role="status">
        <div className="rounded-[var(--radius-os)] border border-[var(--warning)]/30 bg-[var(--surface)] p-[var(--space-3)]">
          <p className="text-sm font-medium text-[var(--fg)]">{surfaceCopy.title}</p>
          <p className="mt-1 text-sm text-[var(--fg-muted)]">{surfaceCopy.detail}</p>
          <p className="mt-2 font-mono text-[11px] text-[var(--fg-subtle)]">
            infra={tradingInfra} · gateway=
            {componentsView?.gateway.status || "UNKNOWN"} · mt5=
            {componentsView?.mt5.status || "UNKNOWN"} · oms=
            {componentsView?.oms.status || "UNKNOWN"}
          </p>
          {surface.surface === "LOADING_OPS" ? <DeskSkeleton rows={6} /> : null}
          {surface.surface === "DEGRADED" ? (
            <Button
              className="mt-3"
              size="sm"
              variant="secondary"
              onClick={() => {
                void qc.invalidateQueries({ queryKey: ["ite-ops-auto-trading"] });
                void qc.invalidateQueries({ queryKey: ["trading-components-health"] });
              }}
            >
              Retry ops
            </Button>
          ) : null}
        </div>
      </div>
    );
  }
  if (!opsPayload) {
    return <DeskSkeleton rows={8} />;
  }

  const orch = asRecord(asRecord(opsPayload).orchestrator);
  const last = asRecord(orch.last_cycle);
  const diag = asRecord(last.market_context_diagnostics);
  const scanSnap = asRecord(aiScalping.scan);
  const currentScan = asRecord(
    orch.current_scan ??
      scanSnap.current_scan ??
      asRecord(asRecord(opsPayload).fast_decision).current_scan,
  );
  const lastPipeline = asRecord(
    orch.last_pipeline ??
      asRecord(asRecord(opsPayload).fast_decision).last_pipeline,
  );
  const bestCandidate = asRecord(
    currentScan.best_candidate ?? scanSnap.best_candidate ?? scanSnap.best,
  );
  const bestCandidateSymbol = goldOnlyMode
    ? isGoldSymbol(str(bestCandidate.symbol || currentScan.symbol))
      ? str(bestCandidate.symbol || currentScan.symbol, autonomousSymbol)
      : "NONE"
    : str(bestCandidate.symbol || currentScan.symbol, "—");
  const bestEligible = asRecord(
    currentScan.best_eligible ?? scanSnap.best_eligible_candidate,
  );
  const eligibleCount = str(
    currentScan.eligible_count ?? scanSnap.eligible_count,
    "0",
  );
  const noEligibleSetup =
    str(currentScan.state) === "NO_ELIGIBLE_SETUP" ||
    (Boolean(scanSnap.no_eligible_setup) && !str(scanSnap.best_symbol)) ||
    num(currentScan.eligible_count ?? scanSnap.eligible_count, 0) === 0;
  const namedRejectReasons = asList(
    currentScan.all_reject_reasons ?? bestCandidate.reject_reasons,
  ).map(String);
  const rawBlockingGate = str(
    currentScan.first_blocking_gate ||
      currentScan.fault_reason ||
      namedRejectReasons[0] ||
      scanSnap.first_blocking_gate,
    "",
  );
  const genericBlockingGate =
    !rawBlockingGate ||
    rawBlockingGate === "NO_ELIGIBLE_SETUP" ||
    rawBlockingGate === "NONE" ||
    rawBlockingGate === "NO_CURRENT_BLOCKING_GATE";
  const firstBlockingGateFull =
    namedRejectReasons[0] ||
    (!genericBlockingGate
      ? rawBlockingGate
      : noEligibleSetup
        ? "NO_ELIGIBLE_SETUP"
        : "—");
  const otherRejectReasons = namedRejectReasons.filter(
    (reason) => reason && reason !== firstBlockingGateFull,
  );
  const optimizerSnap = asRecord(
    noEligibleSetup
      ? {}
      : (diag.execution_optimizer ?? lastPipeline.optimizer_result ?? {}),
  );
  const optimizerState = "NOT_RUN";
  const optimizerRemaining = str(optimizerSnap.remaining_wait_ms, "0");
  const optimizerLabel = "NOT_RUN";
  const lastPipelineOutcome = str(
    lastPipeline.cycle_outcome || last.cycle_outcome,
    "",
  ).toLowerCase();
  const lastSafetyState = str(lastPipeline.safety_state, "");
  const lastOptimizerState = str(lastPipeline.optimizer_state, "NOT_RUN");
  const currentSafetyState = "NOT_REACHED";
  const lastSafetyReasons = asList(
    lastPipeline.safety_failed_reasons ?? last.safety_failed_reasons,
  ).map(String);
  const decisionReasons = asList(last.decision_reasons).map(String);
  const pipelineSafetyState = "NOT_REACHED";
  const pipelineOptimizerState = "NOT_RUN";

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
    statusLabel?: string;
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
        Boolean(last.decision_action) ||
          cycleOutcome.includes("no_trade") ||
          noEligibleSetup,
        cycleOutcome.includes("decision") && cycleOutcome.includes("fail"),
      ),
      statusLabel: noEligibleSetup ? "NO_ELIGIBLE" : undefined,
      detail: noEligibleSetup
        ? str(currentScan.state, "NO_ELIGIBLE_SETUP")
        : str(last.decision_action || last.cycle_outcome, ""),
    },
    {
      id: "risk",
      label: "Risk",
      state: noEligibleSetup
        ? "waiting"
        : stageOf(
            cycleOutcome === "forwarded" ||
              cycleOutcome === "safety_blocked" ||
              (cycleOutcome.length > 0 && !cycleOutcome.includes("risk")),
            cycleOutcome.includes("risk") || riskReasons.length > 0,
          ),
      statusLabel: noEligibleSetup ? "NOT_REACHED" : undefined,
      detail: noEligibleSetup ? "Current scan did not reach Risk" : riskReasons[0] || "",
    },
    {
      id: "safety",
      label: "Safety",
      state: "waiting",
      statusLabel: pipelineSafetyState,
      detail: "Current scan did not reach Safety",
    },
    {
      id: "optimizer",
      label: "Optimizer",
      state: "waiting",
      statusLabel: pipelineOptimizerState,
      detail: "Current scan did not reach Optimizer",
    },
    {
      id: "oms",
      label: "OMS",
      state: noEligibleSetup
        ? "waiting"
        : stageOf(
            forwarded,
            Boolean(str(last.oms_message)) && !forwarded && cycleOutcome.includes("oms"),
          ),
      statusLabel: noEligibleSetup ? "NOT_REACHED" : undefined,
      detail: noEligibleSetup
        ? "Current scan did not reach OMS"
        : cycleOutcome === "execution_deferred"
          ? `WAIT_BOUNDED remaining=${optimizerRemaining}ms`
          : str(last.oms_message, ""),
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

  const safetyBlocked = killArmed || failedReasons.length > 0;
  const safetyStatusLabel = killArmed
    ? "BLOCK"
    : failedReasons.length
      ? "BLOCK"
      : gateStatus.toLowerCase() === "enabled"
        ? "PASS"
        : str(gateStatus, "—").toUpperCase();
  const exactSafetyReason = killArmed
    ? "Emergency STOP is armed"
    : failedReasons[0] ||
      "Ops safety poll — cycle Safety is on Last completed ITE cycle";

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
  const forceFirst = asRecord(asRecord(opsPayload).force_first_trade);
  const forceBanner = Boolean(forceFirst.banner);
  const riskLockOverride = asRecord(asRecord(opsPayload).risk_lock_override);
  const riskLockBanner = Boolean(riskLockOverride.banner);
  const opportunityTarget = asRecord(asRecord(opsPayload).daily_opportunity_target);
  const oppPerf = asRecord(opportunityTarget.performance);
  const tradesTodayTarget = num(opportunityTarget.trades_today, executedToday);
  const targetTradesDay = num(opportunityTarget.target_trades_per_day, 3);
  return (
    <div className="space-y-3">
      {surface.surface === "DEGRADED" ? (
        <section
          role="status"
          className="border border-[var(--warning)] bg-[var(--warning)]/10 px-3 py-2.5"
        >
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--warning)]">
            {surfaceCopy.title}
          </p>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">{surfaceCopy.detail}</p>
        </section>
      ) : null}
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
      {riskLockBanner ? (
        <section
          role="status"
          className="border border-[var(--warning)] bg-[var(--warning)]/10 px-3 py-2.5"
        >
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--warning)]">
            TEST MODE
          </p>
          <p className="mt-1 text-sm font-medium text-[var(--fg)]">
            Daily loss lock overridden.
          </p>
          <p className="mt-0.5 text-xs text-[var(--fg-muted)]">
            Risk Engine remains active. Margin, broker validation, market closed,
            invalid volume/stops, and emergency stop are never bypassed.
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
              label={`AUTO ${String(runState || "off").toUpperCase()}`}
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
            <Badge tone={goldOnlyMode ? "neutral" : "warning"}>
              {goldOnlyMode ? "GOLD ONLY" : "MULTI SYMBOL"}
            </Badge>
            <Badge tone={runState === "running" ? "success" : "neutral"}>
              AUTONOMOUS = {String(runState || "off").toUpperCase()}
            </Badge>
            <Badge tone="neutral">
              AUTO {autonomousSymbol}
            </Badge>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="font-mono text-[11px] tabular text-[var(--fg-muted)]">
              Latency {latencyMs}
            </span>
            <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-[var(--fg-muted)]">
              {tradingSession}
            </span>
            <span className="font-mono text-[11px] text-[var(--fg)]">{autonomousSymbol}</span>
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
        {goldOnlyMode ? (
          <p className="mt-2 font-mono text-[11px] text-[var(--fg-muted)]">
            TRADING MODE: GOLD ONLY · AUTONOMOUS SYMBOL: {autonomousSymbol} ·
            AUTONOMOUS = {runState === "running" ? "RUNNING" : String(runState || "off").toUpperCase()} ·
            OTHER PAIRS: DISABLED FOR AUTONOMOUS EXECUTION · CURRENT FOCUS:{" "}
            {(() => {
              const focus = str(currentScan.executable_focus, "");
              if (!focus) return "NONE";
              return isGoldSymbol(focus) ? focus : "NONE";
            })()}
          </p>
        ) : null}
        {(() => {
          const accountLev = num(
            session.leverage || asRecord(mt5Q.data).leverage,
            NaN,
          );
          const deskMax = num(
            goldOnly.desk_max_leverage ?? asRecord(policy).desk_max_leverage,
            NaN,
          );
          const hasAccount = Number.isFinite(accountLev);
          const hasDesk = Number.isFinite(deskMax) && deskMax > 0;
          let status = "—";
          if (hasAccount && hasDesk) {
            status = accountLev <= deskMax ? "PASS" : "BLOCK";
          }
          const statusTone =
            status === "PASS"
              ? "text-[var(--success)]"
              : status === "BLOCK"
                ? "text-[var(--danger)]"
                : "text-[var(--fg-muted)]";
          return (
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              <div>
                <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                  LEVERAGE · Account
                </p>
                <p className="font-mono text-[13px] tabular text-[var(--fg)]">
                  {hasAccount ? String(accountLev) : "—"}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                  Desk Max
                </p>
                <p className="font-mono text-[13px] tabular text-[var(--fg)]">
                  {hasDesk ? String(deskMax) : "—"}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                  Leverage gate
                </p>
                <p className={`font-mono text-[13px] ${statusTone}`}>{status}</p>
              </div>
            </div>
          );
        })()}
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] px-3 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            30-minute opportunity tracker
          </h2>
          <Badge
            tone={
              Boolean(asRecord(asRecord(opsPayload).fast_decision).active)
                ? "warning"
                : "neutral"
            }
            className="h-5 px-1.5 text-[10px]"
          >
            {str(
              asRecord(asRecord(opsPayload).fast_decision).tracker_state
                || asRecord(asRecord(opsPayload).fast_decision).decision_state,
              "FOCUS_FORMING",
            )}
          </Badge>
        </div>
        <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
          Observes {autonomousSymbol} only. Does not force trades or
          bypass Safety/Risk/OMS.
        </p>
        {(() => {
          const fd = asRecord(asRecord(opsPayload).fast_decision);
          const remain = num(fd.remaining_seconds, 0);
          const mm = Math.floor(Math.max(0, remain) / 60);
          const ss = Math.floor(Math.max(0, remain) % 60);
          const pad = (n: number) => String(n).padStart(2, "0");
          const windowFocus = str(fd.current_focus, "NONE") || "NONE";
          const windowBest = str(
            fd.best_candidate || fd.current_best_candidate || fd.symbol,
            "NONE",
          );
          const windowEligible = str(fd.eligible_count, "0");
          const windowNext = str(fd.next_action, "—");
          const windowGate = str(
            fd.blocking_gate || fd.fault_reason || fd.first_blocking_gate,
            "—",
          );
          const windowFault = str(fd.fault_code, "—");
          const windowDetail = str(fd.fault_reason, windowGate);
          const trackerState = str(fd.tracker_state, str(fd.decision_state, "FOCUS_FORMING"));
          const blockingStage = str(fd.blocking_stage, "—");
          const executionReadiness = str(
            fd.execution_readiness || fd.decision_state,
            "NOT_READY",
          );
          const firstBlocker = str(
            fd.first_authoritative_blocker || windowDetail,
            "—",
          );
          const readiness = asRecord(asRecord(fd.readiness_matrix).stages);
          const bottleneck = asRecord(fd.bottleneck_report);
          const stageOrder = [
            "MARKET",
            "STRATEGY",
            "DECISION",
            "SAFETY",
            "RISK",
            "SIZING",
            "PORTFOLIO",
            "OPTIMIZER",
            "OMS",
            "BROKER",
          ] as const;
          return (
            <div className="mt-2 space-y-3">
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                  Time remaining
                </p>
                <p className="font-mono text-[13px] tabular text-[var(--fg)]">
                  {pad(mm)}:{pad(ss)}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                  Current state
                </p>
                <p className="font-mono text-[13px] text-[var(--fg)]">
                  {trackerState}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                  Current focus
                </p>
                <p className="font-mono text-[13px] text-[var(--fg)]">
                  {windowFocus}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                  Current best candidate
                </p>
                <p className="font-mono text-[13px] text-[var(--fg)]">
                  {windowBest}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                  Eligible count
                </p>
                <p className="font-mono text-[13px] text-[var(--fg)]">
                  {windowEligible}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                  Next action
                </p>
                <p className="font-mono text-[13px] text-[var(--fg)]">
                  {windowNext}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                  Blocking stage
                </p>
                <p className="font-mono text-[13px] text-[var(--fg)]">
                  {blockingStage}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                  Execution readiness
                </p>
                <p className="font-mono text-[13px] text-[var(--fg)]">
                  {executionReadiness}
                </p>
              </div>
              <div className="sm:col-span-2 lg:col-span-1">
                <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                  Current fault
                </p>
                <p className="truncate font-mono text-[12px] text-[var(--fg)]" title={windowDetail}>
                  {windowFault}
                </p>
              </div>
              <div className="sm:col-span-2 lg:col-span-4">
                <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                  Current blocking gate
                </p>
                <p className="text-[12px] text-[var(--fg)]" title={windowGate}>
                  {windowGate}
                </p>
                <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
                  {windowDetail}
                </p>
                {firstBlocker && firstBlocker !== "—" ? (
                  <p className="mt-1 font-mono text-[11px] text-[var(--fg)]">
                    First authoritative blocker: {firstBlocker}
                  </p>
                ) : null}
              </div>
              </div>
              <div>
                <p className="text-[9px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  Execution readiness
                </p>
                <div className="mt-1 grid grid-cols-2 gap-1 sm:grid-cols-5">
                  {stageOrder.map((stage) => {
                    const status = str(readiness[stage], "NOT_REACHED");
                    const tone =
                      status === "PASS"
                        ? "text-[var(--success)]"
                        : status === "BLOCK"
                          ? "text-[var(--danger)]"
                          : status === "WAIT"
                            ? "text-[var(--warning)]"
                            : "text-[var(--fg-muted)]";
                    return (
                      <div
                        key={stage}
                        className="border border-[var(--border)] px-2 py-1"
                      >
                        <p className="text-[9px] uppercase text-[var(--fg-subtle)]">
                          {stage}
                        </p>
                        <p className={`font-mono text-[11px] ${tone}`}>{status}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
              {str(bottleneck.why_no_order) ? (
                <p className="font-mono text-[11px] text-[var(--fg-muted)]">
                  Bottleneck: {str(bottleneck.why_no_order)}
                </p>
              ) : null}
            </div>
          );
        })()}
      </section>

      <LaunchReadinessPanel />

      <section className="border border-[var(--border)] bg-[var(--surface)] px-3 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Daily opportunity target
          </h2>
          <Badge tone="neutral" className="h-5 px-1.5 text-[10px]">
            {str(opportunityTarget.seeking_mode, "seeking_quality_opportunities")}
          </Badge>
        </div>
        <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
          Target is opportunity-based — never forces trades. Safety/Risk/OMS always win.
        </p>
        <div className="mt-2 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <div>
            <p className="text-[9px] uppercase text-[var(--fg-subtle)]">Trades today</p>
            <p className="font-mono text-[13px] tabular text-[var(--fg)]">
              {tradesTodayTarget} / {targetTradesDay}
            </p>
          </div>
          <div>
            <p className="text-[9px] uppercase text-[var(--fg-subtle)]">Remaining</p>
            <p className="font-mono text-[13px] tabular text-[var(--fg)]">
              {str(opportunityTarget.remaining_trade_opportunities, "—")}
            </p>
          </div>
          <div>
            <p className="text-[9px] uppercase text-[var(--fg-subtle)]">Open positions</p>
            <p className="font-mono text-[13px] tabular text-[var(--fg)]">
              {positions.length}
            </p>
          </div>
          <div>
            <p className="text-[9px] uppercase text-[var(--fg-subtle)]">Win rate</p>
            <p className="font-mono text-[13px] tabular text-[var(--fg)]">
              {Number.isFinite(num(oppPerf.win_rate, NaN))
                ? `${(num(oppPerf.win_rate) * 100).toFixed(0)}%`
                : "—"}
            </p>
          </div>
          <div>
            <p className="text-[9px] uppercase text-[var(--fg-subtle)]">Expectancy</p>
            <p className="font-mono text-[13px] tabular text-[var(--fg)]">
              {Number.isFinite(num(oppPerf.expectancy_per_trade, NaN))
                ? num(oppPerf.expectancy_per_trade).toFixed(2)
                : "—"}
            </p>
          </div>
          <div>
            <p className="text-[9px] uppercase text-[var(--fg-subtle)]">Last reject gate</p>
            <p className="truncate font-mono text-[11px] text-[var(--fg)]">
              {str(opportunityTarget.last_reject_gate, "—")}
            </p>
          </div>
        </div>
      </section>

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
            disabled={executeNowMut.isPending || surface.blockNewEntries}
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
        <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
          Autonomous Gold execution uses the scheduler cycle — Execute Now is
          manual only and is not required when AUTONOMOUS = RUNNING.
        </p>
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
            variant={tradingMode === "alpha" ? "default" : "outline"}
            disabled={setModeMut.isPending}
            onClick={() => setModeMut.mutate("alpha")}
          >
            Institutional Alpha
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
            {tradingMode === "alpha"
              ? " · Multi-symbol Alpha"
              : tradingMode === "scalping"
                ? " · H1→M1 (no H4)"
                : " · H4→M5"}
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
            <Badge
              tone={
                tradingMode === "alpha" || tradingMode === "scalping"
                  ? "success"
                  : "neutral"
              }
            >
              {tradingMode === "alpha"
                ? "ALPHA"
                : tradingMode === "scalping"
                  ? "SCALPING"
                  : "SWING"}
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

      {/* Current scan vs last ITE cycle — never merged */}
      <OpsPanel title="Current scan">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
          <MetricCard
            label="Best candidate"
            value={bestCandidateSymbol}
          />
          <MetricCard
            label="Best eligible"
            value={
              noEligibleSetup
                ? "—"
                : str(bestEligible.symbol || scanSnap.best_symbol, "—")
            }
          />
          <MetricCard label="Eligible count" value={eligibleCount} />
          <MetricCard
            label="First blocking gate"
            value={firstBlockingGateFull}
          />
          <MetricCard
            label="Optimizer"
            value={optimizerLabel}
            tone="neutral"
          />
          <MetricCard
            label="Safety"
            value={currentSafetyState}
            tone="neutral"
          />
          <MetricCard
            label="Next action"
            value={str(currentScan.next_action, "—")}
          />
          <MetricCard
            label="Fault code"
            value={str(currentScan.fault_code, "—")}
          />
        </div>
        <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
          Best Candidate may be rejected. Only Best Eligible / execution-ready
          can become an execution focus. Soft optimizer never waits forever.
          Hard Safety / Risk / min-lot gates remain authoritative.
        </p>
        <div className="mt-3 border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2">
          <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            First blocking gate · detail
          </p>
          <p className="mt-1 font-mono text-[12px] text-[var(--fg)]">
            {str(currentScan.symbol || bestCandidate.symbol, "—")} ·{" "}
            {str(currentScan.fault_code, "—")} · {firstBlockingGateFull}
          </p>
          {otherRejectReasons.length > 0 ? (
            <p className="mt-1 font-mono text-[11px] text-[var(--fg-muted)]">
              OTHER REJECTS: {otherRejectReasons.join(" · ")}
            </p>
          ) : null}
          <p className="mt-1 font-mono text-[11px] text-[var(--fg-muted)]">
            ATR%={str(currentScan.atr_pct, "—")} hard_min=
            {str(currentScan.hard_min_pct, "—")} band=
            {str(currentScan.band, "—")} tf=
            {str(currentScan.atr_source_timeframe, "M15")} as_of=
            {str(currentScan.as_of, "—")} next=
            {str(currentScan.next_action, "—")}
          </p>
        </div>
      </OpsPanel>

      <OpsPanel title="Last completed ITE cycle">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
          <MetricCard
            label="Pipeline symbol"
            value={
              lastPipeline.autonomous_valid === false
                ? "—"
                : str(lastPipeline.last_pipeline_symbol || lastPipeline.symbol, "—")
            }
          />
          <MetricCard
            label="Cycle outcome"
            value={str(lastPipeline.cycle_outcome || lastPipelineOutcome, "—")}
          />
          <MetricCard
            label="Safety"
            value={str(lastSafetyState, "—")}
            tone={
              lastSafetyState === "FAIL"
                ? "bad"
                : lastSafetyState === "PASS"
                  ? "ok"
                  : "neutral"
            }
          />
          <MetricCard
            label="Optimizer"
            value={str(lastOptimizerState, "NOT_RUN")}
          />
          <MetricCard
            label="OMS"
            value={str(lastPipeline.oms_state, "—")}
          />
        </div>
        <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
          Separate from Current scan. Safety symbol={" "}
          {str(lastPipeline.last_safety_symbol, "—")} · Optimizer symbol={" "}
          {str(lastPipeline.last_optimizer_symbol, "—")}
          {lastSafetyReasons[0] ? ` · ${lastSafetyReasons[0]}` : ""}
        </p>
      </OpsPanel>

      {/* Pipeline */}
      <OpsPanel title="Execution pipeline · current scan">
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

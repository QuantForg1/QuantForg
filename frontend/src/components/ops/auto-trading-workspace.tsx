"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  Bot,
  Pause,
  Play,
  ShieldAlert,
  Square,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/execution/confirm-dialog";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import {
  executionApi,
  iteOpsApi,
  mt5Api,
  portfolioApi,
  strategyApi,
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

type RunState = "off" | "running" | "paused" | "stopped";

function Panel({
  title,
  children,
  action,
  danger,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <section
      className={cn(
        "border bg-[var(--surface)]",
        danger ? "border-[var(--danger)]/50" : "border-[var(--border)]",
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "ok" | "warn" | "bad" | "neutral";
}) {
  const color =
    tone === "ok"
      ? "text-[var(--success)]"
      : tone === "warn"
        ? "text-[var(--warning)]"
        : tone === "bad"
          ? "text-[var(--danger)]"
          : "text-[var(--fg)]";
  return (
    <div className="min-w-0 border border-[var(--border)] bg-[var(--bg)]/35 px-2.5 py-2">
      <p className="text-[9px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">{label}</p>
      <p className={cn("mt-1 truncate font-mono text-[12px] tabular", color)}>{value}</p>
    </div>
  );
}

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
  const gateStatus = str(asRecord(autoQ.data).status, "—");
  const failedReasons = asList(asRecord(autoQ.data).failed_reasons).map(String);
  const reasonGroups = asRecord(asRecord(autoQ.data).reason_groups);
  const riskReasons = asList(reasonGroups.risk).map(String);
  const connectivityReasons = asList(reasonGroups.connectivity).map(String);
  const operatorReasons = [
    ...asList(reasonGroups.operator).map(String),
    ...asList(reasonGroups.configuration).map(String),
    ...asList(reasonGroups.safety).map(String),
  ];
  const liveFacts = asRecord(asRecord(autoQ.data).live);
  const gatewayLive = Boolean(
    liveFacts.gateway_connected ?? asRecord(asRecord(autoQ.data).facts).gateway_connected,
  );
  const brokerLive = Boolean(
    liveFacts.broker_connected ?? asRecord(asRecord(autoQ.data).facts).broker_connected,
  );
  const killArmed = Boolean(
    asRecord(centerQ.data).kill_switch_armed ?? asRecord(autoQ.data).emergency_stop,
  );
  const opsMode = str(
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
      }),
    onSuccess: () => {
      toast.success("Auto Trading state updated");
      invalidate();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Failed to update Auto Trading"),
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
    const decision = str(s.decision || s.status || s.outcome, "queued").toLowerCase();
    let status = "Queued";
    if (decision.includes("allow") || decision.includes("approv")) status = "Approved";
    else if (decision.includes("reject") || decision.includes("block")) status = "Rejected";
    else if (decision.includes("execut") || decision.includes("fill")) status = "Executed";
    else if (decision.includes("expir")) status = "Expired";
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

  return (
    <div className="space-y-3">
      {/* 1. Overview status bar */}
      <section className="border border-[var(--border)] bg-[var(--surface)] px-3 py-2.5">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Bot className="h-4 w-4 text-[var(--fg-subtle)]" aria-hidden />
            <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Auto Trading · Command Center
            </span>
            <Badge tone={toneRun(runState)}>{runState.toUpperCase()}</Badge>
            <Badge tone={killArmed ? "danger" : "neutral"}>
              {killArmed ? "KILL ARMED" : "Kill clear"}
            </Badge>
            <Badge tone={gateStatus.toLowerCase() === "enabled" ? "success" : "warning"}>
              Gate {gateStatus}
            </Badge>
          </div>
          <Button asChild size="sm" variant="ghost">
            <Link href="/ops">ITE Ops</Link>
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
          <Stat label="Engine" value={runState.toUpperCase()} tone={runState === "running" ? "ok" : "warn"} />
          <Stat label="Market" value={marketOpen ? "OPEN" : session.connected ? "QUIET" : "OFF"} />
          <Stat
            label="Strategy"
            value={
              Object.values(toggles).some(Boolean) ? "ARMED" : "ALL OFF"
            }
          />
          <Stat
            label="Gateway"
            value={gatewayLive ? "CONNECTED" : "OFFLINE"}
            tone={gatewayLive ? "ok" : "bad"}
          />
          <Stat
            label="Broker"
            value={
              brokerLive || session.connected || asRecord(mt5Q.data).connected
                ? "LIVE"
                : "OFF"
            }
            tone={brokerLive || session.connected ? "ok" : "bad"}
          />
          <Stat
            label="Risk"
            value={
              riskReasons.length
                ? "BLOCK"
                : asRecord(asRecord(autoQ.data).facts).risk_engine_evaluated === false
                  ? "N/A"
                  : "PASS"
            }
            tone={riskReasons.length ? "bad" : "neutral"}
          />
          <Stat
            label="Ops Mode"
            value={opsMode}
            tone={opsMode === "LIVE" || opsMode === "CANARY" ? "ok" : "warn"}
          />
          <Stat label="Last Signal" value={lastSignalTime} />
          <Stat label="Last Trade" value={lastTradeTime} />
          <Stat
            label="Today P/L"
            value={formatNumber(todayPl + floating, 2)}
            tone={todayPl + floating >= 0 ? "ok" : "bad"}
          />
          <Stat label="Active Trades" value={String(positions.length)} />
          <Stat
            label="Daily Risk Used"
            value={`${formatNumber(dailyRiskUsed, 2)}% / ${formatNumber(maxDailyLossPct, 1)}%`}
            tone={dailyRiskUsed >= maxDailyLossPct ? "bad" : "neutral"}
          />
          <Stat label="Emergency" value={killArmed ? "STOP" : "READY"} tone={killArmed ? "bad" : "neutral"} />
        </div>
        {autoPausedNote ? (
          <p className="mt-2 text-xs text-[var(--warning)]">{autoPausedNote}</p>
        ) : null}
        {failedReasons.length > 0 ? (
          <div className="mt-2 space-y-1.5 text-xs text-[var(--fg-muted)]">
            {operatorReasons.length > 0 ? (
              <div>
                <p className="font-medium text-[var(--fg-subtle)]">Operator / configuration</p>
                <ul className="list-disc space-y-0.5 pl-4">
                  {operatorReasons.slice(0, 4).map((r) => (
                    <li key={`op-${r}`}>{r}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {connectivityReasons.length > 0 ? (
              <div>
                <p className="font-medium text-[var(--fg-subtle)]">Connectivity</p>
                <ul className="list-disc space-y-0.5 pl-4">
                  {connectivityReasons.map((r) => (
                    <li key={`conn-${r}`}>{r}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {riskReasons.length > 0 ? (
              <div>
                <p className="font-medium text-[var(--fg-subtle)]">Risk</p>
                <ul className="list-disc space-y-0.5 pl-4">
                  {riskReasons.map((r) => (
                    <li key={`risk-${r}`}>{r}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {operatorReasons.length === 0 &&
            connectivityReasons.length === 0 &&
            riskReasons.length === 0 ? (
              <ul className="list-disc space-y-0.5 pl-4">
                {failedReasons.slice(0, 6).map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </section>

      <div className="grid gap-3 xl:grid-cols-[1.15fr_0.85fr]">
        {/* 2. Strategy control */}
        <Panel title="Strategy control">
          <div className="grid gap-2 sm:grid-cols-2">
            {AUTO_STRATEGY_MODULES.map((m) => {
              const st = strategyStats(m.id);
              const on = toggles[m.id];
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => toggleStrategy(m.id)}
                  className={cn(
                    "border px-3 py-2.5 text-left transition",
                    on
                      ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                      : "border-[var(--border)] opacity-70",
                  )}
                  aria-pressed={on}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-[var(--fg)]">
                      {on ? "✓ " : ""}
                      {m.label}
                    </span>
                    <Badge tone={on ? "success" : "neutral"}>{st.status}</Badge>
                  </div>
                  <p className="mt-1 text-[10px] text-[var(--fg-subtle)]">{m.hint}</p>
                  <div className="mt-2 grid grid-cols-2 gap-1 text-[10px] text-[var(--fg-muted)]">
                    <span>Win rate: {st.winRate}</span>
                    <span>Today: {st.todayTrades}</span>
                    <span className="col-span-2 truncate">Last signal: {st.lastSignal}</span>
                    <span className="col-span-2 truncate">Last exec: {st.lastExecution}</span>
                  </div>
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-[10px] text-[var(--fg-subtle)]">
            Toggles are operator arming preferences for XAUUSD modules. Submits still require Risk
            Engine + Safety + EXECUTION_ENABLED via the institutional pipeline.
          </p>
        </Panel>

        {/* 6 + 7 risk + performance */}
        <div className="space-y-3">
          <Panel title="Daily risk center">
            <div className="grid grid-cols-2 gap-2">
              <Stat label="Daily Drawdown" value={`${formatNumber(dailyDdPct, 2)}%`} />
              <Stat label="Today's Risk" value={`${formatNumber(dailyRiskUsed, 2)}%`} />
              <Stat
                label="Open Exposure"
                value={formatNumber(openExposure, 2)}
              />
              <Stat label="Max Exposure" value={`${formatNumber(maxDailyLossPct, 1)}% DD`} />
              <Stat
                label="Remaining Capacity"
                value={`${formatNumber(remainingCapacity, 2)}%`}
                tone={remainingCapacity <= 0 ? "bad" : "ok"}
              />
              <Stat label="Risk / Trade" value={`${formatNumber(riskPerTradePct, 2)}%`} />
            </div>
            {remainingCapacity <= 0 ? (
              <p className="mt-2 text-xs text-[var(--danger)]">
                Daily limit reached — Auto Trading pauses automatically.
              </p>
            ) : null}
          </Panel>

          <Panel title="Performance · today">
            <div className="grid grid-cols-2 gap-2">
              <Stat label="Win Rate" value={todayWinRate} />
              <Stat
                label="Avg Execution"
                value={
                  analytics.latency_ms_avg != null
                    ? `${formatNumber(num(analytics.latency_ms_avg), 0)} ms`
                    : latestFill?.metrics.totalMs != null
                      ? `${formatNumber(latestFill.metrics.totalMs, 0)} ms`
                      : "—"
                }
              />
              <Stat
                label="Broker Fill"
                value={
                  latestFill?.metrics.brokerFillMs != null
                    ? `${formatNumber(latestFill.metrics.brokerFillMs, 0)} ms`
                    : "—"
                }
              />
              <Stat
                label="Fill Rate"
                value={
                  analytics.fill_rate != null
                    ? `${formatNumber(num(analytics.fill_rate) * 100, 0)}%`
                    : "—"
                }
              />
              <Stat label="Profit Factor" value={pf} />
              <Stat label="Expectancy" value={expectancy} />
              <Stat label="Average R" value={avgR} />
              <Stat label="Avg Hold Time" value={avgHold} />
              <Stat
                label="Latency P95"
                value={
                  analytics.order_latency_ms_p95 != null
                    ? `${formatNumber(num(analytics.order_latency_ms_p95), 0)} ms`
                    : "—"
                }
              />
            </div>
            <p className="mt-2 text-[10px] text-[var(--fg-subtle)]">
              Blank metrics stay empty until enough closed trades exist — never invented.
            </p>
          </Panel>
        </div>
      </div>

      {/* 3. Signal center */}
      <Panel
        title="Signal center"
        action={
          <Button asChild size="sm" variant="ghost">
            <Link href="/ai-signals">Counsel</Link>
          </Button>
        }
      >
        {signalsQ.isLoading ? (
          <DeskSkeleton rows={3} />
        ) : signalRows.length === 0 ? (
          <DeskEmpty
            icon={Activity}
            title="No live signals"
            description="Strategy Runtime signals appear here when generated. QuantForg never fabricates signal rows."
          />
        ) : (
          <DeskTable
            columns={[
              "Time",
              "Direction",
              "Confidence",
              "Entry",
              "SL",
              "TP",
              "Risk %",
              "Decision",
            ]}
            rows={signalRows}
          />
        )}
      </Panel>

      {/* 4. Decision pipeline */}
      <Panel title="Decision pipeline · last successful execution">
        {latestFill ? (
          <div className="flex flex-wrap items-stretch gap-1">
            {pipelineStages.map((s, i) => (
              <div key={s.label} className="flex items-center gap-1">
                <div className="min-w-[6.5rem] border border-[var(--border)] bg-[var(--bg)]/40 px-2 py-2">
                  <p className="text-[9px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                    {s.label}
                  </p>
                  <p className="mt-1 font-mono text-[11px] tabular text-[var(--fg)]">{s.dur}</p>
                </div>
                {i < pipelineStages.length - 1 ? (
                  <span className="text-[var(--fg-subtle)]" aria-hidden>
                    →
                  </span>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[var(--fg-muted)]">
            Pipeline timings appear after the next successful fill through Risk → Safety → Broker.
          </p>
        )}
      </Panel>

      {/* 5. Active positions */}
      <Panel title="Active positions">
        {positions.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">No open positions.</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {positions.map((p) => {
              const entry = num(p.open_price ?? p.price_open);
              const pnl = num(p.profit);
              const cur = Number.isFinite(mid) ? mid : num(p.current_price ?? p.price_current);
              return (
                <div
                  key={str(p.ticket)}
                  className="border border-[var(--border)] bg-[var(--bg)]/30 p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <Badge tone={str(p.side).toLowerCase() === "buy" ? "success" : "danger"}>
                      {str(p.side).toUpperCase()}
                    </Badge>
                    <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                      #{str(p.ticket)}
                    </span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-1 text-[11px]">
                    <span className="text-[var(--fg-subtle)]">Entry</span>
                    <span className="font-mono tabular text-right">{formatNumber(entry, 3)}</span>
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
                    <span className="text-[var(--fg-subtle)]">SL</span>
                    <span className="font-mono tabular text-right">
                      {str(p.stop_loss ?? p.sl, "—")}
                    </span>
                    <span className="text-[var(--fg-subtle)]">TP</span>
                    <span className="font-mono tabular text-right">
                      {str(p.take_profit ?? p.tp, "—")}
                    </span>
                    <span className="text-[var(--fg-subtle)]">Volume</span>
                    <span className="font-mono tabular text-right">{str(p.volume)}</span>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-3 w-full"
                    disabled={closeAllMut.isPending}
                    onClick={() => {
                      const side = str(p.side).toLowerCase() === "buy" ? "sell" : "buy";
                      void executionApi
                        .manage({
                          request_id: `at_close_${str(p.ticket)}_${Date.now()}`,
                          action: "close",
                          symbol: str(p.symbol, TRADING_SYMBOL),
                          ticket: Number(str(p.ticket)) || null,
                          side,
                          order_type: "market",
                          volume: str(p.volume, "0.01"),
                          price: null,
                          stop_loss: null,
                          take_profit: null,
                          slippage: 10,
                          magic: 0,
                          comment: "auto-workspace-close",
                        })
                        .then(() => {
                          toast.success("Close submitted");
                          invalidate();
                        })
                        .catch((e: unknown) =>
                          toast.error(
                            e instanceof ApiError ? e.message : "Close failed",
                          ),
                        );
                    }}
                  >
                    Close Position
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </Panel>

      {/* 8. Safety */}
      <Panel
        title="Safety · emergency"
        danger
        action={
          <span className="text-[10px] text-[var(--fg-subtle)]">Mode {opsMode}</span>
        }
      >
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            disabled={setRunMut.isPending || runState === "paused"}
            onClick={() => setRunMut.mutate("paused")}
          >
            <Pause className="h-4 w-4" />
            Pause Auto Trading
          </Button>
          <Button
            disabled={setRunMut.isPending || runState === "running"}
            onClick={() => setRunMut.mutate("running")}
          >
            <Play className="h-4 w-4" />
            Resume
          </Button>
          <Button variant="outline" onClick={() => setConfirmCloseAll(true)}>
            <XCircle className="h-4 w-4" />
            Close All Positions
          </Button>
          <Button variant="outline" onClick={() => setConfirmCancel(true)}>
            Cancel Pending Orders
          </Button>
          <Button variant="danger" onClick={() => setConfirmEmergency(true)}>
            <ShieldAlert className="h-4 w-4" />
            Emergency Stop
          </Button>
          <Button
            variant="ghost"
            disabled={setRunMut.isPending}
            onClick={() => setRunMut.mutate("stopped")}
          >
            <Square className="h-4 w-4" />
            Stop
          </Button>
        </div>
        <p className="mt-3 flex items-start gap-2 text-xs text-[var(--fg-muted)]">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--warning)]" />
          Emergency Stop requires confirmation. Closes and cancels use the existing execution
          pipeline (Risk → Safety → Gateway) — never a direct MT5 bypass.
        </p>
        {busyLabel ? (
          <p className="mt-2 text-xs text-[var(--accent)]">{busyLabel}</p>
        ) : null}
      </Panel>

      {/* 9. Event timeline */}
      <Panel title="Event timeline">
        {eventTimeline.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">
            Live auto-trade and execution events appear here.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {eventTimeline.map((e, i) => (
              <li
                key={`${e.at}-${e.label}-${i}`}
                className="grid grid-cols-[4.5rem_1fr] gap-3 border-b border-[var(--border)]/60 py-1.5 text-sm last:border-0"
              >
                <span className="font-mono text-[11px] tabular text-[var(--fg-subtle)]">
                  {e.at || "—"}
                </span>
                <div>
                  <p className="text-[var(--fg)]">{e.label}</p>
                  {e.detail ? (
                    <p className="text-[11px] text-[var(--fg-muted)]">{e.detail}</p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>

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

"use client";

import dynamic from "next/dynamic";
import { useMemo, useState, useTransition } from "react";
import { BrandLogo } from "@/components/brand/brand-logo";
import { useNocCommandCenter } from "@/hooks/use-noc-command-center";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessIteOps,
  iteOpsAccessDeniedMessage,
} from "@/lib/auth/ite-ops-access";
import { asList, asRecord, num, str } from "@/lib/desk";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { cn } from "@/lib/utils";
import {
  DECISION_TONES,
  fmt,
  GaugeRing,
  HealthCard,
  MetricBar,
  NocPanel,
  NocRow,
  pipelineTone,
  SparkBars,
} from "@/components/ops/noc/noc-primitives";
import { ProductionAcceptancePanel } from "@/components/ops/noc/production-acceptance-panel";

const NocCopilotPanel = dynamic(
  () =>
    import("@/components/ops/noc/noc-copilot-panel").then((m) => m.NocCopilotPanel),
  { ssr: false, loading: () => <DeskSkeleton rows={6} /> },
);

const LOG_FILTERS = [
  "ALL",
  "AI",
  "OMS",
  "Gateway",
  "MT5",
  "Risk",
  "Execution",
  "Errors",
] as const;

type LogFilter = (typeof LOG_FILTERS)[number];

function remapHealthLabel(label: string): string {
  const u = label.toLowerCase();
  if (u.includes("execution enabled") || u === "execution") return "Execution Engine";
  if (u.includes("autotrading") || u.includes("auto trading")) return "Auto Trading";
  return label;
}

function healthPriority(label: string): number {
  const order = [
    "gateway",
    "oms",
    "mt5",
    "broker",
    "ai engine",
    "execution engine",
    "auto trading",
  ];
  const i = order.findIndex((k) => label.toLowerCase().includes(k));
  return i < 0 ? 99 : i;
}

function decisionTone(decision: string): "ok" | "warn" | "bad" | undefined {
  const t = DECISION_TONES[decision.toUpperCase()];
  if (t === "ok") return "ok";
  if (t === "warn") return "warn";
  if (t === "bad") return "bad";
  return undefined;
}

function TopBar({
  header,
  version,
  healthOk,
  buildVersion,
  refetchMs,
  asOf,
}: {
  header: Record<string, unknown>;
  version: Record<string, unknown>;
  healthOk: boolean;
  buildVersion: string;
  refetchMs: number;
  asOf: string;
}) {
  const commit = str(header.commit_sha, "—");
  const envName = str(header.environment || version.environment, "—");
  const ver = str(header.version || version.version, buildVersion || "—");
  return (
    <div className="flex flex-wrap items-center gap-3 border border-[var(--border)] bg-[var(--surface)] px-3 py-2.5">
      <BrandLogo size={28} wordmark caption="Institutional NOC" priority />
      <Badge tone={healthOk ? "success" : "warning"}>
        {healthOk ? "LIVE" : "DEGRADED"}
      </Badge>
      <Badge tone="neutral">Env · {envName}</Badge>
      <Badge tone="accent">RC4</Badge>
      <span className="font-mono text-[11px] text-[var(--fg-muted)]">v{ver}</span>
      <span className="font-mono text-[11px] text-[var(--fg-subtle)]" title={commit}>
        SHA {commit.slice(0, 12)}
      </span>
      <Badge
        tone={str(header.railway_status) === "online" ? "success" : "warning"}
      >
        Railway · {str(header.railway_status, "unknown")}
      </Badge>
      <span className="ml-auto flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        <span>Refresh {Math.round(refetchMs / 1000)}s</span>
        <span className="font-mono normal-case tracking-normal">
          As of {asOf.slice(11, 19) || "—"}Z
        </span>
        <span>Observe-only</span>
      </span>
    </div>
  );
}

function PipelineStrip({
  nodes,
  validationId,
}: {
  nodes: unknown[];
  validationId: string;
}) {
  return (
    <div className="overflow-x-auto">
      <div className="flex min-w-max items-stretch gap-1">
        {nodes.map((raw, idx) => {
          const n = asRecord(raw);
          const status = str(n.status, "WAIT");
          const tone = pipelineTone(status);
          return (
            <div key={`${str(n.stage)}-${idx}`} className="flex items-center gap-1">
              <div
                className={cn(
                  "min-w-[108px] border px-2 py-2 transition-colors duration-[var(--duration-os)]",
                  tone === "ok" && "border-[var(--success)] bg-[var(--success-soft)]",
                  tone === "bad" && "border-[var(--danger)] bg-[var(--danger-soft)]",
                  tone === "warn" && "border-[var(--warning)] bg-[var(--warning-soft)]",
                  !tone && "border-[var(--border)] bg-[var(--surface-2)]",
                )}
              >
                <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--fg)]">
                  {str(n.stage, "—")}
                </p>
                <p
                  className={cn(
                    "mt-1 font-mono text-[11px]",
                    tone === "ok" && "text-[var(--success)]",
                    tone === "bad" && "text-[var(--danger)]",
                    tone === "warn" && "text-[var(--warning)]",
                  )}
                >
                  {status === "WAITING" ? "WAIT" : status}
                </p>
                <p className="mt-0.5 font-mono text-[10px] text-[var(--fg-subtle)]">
                  {n.latency_ms == null ? "—" : `${n.latency_ms} ms`}
                </p>
                <p
                  className="mt-0.5 max-w-[140px] truncate text-[10px] text-[var(--fg-muted)]"
                  title={str(n.reason, "")}
                >
                  {str(n.reason, "—")}
                </p>
              </div>
              {idx < nodes.length - 1 ? (
                <span className="px-0.5 font-mono text-[12px] text-[var(--accent)]/60">
                  ↓
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
      <p className="mt-2 font-mono text-[11px] text-[var(--fg-muted)]">
        Validation ID · {validationId || "—"}
      </p>
    </div>
  );
}

function matchLogFilter(message: string, level: string, filter: LogFilter): boolean {
  if (filter === "ALL") return true;
  if (filter === "Errors") {
    return (
      level === "critical" ||
      level === "error" ||
      message.toLowerCase().includes("fail") ||
      message.toLowerCase().includes("error")
    );
  }
  return message.toUpperCase().includes(filter.toUpperCase());
}

export function NocCommandCenter() {
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);
  const { noc, version, healthLive, copilot, buildVersion, refetchMs } =
    useNocCommandCenter(allowed);
  const [historyFilter, setHistoryFilter] = useState("");
  const [logFilter, setLogFilter] = useState<LogFilter>("ALL");
  const [pending, startTransition] = useTransition();

  const data = asRecord(noc.data);
  const header = asRecord(data.header);
  const healthRaw = asList(data.global_health);
  const pipeline = asRecord(data.pipeline);
  const nodes = asList(pipeline.nodes);
  const ai = asRecord(data.ai_engine);
  const market = asRecord(data.market_context);
  const symbolScan = asRecord(data.symbol_scan);
  const scanRows = Array.isArray(symbolScan.rows) ? symbolScan.rows : [];
  const scanUniverse = Array.isArray(symbolScan.universe)
    ? symbolScan.universe.map((s) => String(s))
    : [];
  const executionTrace = asRecord(data.execution_trace);
  const traceStages = Array.isArray(executionTrace.stages)
    ? executionTrace.stages
    : [];
  const learning = asRecord(asRecord(data.learning).summary);
  const protection = asRecord(data.protection);
  const liveHealth = asRecord(protection.live_health);
  const continuousOp = asRecord(protection.continuous_operation);
  const intelligence = asRecord(data.intelligence);
  const oppRanking = asRecord(intelligence.opportunity_ranking);
  const oppRows = Array.isArray(oppRanking.rows) ? oppRanking.rows : [];
  const tradeQueue = asRecord(intelligence.trade_queue);
  const queueCandidates = Array.isArray(tradeQueue.candidates)
    ? tradeQueue.candidates
    : [];
  const portfolioExposure = asRecord(intelligence.portfolio_exposure);
  const perfAnalytics = asRecord(intelligence.performance_analytics);
  const replayLibrary = asRecord(intelligence.replay_library);
  const replayItems = Array.isArray(replayLibrary.items)
    ? replayLibrary.items
    : [];
  const execProbability = asRecord(intelligence.execution_probability);
  const executionOptimizer = asRecord(intelligence.execution_optimizer);
  const smartRouting = asRecord(intelligence.smart_order_routing);
  const executionQuality = asRecord(intelligence.execution_quality);
  const eqRolling = asRecord(executionQuality.rolling);
  const eqAnalytics = asRecord(executionQuality.analytics);
  const brokerPerf = asRecord(intelligence.broker_performance);
  const lifecycleTimeline = asRecord(intelligence.lifecycle_timeline);
  const lifecycleActive = Array.isArray(lifecycleTimeline.active)
    ? lifecycleTimeline.active
    : [];
  const lifecycleRecent = Array.isArray(lifecycleTimeline.recent)
    ? lifecycleTimeline.recent
    : [];
  const positionMonitor = asRecord(intelligence.position_monitor);
  const positionRows = Array.isArray(positionMonitor.rows)
    ? positionMonitor.rows
    : [];
  const opsIntel = asRecord(intelligence.operational_intelligence);
  const opsWarnings = Array.isArray(opsIntel.warnings) ? opsIntel.warnings : [];
  const dailyExecReport = asRecord(intelligence.daily_execution_report);
  const learningDashboard = asRecord(intelligence.learning_dashboard);
  const learningRecent = Array.isArray(learningDashboard.recent)
    ? learningDashboard.recent
    : [];
  const patternLibrary = asRecord(intelligence.pattern_library);
  const adaptiveRecs = asRecord(intelligence.adaptive_recommendations);
  const adaptiveRecList = Array.isArray(adaptiveRecs.recommendations)
    ? adaptiveRecs.recommendations
    : [];
  const institutionalKpis = asRecord(intelligence.institutional_kpis);
  const portfolioForecast = asRecord(intelligence.portfolio_forecast);
  const forecastWarnings = Array.isArray(portfolioForecast.warnings)
    ? portfolioForecast.warnings
    : [];
  const periodReports = asRecord(intelligence.period_reports);
  const periodMap = asRecord(periodReports.periods);
  const positions = asList(data.open_positions);
  const closed = asList(data.closed_trades);
  const oms = asRecord(data.oms);
  const gateway = asRecord(data.gateway);
  const broker = asRecord(data.broker);
  const perfToday = asRecord(asRecord(data.performance).today);
  const perfWeekly = asRecord(asRecord(data.performance).weekly);
  const perfMonthly = asRecord(asRecord(data.performance).monthly);
  const events = asList(data.event_stream);
  const alerts = asList(data.alerts);
  const history = asList(data.validation_history);
  const metrics = asRecord(data.system_metrics);
  const productionAcceptance = asRecord(data.production_acceptance);
  const execState = asRecord(data.execution_state);
  const sizing = asRecord(data.sizing || data.position_sizing);

  const health = useMemo(() => {
    return [...healthRaw]
      .map((row) => {
        const c = asRecord(row);
        return {
          key: str(c.key || c.label),
          label: remapHealthLabel(str(c.label, "—")),
          status: str(c.status, "unknown"),
          latency_ms: c.latency_ms,
          last_heartbeat: c.last_heartbeat,
          detail: c.detail,
        };
      })
      .sort((a, b) => healthPriority(a.label) - healthPriority(b.label));
  }, [healthRaw]);

  const filteredHistory = useMemo(() => {
    const q = historyFilter.trim().toLowerCase();
    if (!q) return history;
    return history.filter((row) => {
      const r = asRecord(row);
      const blob = [
        r.validation_id,
        r.final_result,
        r.pipeline_status,
        r.result,
        r.first_blocker,
        r.reason,
        r.ai_action,
        r.symbol,
      ]
        .map((x) => String(x ?? "").toLowerCase())
        .join(" ");
      return blob.includes(q);
    });
  }, [history, historyFilter]);

  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      const r = asRecord(e);
      return matchLogFilter(
        str(r.message, ""),
        str(r.level, "info").toLowerCase(),
        logFilter,
      );
    });
  }, [events, logFilter]);

  const pnlSeries = useMemo(() => {
    const out: number[] = [];
    for (const row of closed) {
      const r = asRecord(row);
      const p = num(r.profit ?? r.floating_pnl ?? r.net_pnl);
      if (Number.isFinite(p)) out.push(p);
    }
    return out.slice(-48);
  }, [closed]);

  const latencySeries = useMemo(() => {
    const out: number[] = [];
    for (const row of history) {
      const r = asRecord(row);
      const p = num(r.latency_ms);
      if (Number.isFinite(p)) out.push(p);
    }
    return out.slice(-48);
  }, [history]);

  const decision = str(ai.decision, "—").toUpperCase().replace("_", " ");
  const blocker = str(
    pipeline.first_blocker || ai.current_blocker || data.primary_blocker,
    "—",
  );

  const floatingPl = useMemo(() => {
    let sum = 0;
    let any = false;
    for (const p of positions) {
      const r = asRecord(p);
      const v = num(r.floating_pnl ?? r.profit);
      if (Number.isFinite(v)) {
        sum += v;
        any = true;
      }
    }
    return any ? sum : null;
  }, [positions]);

  const marginLevel = useMemo(() => {
    const margin = num(broker.margin);
    const equity = num(broker.equity);
    if (!Number.isFinite(margin) || !Number.isFinite(equity) || margin <= 0) {
      return null;
    }
    return (equity / margin) * 100;
  }, [broker.equity, broker.margin]);

  const signalsToday = num(perfToday.signals);
  const rejectedToday = num(perfToday.rejected);
  const eligibleToday =
    Number.isFinite(signalsToday) && Number.isFinite(rejectedToday)
      ? Math.max(0, signalsToday - rejectedToday)
      : null;

  if (!allowed) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(user, undefined, "NOC Command Center")}
      />
    );
  }

  if (noc.isLoading && !noc.data) {
    return <DeskSkeleton rows={14} />;
  }

  if (noc.error && !noc.data) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(user, noc.error, "NOC Command Center")}
      />
    );
  }

  const healthOk = str(asRecord(healthLive.data).status, "") === "ok";
  const reasons = asList(ai.reasons).map(String);
  const asOf = str(header.as_of, "");

  return (
    <div className="space-y-4 lg:grid lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-4 lg:space-y-0">
      <div className="space-y-4">
        <TopBar
          header={header}
          version={asRecord(version.data)}
          healthOk={healthOk}
          buildVersion={buildVersion}
          refetchMs={refetchMs}
          asOf={asOf}
        />

        {/* §1 Global Status */}
        <NocPanel id="noc-global" title="1 · Global Status">
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7">
            {health.map((c) => (
              <HealthCard
                key={c.key}
                label={c.label}
                status={c.status}
                latencyMs={c.latency_ms}
                heartbeat={c.last_heartbeat}
                detail={c.detail}
              />
            ))}
          </div>
        </NocPanel>

        <ProductionAcceptancePanel data={productionAcceptance} />

        {/* §13 Live Counters */}
        <NocPanel id="noc-counters" title="13 · Live Counters">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {[
              ["Trades Today", fmt(perfToday.trades ?? metrics.trades_today)],
              ["Signals Today", fmt(perfToday.signals)],
              ["Rejected Signals", fmt(perfToday.rejected)],
              ["Eligible Signals", fmt(eligibleToday)],
              [
                "Current Cycle",
                fmt(execState.cycle_id || pipeline.validation_id),
              ],
              ["Last Scan", fmt(asOf || header.deployment_time)],
            ].map(([label, value]) => (
              <div
                key={String(label)}
                className="border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2"
              >
                <p className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                  {label}
                </p>
                <p className="mt-1 truncate font-mono text-[15px] text-[var(--fg)]">
                  {value}
                </p>
              </div>
            ))}
          </div>
        </NocPanel>

        {/* §2 Account */}
        <NocPanel id="noc-account" title="2 · Account">
          <div className="grid gap-x-6 gap-y-0 sm:grid-cols-2 lg:grid-cols-3">
            <NocRow label="Balance" value={fmt(broker.balance)} />
            <NocRow label="Equity" value={fmt(broker.equity)} />
            <NocRow label="Free Margin" value={fmt(broker.free_margin)} />
            <NocRow
              label="Margin Level"
              value={
                marginLevel == null ? "—" : `${marginLevel.toFixed(1)}%`
              }
            />
            <NocRow
              label="Floating P/L"
              value={floatingPl == null ? "—" : floatingPl.toFixed(2)}
              tone={
                floatingPl == null
                  ? undefined
                  : floatingPl >= 0
                    ? "ok"
                    : "bad"
              }
            />
            <NocRow label="Daily P/L" value={fmt(perfToday.net_profit)} />
            <NocRow
              label="Weekly P/L"
              value={fmt(perfWeekly?.net_profit ?? perfWeekly?.pnl)}
            />
            <NocRow
              label="Monthly P/L"
              value={fmt(perfMonthly?.net_profit ?? perfMonthly?.pnl)}
            />
            <NocRow label="Open Positions" value={String(positions.length)} />
            <NocRow
              label="Pending Orders"
              value={fmt(oms.pending_orders ?? oms.queue_size)}
            />
            <NocRow
              label="Account Mode"
              value={fmt(broker.account_mode ?? gateway.account_mode ?? "—")}
            />
            <NocRow label="Broker" value={fmt(broker.server)} />
            <NocRow label="Leverage" value={fmt(broker.leverage)} />
            <NocRow label="Account" value={fmt(broker.account)} />
            <NocRow label="Currency" value={fmt(broker.currency)} />
          </div>
        </NocPanel>

        {/* §3 + §4 */}
        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel id="noc-market" title="3 · Live Market">
            <NocRow label="Current Symbol" value={str(ai.symbol, "—")} />
            <NocRow label="Session" value={str(market.session || ai.current_session, "—")} />
            <NocRow
              label="Market Open"
              value={
                market.market_data_live === true
                  ? "YES"
                  : market.market_data_live === false
                    ? "NO"
                    : "—"
              }
              tone={market.market_data_live ? "ok" : "warn"}
            />
            <NocRow label="Spread" value={fmt(market.spread ?? ai.spread)} />
            <NocRow label="ATR" value={fmt(market.atr ?? ai.atr)} />
            <NocRow label="ATR %" value={fmt(market.atr_pct ?? ai.atr_pct)} />
            <NocRow
              label="Volatility Band"
              value={fmt(market.volatility_band ?? market.volatility)}
            />
            <NocRow label="Liquidity" value={fmt(market.liquidity ?? ai.liquidity)} />
            <NocRow label="Current Trend" value={str(market.trend, "—")} />
            <NocRow
              label="Current Regime"
              value={fmt(market.regime ?? market.market_structure)}
            />
          </NocPanel>

          <NocPanel
            id="noc-ai"
            title="4 · AI Decision"
            action={
              <Badge
                tone={
                  decisionTone(decision) === "ok"
                    ? "success"
                    : decisionTone(decision) === "bad"
                      ? "danger"
                      : "warning"
                }
              >
                {decision || "—"}
              </Badge>
            }
          >
            <div className="mb-2 flex flex-wrap justify-center gap-1">
              <GaugeRing
                label="Quality"
                value={ai.quality_score}
                threshold={80}
              />
              <GaugeRing
                label="Confidence"
                value={ai.confidence}
                threshold={80}
              />
              <GaugeRing label="Risk" value={ai.risk_score} max={100} />
            </div>
            <NocRow label="MTF" value={fmt(ai.mtf_alignment ?? market.mtf_alignment)} />
            <NocRow label="Liquidity" value={fmt(ai.liquidity)} />
            <NocRow label="Volatility" value={fmt(market.volatility)} />
            <NocRow
              label="Decision"
              value={decision}
              tone={decisionTone(decision)}
            />
            <NocRow label="Blocking Gate" value={blocker} tone="warn" />
            <NocRow label="Expected RR" value={fmt(ai.expected_rr)} />
            {reasons.length > 0 ? (
              <ul className="mt-2 max-h-40 space-y-1 overflow-auto text-[11px] text-[var(--fg-muted)]">
                {reasons.slice(0, 24).map((r) => (
                  <li key={r}>· {r}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
                No reject reasons in snapshot.
              </p>
            )}
          </NocPanel>
        </div>

        {/* §4b Multi-Asset Scanner */}
        <NocPanel
          id="noc-symbol-scan"
          title="4b · Multi-Asset Scanner"
          action={
            <Badge tone="neutral">
              {fmt(symbolScan.best_symbol, "no best")} ·{" "}
              {fmt(symbolScan.eligible_count, "0")} eligible
            </Badge>
          }
        >
          <NocRow
            label="Universe"
            value={
              scanUniverse.length > 0 ? scanUniverse.join(" · ") : "—"
            }
          />
          <NocRow
            label="As of"
            value={fmt(symbolScan.as_of)}
          />
          <NocRow
            label="Portfolio block"
            value={
              symbolScan.blocked_by_portfolio
                ? fmt(symbolScan.portfolio_block_reason, "blocked")
                : "none"
            }
            tone={symbolScan.blocked_by_portfolio ? "warn" : "ok"}
          />
          <NocRow
            label="Governance"
            value="Existing AI + Risk / PRE / OMS / MT5 only"
            tone="ok"
          />
          {scanRows.length === 0 ? (
            <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
              {fmt(symbolScan.note, "Awaiting first institutional multi-asset scan.")}
            </p>
          ) : (
            <div className="mt-2">
              <DeskTable
                columns={[
                  "Symbol",
                  "Quality",
                  "Confidence",
                  "MTF",
                  "Liquidity",
                  "Volatility",
                  "Decision",
                  "Blocking Gate",
                ]}
                rows={scanRows.map((row) => {
                  const r = asRecord(row);
                  return [
                    fmt(r.symbol),
                    fmt(r.quality),
                    fmt(r.confidence),
                    fmt(r.mtf),
                    fmt(r.liquidity),
                    fmt(r.volatility),
                    fmt(r.decision),
                    fmt(r.blocking_gate, "—"),
                  ];
                })}
              />
            </div>
          )}
        </NocPanel>

        {/* §4c Execution Trace */}
        <NocPanel
          id="noc-execution-trace"
          title="4c · Institutional Execution Trace"
          action={
            <Badge tone="neutral">
              {fmt(asRecord(executionTrace.first_blocker).stage, "clear")}
            </Badge>
          }
        >
          {traceStages.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              Awaiting live pipeline artefacts.
            </p>
          ) : (
            <DeskTable
              columns={["Stage", "Status", "Blocking Gate", "Reason"]}
              rows={traceStages.map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.stage),
                  fmt(r.status),
                  fmt(r.blocking_gate, "—"),
                  fmt(r.reason, "—"),
                ];
              })}
            />
          )}
        </NocPanel>

        {/* §4d Protection + Learning */}
        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel id="noc-protection" title="4d · Emergency Protection">
            <NocRow
              label="New entries paused"
              value={fmt(
                asRecord(liveHealth.self_protection).new_entries_paused ??
                  continuousOp.pause_new_entries
              )}
              tone={
                asRecord(liveHealth.self_protection).new_entries_paused ||
                continuousOp.pause_new_entries
                  ? "warn"
                  : "ok"
              }
            />
            <NocRow
              label="Pause reasons"
              value={fmt(
                (
                  asList(asRecord(liveHealth.self_protection).reasons).length
                    ? asList(asRecord(liveHealth.self_protection).reasons).join("; ")
                    : asList(continuousOp.reasons).join("; ")
                ) || "none"
              )}
            />
            <NocRow
              label="Manage open positions"
              value={fmt(continuousOp.manage_open_positions, "true")}
              tone="ok"
            />
          </NocPanel>
          <NocPanel id="noc-learning" title="4e · AI Learning Dataset">
            <NocRow label="Trades recorded" value={fmt(learning.trades, "0")} />
            <NocRow label="Wins" value={fmt(learning.wins, "0")} />
            <NocRow label="Losses" value={fmt(learning.losses, "0")} />
            <NocRow label="Win rate" value={fmt(learning.win_rate)} />
          </NocPanel>
        </div>

        {/* §4f Institutional Intelligence */}
        <NocPanel
          id="noc-opportunity-ranking"
          title="4f · Opportunity Ranking"
          action={
            <Badge tone="neutral">
              best · {fmt(oppRanking.best_symbol, "none")}
            </Badge>
          }
        >
          {oppRows.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              Awaiting live opportunity ranking from multi-asset scan.
            </p>
          ) : (
            <DeskTable
              columns={[
                "Symbol",
                "Score",
                "Quality",
                "Confidence",
                "P(success)",
                "Eligible",
                "Gate",
              ]}
              rows={oppRows.slice(0, 13).map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.symbol),
                  fmt(r.opportunity_score),
                  fmt(r.quality),
                  fmt(r.confidence),
                  fmt(r.estimated_probability),
                  r.eligible ? "yes" : "no",
                  fmt(r.blocking_gate, "—"),
                ];
              })}
            />
          )}
        </NocPanel>

        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel
            id="noc-trade-queue"
            title="4g · Trade Queue"
            action={
              <Badge tone="neutral">
                {fmt(tradeQueue.size ?? queueCandidates.length, "0")} · one-to-Risk
              </Badge>
            }
          >
            <NocRow
              label="Selected"
              value={fmt(tradeQueue.selected_symbol, "none")}
            />
            <NocRow
              label="Eligible"
              value={fmt(tradeQueue.eligible_count, "0")}
            />
            {queueCandidates.length === 0 ? (
              <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
                Queue empty — no eligible candidates this scan window.
              </p>
            ) : (
              <div className="mt-2">
                <DeskTable
                  columns={["Symbol", "Score", "Q", "C", "P", "Gate"]}
                  rows={queueCandidates.slice(0, 8).map((row) => {
                    const r = asRecord(row);
                    return [
                      fmt(r.symbol),
                      fmt(r.score ?? r.opportunity_score),
                      fmt(r.quality),
                      fmt(r.confidence),
                      fmt(r.estimated_probability),
                      fmt(r.blocking_gate, "—"),
                    ];
                  })}
                />
              </div>
            )}
          </NocPanel>

          <NocPanel id="noc-exec-probability" title="4h · Execution Probability">
            <NocRow label="Symbol" value={fmt(execProbability.symbol)} />
            <NocRow
              label="P(success)"
              value={fmt(execProbability.probability_of_success)}
            />
            <NocRow
              label="P(failure)"
              value={fmt(execProbability.probability_of_failure)}
            />
            <NocRow
              label="Estimated RR"
              value={fmt(execProbability.estimated_rr)}
            />
            <NocRow
              label="Hold (min)"
              value={fmt(execProbability.expected_holding_time_minutes)}
            />
            <NocRow
              label="CI"
              value={
                asRecord(execProbability.confidence_interval).low != null
                  ? `${fmt(asRecord(execProbability.confidence_interval).low)}–${fmt(
                      asRecord(execProbability.confidence_interval).high,
                    )}`
                  : "—"
              }
            />
            <NocRow
              label="Source"
              value={fmt(execProbability.source, "existing_ai_outputs_only")}
              tone="ok"
            />
          </NocPanel>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel id="noc-portfolio-exposure" title="4i · Portfolio Exposure">
            <NocRow
              label="Net"
              value={fmt(portfolioExposure.net_exposure, "0")}
            />
            <NocRow
              label="Long"
              value={fmt(portfolioExposure.long_exposure, "0")}
            />
            <NocRow
              label="Short"
              value={fmt(portfolioExposure.short_exposure, "0")}
            />
            <NocRow
              label="Open positions"
              value={fmt(portfolioExposure.open_positions, "0")}
            />
            <NocRow
              label="Sectors"
              value={
                Object.keys(asRecord(portfolioExposure.sector_exposure)).length
                  ? Object.entries(asRecord(portfolioExposure.sector_exposure))
                      .map(([k, v]) => `${k}:${String(v)}`)
                      .join(" · ")
                  : "—"
              }
            />
            <NocRow
              label="Correlation risk"
              value={
                Object.keys(asRecord(portfolioExposure.correlation_risk)).length
                  ? Object.entries(asRecord(portfolioExposure.correlation_risk))
                      .map(([k, v]) => `${k}:${String(v)}`)
                      .join(" · ")
                  : "—"
              }
            />
            <NocRow
              label="Enforcement"
              value={fmt(
                portfolioExposure.enforcement,
                "existing_PRE_and_risk_limits",
              )}
              tone="ok"
            />
          </NocPanel>

          <NocPanel
            id="noc-perf-analytics"
            title="4j · Performance Analytics"
          >
            <NocRow label="Trades" value={fmt(perfAnalytics.trades, "0")} />
            <NocRow label="Win rate" value={fmt(perfAnalytics.win_rate)} />
            <NocRow label="Avg RR" value={fmt(perfAnalytics.average_rr)} />
            <NocRow
              label="Avg hold (min)"
              value={fmt(perfAnalytics.average_hold_time_minutes)}
            />
            <NocRow
              label="Profit factor"
              value={fmt(perfAnalytics.profit_factor)}
            />
            <NocRow label="Sharpe" value={fmt(perfAnalytics.sharpe)} />
            <NocRow label="Expectancy" value={fmt(perfAnalytics.expectancy)} />
            <NocRow
              label="Avg quality"
              value={fmt(perfAnalytics.average_quality)}
            />
            <NocRow
              label="Avg confidence"
              value={fmt(perfAnalytics.average_confidence)}
            />
            <NocRow
              label="Best / worst session"
              value={`${fmt(perfAnalytics.best_session)} / ${fmt(
                perfAnalytics.worst_session,
              )}`}
            />
            <NocRow
              label="Best / worst symbol"
              value={`${fmt(perfAnalytics.best_symbol)} / ${fmt(
                perfAnalytics.worst_symbol,
              )}`}
            />
            <NocRow
              label="Source"
              value={fmt(perfAnalytics.source, "real_completed_trades_only")}
              tone="ok"
            />
          </NocPanel>
        </div>

        <NocPanel
          id="noc-replay-library"
          title="4k · Replay Library"
          action={
            <Badge tone="neutral">{fmt(replayLibrary.count, "0")} replays</Badge>
          }
        >
          {replayItems.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No completed trade replays recorded yet.
            </p>
          ) : (
            <DeskTable
              columns={[
                "Symbol",
                "Dir",
                "Ticket",
                "Entry",
                "Exit",
                "Close",
                "AI",
              ]}
              rows={replayItems.slice(0, 12).map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.symbol),
                  fmt(r.direction),
                  fmt(r.ticket),
                  fmt(r.entry),
                  fmt(r.exit),
                  fmt(r.close_reason, "—"),
                  fmt(r.ai_decision, "—").slice(0, 48),
                ];
              })}
            />
          )}
        </NocPanel>

        {/* §4l–4r Execution Intelligence */}
        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel
            id="noc-execution-optimizer"
            title="4l · Execution Optimizer"
            action={
              <Badge tone="neutral">
                {fmt(executionOptimizer.recommendation, "idle")}
              </Badge>
            }
          >
            <NocRow label="Symbol" value={fmt(executionOptimizer.symbol)} />
            <NocRow
              label="Quality score"
              value={fmt(executionOptimizer.execution_quality_score)}
            />
            <NocRow
              label="Recommendation"
              value={fmt(executionOptimizer.recommendation)}
            />
            <NocRow label="Reason" value={fmt(executionOptimizer.reason)} />
            <NocRow
              label="Defer count"
              value={`${fmt(executionOptimizer.defer_count, "0")} / ${fmt(
                executionOptimizer.max_defers,
                "3",
              )}`}
            />
            <NocRow
              label="Direction unchanged"
              value={fmt(executionOptimizer.direction_unchanged, "true")}
              tone="ok"
            />
          </NocPanel>

          <NocPanel id="noc-smart-routing" title="4m · Smart Order Routing">
            <NocRow
              label="Expected slippage"
              value={fmt(smartRouting.expected_slippage)}
            />
            <NocRow
              label="Fill probability"
              value={fmt(smartRouting.fill_probability)}
            />
            <NocRow
              label="Execution quality"
              value={fmt(smartRouting.execution_quality_score)}
            />
            <NocRow
              label="Recommendation"
              value={fmt(smartRouting.recommendation)}
            />
            <NocRow
              label="AI unchanged"
              value={fmt(smartRouting.ai_decision_unchanged, "true")}
              tone="ok"
            />
          </NocPanel>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel id="noc-execution-quality" title="4n · Execution Quality">
            <NocRow label="Samples" value={fmt(eqRolling.samples, "0")} />
            <NocRow label="Fill rate" value={fmt(eqRolling.fill_rate)} />
            <NocRow label="Reject rate" value={fmt(eqRolling.reject_rate)} />
            <NocRow
              label="Avg latency ms"
              value={fmt(eqRolling.avg_latency_ms ?? eqAnalytics.avg_latency_ms)}
            />
            <NocRow
              label="Avg slippage"
              value={fmt(eqRolling.avg_slippage ?? eqAnalytics.avg_slippage)}
            />
            <NocRow
              label="Avg exec score"
              value={fmt(eqAnalytics.avg_execution_score)}
            />
          </NocPanel>

          <NocPanel id="noc-broker-performance" title="4o · Broker Performance">
            <NocRow label="Fill rate" value={fmt(brokerPerf.fill_rate)} />
            <NocRow label="Reject rate" value={fmt(brokerPerf.reject_rate)} />
            <NocRow label="Requote rate" value={fmt(brokerPerf.requote_rate)} />
            <NocRow
              label="Avg latency ms"
              value={fmt(brokerPerf.avg_latency_ms)}
            />
            <NocRow label="Avg slippage" value={fmt(brokerPerf.avg_slippage)} />
            <NocRow
              label="Source"
              value={fmt(brokerPerf.source, "execution_quality_store")}
              tone="ok"
            />
          </NocPanel>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel id="noc-latency-slippage" title="4p · Latency / Slippage">
            <NocRow
              label="Latency ms"
              value={fmt(eqRolling.avg_latency_ms ?? dailyExecReport.average_latency_ms)}
            />
            <NocRow
              label="Slippage"
              value={fmt(eqRolling.avg_slippage ?? dailyExecReport.average_slippage)}
            />
            <NocRow
              label="Daily exec quality"
              value={fmt(dailyExecReport.execution_quality)}
            />
            <NocRow
              label="Trade execution rate"
              value={fmt(dailyExecReport.trade_execution_rate)}
            />
            <NocRow
              label="Best symbols"
              value={
                Array.isArray(dailyExecReport.best_symbols) &&
                dailyExecReport.best_symbols.length
                  ? dailyExecReport.best_symbols.map(String).join(" · ")
                  : "—"
              }
            />
            <NocRow
              label="Worst symbols"
              value={
                Array.isArray(dailyExecReport.worst_symbols) &&
                dailyExecReport.worst_symbols.length
                  ? dailyExecReport.worst_symbols.map(String).join(" · ")
                  : "—"
              }
            />
          </NocPanel>

          <NocPanel
            id="noc-ops-intel"
            title="4q · Operational Intelligence"
            action={
              <Badge tone={opsWarnings.length ? "warning" : "neutral"}>
                {fmt(opsIntel.warning_count ?? opsWarnings.length, "0")} warns
              </Badge>
            }
          >
            <NocRow
              label="Stops production"
              value={fmt(opsIntel.stops_production, "false")}
              tone="ok"
            />
            {opsWarnings.length === 0 ? (
              <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
                No operational warnings.
              </p>
            ) : (
              <DeskTable
                columns={["Code", "Severity", "Message"]}
                rows={opsWarnings.slice(0, 8).map((row) => {
                  const r = asRecord(row);
                  return [fmt(r.code), fmt(r.severity), fmt(r.message)];
                })}
              />
            )}
          </NocPanel>
        </div>

        <NocPanel
          id="noc-lifecycle-timeline"
          title="4r · Lifecycle Timeline"
          action={
            <Badge tone="neutral">
              {fmt(lifecycleTimeline.active_count, "0")} active
            </Badge>
          }
        >
          {lifecycleActive.length === 0 && lifecycleRecent.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              Awaiting live lifecycle events.
            </p>
          ) : (
            <DeskTable
              columns={["ID", "Symbol", "Stage", "Updated"]}
              rows={[...lifecycleActive, ...lifecycleRecent]
                .slice(0, 12)
                .map((row) => {
                  const r = asRecord(row);
                  return [
                    fmt(r.id).slice(0, 12),
                    fmt(r.symbol),
                    fmt(r.current_stage),
                    fmt(r.updated_at ?? r.started_at),
                  ];
                })}
            />
          )}
        </NocPanel>

        <NocPanel
          id="noc-position-monitor"
          title="4s · Institutional Position Monitor"
          action={
            <Badge tone="neutral">
              {fmt(positionMonitor.open_positions, "0")} open
            </Badge>
          }
        >
          {positionRows.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No live managed positions.
            </p>
          ) : (
            <DeskTable
              columns={[
                "Symbol",
                "Side",
                "Float",
                "Heat",
                "RR",
                "Stop dist",
                "Phase",
                "Session",
              ]}
              rows={positionRows.slice(0, 12).map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.symbol),
                  fmt(r.side),
                  fmt(r.floating_pnl),
                  fmt(r.heat),
                  fmt(r.remaining_rr),
                  fmt(r.stop_distance),
                  fmt(r.management_phase),
                  fmt(r.session, "—"),
                ];
              })}
            />
          )}
        </NocPanel>

        {/* §4t–4y AI v8 Adaptive Intelligence (observe / recommend only) */}
        <NocPanel
          id="noc-learning-dashboard"
          title="4t · Learning Dashboard"
          action={
            <Badge tone="neutral">
              {fmt(learningDashboard.count, "0")} obs · no auto-apply
            </Badge>
          }
        >
          <NocRow
            label="Overwrite forbidden"
            value={fmt(learningDashboard.overwrite_forbidden, "true")}
            tone="ok"
          />
          <NocRow
            label="Auto-applies"
            value={fmt(learningDashboard.auto_applies_to_strategy, "false")}
            tone="ok"
          />
          {learningRecent.length === 0 ? (
            <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
              No learning observations yet.
            </p>
          ) : (
            <DeskTable
              columns={["Symbol", "Dir", "Win", "Q", "C", "Session", "Regime"]}
              rows={learningRecent.slice(0, 10).map((row) => {
                const r = asRecord(row);
                return [
                  fmt(r.symbol),
                  fmt(r.direction),
                  r.win ? "yes" : "no",
                  fmt(r.quality),
                  fmt(r.confidence),
                  fmt(r.session, "—"),
                  fmt(r.market_regime, "—"),
                ];
              })}
            />
          )}
        </NocPanel>

        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel id="noc-pattern-library" title="4u · Pattern Library">
            <NocRow label="Trades" value={fmt(patternLibrary.trades, "0")} />
            <NocRow
              label="Best / worst regime"
              value={`${fmt(patternLibrary.best_market_regimes)} / ${fmt(
                patternLibrary.worst_market_regimes,
              )}`}
            />
            <NocRow
              label="Best / worst session"
              value={`${fmt(patternLibrary.best_sessions)} / ${fmt(
                patternLibrary.worst_sessions,
              )}`}
            />
            <NocRow
              label="Best / worst symbol"
              value={`${fmt(patternLibrary.best_symbols)} / ${fmt(
                patternLibrary.worst_symbols,
              )}`}
            />
            <NocRow
              label="Best weekday"
              value={fmt(patternLibrary.best_weekdays)}
            />
            <NocRow
              label="Best hold range"
              value={fmt(patternLibrary.best_holding_times)}
            />
            <NocRow
              label="Modifies strategy"
              value={fmt(patternLibrary.modifies_strategy, "false")}
              tone="ok"
            />
          </NocPanel>

          <NocPanel
            id="noc-adaptive-recommendations"
            title="4v · Adaptive Recommendations"
            action={
              <Badge tone="neutral">
                {fmt(adaptiveRecs.count ?? adaptiveRecList.length, "0")} · human
                approval
              </Badge>
            }
          >
            <NocRow
              label="Auto-applies"
              value={fmt(adaptiveRecs.auto_applies, "false")}
              tone="ok"
            />
            {adaptiveRecList.length === 0 ? (
              <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
                No recommendations.
              </p>
            ) : (
              <DeskTable
                columns={["Code", "Severity", "Message"]}
                rows={adaptiveRecList.slice(0, 8).map((row) => {
                  const r = asRecord(row);
                  return [fmt(r.code), fmt(r.severity), fmt(r.message)];
                })}
              />
            )}
          </NocPanel>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel id="noc-institutional-kpis" title="4w · Institutional KPIs">
            <NocRow label="Trades" value={fmt(institutionalKpis.trades, "0")} />
            <NocRow
              label="Expectancy"
              value={fmt(institutionalKpis.expectancy)}
            />
            <NocRow label="Sharpe" value={fmt(institutionalKpis.sharpe)} />
            <NocRow label="Sortino" value={fmt(institutionalKpis.sortino)} />
            <NocRow label="Calmar" value={fmt(institutionalKpis.calmar)} />
            <NocRow
              label="Profit factor"
              value={fmt(institutionalKpis.profit_factor)}
            />
            <NocRow
              label="Recovery factor"
              value={fmt(institutionalKpis.recovery_factor)}
            />
            <NocRow
              label="Ulcer index"
              value={fmt(institutionalKpis.ulcer_index)}
            />
            <NocRow
              label="Avg MAE / MFE"
              value={`${fmt(institutionalKpis.average_mae)} / ${fmt(
                institutionalKpis.average_mfe,
              )}`}
            />
            <NocRow
              label="EQI"
              value={fmt(institutionalKpis.execution_quality_index)}
            />
            <NocRow
              label="Institutional score"
              value={fmt(institutionalKpis.institutional_score)}
            />
          </NocPanel>

          <NocPanel
            id="noc-portfolio-forecast"
            title="4x · Portfolio Forecast"
            action={
              <Badge tone={forecastWarnings.length ? "warning" : "neutral"}>
                {fmt(portfolioForecast.warning_count ?? forecastWarnings.length, "0")}{" "}
                warns
              </Badge>
            }
          >
            <NocRow
              label="Heat"
              value={fmt(portfolioForecast.portfolio_heat, "0")}
            />
            <NocRow
              label="Blocks Risk Engine"
              value={fmt(portfolioForecast.blocks_risk_engine, "false")}
              tone="ok"
            />
            {forecastWarnings.length === 0 ? (
              <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
                No portfolio forecast warnings.
              </p>
            ) : (
              <DeskTable
                columns={["Code", "Severity", "Message"]}
                rows={forecastWarnings.slice(0, 8).map((row) => {
                  const r = asRecord(row);
                  return [fmt(r.code), fmt(r.severity), fmt(r.message)];
                })}
              />
            )}
          </NocPanel>
        </div>

        <NocPanel id="noc-period-reports" title="4y · Performance Intelligence">
          <NocRow
            label="Daily trades"
            value={fmt(asRecord(periodMap.daily).trades, "0")}
          />
          <NocRow
            label="Weekly WR"
            value={fmt(asRecord(periodMap.weekly).win_rate)}
          />
          <NocRow
            label="Monthly net"
            value={fmt(asRecord(periodMap.monthly).net_pnl)}
          />
          <NocRow
            label="Quarterly PF"
            value={fmt(asRecord(periodMap.quarterly).profit_factor)}
          />
          <NocRow
            label="Yearly trades"
            value={fmt(asRecord(periodMap.yearly).trades, "0")}
          />
          <NocRow
            label="All-time score"
            value={fmt(asRecord(periodReports.kpis_all_time).institutional_score)}
          />
          <NocRow
            label="Auto-applies"
            value={fmt(periodReports.auto_applies, "false")}
            tone="ok"
          />
        </NocPanel>

        {/* §5 Pipeline */}
        <NocPanel
          id="noc-pipeline"
          title="5 · Execution Pipeline"
          action={
            <Badge
              tone={
                str(pipeline.final_result) === "ACCEPTED" ? "success" : "warning"
              }
            >
              {str(pipeline.final_result, "—")}
            </Badge>
          }
        >
          <PipelineStrip
            nodes={nodes}
            validationId={str(pipeline.validation_id, "—")}
          />
          {blocker !== "—" ? (
            <p className="mt-2 text-[12px] text-[var(--warning)]">
              First blocker · {blocker}
            </p>
          ) : null}
        </NocPanel>

        {/* §6 Position Sizing */}
        <NocPanel id="noc-sizing" title="6 · Position Sizing">
          <div className="grid gap-x-6 sm:grid-cols-2 lg:grid-cols-4">
            <NocRow
              label="Risk %"
              value={fmt(sizing.risk_pct ?? sizing.risk_percentage ?? perfToday.risk_pct)}
            />
            <NocRow
              label="Calculated Lot"
              value={fmt(sizing.calculated_lot ?? sizing.calculated_lots)}
            />
            <NocRow
              label="Final Lot"
              value={fmt(sizing.approved_lots ?? sizing.final_lot)}
            />
            <NocRow
              label="Broker Min Lot"
              value={fmt(sizing.broker_min_lot ?? sizing.broker_minimum)}
            />
            <NocRow label="Margin Used" value={fmt(broker.margin)} />
            <NocRow
              label="Portfolio Exposure"
              value={fmt(sizing.portfolio_exposure ?? oms.portfolio_exposure)}
            />
            <NocRow
              label="Symbol Exposure"
              value={fmt(sizing.symbol_exposure)}
            />
            <NocRow
              label="Correlation"
              value={fmt(sizing.correlation ?? sizing.correlation_group)}
            />
            <NocRow
              label="Sizing Status"
              value={fmt(sizing.sizing_status)}
              tone={
                str(sizing.sizing_status).includes("below") ? "warn" : undefined
              }
            />
          </div>
          <p className="mt-2 text-[10px] text-[var(--fg-subtle)]">
            Sizing fields render only when present in telemetry — never fabricated.
          </p>
        </NocPanel>

        {/* §7 Positions */}
        <NocPanel id="noc-positions" title="7 · Positions">
          {positions.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No open managed positions in telemetry.
            </p>
          ) : (
            <DeskTable
              columns={[
                "Symbol",
                "Direction",
                "Lots",
                "Entry",
                "Current",
                "Profit",
                "SL",
                "TP",
                "Age",
              ]}
              rows={positions.map((p) => {
                const r = asRecord(p);
                return [
                  fmt(r.symbol),
                  fmt(r.direction),
                  fmt(r.lots ?? r.volume),
                  fmt(r.entry),
                  fmt(r.current_price),
                  fmt(r.profit ?? r.floating_pnl),
                  fmt(r.sl ?? r.stop_loss),
                  fmt(r.tp ?? r.take_profit),
                  fmt(r.duration ?? r.age),
                ];
              })}
            />
          )}
        </NocPanel>

        {/* §8 Trade History */}
        <NocPanel id="noc-history" title="8 · Trade History">
          {closed.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No closed-trade fields in journal telemetry (never fabricated).
            </p>
          ) : (
            <DeskTable
              columns={[
                "Ticket",
                "Symbol",
                "Result",
                "P/L",
                "Duration",
                "Exit reason",
              ]}
              rows={closed.slice(0, 40).map((p) => {
                const r = asRecord(p);
                const pnl = num(r.profit ?? r.net_pnl);
                const result = !Number.isFinite(pnl)
                  ? "—"
                  : pnl > 0
                    ? "Win"
                    : pnl < 0
                      ? "Loss"
                      : "BE";
                return [
                  fmt(r.ticket),
                  fmt(r.symbol),
                  result,
                  fmt(r.profit ?? r.exit),
                  fmt(r.duration),
                  fmt(r.reason_closed ?? r.exit),
                ];
              })}
            />
          )}
        </NocPanel>

        {/* §12 Charts */}
        <NocPanel id="noc-charts" title="12 · Charts">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <SparkBars label="Closed Trade P/L (recent)" series={pnlSeries} />
            <SparkBars label="Validation Latency ms" series={latencySeries} />
            <div className="border border-[var(--border)] bg-[var(--surface-2)] p-2">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Diagnostics snapshot
              </p>
              <NocRow label="Win Rate" value={fmt(perfToday.win_rate)} />
              <NocRow label="Drawdown" value={fmt(perfToday.drawdown)} />
              <NocRow label="Net Profit" value={fmt(perfToday.net_profit)} />
              <NocRow label="Trades / Day" value={fmt(perfToday.trades)} />
              <p className="mt-2 text-[10px] text-[var(--fg-subtle)]">
                Equity/balance curves appear when historical series are present —
                empty otherwise.
              </p>
            </div>
          </div>
        </NocPanel>

        <div className="grid gap-3 lg:grid-cols-3">
          <NocPanel title="OMS">
            <NocRow label="Status" value={str(oms.status, "—")} />
            <NocRow label="Queue Size" value={fmt(oms.queue_size)} />
            <NocRow
              label="Avg Latency"
              value={
                oms.average_latency_ms == null
                  ? "—"
                  : `${oms.average_latency_ms} ms`
              }
            />
            <NocRow label="Retries" value={fmt(oms.retries)} />
            <NocRow label="Failures" value={fmt(oms.failures_today)} />
          </NocPanel>
          <NocPanel title="MT5 Gateway">
            <NocRow label="Version" value={fmt(gateway.gateway_version)} />
            <NocRow label="Connection" value={str(gateway.connection, "—")} />
            <NocRow
              label="Ping"
              value={gateway.ping_ms == null ? "—" : `${gateway.ping_ms} ms`}
            />
            <NocRow label="Reconnects" value={fmt(gateway.reconnect_count)} />
            <NocRow
              label="Last Error"
              value={fmt(gateway.last_error)}
              tone={gateway.last_error ? "warn" : undefined}
            />
          </NocPanel>
          <NocPanel title="Performance · Today">
            <NocRow label="Trades" value={fmt(perfToday.trades)} />
            <NocRow label="Win Rate" value={fmt(perfToday.win_rate)} />
            <NocRow label="Profit Factor" value={fmt(perfToday.profit_factor)} />
            <NocRow label="Expectancy" value={fmt(perfToday.expectancy)} />
            <NocRow label="Avg Latency" value={fmt(perfToday.average_latency_ms)} />
          </NocPanel>
        </div>

        {/* §11 System Health */}
        <NocPanel id="noc-system" title="11 · System Health">
          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <MetricBar label="CPU %" value={metrics.cpu} max={100} />
              <MetricBar label="RAM %" value={metrics.memory} max={100} />
              <MetricBar
                label="Gateway Ping ms"
                value={metrics.gateway_latency_ms ?? gateway.ping_ms}
              />
              <MetricBar
                label="Broker Ping ms"
                value={metrics.broker_latency_ms}
              />
            </div>
            <div>
              <NocRow
                label="API Response"
                value={fmt(metrics.request_latency_ms_avg)}
              />
              <NocRow label="OMS Latency" value={fmt(metrics.oms_latency_ms)} />
              <NocRow label="Database" value={fmt(metrics.database ?? "—")} />
              <NocRow label="Redis" value={fmt(metrics.redis ?? "—")} />
              <NocRow label="Throughput / min" value={fmt(metrics.throughput_per_minute)} />
              <NocRow label="Error Rate" value={fmt(metrics.error_rate)} />
            </div>
          </div>
        </NocPanel>

        {/* §9 Live Log + §10 Alerts */}
        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel
            id="noc-log"
            title="9 · Live Log"
            action={
              <div className="flex flex-wrap gap-1">
                {LOG_FILTERS.map((f) => (
                  <button
                    key={f}
                    type="button"
                    onClick={() => setLogFilter(f)}
                    className={cn(
                      "border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide",
                      logFilter === f
                        ? "border-[var(--accent)] text-[var(--accent)]"
                        : "border-[var(--border)] text-[var(--fg-subtle)]",
                    )}
                  >
                    {f}
                  </button>
                ))}
              </div>
            }
          >
            <ul className="max-h-80 space-y-1 overflow-auto text-[11px]">
              {filteredEvents.length === 0 ? (
                <li className="text-[var(--fg-muted)]">No events for filter.</li>
              ) : (
                filteredEvents.slice(0, 100).map((e, i) => {
                  const r = asRecord(e);
                  const level = str(r.level, "info");
                  return (
                    <li
                      key={`${str(r.timestamp)}-${i}`}
                      className={cn(
                        "border-b border-[var(--border)]/50 py-1 font-mono",
                        level === "critical" && "text-[var(--danger)]",
                        level === "warning" && "text-[var(--warning)]",
                        level === "info" && "text-[var(--fg-muted)]",
                      )}
                    >
                      <span className="text-[var(--fg-subtle)]">
                        {str(r.timestamp, "—").slice(11, 19)}
                      </span>{" "}
                      {str(r.message, "—")}
                      {r.reason ? ` · ${str(r.reason)}` : ""}
                    </li>
                  );
                })
              )}
            </ul>
          </NocPanel>

          <NocPanel id="noc-alerts" title="10 · Alerts">
            <ul className="max-h-80 space-y-2 overflow-auto text-[12px]">
              {alerts.length === 0 ? (
                <li className="text-[var(--fg-muted)]">No alerts in window.</li>
              ) : (
                alerts.slice(0, 50).map((a, i) => {
                  const r = asRecord(a);
                  const sev = str(r.severity || r.level, "info").toLowerCase();
                  return (
                    <li
                      key={str(r.id, String(i))}
                      className="border border-[var(--border)] px-2 py-1.5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <Badge
                          tone={
                            sev === "critical"
                              ? "danger"
                              : sev === "warning"
                                ? "warning"
                                : "neutral"
                          }
                        >
                          {sev}
                        </Badge>
                        <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                          {str(r.created_at || r.timestamp, "—").slice(0, 19)}
                        </span>
                      </div>
                      <p className="mt-1 text-[var(--fg)]">{str(r.message, "—")}</p>
                    </li>
                  );
                })
              )}
            </ul>
          </NocPanel>
        </div>

        <NocPanel
          title="Validation History"
          action={
            <input
              className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 font-mono text-[11px] text-[var(--fg)]"
              placeholder="Filter ID / result / reason"
              value={historyFilter}
              onChange={(e) => {
                const v = e.target.value;
                startTransition(() => setHistoryFilter(v));
              }}
              aria-label="Filter validation history"
            />
          }
        >
          <DeskTable
            columns={[
              "Validation ID",
              "Timestamp",
              "Pipeline",
              "Latency",
              "Result",
              "AI",
              "Reason",
            ]}
            rows={filteredHistory.slice(0, 60).map((row) => {
              const r = asRecord(row);
              return [
                str(r.validation_id, "—"),
                str(r.timestamp, "—").slice(0, 19),
                str(r.pipeline_status || r.final_result, "—"),
                r.latency_ms == null ? "—" : `${r.latency_ms} ms`,
                str(r.result || r.final_result, "—"),
                str(r.ai_action, "—"),
                str(r.reason || r.first_blocker, "—"),
              ];
            })}
          />
          {pending ? (
            <p className="mt-1 text-[10px] text-[var(--fg-subtle)]">Filtering…</p>
          ) : null}
        </NocPanel>
      </div>

      <aside className="space-y-3 lg:sticky lg:top-3 lg:self-start">
        <NocCopilotPanel
          onAsk={(q) => copilot.mutateAsync(q)}
          loading={copilot.isPending}
          result={copilot.data}
          error={copilot.error}
        />
        <Button
          size="sm"
          variant="outline"
          className="w-full"
          onClick={() => noc.refetch()}
        >
          Refresh telemetry now
        </Button>
        <p className="text-center text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          §14 Auto-refresh · {Math.round(refetchMs / 1000)}s · no full reload
        </p>
      </aside>
    </div>
  );
}

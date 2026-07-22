"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Crosshair, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { scalpingAiV2Api } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
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

export function ScalpingAiV2Workspace() {
  const qc = useQueryClient();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [riskOk, setRiskOk] = useState(true);
  const [safetyOk, setSafetyOk] = useState(true);
  const [decisionOk, setDecisionOk] = useState(true);

  const statusQ = useQuery({
    queryKey: ["scalping-ai-v2-status"],
    queryFn: () => scalpingAiV2Api.status(),
    staleTime: 15_000,
  });

  const historyQ = useQuery({
    queryKey: ["scalping-ai-v2-history"],
    queryFn: () => scalpingAiV2Api.history(15),
    staleTime: 10_000,
  });

  const operatorQ = useQuery({
    queryKey: ["scalping-ai-v2-operator"],
    queryFn: () => scalpingAiV2Api.operator(),
    staleTime: 10_000,
  });

  const diagnosticsQ = useQuery({
    queryKey: ["scalping-ai-v2-diagnostics"],
    queryFn: () => scalpingAiV2Api.diagnostics(),
    staleTime: 10_000,
  });

  const emergencyM = useMutation({
    mutationFn: () => scalpingAiV2Api.emergencyStop("operator_ui"),
    onSuccess: async () => {
      toast.success("Emergency stop armed");
      await qc.invalidateQueries({ queryKey: ["scalping-ai-v2-status"] });
      await qc.invalidateQueries({ queryKey: ["scalping-ai-v2-operator"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Emergency stop failed"),
  });

  const clearEmergencyM = useMutation({
    mutationFn: () => scalpingAiV2Api.clearEmergencyStop("operator_ui"),
    onSuccess: async () => {
      toast.success("Emergency stop cleared");
      await qc.invalidateQueries({ queryKey: ["scalping-ai-v2-status"] });
      await qc.invalidateQueries({ queryKey: ["scalping-ai-v2-operator"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Clear failed"),
  });

  const soakM = useMutation({
    mutationFn: () => scalpingAiV2Api.soak("stress"),
    onSuccess: (data) => {
      toast.success(`Soak ${str(data.status, "done")} (${str(data.profile)})`);
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Soak failed"),
  });

  const cycleM = useMutation({
    mutationFn: () =>
      scalpingAiV2Api.cycle({
        side: "buy",
        spread: 0.28,
        atr: 4.5,
        price: 2350,
        regime: "trend",
        session: "london",
        trend: "up",
        volatility: "normal",
        liquidity_state: "healthy",
        market_health: "good",
        confidence: 72,
        htf_bias: "bullish",
        ltf_confirmation: "bullish",
        trend_strength: 70,
        trend_consistency: 68,
        sweep_detected: true,
        equal_highs_lows: false,
        session_liquidity: "external",
        liquidity_side: "external",
        stop_hunt: false,
        bos: true,
        choch: false,
        mss: false,
        swing_bias: "bullish",
        structure_phase: "continuation",
        opportunities: [
          {
            id: "sweep-reclaim",
            quality_score: 78,
            confidence_score: 74,
            risk_score: 35,
            execution_score: 80,
          },
        ],
        risk_engine_passed: riskOk,
        safety_engine_passed: safetyOk,
        decision_approved: decisionOk,
        decision_center: {
          decision: decisionOk ? "APPROVE" : "HOLD",
        },
        broker_connected: true,
        gateway_healthy: true,
        latency_ms: 40,
        market_open: true,
        margin_available: true,
        equity: 10000,
        daily_loss_pct: 0.2,
        open_exposure_pct: 1.0,
        trades_today: 2,
        consecutive_losses: 0,
        run_state: "running",
        kill_switch: false,
        news_blackout: false,
        health: {
          execution_loop: true,
          broker_connection: true,
          gateway: true,
          database: true,
          analytics: true,
          risk_engine: riskOk,
          safety_engine: safetyOk,
          decision_engine: decisionOk,
          analytics_metrics: {
            win_rate: 52,
            average_rr: 1.4,
            execution_latency: 40,
            capital_preservation: 80,
          },
          resources: {
            memory_mb: 256,
            cpu_pct: 22,
            queue_size: 0,
            worker_health: "ok",
            orphan_tasks: 0,
            stale_subscriptions: 0,
          },
          latencies: {
            signal: 6,
            decision: 8,
            risk: 4,
            safety: 3,
            gateway: 12,
            broker: 15,
            fill: 18,
            total: 66,
          },
          mt5_sync: {
            local_open_positions: 1,
            mt5_open_positions: 1,
            local_balance: 10000,
            mt5_balance: 10000,
          },
        },
        market_data: {
          timestamp: new Date().toISOString(),
          ohlc: { o: 2350, h: 2352, l: 2348, c: 2351 },
          duplicate_tick: false,
          missing_candles: false,
          clock_drift_ms: 12,
        },
        active_trade: {
          unrealized_pnl: 12,
          r_multiple: 1.2,
          time_in_trade_sec: 90,
        },
      }),
    onSuccess: async (data) => {
      setResult(data);
      toast.success(
        `Scalping AI → ${str(data.recommendation, "No Trade")} (advisory)`,
      );
      await qc.invalidateQueries({ queryKey: ["scalping-ai-v2-status"] });
      await qc.invalidateQueries({ queryKey: ["scalping-ai-v2-history"] });
      await qc.invalidateQueries({ queryKey: ["scalping-ai-v2-operator"] });
      await qc.invalidateQueries({ queryKey: ["scalping-ai-v2-diagnostics"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Cycle failed"),
  });

  const caps = asRecord(statusQ.data?.capabilities);
  const modules = asRecord(asRecord(result).modules);
  const moduleEntries = Object.entries(modules);
  const events = asList(asRecord(result).events);
  const obs = asRecord(asRecord(result).observability);
  const history = asList(asRecord(historyQ.data).items);
  const rec = str(result?.recommendation, "");
  const emergency = asRecord(statusQ.data?.emergency_stop);
  const operator = asRecord(operatorQ.data);
  const diag = asRecord(diagnosticsQ.data);
  const diagPanels = asRecord(asRecord(diag.details).panels);
  const healthState = asRecord(operator.health);
  const currentState = asRecord(operator.current_state);

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Scalping AI V2 unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <Crosshair className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">{TRADING_SYMBOL} scalping</span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Prefer No Trade
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          No order_send
        </Badge>
        {emergency.armed === true ? (
          <Badge tone="danger" className="text-[9px] uppercase">
            Emergency stop
          </Badge>
        ) : null}
        {currentState.safe_mode === true ? (
          <Badge tone="warning" className="text-[9px] uppercase">
            Safe mode
          </Badge>
        ) : null}
        {caps.never_bypass_risk === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            Risk authoritative
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "scalping-ai-v2.1")}
        </span>
        <Button
          size="sm"
          variant="outline"
          disabled={emergencyM.isPending}
          onClick={() => emergencyM.mutate()}
        >
          Emergency
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={clearEmergencyM.isPending}
          onClick={() => clearEmergencyM.mutate()}
        >
          Clear
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={soakM.isPending}
          onClick={() => soakM.mutate()}
        >
          Soak stress
        </Button>
        <Button
          size="sm"
          disabled={cycleM.isPending}
          onClick={() => cycleM.mutate()}
        >
          Run cycle
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Operator">
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-[var(--fg-muted)]">Auto trading</span>
              <span className="font-mono text-[10px]">
                {str(operator.auto_trading_status, "—")}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--fg-muted)]">State</span>
              <span className="font-mono text-[10px]">
                {str(currentState.recommendation, "—")}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--fg-muted)]">Market quality</span>
              <span className="font-mono text-[10px]">
                {str(asRecord(operator.market_quality).score, "—")}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--fg-muted)]">Health</span>
              <span className="font-mono text-[10px]">
                {str(asRecord(healthState.diagnostics).recommendation, "—")}
              </span>
            </div>
            <p className="text-[10px] text-[var(--fg-subtle)]">
              Reliability only — no profitability claims.
            </p>
          </div>
        </Panel>

        <Panel title="Diagnostics">
          {!Object.keys(diagPanels).length ? (
            <DeskEmpty
              icon={Shield}
              title="No diagnostics"
              description="Run a cycle to populate health score"
            />
          ) : (
            <ul className="max-h-40 space-y-1 overflow-auto font-mono text-[10px]">
              <li className="text-[var(--fg-muted)]">
                health {str(asRecord(diag.details).health_score, "—")} ·{" "}
                {str(diag.recommendation, "—")}
              </li>
              {Object.keys(diagPanels)
                .slice(0, 14)
                .map((k) => (
                  <li key={k} className="text-[var(--fg-subtle)]">
                    {k}
                  </li>
                ))}
            </ul>
          )}
        </Panel>

        <Panel title="Authority gates">
          <div className="space-y-2 text-xs">
            {(
              [
                ["Risk Engine", riskOk, setRiskOk],
                ["Safety Engine", safetyOk, setSafetyOk],
                ["Decision Center", decisionOk, setDecisionOk],
              ] as const
            ).map(([label, val, set]) => (
              <label
                key={label}
                className="flex items-center justify-between gap-2"
              >
                <span className="text-[var(--fg-muted)]">{label}</span>
                <input
                  type="checkbox"
                  checked={val}
                  onChange={(e) => set(e.target.checked)}
                  className="size-3.5"
                />
              </label>
            ))}
            <p className="text-[10px] text-[var(--fg-subtle)]">
              Existing engines remain authoritative. V2.1 hardens reliability
              without a second execution path.
            </p>
          </div>
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Cycle result">
          {!result ? (
            <DeskEmpty
              icon={Crosshair}
              title="No cycle"
              description="Run a continuous advisory cycle"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Recommendation</span>
                <Badge
                  tone={rec === "No Trade" ? "warning" : "success"}
                  className="text-[9px] uppercase"
                >
                  {rec || "—"}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Exec identity</span>
                <span className="font-mono text-[10px]">
                  {str(result.execution_identity, "—").slice(0, 18)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Events</span>
                <span className="font-mono">{events.length}</span>
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                Cycle {str(result.cycle_id, "—")}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Observability">
          {!Object.keys(obs).length ? (
            <DeskEmpty
              icon={Shield}
              title="No dashboards"
              description="Auto · Risk · Safety · Recovery"
            />
          ) : (
            <ul className="max-h-36 space-y-1 overflow-auto font-mono text-[10px]">
              {Object.keys(asRecord(obs.dashboards)).map((k) => (
                <li key={k} className="text-[var(--fg-muted)]">
                  {k}
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Latency / soak">
          <div className="space-y-1.5 text-xs">
            <p className="text-[10px] text-[var(--fg-subtle)]">
              Distributions update from supplied latency samples.
            </p>
            <ul className="max-h-28 space-y-1 overflow-auto font-mono text-[10px]">
              {Object.keys(
                asRecord(statusQ.data?.latency_distributions),
              ).map((k) => (
                <li key={k} className="text-[var(--fg-muted)]">
                  {k}
                </li>
              ))}
            </ul>
            {soakM.data ? (
              <p className="font-mono text-[10px]">
                last soak {str(asRecord(soakM.data).status)} ·{" "}
                {str(asRecord(soakM.data).cycles_run)} cycles
              </p>
            ) : null}
          </div>
        </Panel>
      </div>

      <Panel title="Engines">
        {!moduleEntries.length ? (
          <DeskEmpty
            icon={Crosshair}
            title="No modules"
            description="Market quality → execution monitor"
          />
        ) : (
          <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {moduleEntries.map(([key, val]) => {
              const row = asRecord(val);
              return (
                <li
                  key={key}
                  className={cn(
                    "border px-2 py-2",
                    row.recommendation === "No Trade"
                      ? "border-[var(--warning)]/40"
                      : "border-[var(--border)]",
                  )}
                >
                  <p className="text-[10px] font-medium leading-tight">
                    {str(row.module, key).replace(/_/g, " ")}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-[var(--fg-subtle)]">
                    {str(row.status, "—")} · {str(row.score, "—")}
                  </p>
                  <p className="mt-1 text-[9px] text-[var(--fg-muted)] line-clamp-2">
                    {str(row.recommendation, "")}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel title="Event log">
          {!events.length ? (
            <DeskEmpty
              icon={Crosshair}
              title="No events"
              description="Every decision is auditable"
            />
          ) : (
            <ul className="max-h-48 space-y-1 overflow-auto font-mono text-[10px]">
              {events.slice(0, 40).map((e) => {
                const row = asRecord(e);
                return (
                  <li
                    key={`${str(row.event_id)}-${str(row.sequence)}`}
                    className="border-b border-[var(--border)]/60 py-1"
                  >
                    {str(row.event_type, "event")}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel title="History">
          {!history.length ? (
            <DeskEmpty
              icon={Crosshair}
              title="No history"
              description="Auditable cycles"
            />
          ) : (
            <ul className="max-h-48 space-y-1 overflow-auto font-mono text-[10px]">
              {history.map((h) => {
                const row = asRecord(h);
                return (
                  <li
                    key={str(row.cycle_id, "h")}
                    className="border-b border-[var(--border)]/60 py-1"
                  >
                    {str(row.cycle_id, "—")} · {str(row.recommendation, "—")}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}

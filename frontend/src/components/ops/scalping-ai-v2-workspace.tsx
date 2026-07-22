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
        {caps.never_bypass_risk === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            Risk authoritative
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "scalping-ai-v2")}
        </span>
        <Button
          size="sm"
          disabled={cycleM.isPending}
          onClick={() => cycleM.mutate()}
        >
          Run cycle
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
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
              Existing engines remain authoritative. Scalping AI never bypasses
              them or creates alternate execution paths.
            </p>
          </div>
        </Panel>

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

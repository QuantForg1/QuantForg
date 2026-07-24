"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteReliabilityApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "border border-[var(--border)] bg-[var(--surface)]",
        className,
      )}
    >
      <header className="border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="border border-[var(--border)]/70 bg-[var(--bg)] px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg text-[var(--fg)]">{value}</div>
      {hint ? (
        <div className="mt-0.5 text-[10px] text-[var(--fg-muted)]">{hint}</div>
      ) : null}
    </div>
  );
}

function fmt(v: unknown, digits = 2): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(digits);
  return str(v, "—");
}

export function AiValidationWorkspace() {
  const [replayDay, setReplayDay] = useState<string>("");
  const dash = useQuery({
    queryKey: ["ai-validation-v7", replayDay],
    queryFn: () => iteReliabilityApi.aiValidation(replayDay || undefined),
    retry: false,
    refetchInterval: 20_000,
  });

  if (dash.isLoading) return <DeskSkeleton rows={6} />;
  if (dash.isError) {
    return (
      <DeskError message="AI Validation dashboard unavailable (OWNER/ADMIN · /ite/reliability/ai-validation)." />
    );
  }

  const d = asRecord(dash.data);
  const byStrategy = asRecord(d.strategy_comparison);
  const exec = asRecord(d.execution_quality);
  const avgStages = asRecord(exec.avg_ms_by_stage);
  const slip = asRecord(d.slippage_report);
  const validation = asRecord(d.ai_validation_report);
  const summary = asRecord(validation.summary);
  const comparisons = asList(validation.recent_comparisons).map(asRecord);
  const replay = asRecord(d.opportunity_replay);
  const opportunities = asList(replay.opportunities).map(asRecord);
  const days = asList(replay.available_days).map(String);
  const risk = asRecord(d.risk_overview);
  const portfolio = asRecord(risk.portfolio ?? d.portfolio_analytics);
  const alerts = asList(d.alerts).map(asRecord);
  const opt = asRecord(d.weight_optimizer);
  const mult = asRecord(opt.multipliers);
  const bench = asRecord(d.benchmarks);
  const series = asList(bench.series).map(asRecord);

  const strategies = ["scalping", "intraday", "swing"] as const;

  return (
    <div className="space-y-3">
      <Panel title="Performance trends · by strategy">
        <div className="grid gap-3 lg:grid-cols-3">
          {strategies.map((name) => {
            const m = asRecord(byStrategy[name]);
            return (
              <div
                key={name}
                className="border border-[var(--border)]/70 bg-[var(--bg)] p-3"
              >
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  {name}
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <Metric label="Win rate" value={m.win_rate == null ? "—" : `${fmt(m.win_rate, 1)}%`} />
                  <Metric label="Avg RR" value={fmt(m.avg_rr, 2)} />
                  <Metric label="Avg profit" value={fmt(m.avg_profit)} />
                  <Metric label="Avg loss" value={fmt(m.avg_loss)} />
                  <Metric label="Profit factor" value={fmt(m.profit_factor, 2)} />
                  <Metric label="Sharpe" value={fmt(m.sharpe, 2)} />
                  <Metric
                    label="Avg hold"
                    value={
                      m.avg_holding_seconds == null
                        ? "—"
                        : `${fmt(Number(m.avg_holding_seconds) / 60, 1)} m`
                    }
                  />
                  <Metric label="Trades" value={str(m.trades, "0")} />
                </div>
              </div>
            );
          })}
        </div>
      </Panel>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Execution quality">
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            <Metric label="Signal" value={`${fmt(avgStages.signal_generation, 0)} ms`} />
            <Metric label="AI decision" value={`${fmt(avgStages.ai_decision, 0)} ms`} />
            <Metric label="OMS" value={`${fmt(avgStages.oms, 0)} ms`} />
            <Metric label="Gateway" value={`${fmt(avgStages.gateway, 0)} ms`} />
            <Metric label="MT5" value={`${fmt(avgStages.mt5, 0)} ms`} />
            <Metric label="Broker" value={`${fmt(avgStages.broker, 0)} ms`} />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
            <span className="font-mono text-[var(--fg)]">
              Total {fmt(exec.avg_total_execution_ms, 0)} ms
            </span>
            {exec.bottleneck ? (
              <Badge tone="warning">
                Bottleneck {str(exec.bottleneck)} · {fmt(exec.bottleneck_ms, 0)} ms
              </Badge>
            ) : null}
          </div>
        </Panel>

        <Panel title="Slippage report">
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Avg slippage" value={fmt(slip.avg_slippage, 4)} />
            <Metric label="Worst" value={fmt(slip.worst_slippage, 4)} />
            <Metric label="Best" value={fmt(slip.best_slippage, 4)} />
            <Metric label="Samples" value={str(slip.samples, "0")} />
          </div>
          <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
            {str(slip.recommendation, "—")}
          </p>
        </Panel>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="AI validation report (Shadow AI)">
          <div className="grid gap-2 sm:grid-cols-3">
            <Metric label="Comparisons" value={str(summary.total_comparisons, "0")} />
            <Metric
              label="Disagreements"
              value={str(summary.significant_disagreements, "0")}
            />
            <Metric
              label="Agreement"
              value={
                summary.agreement_rate == null
                  ? "—"
                  : `${fmt(summary.agreement_rate, 1)}%`
              }
            />
          </div>
          <div className="mt-2 max-h-56 space-y-1 overflow-auto font-mono text-[11px]">
            {comparisons.length === 0 ? (
              <p className="text-[var(--fg-muted)]">No shadow comparisons yet.</p>
            ) : (
              comparisons.slice(0, 25).map((c) => (
                <div
                  key={str(c.id)}
                  className="border-b border-[var(--border)]/40 py-1 last:border-0"
                >
                  <Badge
                    tone={c.significant_disagreement === true ? "warning" : "success"}
                  >
                    {c.significant_disagreement === true ? "DISAGREE" : "OK"}
                  </Badge>{" "}
                  {str(c.symbol)} · primary{" "}
                  {str(asRecord(c.primary).direction)}/
                  {str(asRecord(c.primary).confidence)} · shadow{" "}
                  {str(asRecord(c.shadow).direction)}/
                  {str(asRecord(c.shadow).confidence)}
                </div>
              ))
            )}
          </div>
        </Panel>

        <Panel title="Opportunity replay">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <label className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
              Day
            </label>
            <select
              className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 font-mono text-[11px] text-[var(--fg)]"
              value={replayDay || str(replay.day, "")}
              onChange={(e) => setReplayDay(e.target.value)}
            >
              <option value="">Today / latest</option>
              {days.map((day) => (
                <option key={day} value={day}>
                  {day}
                </option>
              ))}
            </select>
          </div>
          {opportunities.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No opportunities stored for this day.</p>
          ) : (
            <div className="max-h-56 space-y-1 overflow-auto font-mono text-[11px]">
              {opportunities.map((o) => (
                <div
                  key={str(o.id)}
                  className="border-b border-[var(--border)]/40 py-1 last:border-0"
                >
                  #{str(o.rank)} {str(o.symbol)} {str(o.direction)} · score{" "}
                  {str(o.opportunity_score)} ·{" "}
                  {o.traded === true
                    ? `traded ${str(o.result, "")}`
                    : `skipped ${str(o.skip_reason, "")}`}
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <Panel title="Risk overview">
          <div className="grid gap-2 sm:grid-cols-2">
            <Metric label="Daily return" value={`${fmt(portfolio.daily_return_pct)}%`} />
            <Metric label="Weekly" value={`${fmt(portfolio.weekly_return_pct)}%`} />
            <Metric label="Monthly" value={`${fmt(portfolio.monthly_return_pct)}%`} />
            <Metric label="Max DD" value={`${fmt(portfolio.max_drawdown_pct)}%`} />
            <Metric label="Current DD" value={`${fmt(portfolio.current_drawdown_pct)}%`} />
            <Metric
              label="Corr exposure"
              value={fmt(portfolio.correlation_exposure, 2)}
            />
          </div>
        </Panel>

        <Panel title="Weight optimizer">
          <p className="text-[11px] text-[var(--fg-muted)]">
            {str(opt.note)} · updates {str(opt.updates, "0")}
          </p>
          <div className="mt-2 max-h-40 overflow-auto font-mono text-[10px] text-[var(--fg-muted)]">
            {Object.entries(mult).map(([k, v]) => (
              <div key={k}>
                {k}: {fmt(v, 3)}
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Benchmarks">
          <p className="mb-2 text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
            {str(bench.period, "period")}
          </p>
          <div className="space-y-1 font-mono text-[11px]">
            {series.map((s) => (
              <div key={str(s.name)} className="flex justify-between">
                <span>{str(s.name)}</span>
                <span>{fmt(s.return_pct)}%</span>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[10px] text-[var(--fg-muted)]">
            vs BH {fmt(bench.relative_vs_buy_hold)} · vs SMA{" "}
            {fmt(bench.relative_vs_sma)} · vs baseline{" "}
            {fmt(bench.relative_vs_baseline)}
          </p>
        </Panel>
      </div>

      <Panel title="Alerts (observational — no auto halt)">
        {alerts.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">No validation alerts.</p>
        ) : (
          <div className="max-h-40 space-y-1 overflow-auto text-[11px]">
            {alerts.map((a) => (
              <div
                key={str(a.id)}
                className="border-b border-[var(--border)]/40 py-1 last:border-0"
              >
                <Badge
                  tone={
                    str(a.severity).toUpperCase() === "ERROR" ? "danger" : "warning"
                  }
                >
                  {str(a.kind)}
                </Badge>{" "}
                {str(a.detail)}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}

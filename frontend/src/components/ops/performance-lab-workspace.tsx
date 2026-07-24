"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="border border-[var(--border)]/70 bg-[var(--bg)] px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg text-[var(--fg)]">{value}</div>
      {hint ? <div className="mt-0.5 text-[10px] text-[var(--fg-muted)]">{hint}</div> : null}
    </div>
  );
}

function fmt(v: unknown, digits = 2): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(digits);
  return str(v, "—");
}

function heatBg(intensity: unknown): string {
  const n = Math.max(0, Math.min(100, Number(intensity) || 0));
  const alpha = (0.08 + n / 140).toFixed(2);
  return `color-mix(in srgb, var(--fg) ${Number(alpha) * 100}%, var(--bg))`;
}

export function PerformanceLabWorkspace() {
  const [symbol, setSymbol] = useState("");
  const [session, setSession] = useState("");
  const [regime, setRegime] = useState("");
  const [replayId, setReplayId] = useState<string>("");
  const [frameIndex, setFrameIndex] = useState(0);

  const dash = useQuery({
    queryKey: ["performance-lab-v8", symbol, session, regime, replayId, frameIndex],
    queryFn: () =>
      iteReliabilityApi.performanceLab({
        symbol: symbol || undefined,
        session: session || undefined,
        regime: regime || undefined,
        replayId: replayId || undefined,
        frameIndex,
      }),
    retry: false,
    refetchInterval: 20_000,
  });

  if (dash.isLoading) return <DeskSkeleton rows={7} />;
  if (dash.isError) {
    return (
      <DeskError message="Performance Lab unavailable (OWNER/ADMIN · /ite/reliability/performance-lab)." />
    );
  }

  const d = asRecord(dash.data);
  const safeguards = asRecord(d.safeguards);
  const cc = asRecord(d.champion_vs_challenger);
  const ccSummary = asRecord(cc.summary);
  const duels = asList(cc.recent).map(asRecord);
  const cal = asRecord(d.confidence_calibration);
  const calPoints = asList(cal.points).map(asRecord);
  const calFlags = asList(cal.flags).map(String);
  const opp = asRecord(d.opportunity_replay);
  const replays = asList(opp.trade_replays).map(asRecord);
  const step = asRecord(opp.step);
  const frame = asRecord(step.frame);
  const strat = asRecord(asRecord(d.strategy_comparison).by_strategy);
  const heat = asList(asRecord(d.portfolio_heatmap).cells).map(asRecord);
  const ranks = asRecord(d.symbol_rankings);
  const best = asList(ranks.best_symbols).map(asRecord);
  const worst = asList(ranks.worst_symbols).map(asRecord);
  const recs = asList(d.adaptive_recommendations).map(asRecord);

  return (
    <div className="space-y-3">
      <Panel title="Safeguards">
        <div className="flex flex-wrap gap-2 text-[11px]">
          <Badge tone="success">
            Challenger execute {safeguards.challenger_may_execute === true ? "ON" : "OFF"}
          </Badge>
          <Badge tone="success">
            Recs auto-apply {safeguards.recommendations_auto_applied === true ? "ON" : "OFF"}
          </Badge>
          <Badge tone="neutral">Trading logic unchanged</Badge>
        </div>
      </Panel>

      <Panel title="Champion vs Challenger">
        <div className="grid gap-2 sm:grid-cols-3">
          <Metric label="Duels" value={str(ccSummary.total_duels, "0")} />
          <Metric
            label="Direction agreement"
            value={
              ccSummary.direction_agreement_rate == null
                ? "—"
                : `${fmt(ccSummary.direction_agreement_rate, 1)}%`
            }
          />
          <Metric
            label="Challenger executions"
            value={str(ccSummary.challenger_executions, "0")}
            hint="must remain 0"
          />
        </div>
        <div className="mt-2 max-h-48 space-y-1 overflow-auto font-mono text-[11px]">
          {duels.length === 0 ? (
            <p className="text-[var(--fg-muted)]">No duels yet.</p>
          ) : (
            duels.slice(0, 20).map((x) => (
              <div key={str(x.id)} className="border-b border-[var(--border)]/40 py-1 last:border-0">
                <Badge tone={x.agree_direction === true ? "success" : "warning"}>
                  {x.agree_direction === true ? "AGREE" : "DIVERGE"}
                </Badge>{" "}
                {str(x.symbol)} · champ {str(asRecord(x.champion).direction)}/
                {str(asRecord(x.champion).confidence)} · chall{" "}
                {str(asRecord(x.challenger).direction)}/
                {str(asRecord(x.challenger).confidence)} · {str(x.session)}/{str(x.regime)}
              </div>
            ))
          )}
        </div>
      </Panel>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Confidence calibration">
          <div className="space-y-1">
            {calPoints.map((p) => (
              <div key={str(p.predicted_confidence)} className="flex items-center gap-2 text-[11px]">
                <span className="w-16 font-mono">{str(p.predicted_confidence)}%</span>
                <div className="h-2 flex-1 border border-[var(--border)] bg-[var(--bg)]">
                  <div
                    className="h-full bg-[var(--fg-muted)]"
                    style={{
                      width: `${Math.min(100, Number(p.actual_win_rate) || 0)}%`,
                    }}
                  />
                </div>
                <span className="w-20 font-mono text-right">
                  {p.actual_win_rate == null ? "—" : `${fmt(p.actual_win_rate, 0)}%`}
                </span>
                <Badge
                  tone={
                    str(p.status) === "overconfident"
                      ? "danger"
                      : str(p.status) === "underconfident"
                        ? "warning"
                        : "neutral"
                  }
                >
                  {str(p.status)}
                </Badge>
              </div>
            ))}
          </div>
          {calFlags.length > 0 ? (
            <p className="mt-2 text-[10px] text-[var(--fg-muted)]">{calFlags.join(" · ")}</p>
          ) : null}
        </Panel>

        <Panel title="Opportunity / trade replay">
          <div className="mb-2 flex flex-wrap gap-2">
            <select
              className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 font-mono text-[11px]"
              value={replayId}
              onChange={(e) => {
                setReplayId(e.target.value);
                setFrameIndex(0);
              }}
            >
              <option value="">Select replay</option>
              {replays.map((r) => (
                <option key={str(r.id)} value={str(r.id)}>
                  {str(r.symbol)} {str(r.direction)} · {str(r.ticket, "no-ticket")}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              variant="outline"
              disabled={!replayId}
              onClick={() => setFrameIndex((i) => Math.max(0, i - 1))}
            >
              Prev
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!replayId}
              onClick={() => setFrameIndex((i) => i + 1)}
            >
              Next
            </Button>
          </div>
          {replayId && frame.label ? (
            <div className="border border-[var(--border)]/60 bg-[var(--bg)] p-2 font-mono text-[11px]">
              Frame {str(step.frame_index)}/{str(step.frame_count)} ·{" "}
              <span className="uppercase">{str(frame.label)}</span>
              <div className="mt-1 text-[var(--fg-muted)]">{str(frame.detail)}</div>
              <div className="mt-1">
                px {fmt(frame.price, 4)} · SL {fmt(frame.stop, 4)} · TP {fmt(frame.tp, 4)} ·
                trail {fmt(frame.trail, 4)}
              </div>
            </div>
          ) : (
            <p className="text-sm text-[var(--fg-muted)]">
              Select a completed trade to step the timeline (structure, AI, entry, trail, exit).
            </p>
          )}
          <p className="mt-2 text-[10px] text-[var(--fg-muted)]">
            Opportunity DB: {str(asRecord(opp.database_summary).total, "0")} total · traded{" "}
            {str(asRecord(opp.database_summary).traded, "0")} · skipped{" "}
            {str(asRecord(opp.database_summary).skipped, "0")}
          </p>
        </Panel>
      </div>

      <Panel title="Strategy comparison">
        <div className="mb-2 flex flex-wrap gap-2 text-[11px]">
          <input
            className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 font-mono"
            placeholder="Symbol filter"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          />
          <input
            className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 font-mono"
            placeholder="Session"
            value={session}
            onChange={(e) => setSession(e.target.value)}
          />
          <input
            className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 font-mono"
            placeholder="Regime"
            value={regime}
            onChange={(e) => setRegime(e.target.value)}
          />
        </div>
        <div className="grid gap-3 lg:grid-cols-3">
          {(["scalping", "intraday", "swing"] as const).map((name) => {
            const m = asRecord(strat[name]);
            return (
              <div key={name} className="border border-[var(--border)]/70 bg-[var(--bg)] p-2">
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  {name}
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <Metric label="Win rate" value={m.win_rate == null ? "—" : `${fmt(m.win_rate, 1)}%`} />
                  <Metric label="PF" value={fmt(m.profit_factor, 2)} />
                  <Metric label="DD" value={fmt(m.drawdown, 1)} />
                  <Metric label="Avg RR" value={fmt(m.avg_rr, 2)} />
                  <Metric label="Slippage" value={fmt(m.avg_slippage, 4)} />
                  <Metric label="Trades" value={str(m.trades, "0")} />
                </div>
              </div>
            );
          })}
        </div>
      </Panel>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Portfolio heatmap">
          {heat.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No open positions for heatmap.</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2">
              {heat.map((c) => (
                <div
                  key={str(c.symbol)}
                  className="border border-[var(--border)] p-2 font-mono text-[11px]"
                  style={{ background: heatBg(c.heat_exposure) }}
                >
                  <div className="font-semibold">{str(c.symbol)}</div>
                  <div>exp {fmt(c.exposure, 3)} · corr {fmt(c.correlation, 2)}</div>
                  <div>
                    conf {fmt(c.ai_confidence, 0)} · uPnL {fmt(c.unrealized_pnl)} · rPnL{" "}
                    {fmt(c.realized_pnl)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Symbol rankings">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <div className="text-[10px] uppercase text-[var(--fg-subtle)]">Best</div>
              {best.slice(0, 5).map((s) => (
                <div key={str(s.symbol)} className="font-mono text-[11px]">
                  {str(s.symbol)} PF {fmt(s.profit_factor, 2)}
                </div>
              ))}
            </div>
            <div>
              <div className="text-[10px] uppercase text-[var(--fg-subtle)]">Worst</div>
              {worst.slice(0, 5).map((s) => (
                <div key={str(s.symbol)} className="font-mono text-[11px]">
                  {str(s.symbol)} PF {fmt(s.profit_factor, 2)}
                </div>
              ))}
            </div>
          </div>
          <p className="mt-2 text-[10px] text-[var(--fg-muted)]">
            Best session:{" "}
            {str(asRecord(ranks.most_profitable_session).session, "—")} · pnl{" "}
            {fmt(asRecord(ranks.most_profitable_session).total_pnl)}
          </p>
        </Panel>
      </div>

      <Panel title="Adaptive recommendations (advisory only)">
        {recs.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">No recommendations yet.</p>
        ) : (
          <div className="max-h-40 space-y-1 overflow-auto text-[11px]">
            {recs.map((r) => (
              <div key={str(r.id)} className="border-b border-[var(--border)]/40 py-1 last:border-0">
                <Badge tone="neutral">{str(r.kind)}</Badge> {str(r.message)}{" "}
                <span className="text-[var(--fg-muted)]">auto_applied=false</span>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}

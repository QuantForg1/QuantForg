"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { performanceIntelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";

type Period = "daily" | "weekly" | "monthly";

function Stat({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="border border-[var(--border)] bg-[var(--bg)]/40 px-2.5 py-2">
      <p className="text-[9px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p className="mt-1 font-mono text-sm tabular text-[var(--fg)]">{value}</p>
    </div>
  );
}

function fmtPct(v: unknown): string {
  const n = num(v);
  return Number.isFinite(n) ? `${formatNumber(n * 100, 1)}%` : "—";
}

function fmt(v: unknown, d = 2): string {
  const n = num(v);
  return Number.isFinite(n) ? formatNumber(n, d) : "—";
}

/**
 * Institutional Performance Intelligence desk — journals only.
 * Never modifies strategy / risk / safety / execution.
 */
export function PerformanceIntelligenceWorkspace() {
  const [period, setPeriod] = useState<Period>("monthly");
  const q = useQuery({
    queryKey: ["performance-intelligence", period],
    queryFn: () => performanceIntelligenceApi.dashboard(200, period),
    retry: false,
    staleTime: 20_000,
  });

  if (q.isLoading && !q.data) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message="Performance Intelligence unavailable."
        onRetry={() => void q.refetch()}
      />
    );
  }

  const d = asRecord(q.data);
  const perf = asRecord(asRecord(d.performance).metrics);
  const sessions = asRecord(asRecord(d.sessions).sessions);
  const regimes = asRecord(asRecord(d.regimes).regimes);
  const signals = asRecord(asRecord(d.signals).signals);
  const combinations = asList(asRecord(d.signals).combinations).map(asRecord);
  const noTrade = asRecord(d.no_trade);
  const timeM = asRecord(asRecord(d.time).metrics);
  const recs = asList(d.recommendations).map(String);
  const evidence = asRecord(d.evidence_summary);
  const openQ = asList(asRecord(asRecord(d.report).open_questions)).map(String);

  const sessionKeys = ["london", "new_york", "overlap", "tokyo", "sydney"] as const;
  const regimeKeys = [
    "trend",
    "range",
    "high_volatility",
    "low_volatility",
  ] as const;

  if (str(d.status) === "unavailable" && num(evidence.closed_trades_with_pnl) === 0) {
    return (
      <DeskEmpty
        icon={BarChart3}
        title="No closed-trade PnL in journal"
        description="Performance Intelligence reads execution journal rows with PnL only. Metrics stay unavailable rather than fabricated."
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Institutional Performance Intelligence
          </span>
          <Badge tone="neutral">v{str(d.version, "1.0.1")}</Badge>
          <Badge tone="neutral">
            n={str(evidence.closed_trades_with_pnl, "0")}
          </Badge>
        </div>
        <div className="flex gap-1">
          {(["daily", "weekly", "monthly"] as const).map((p) => (
            <Button
              key={p}
              size="sm"
              variant={period === p ? "default" : "outline"}
              onClick={() => setPeriod(p)}
            >
              {p}
            </Button>
          ))}
        </div>
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Performance
        </h2>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          <Stat label="Total Trades" value={str(perf.total_trades, "—")} />
          <Stat label="Winning" value={str(perf.winning_trades, "—")} />
          <Stat label="Losing" value={str(perf.losing_trades, "—")} />
          <Stat label="Win Rate" value={fmtPct(perf.win_rate)} />
          <Stat label="Profit Factor" value={fmt(perf.profit_factor)} />
          <Stat label="Expectancy" value={fmt(perf.expectancy, 3)} />
          <Stat label="Avg Win" value={fmt(perf.average_win)} />
          <Stat label="Avg Loss" value={fmt(perf.average_loss)} />
          <Stat label="Avg RR" value={fmt(perf.average_rr)} />
          <Stat label="Largest Win" value={fmt(perf.largest_win)} />
          <Stat label="Largest Loss" value={fmt(perf.largest_loss)} />
          <Stat label="Consec Wins" value={str(perf.consecutive_wins, "—")} />
          <Stat label="Consec Losses" value={str(perf.consecutive_losses, "—")} />
          <Stat label="Max DD %" value={fmt(perf.maximum_drawdown_pct)} />
          <Stat label="Recovery Factor" value={fmt(perf.recovery_factor)} />
        </div>
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Sessions (never mixed)
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-xs">
            <thead className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              <tr>
                <th className="py-1 pr-2">Session</th>
                <th className="py-1 pr-2">Trades</th>
                <th className="py-1 pr-2">Win Rate</th>
                <th className="py-1 pr-2">PF</th>
                <th className="py-1 pr-2">Expectancy</th>
                <th className="py-1 pr-2">Avg RR</th>
                <th className="py-1">Net P/L</th>
              </tr>
            </thead>
            <tbody>
              {sessionKeys.map((key) => {
                const s = asRecord(sessions[key]);
                return (
                  <tr key={key} className="border-t border-[var(--border)]">
                    <td className="py-1.5 pr-2 capitalize">{key}</td>
                    <td className="py-1.5 pr-2 font-mono">{str(s.trade_count, "0")}</td>
                    <td className="py-1.5 pr-2 font-mono">{fmtPct(s.win_rate)}</td>
                    <td className="py-1.5 pr-2 font-mono">{fmt(s.profit_factor)}</td>
                    <td className="py-1.5 pr-2 font-mono">{fmt(s.expectancy, 3)}</td>
                    <td className="py-1.5 pr-2 font-mono">{fmt(s.average_rr)}</td>
                    <td className="py-1.5 font-mono">{fmt(s.net_pnl)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Market regimes (never mixed)
        </h2>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {regimeKeys.map((key) => {
            const r = asRecord(regimes[key]);
            return (
              <div key={key} className="border border-[var(--border)] px-2.5 py-2">
                <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  {key.replace(/_/g, " ")}
                </p>
                <p className="mt-1 font-mono text-xs">
                  n={str(r.trade_count, "0")} · WR {fmtPct(r.win_rate)}
                </p>
                <p className="font-mono text-xs text-[var(--fg-muted)]">
                  Exp {fmt(r.expectancy, 3)} · Hold {fmt(r.average_hold_seconds, 0)}s
                </p>
              </div>
            );
          })}
        </div>
        {num(asRecord(d.regimes).unlabeled_trades) > 0 ? (
          <p className="mt-2 text-xs text-[var(--warning)]">
            Unlabeled trades excluded: {str(asRecord(d.regimes).unlabeled_trades)}
          </p>
        ) : null}
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Signal analytics
        </h2>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {(
            [
              "bos",
              "choch",
              "liquidity_sweep",
              "order_block",
              "fair_value_gap",
              "confluence_90_plus",
            ] as const
          ).map((key) => {
            const s = asRecord(signals[key]);
            return (
              <Stat
                key={key}
                label={key.replace(/_/g, " ")}
                value={`n=${str(s.trade_count, "0")} WR ${fmtPct(s.win_rate)}`}
              />
            );
          })}
        </div>
        {combinations[0] ? (
          <p className="mt-2 text-xs text-[var(--fg-muted)]">
            Best tagged combination:{" "}
            <span className="font-mono text-[var(--fg)]">
              {str(combinations[0].combination)}
            </span>{" "}
            (n={str(combinations[0].trade_count)}, exp {fmt(combinations[0].expectancy, 3)})
          </p>
        ) : (
          <p className="mt-2 text-xs text-[var(--fg-muted)]">
            No signal tags on journal rows yet — combinations unavailable.
          </p>
        )}
      </section>

      <div className="grid gap-3 lg:grid-cols-2">
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            NO_TRADE analytics
          </h2>
          <p className="font-mono text-sm">
            Count: {str(noTrade.no_trade_count, "—")}
          </p>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">
            {str(noTrade.message || noTrade.assessment, "Decision journal not supplied")}
          </p>
          <p className="mt-1 text-[10px] text-[var(--fg-subtle)]">
            Estimated bad trades avoided is research-only — never realized PnL.
          </p>
        </section>
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Time analytics
          </h2>
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Avg duration" value={`${fmt(timeM.average_trade_duration_seconds, 0)}s`} />
            <Stat label="Fastest" value={`${fmt(timeM.fastest_trade_seconds, 0)}s`} />
            <Stat label="Longest" value={`${fmt(timeM.longest_trade_seconds, 0)}s`} />
            <Stat label="Avg to TP" value={`${fmt(timeM.average_time_to_tp_seconds, 0)}s`} />
            <Stat label="Avg to SL" value={`${fmt(timeM.average_time_to_sl_seconds, 0)}s`} />
          </div>
        </section>
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Recommendations (never auto-applied)
        </h2>
        {recs.length ? (
          <ul className="list-disc space-y-1 pl-4 text-xs text-[var(--fg-muted)]">
            {recs.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-[var(--fg-muted)]">No recommendations.</p>
        )}
        {openQ.length ? (
          <div className="mt-3">
            <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Open questions
            </p>
            <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-[var(--fg-muted)]">
              {openQ.map((qItem) => (
                <li key={qItem}>{qItem}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>
    </div>
  );
}

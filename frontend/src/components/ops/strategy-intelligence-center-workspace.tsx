"use client";

import { useQuery } from "@tanstack/react-query";
import { Brain } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, bool, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function ScoreBanner({ score }: { score: Record<string, unknown> }) {
  const level = str(score.level, "YELLOW");
  const label = str(score.label, "Neutral");
  const value = score.score == null ? "—" : String(num(score.score));
  return (
    <div
      className={cn(
        "border px-4 py-4",
        level === "GREEN" && "border-[var(--success)]/40 bg-[var(--success)]/10",
        level === "YELLOW" && "border-[var(--warning)]/40 bg-[var(--warning)]/10",
        level === "RED" && "border-[var(--danger)]/40 bg-[var(--danger)]/10",
      )}
    >
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
        Strategy Intelligence Score
      </p>
      <p
        className={cn(
          "mt-1 text-[28px] font-semibold tabular-nums tracking-tight",
          level === "GREEN" && "text-[var(--success)]",
          level === "YELLOW" && "text-[var(--warning)]",
          level === "RED" && "text-[var(--danger)]",
        )}
      >
        {value}
        <span className="ml-2 text-[14px] font-medium">{level}</span>
      </p>
      <p className="mt-1 text-[14px] text-[var(--fg)]">{label}</p>
      <ul className="mt-3 space-y-1 font-mono text-[11px] text-[var(--fg-muted)]">
        {asList(score.reasons)
          .slice(0, 8)
          .map((r, i) => (
            <li key={`${i}-${str(r)}`}>{str(r)}</li>
          ))}
      </ul>
    </div>
  );
}

function PatternList({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "success" | "danger";
}) {
  return (
    <div
      className={cn(
        "border px-3 py-3",
        tone === "success" && "border-[var(--success)]/30 bg-[var(--success)]/5",
        tone === "danger" && "border-[var(--danger)]/30 bg-[var(--danger)]/5",
      )}
    >
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg)]">
        {title}
      </p>
      {items.length === 0 ? (
        <p className="text-[12px] text-[var(--fg-subtle)]">
          Insufficient enriched sample
        </p>
      ) : (
        <ul className="space-y-1 font-mono text-[12px] text-[var(--fg-muted)]">
          {items.map((line) => (
            <li key={line}>• {line}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function StrategyIntelligenceCenterWorkspace() {
  const q = useQuery({
    queryKey: ["ite-ops-strategy-intelligence-center"],
    queryFn: () => iteOpsApi.strategyIntelligenceCenter(90),
    retry: false,
    refetchInterval: 60_000,
  });

  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Strategy Intelligence Center unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }

  const root = asRecord(q.data);
  const intel = asRecord(root.intelligence);
  const patterns = asRecord(root.patterns);
  const score = asRecord(root.strategy_intelligence_score);
  const trades = asList(root.trades).map(asRecord);
  const winLines = asList(patterns.winning_trades_usually_occur_when).map((x) =>
    str(x),
  );
  const loseLines = asList(patterns.losing_trades_usually_occur_when).map((x) =>
    str(x),
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">STRATEGY INTELLIGENCE</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">NEVER AUTO-OPTIMIZES</Badge>
        <Badge tone="neutral">
          {num(root.trade_count, 0)} closed · {num(root.wins, 0)}W /{" "}
          {num(root.losses, 0)}L
        </Badge>
      </div>

      <ScoreBanner score={score} />

      {asRecord(root.market_regime_intelligence).current_regime ? (
        <OpsPanel title="Market Regime (integrated)">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Current Regime
              </p>
              <p className="text-[18px] font-semibold text-[var(--fg)]">
                {str(asRecord(root.market_regime_intelligence).current_regime)}
                {asRecord(root.market_regime_intelligence).secondary_regime
                  ? ` · ${str(asRecord(root.market_regime_intelligence).secondary_regime)}`
                  : ""}
              </p>
              <p className="mt-1 font-mono text-[12px] text-[var(--fg-muted)]">
                Confidence{" "}
                {str(
                  asRecord(root.market_regime_intelligence).confidence_display,
                  "—",
                )}
              </p>
            </div>
            <Button asChild size="sm" variant="outline">
              <Link href="/market-regime-intelligence">Regime Dashboard</Link>
            </Button>
          </div>
        </OpsPanel>
      ) : null}

      <OpsPanel title="Intelligence">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <MetricCard
            label="Best Trading Session"
            value={str(intel.best_trading_session, "—")}
          />
          <MetricCard
            label="Worst Trading Session"
            value={str(intel.worst_trading_session, "—")}
          />
          <MetricCard
            label="Best Day of Week"
            value={str(intel.best_day_of_week, "—")}
          />
          <MetricCard
            label="Worst Day of Week"
            value={str(intel.worst_day_of_week, "—")}
          />
          <MetricCard
            label="Best Volatility Range"
            value={str(intel.best_volatility_range, "—")}
          />
          <MetricCard
            label="Worst Volatility Range"
            value={str(intel.worst_volatility_range, "—")}
          />
          <MetricCard
            label="Best ATR Range"
            value={str(intel.best_atr_range, "—")}
          />
          <MetricCard
            label="Worst ATR Range"
            value={str(intel.worst_atr_range, "—")}
          />
          <MetricCard
            label="Best Spread Range"
            value={str(intel.best_spread_range, "—")}
          />
          <MetricCard
            label="Average Holding Time"
            value={str(intel.average_holding_time_display, "—")}
          />
          <MetricCard
            label="Average Winning RR"
            value={
              intel.average_winning_rr != null
                ? String(num(intel.average_winning_rr))
                : "—"
            }
          />
          <MetricCard
            label="Average Losing RR"
            value={
              intel.average_losing_rr != null
                ? String(num(intel.average_losing_rr))
                : "—"
            }
          />
        </div>
      </OpsPanel>

      <OpsPanel title="Patterns">
        <div className="grid gap-3 md:grid-cols-2">
          <PatternList
            title="Winning trades usually occur when"
            items={winLines}
            tone="success"
          />
          <PatternList
            title="Losing trades usually occur when"
            items={loseLines}
            tone="danger"
          />
        </div>
      </OpsPanel>

      <OpsPanel title="Completed trades (enriched)">
        {trades.length === 0 ? (
          <DeskEmpty
            icon={Brain}
            title="No closed trades yet"
            description="Intelligence appears when MT5 history contains completed XAUUSD round-trips. Context (MTF/Quality/Confluence/ATR/Spread) soft-joins from Strategy Diagnostics when available."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] border-collapse text-left text-[12px]">
              <thead>
                <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                  <th className="px-2 py-2 font-medium">Session</th>
                  <th className="px-2 py-2 font-medium">Regime</th>
                  <th className="px-2 py-2 font-medium">MTF</th>
                  <th className="px-2 py-2 font-medium">Q</th>
                  <th className="px-2 py-2 font-medium">C</th>
                  <th className="px-2 py-2 font-medium">ATR</th>
                  <th className="px-2 py-2 font-medium">Spread</th>
                  <th className="px-2 py-2 font-medium">Entry</th>
                  <th className="px-2 py-2 font-medium">Exit</th>
                  <th className="px-2 py-2 font-medium">Hold</th>
                  <th className="px-2 py-2 font-medium">RR</th>
                  <th className="px-2 py-2 font-medium">P/L</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => {
                  const pnl = num(t.profit_loss, 0);
                  return (
                    <tr
                      key={`${str(t.id, String(i))}-${str(t.exit_time)}`}
                      className="border-b border-[var(--border)]/60 font-mono tabular-nums"
                    >
                      <td className="px-2 py-1.5">{str(t.market_session, "—")}</td>
                      <td className="px-2 py-1.5">
                        {str(t.market_regime, "—")}
                        {bool(t.trending) ? " · T" : ""}
                        {bool(t.ranging) ? " · R" : ""}
                        {bool(t.high_volatility) ? " · HV" : ""}
                        {bool(t.low_volatility) ? " · LV" : ""}
                      </td>
                      <td className="px-2 py-1.5">{str(t.mtf_score, "—")}</td>
                      <td className="px-2 py-1.5">{str(t.quality, "—")}</td>
                      <td className="px-2 py-1.5">{str(t.confluence, "—")}</td>
                      <td className="px-2 py-1.5">{str(t.atr, "—")}</td>
                      <td className="px-2 py-1.5">{str(t.spread, "—")}</td>
                      <td className="px-2 py-1.5">{str(t.entry, "—")}</td>
                      <td className="px-2 py-1.5">{str(t.exit, "—")}</td>
                      <td className="px-2 py-1.5">
                        {t.holding_time_sec != null
                          ? `${num(t.holding_time_sec).toFixed(0)}s`
                          : "—"}
                      </td>
                      <td className="px-2 py-1.5">{str(t.risk_reward, "—")}</td>
                      <td
                        className={cn(
                          "px-2 py-1.5",
                          pnl > 0 && "text-[var(--success)]",
                          pnl < 0 && "text-[var(--danger)]",
                        )}
                      >
                        {pnl.toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </OpsPanel>
    </div>
  );
}

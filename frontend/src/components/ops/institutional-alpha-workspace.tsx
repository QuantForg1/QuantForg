"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iteOpsApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn, formatNumber } from "@/lib/utils";

/**
 * Institutional Alpha Engine desk — opportunity ranking, correlation, analytics.
 * Extends Auto Trading; never bypasses Risk / OMS / Safety.
 */
export function InstitutionalAlphaWorkspace() {
  const qc = useQueryClient();
  const alphaQ = useQuery({
    queryKey: ["ite-ops-institutional-alpha"],
    queryFn: iteOpsApi.institutionalAlpha,
    retry: false,
    refetchInterval: 8_000,
  });
  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 12_000,
  });

  const enableMut = useMutation({
    mutationFn: (on: boolean) =>
      iteOpsApi.updateAutoTrading({
        confirmed: true,
        reason: on ? "enable institutional alpha" : "disable institutional alpha",
        trading_mode: on ? "alpha" : "swing",
        alpha_engine_enabled: on,
        max_open_positions: on
          ? 3
          : num(asRecord(asRecord(autoQ.data).policy).max_open_positions, 1),
      }),
    onSuccess: (_d, on) => {
      toast.success(on ? "Institutional Alpha enabled" : "Alpha disabled — Swing mode");
      void qc.invalidateQueries({ queryKey: ["ite-ops-institutional-alpha"] });
      void qc.invalidateQueries({ queryKey: ["ite-ops-auto-trading"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Failed to update Alpha mode"),
  });

  const data = asRecord(alphaQ.data);
  const matrix = asRecord(data.correlation_matrix);
  const symbols = Object.keys(matrix);
  const matrixRows = useMemo(() => {
    return symbols.map((row) => {
      const cells = asRecord(matrix[row]);
      return { row, cells };
    });
  }, [matrix, symbols]);

  if (alphaQ.isLoading) return <DeskSkeleton rows={6} />;
  if (alphaQ.isError) {
    return (
      <DeskError
        message={alphaQ.error instanceof Error ? alphaQ.error.message : "Institutional Alpha load failed"}
      />
    );
  }

  const ranking = asList(data.opportunity_ranking).map(asRecord);
  const selected = asList(data.selected).map(asRecord);
  const analytics = asRecord(data.analytics);
  const performance = asRecord(data.performance);
  const recovery = asRecord(data.recovery);
  const confBySym = asRecord(data.ai_confidence_by_symbol);
  const enabled = Boolean(data.enabled || data.plane_enabled);

  const portfolioRisk = num(data.portfolio_risk_pct);
  const dailyRisk = str(data.daily_risk_used_pct, "0");
  return (
    <div className="space-y-3">
      <section className="border border-[var(--border)] bg-[var(--surface)]/90 px-3 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--fg-subtle)]">
              Institutional Alpha Engine
            </span>
            <Badge tone={enabled ? "success" : "neutral"}>
              {enabled ? "ALPHA ON" : "ALPHA OFF"}
            </Badge>
            <Badge tone={recovery.active ? "warning" : "neutral"}>
              {recovery.active
                ? `Recovery ${String(recovery.remaining_trades)} left`
                : "Recovery clear"}
            </Badge>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={enableMut.isPending || enabled}
              onClick={() => enableMut.mutate(true)}
            >
              Enable Alpha
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={enableMut.isPending || !enabled}
              onClick={() => enableMut.mutate(false)}
            >
              Disable
            </Button>
            <Button asChild size="sm" variant="ghost">
              <Link href="/auto-trading">Auto Trading</Link>
            </Button>
          </div>
        </div>
        <p className="mt-2 text-xs text-[var(--fg-muted)]">
          Scans the configured universe, ranks opportunities, blocks correlated books, and
          allocates risk by quality — never Martingale / Grid / averaging down.
        </p>
      </section>

      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Portfolio Risk %" value={formatNumber(portfolioRisk, 2)} />
        <MetricCard label="Daily Risk Used %" value={dailyRisk} />
        <MetricCard
          label="Win Rate"
          value={
            performance.win_rate != null ? `${String(performance.win_rate)}%` : "—"
          }
        />
        <MetricCard
          label="Avg RR"
          value={performance.avg_rr != null ? String(performance.avg_rr) : "—"}
        />
        <MetricCard
          label="Daily PnL"
          value={performance.daily != null ? String(performance.daily) : "—"}
        />
        <MetricCard
          label="Weekly PnL"
          value={performance.weekly != null ? String(performance.weekly) : "—"}
        />
        <MetricCard
          label="Monthly PnL"
          value={performance.monthly != null ? String(performance.monthly) : "—"}
        />
        <MetricCard
          label="Avg Hold"
          value={
            performance.avg_hold_minutes != null
              ? `${String(performance.avg_hold_minutes)} m`
              : "—"
          }
        />
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <OpsPanel title="Live Opportunity Ranking">
          {ranking.length === 0 ? (
            <p className="text-xs text-[var(--fg-muted)]">No ranked opportunities yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  <tr>
                    <th className="py-1 pr-2">#</th>
                    <th className="py-1 pr-2">Symbol</th>
                    <th className="py-1 pr-2">Score</th>
                    <th className="py-1 pr-2">Conf</th>
                    <th className="py-1 pr-2">Dir</th>
                    <th className="py-1 pr-2">RR</th>
                    <th className="py-1 pr-2">Session</th>
                  </tr>
                </thead>
                <tbody>
                  {ranking.map((row) => {
                    const isSel = selected.some(
                      (s) => str(s.symbol) === str(row.symbol),
                    );
                    return (
                      <tr
                        key={str(row.symbol)}
                        className={cn(
                          "border-t border-[var(--border)] font-mono",
                          isSel && "bg-[var(--accent-soft)]",
                        )}
                      >
                        <td className="py-1.5 pr-2">{str(row.rank, "—")}</td>
                        <td className="py-1.5 pr-2 text-[var(--fg)]">{str(row.symbol)}</td>
                        <td className="py-1.5 pr-2">{str(row.opportunity_score)}</td>
                        <td className="py-1.5 pr-2">{str(row.ai_confidence)}</td>
                        <td className="py-1.5 pr-2">{str(row.direction)}</td>
                        <td className="py-1.5 pr-2">{str(row.expected_rr)}</td>
                        <td className="py-1.5 pr-2">{str(row.session_score)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </OpsPanel>

        <OpsPanel title="AI Confidence per Symbol">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {Object.keys(confBySym).length === 0 ? (
              <p className="text-xs text-[var(--fg-muted)]">Waiting for scan…</p>
            ) : (
              Object.entries(confBySym).map(([sym, conf]) => (
                <MetricCard key={sym} label={sym} value={String(conf)} />
              ))
            )}
          </div>
        </OpsPanel>
      </div>

      <OpsPanel title="Correlation Matrix">
        {symbols.length === 0 ? (
          <p className="text-xs text-[var(--fg-muted)]">Matrix unavailable.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-center font-mono text-[10px]">
              <thead>
                <tr>
                  <th className="p-1" />
                  {symbols.map((s) => (
                    <th key={s} className="p-1 text-[var(--fg-subtle)]">
                      {s}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrixRows.map(({ row, cells }) => (
                  <tr key={row}>
                    <td className="p-1 text-left text-[var(--fg-subtle)]">{row}</td>
                    {symbols.map((col) => {
                      const v = num(cells[col]);
                      return (
                        <td
                          key={`${row}-${col}`}
                          className={cn(
                            "p-1",
                            v >= 1 && row !== col
                              ? "bg-[var(--danger)]/20 text-[var(--danger)]"
                              : "text-[var(--fg-muted)]",
                          )}
                        >
                          {formatNumber(v, 0)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </OpsPanel>

      <OpsPanel title="Institutional Analytics">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
          <MetricCard label="Best Session" value={str(analytics.best_session, "—")} />
          <MetricCard label="Worst Session" value={str(analytics.worst_session, "—")} />
          <MetricCard label="Best Symbol" value={str(analytics.best_symbol, "—")} />
          <MetricCard label="Worst Symbol" value={str(analytics.worst_symbol, "—")} />
          <MetricCard label="Best Strategy" value={str(analytics.best_strategy, "—")} />
          <MetricCard label="Worst Strategy" value={str(analytics.worst_strategy, "—")} />
          <MetricCard
            label="Avg Latency"
            value={
              analytics.avg_execution_ms != null
                ? `${String(analytics.avg_execution_ms)} ms`
                : "—"
            }
          />
          <MetricCard
            label="Avg Slippage"
            value={analytics.avg_slippage != null ? String(analytics.avg_slippage) : "—"}
          />
          <MetricCard
            label="Avg Spread"
            value={analytics.avg_spread != null ? String(analytics.avg_spread) : "—"}
          />
          <MetricCard label="Trades" value={str(analytics.trades, "0")} />
        </div>
      </OpsPanel>
    </div>
  );
}

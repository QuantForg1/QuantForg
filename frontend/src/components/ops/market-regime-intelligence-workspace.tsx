"use client";

import { useQuery } from "@tanstack/react-query";
import { Layers3 } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function CurrentRegimeCard({ current }: { current: Record<string, unknown> }) {
  const perf = asRecord(current.historical_performance);
  const primary = str(current.current_regime, "UNKNOWN");
  const secondary = str(current.secondary_regime, "");
  return (
    <div className="border border-[var(--border)] bg-[var(--surface)]/90 px-4 py-4">
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
        Current Regime
      </p>
      <p className="mt-1 text-[24px] font-semibold tracking-tight text-[var(--fg)]">
        {primary}
      </p>
      {secondary ? (
        <p className="mt-1 text-[13px] text-[var(--fg-muted)]">
          Secondary · <span className="font-semibold text-[var(--fg)]">{secondary}</span>
        </p>
      ) : null}
      <p className="mt-3 font-mono text-[13px] tabular-nums text-[var(--fg)]">
        Confidence · {str(current.confidence_display, `${str(current.confidence)}%`)}
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <MetricCard
          label="Win Rate"
          value={str(perf.win_rate_display, "—")}
        />
        <MetricCard
          label="Profit Factor"
          value={
            perf.profit_factor != null ? String(num(perf.profit_factor)) : "—"
          }
        />
        <MetricCard
          label="Expectancy"
          value={str(perf.expectancy_display, "—")}
        />
      </div>

      <ul className="mt-4 space-y-1 font-mono text-[11px] text-[var(--fg-subtle)]">
        {asList(current.evidence)
          .slice(0, 6)
          .map((e, i) => (
            <li key={`${i}-${str(e)}`}>{str(e)}</li>
          ))}
      </ul>
    </div>
  );
}

export function MarketRegimeIntelligenceWorkspace() {
  const q = useQuery({
    queryKey: ["ite-ops-market-regime-intelligence"],
    queryFn: () => iteOpsApi.marketRegimeIntelligence(100),
    retry: false,
    refetchInterval: 8_000,
  });

  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Market Regime Intelligence unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }

  const root = asRecord(q.data);
  const current = asRecord(root.current);
  const history = asList(root.regime_history).map(asRecord);
  const distribution = asList(root.regime_distribution).map(asRecord);
  const performance = asRecord(root.regime_performance);
  const perfRows = Object.keys(performance).map((k) => asRecord(performance[k]));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">MARKET REGIME</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">NEVER INFLUENCES EXECUTION</Badge>
        <Badge tone="neutral">{num(root.count, 0)}/100 evaluations</Badge>
        <Button asChild size="sm" variant="outline">
          <Link href="/strategy-intelligence-center">Strategy Intelligence</Link>
        </Button>
      </div>

      <CurrentRegimeCard current={current} />

      <OpsPanel title="Regime Distribution (last 100)">
        {distribution.length === 0 ? (
          <DeskEmpty
            icon={Layers3}
            title="No regime samples yet"
            description="Distribution fills as live ITE evaluations are recorded."
          />
        ) : (
          <div className="space-y-2">
            {distribution.map((row) => {
              const share = num(row.share_pct, 0);
              return (
                <div key={str(row.regime)} className="grid grid-cols-[140px_1fr_64px] items-center gap-2">
                  <span className="font-mono text-[11px] text-[var(--fg)]">
                    {str(row.regime)}
                  </span>
                  <div className="h-2 bg-[var(--surface-2)]">
                    <div
                      className="h-2 bg-[var(--accent)]"
                      style={{ width: `${Math.min(100, share)}%` }}
                    />
                  </div>
                  <span className="font-mono text-[11px] tabular-nums text-[var(--fg-muted)]">
                    {share}% · {num(row.count, 0)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </OpsPanel>

      <OpsPanel title="Regime Performance">
        {perfRows.length === 0 ? (
          <p className="text-[12px] text-[var(--fg-subtle)]">
            Historical win rate / PF / expectancy appear when closed trades can
            be soft-joined to regime labels.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-left text-[12px]">
              <thead>
                <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                  <th className="px-2 py-2 font-medium">Regime</th>
                  <th className="px-2 py-2 font-medium">Samples</th>
                  <th className="px-2 py-2 font-medium">Win Rate</th>
                  <th className="px-2 py-2 font-medium">Profit Factor</th>
                  <th className="px-2 py-2 font-medium">Expectancy</th>
                </tr>
              </thead>
              <tbody>
                {perfRows.map((row) => (
                  <tr
                    key={str(row.regime)}
                    className="border-b border-[var(--border)]/60 font-mono tabular-nums"
                  >
                    <td className="px-2 py-1.5">{str(row.regime)}</td>
                    <td className="px-2 py-1.5">{str(row.sample_size, "—")}</td>
                    <td className="px-2 py-1.5">
                      {row.win_rate_pct != null
                        ? `${num(row.win_rate_pct)}%`
                        : "—"}
                    </td>
                    <td className="px-2 py-1.5">
                      {row.profit_factor != null
                        ? String(num(row.profit_factor))
                        : "—"}
                    </td>
                    <td className="px-2 py-1.5">
                      {str(row.expectancy_display, "—")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </OpsPanel>

      <OpsPanel title="Regime History">
        {history.length === 0 ? (
          <DeskEmpty
            icon={Layers3}
            title="No evaluations yet"
            description="Each live evaluation appends a primary/secondary regime label."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-left text-[12px]">
              <thead>
                <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                  <th className="px-2 py-2 font-medium">Time</th>
                  <th className="px-2 py-2 font-medium">Primary</th>
                  <th className="px-2 py-2 font-medium">Secondary</th>
                  <th className="px-2 py-2 font-medium">Confidence</th>
                  <th className="px-2 py-2 font-medium">MTF</th>
                  <th className="px-2 py-2 font-medium">ATR%</th>
                  <th className="px-2 py-2 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {history.map((row, i) => (
                  <tr
                    key={`${str(row.signal_id, String(i))}-${str(row.recorded_at)}`}
                    className="border-b border-[var(--border)]/60 font-mono tabular-nums"
                  >
                    <td className="px-2 py-1.5 text-[var(--fg-subtle)]">
                      {str(row.recorded_at)}
                    </td>
                    <td className="px-2 py-1.5 text-[var(--fg)]">
                      {str(row.primary)}
                    </td>
                    <td className="px-2 py-1.5 text-[var(--fg-muted)]">
                      {str(row.secondary, "—")}
                    </td>
                    <td className="px-2 py-1.5">{str(row.confidence)}%</td>
                    <td className="px-2 py-1.5">{str(row.mtf_score, "—")}</td>
                    <td className="px-2 py-1.5">{str(row.atr_pct, "—")}</td>
                    <td className="px-2 py-1.5 text-[var(--fg-muted)]">
                      {str(row.decision_action)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </OpsPanel>

      <p
        className={cn(
          "text-[11px] text-[var(--fg-subtle)]",
        )}
      >
        Observational only — uses existing MTF / ATR% / structure / news / spread
        artefacts. ADX and raw range width are proxied when not present. Does not
        change strategy behaviour or trade decisions.
      </p>
    </div>
  );
}

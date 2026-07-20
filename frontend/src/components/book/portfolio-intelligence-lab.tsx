"use client";

import { memo, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Layers3 } from "lucide-react";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { portfolioIntelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn, formatNumber } from "@/lib/utils";

const NA = "Not available";

function MetricCell({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="min-w-0 rounded-md border border-[var(--border)] bg-[var(--bg-panel)] px-2.5 py-2">
      <p className="truncate text-[9px] font-medium uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p
        className={cn(
          "mt-0.5 truncate font-mono text-sm tabular-nums text-[var(--fg)]",
          value === NA && "text-[var(--fg-subtle)]",
        )}
      >
        {value}
      </p>
      {hint ? (
        <p className="mt-0.5 truncate text-[9px] text-[var(--fg-subtle)]">{hint}</p>
      ) : null}
    </div>
  );
}

/**
 * Portfolio Intelligence Lab — VaR / ES / correlation / stress from live APIs only.
 * Never invents risk figures when the backend marks them unavailable.
 */
export const PortfolioIntelligenceLab = memo(function PortfolioIntelligenceLab({
  className,
}: {
  className?: string;
}) {
  const session = useTradingSession();
  const enabled = session.connected;

  const dashQ = useQuery({
    queryKey: ["book-pi-dashboard"],
    queryFn: () => portfolioIntelligenceApi.dashboard(0.95),
    enabled,
    staleTime: 30_000,
    retry: false,
  });

  const riskQ = useQuery({
    queryKey: ["book-pi-risk"],
    queryFn: () => portfolioIntelligenceApi.risk(),
    enabled,
    staleTime: 30_000,
    retry: false,
  });

  const corrQ = useQuery({
    queryKey: ["book-pi-correlation"],
    queryFn: () => portfolioIntelligenceApi.correlation(),
    enabled,
    staleTime: 30_000,
    retry: false,
  });

  const stressQ = useQuery({
    queryKey: ["book-pi-stress"],
    queryFn: () => portfolioIntelligenceApi.stress(),
    enabled,
    staleTime: 30_000,
    retry: false,
  });

  const loading =
    dashQ.isLoading || riskQ.isLoading || corrQ.isLoading || stressQ.isLoading;
  const hardError =
    dashQ.isError && riskQ.isError && corrQ.isError && stressQ.isError;

  const { varValue, esValue, varHint, esHint } = useMemo(() => {
    const fromRisk = asRecord(riskQ.data);
    const fromDash = asRecord(asRecord(dashQ.data).risk);
    const metrics = asRecord(
      Object.keys(asRecord(fromRisk.metrics)).length
        ? fromRisk.metrics
        : fromDash.metrics,
    );
    const varStatus = str(metrics.portfolio_var_status);
    const esStatus = str(metrics.expected_shortfall_status);
    const varRaw = num(metrics.portfolio_var, NaN);
    const esRaw = num(metrics.expected_shortfall, NaN);
    return {
      varValue:
        varStatus === "unavailable" || !Number.isFinite(varRaw)
          ? NA
          : formatNumber(varRaw, 2),
      esValue:
        esStatus === "unavailable" || !Number.isFinite(esRaw)
          ? NA
          : formatNumber(esRaw, 2),
      varHint: str(metrics.portfolio_var_reason) || undefined,
      esHint: str(metrics.expected_shortfall_reason) || undefined,
    };
  }, [riskQ.data, dashQ.data]);

  const corr = useMemo(() => {
    const fromCorr = asRecord(corrQ.data);
    const fromDash = asRecord(asRecord(dashQ.data).correlation);
    const src =
      Object.keys(fromCorr).length > 0 ? fromCorr : fromDash;
    const labels = asList(src.labels).map(String);
    const matrix = asList(src.matrix) as unknown[][];
    const status = str(src.status);
    const scoreRaw = num(src.diversification_score, NaN);
    const score = Number.isFinite(scoreRaw) ? scoreRaw : null;
    const reason = str(src.reason);
    return { labels, matrix, status, score, reason };
  }, [corrQ.data, dashQ.data]);

  const scenarios = useMemo(() => {
    const fromStress = asRecord(stressQ.data);
    const fromDash = asRecord(asRecord(dashQ.data).stress);
    const src =
      Object.keys(fromStress).length > 0 ? fromStress : fromDash;
    return asList(src.scenarios).map(asRecord);
  }, [stressQ.data, dashQ.data]);

  if (!session.connected) {
    return null;
  }

  return (
    <section
      className={cn(
        "rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        className,
      )}
      aria-label="Portfolio Intelligence Lab"
    >
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Portfolio Intelligence
          </p>
          <p className="mt-0.5 text-[11px] text-[var(--fg-muted)]">
            VaR · Expected Shortfall · correlation · stress — live APIs only
          </p>
        </div>
      </div>

      {loading ? (
        <DeskSkeleton rows={4} />
      ) : hardError ? (
        <DeskError
          message="Portfolio intelligence unavailable."
          onRetry={() => {
            void dashQ.refetch();
            void riskQ.refetch();
            void corrQ.refetch();
            void stressQ.refetch();
          }}
        />
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            <MetricCell label="VaR 95%" value={varValue} hint={varHint} />
            <MetricCell label="Expected Shortfall" value={esValue} hint={esHint} />
            <MetricCell
              label="Diversification"
              value={
                corr.score == null ? NA : formatNumber(corr.score, 3)
              }
              hint={
                corr.status === "available"
                  ? "From correlation API"
                  : corr.reason || undefined
              }
            />
            <MetricCell
              label="Corr. status"
              value={corr.status || NA}
              hint={
                corr.labels.length
                  ? `${corr.labels.length} symbols`
                  : undefined
              }
            />
          </div>

          <div>
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Correlation matrix
            </p>
            {corr.status !== "available" || corr.labels.length === 0 ? (
              <p className="text-[11px] text-[var(--fg-muted)]">
                {corr.reason || NA}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[16rem] border-collapse text-left text-[10px]">
                  <thead>
                    <tr>
                      <th className="px-1.5 py-1 font-medium text-[var(--fg-subtle)]" />
                      {corr.labels.map((l) => (
                        <th
                          key={`h-${l}`}
                          className="whitespace-nowrap px-1.5 py-1 font-medium text-[var(--fg-subtle)]"
                        >
                          {l}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {corr.labels.map((row, i) => (
                      <tr key={`r-${row}`} className="border-t border-[var(--border)]/60">
                        <td className="whitespace-nowrap px-1.5 py-1 text-[var(--fg-subtle)]">
                          {row}
                        </td>
                        {corr.labels.map((col, j) => {
                          const cell = corr.matrix[i]?.[j];
                          const v =
                            typeof cell === "number"
                              ? cell
                              : cell == null
                                ? null
                                : Number(cell);
                          return (
                            <td
                              key={`${row}-${col}`}
                              className="px-1.5 py-1 font-mono tabular-nums text-[var(--fg)]"
                            >
                              {v == null || Number.isNaN(v)
                                ? NA
                                : formatNumber(v, 2)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
              Diversification note:{" "}
              {corr.score == null
                ? NA
                : corr.score >= 0.7
                  ? "Higher score suggests less concentrated pairwise correlation in the sample."
                  : corr.score >= 0.4
                    ? "Moderate diversification in the observed correlation sample."
                    : "Lower score — positions may move together; review concentration."}
            </p>
          </div>

          <div>
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Stress scenarios
            </p>
            {scenarios.length === 0 ? (
              <DeskEmpty
                icon={Layers3}
                title={NA}
                description="No stress scenarios returned by the portfolio intelligence API."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[28rem] border-collapse text-left text-[11px]">
                  <thead className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                    <tr>
                      <th className="px-2 py-1.5 font-medium">Scenario</th>
                      <th className="px-2 py-1.5 font-medium">Status</th>
                      <th className="px-2 py-1.5 font-medium">Impact</th>
                      <th className="px-2 py-1.5 font-medium">Assumption</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scenarios.map((s) => {
                      const name = str(s.name, "Scenario");
                      const status = str(s.status);
                      const available = status === "available";
                      const impact = available
                        ? formatNumber(num(s.impact_pnl, 0), 2)
                        : str(s.reason) || NA;
                      return (
                        <tr
                          key={name}
                          className="border-t border-[var(--border)]/70"
                        >
                          <td className="px-2 py-1.5 text-[var(--fg)]">{name}</td>
                          <td className="px-2 py-1.5 font-mono text-[var(--fg-muted)]">
                            {status || NA}
                          </td>
                          <td className="px-2 py-1.5 font-mono tabular-nums text-[var(--fg)]">
                            {impact}
                          </td>
                          <td className="px-2 py-1.5 text-[var(--fg-muted)]">
                            {str(s.assumption || s.reason) || NA}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
});

"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Radar, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { realMarketIntelligencePlatformApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

export function RealMarketIntelligencePlatformWorkspace() {
  const qc = useQueryClient();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const statusQ = useQuery({
    queryKey: ["rmip-status"],
    queryFn: () => realMarketIntelligencePlatformApi.status(),
    staleTime: 15_000,
  });

  const evaluateM = useMutation({
    mutationFn: () =>
      realMarketIntelligencePlatformApi.evaluate({
        clock_utc: new Date().toISOString(),
        session_hint: "london",
        regime: "trend",
        trend: "Bullish",
        confidence: "moderate",
        economic_events: [
          {
            name: "US CPI YoY",
            currency: "USD",
            importance: "high",
            scheduled_time: new Date().toISOString(),
            previous: "3.1%",
            forecast: "3.0%",
            actual: null,
          },
          {
            name: "FOMC Minutes",
            currency: "USD",
            importance: "critical",
            scheduled_time: new Date().toISOString(),
            previous: null,
            forecast: null,
            actual: null,
          },
        ],
        volatility_observations: {
          average_daily_range: 28.4,
          current_session_range: 12.1,
          atr: 6.2,
          spread_expansion: 0.18,
          price_acceleration: 0.4,
          atr_vs_average_ratio: 1.05,
          level: "normal",
        },
        liquidity_observations: {
          session_liquidity: "deep",
          daily_high: 2385.2,
          daily_low: 2369.8,
          weekly_high: 2392.0,
          weekly_low: 2355.5,
          liquidity_sweep: false,
          range_compression: false,
          expansion: true,
          liquidity_quality: "Excellent",
        },
        archive_event: { comments: "Operator context refresh" },
      }),
    onSuccess: async (data) => {
      setResult(data);
      const summary = asRecord(data.context_summary);
      toast.success(
        `RMIP · context ${str(summary.market_context, "—")}`,
      );
      await qc.invalidateQueries({ queryKey: ["rmip-status"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Evaluate failed"),
  });

  const caps = asRecord(statusQ.data?.capabilities);
  const summary = asRecord(asRecord(result).context_summary);
  const modules = asRecord(asRecord(result).modules);
  const feed = asRecord(modules.operator_intelligence_feed);
  const feedDetails = asRecord(feed.details);
  const explain = asRecord(modules.explainability);
  const explainDetails = asRecord(explain.details);
  const openRisks = asList(feedDetails.open_risks);
  const upcoming = asList(feedDetails.upcoming_events);

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "RMIP unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <Radar className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">
          {TRADING_SYMBOL} Real Market Intelligence Platform
        </span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Context only
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          Never trades
        </Badge>
        {caps.never_change_trading_rules === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            Rules locked
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "rmip")}
        </span>
        <Button
          size="sm"
          disabled={evaluateM.isPending}
          onClick={() => evaluateM.mutate()}
        >
          Refresh context
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Operator feed">
          {!result ? (
            <DeskEmpty
              icon={Radar}
              title="No context"
              description="Supply calendar · session · vol · liquidity feeds"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Market context</span>
                <span className="font-mono">
                  {str(feedDetails.market_context, str(summary.market_context))}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Session</span>
                <span className="font-mono">
                  {str(feedDetails.current_session, "—")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Volatility</span>
                <span className="font-mono">
                  {str(feedDetails.volatility, "—")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Liquidity</span>
                <span className="font-mono">
                  {str(feedDetails.liquidity, "—")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Regime</span>
                <span className="font-mono">
                  {str(feedDetails.current_regime, "—")}
                </span>
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                Audit {str(result.audit_id, "—")}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Upcoming events / open risks">
          {!result ? (
            <DeskEmpty
              icon={Shield}
              title="Await refresh"
              description="Never invents macro prints"
            />
          ) : (
            <div className="space-y-2 text-[10px]">
              <ul className="max-h-20 space-y-0.5 overflow-auto font-mono">
                {upcoming.length === 0 ? (
                  <li className="text-[var(--fg-subtle)]">No events</li>
                ) : (
                  upcoming.slice(0, 4).map((ev) => {
                    const row = asRecord(ev);
                    return (
                      <li key={str(row.name, "e")}>
                        {str(row.name)} · {str(row.importance)} ·{" "}
                        {str(row.currency)}
                      </li>
                    );
                  })
                )}
              </ul>
              <p className="text-[var(--fg-muted)]">Open risks</p>
              <ul className="max-h-16 space-y-0.5 overflow-auto font-mono">
                {openRisks.length === 0 ? (
                  <li className="text-[var(--fg-subtle)]">None flagged</li>
                ) : (
                  openRisks.slice(0, 4).map((r) => (
                    <li key={String(r)}>{String(r)}</li>
                  ))
                )}
              </ul>
            </div>
          )}
        </Panel>

        <Panel title="Explainability">
          {!result ? (
            <DeskEmpty
              icon={Radar}
              title="No score"
              description="Why · inputs · missing · confidence"
            />
          ) : (
            <div className="space-y-1 text-[10px] text-[var(--fg-muted)]">
              <p>{str(explainDetails.why, "—")}</p>
              <p className="font-mono">
                Confidence {str(explainDetails.confidence, "—")}%
              </p>
              <p className="font-mono text-[var(--fg-subtle)] line-clamp-3">
                Missing:{" "}
                {asList(explainDetails.missing_data)
                  .map(String)
                  .join(", ") || "none"}
              </p>
              <ul className="mt-2 space-y-1">
                <li>Never places trades</li>
                <li>Never changes trading rules</li>
                <li>Never fabricates missing prints</li>
              </ul>
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Modules">
        {!Object.keys(modules).length ? (
          <DeskEmpty
            icon={Radar}
            title="No modules"
            description="Calendar → Context API"
          />
        ) : (
          <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
            {Object.entries(modules).map(([key, val]) => {
              const row = asRecord(val);
              return (
                <li
                  key={key}
                  className={cn(
                    "border px-2 py-2",
                    row.status === "missing_data" ||
                      row.recommendation === "MISSING DATA"
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
    </div>
  );
}

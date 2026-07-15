"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Scale, RefreshCw, PauseCircle, Lightbulb } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { PageMotion, StaggerGrid, StaggerItem } from "@/components/desk/motion";
import { SessionStrip } from "@/components/broker/session-strip";
import { decisionEngineApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber, formatPct } from "@/lib/utils";

export default function DecisionEnginePage() {
  const qc = useQueryClient();
  const [symbol, setSymbol] = useState("EURUSD");
  const [focus, setFocus] = useState("EURUSD");

  const dashQ = useQuery({
    queryKey: ["decision-engine-dashboard", focus],
    queryFn: () => decisionEngineApi.dashboard(focus),
    retry: false,
    staleTime: 10_000,
    refetchInterval: 45_000,
  });

  const evaluate = useMutation({
    mutationFn: () =>
      decisionEngineApi.evaluate({
        symbol: focus,
        mode: "paper",
        force_refresh: true,
      }),
    onSuccess: async () => {
      toast.success("Decision re-evaluated (paper mode)");
      await qc.invalidateQueries({ queryKey: ["decision-engine-dashboard", focus] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Evaluate failed"),
  });

  const data = asRecord(dashQ.data);
  const decision = asRecord(data.decision);
  const analysis = asRecord(decision.analysis);
  const mtf = asRecord(decision.multi_timeframe);
  const score = asRecord(decision.score_detail);
  const risk = asRecord(decision.risk);
  const explanation = asRecord(decision.explanation);
  const liveGate = asRecord(decision.live_gate);
  const paper = asRecord(data.paper);
  const perf = asRecord(paper.performance);
  const reports = asRecord(data.reports);
  const recent = asList(paper.recent).map(asRecord);
  const frames = asRecord(mtf.frames);

  const isWait = str(decision.decision, "WAIT") === "WAIT";

  return (
    <div className="decision-engine-desk">
      <PageHeader
        title="Decision Engine"
        description="Institutional should-we-trade gate. Default is WAIT. Paper mode only — never bypasses EXECUTION_ENABLED and never submits orders."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Input
              className="h-8 w-28 font-mono text-xs"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              aria-label="Symbol"
            />
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setFocus(symbol.trim() || "EURUSD")}
            >
              Focus
            </Button>
            <Button size="sm" onClick={() => evaluate.mutate()} disabled={evaluate.isPending}>
              Re-evaluate
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => dashQ.refetch()}
              disabled={dashQ.isFetching}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${dashQ.isFetching ? "animate-spin" : ""}`} />
            </Button>
          </div>
        }
      />
      <SessionStrip className="mb-4" />

      {dashQ.isLoading ? (
        <DeskSkeleton rows={8} />
      ) : (
        <PageMotion className="space-y-5">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge tone="success">paper default</Badge>
            <Badge tone="neutral">advisory only</Badge>
            <Badge tone="neutral">never_submits_orders</Badge>
            <Badge tone={data.execution_enabled ? "danger" : "success"}>
              EXECUTION_ENABLED={String(Boolean(data.execution_enabled))}
            </Badge>
            <Badge tone="neutral">promises_profit=false</Badge>
            <span className="text-[var(--fg-subtle)]">v{str(data.version, "4.0")}</span>
          </div>

          {dashQ.isError && (
            <DeskError
              message="Decision Engine API unavailable — default stance remains WAIT. No fabricated decisions."
              onRetry={() => dashQ.refetch()}
            />
          )}

          {!dashQ.isError && str(decision.status) === "unavailable" && (
            <DeskError
              message={str(decision.reason, "Unable to evaluate — WAIT")}
              onRetry={() => dashQ.refetch()}
            />
          )}

          <motion.section
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="relative overflow-hidden rounded-xl border border-[var(--border)] bg-[linear-gradient(150deg,rgba(16,28,36,0.96),rgba(6,10,16,0.94))] p-5"
          >
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(80,160,140,0.1),transparent_50%)]" />
            <div className="relative flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                {isWait || dashQ.isError ? (
                  <PauseCircle className="h-8 w-8 text-[var(--warning)]" />
                ) : (
                  <Lightbulb className="h-8 w-8 text-[var(--success)]" />
                )}
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--fg-muted)]">
                    {str(decision.symbol, focus)} · {str(decision.mode, "paper")}
                  </p>
                  <h2 className="font-mono text-2xl tracking-wide text-[var(--fg)]">
                    {dashQ.isError ? "WAIT" : str(decision.decision, "WAIT")}
                  </h2>
                  <p className="text-sm text-[var(--fg-subtle)]">
                    {dashQ.isError
                      ? "Capital preservation first — no trade without live evaluation"
                      : str(explanation.summary, str(decision.reason, "Capital preservation first"))}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge tone={isWait || dashQ.isError ? "warning" : "success"}>
                  Score · {dashQ.isError ? "—" : formatNumber(num(decision.trade_score), 1)}
                </Badge>
                <Badge tone="neutral">
                  Confidence ·{" "}
                  {dashQ.isError ? "—" : `${formatNumber(num(decision.confidence_pct), 0)}%`}
                </Badge>
                <Badge tone="neutral">Risk · {str(decision.risk_level, "—")}</Badge>
              </div>
            </div>

            {!dashQ.isError && (
            <StaggerGrid className="relative mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <StaggerItem>
                <StatCard
                  label="Expected RR"
                  value={
                    decision.expected_rr == null
                      ? "—"
                      : formatNumber(num(decision.expected_rr), 2)
                  }
                />
              </StaggerItem>
              <StaggerItem>
                <StatCard
                  label="Recommended SL"
                  value={
                    decision.recommended_sl == null
                      ? "—"
                      : formatNumber(num(decision.recommended_sl), 5)
                  }
                  hint="Advisory"
                />
              </StaggerItem>
              <StaggerItem>
                <StatCard
                  label="Recommended TP"
                  value={
                    decision.recommended_tp == null
                      ? "—"
                      : formatNumber(num(decision.recommended_tp), 5)
                  }
                  hint="Advisory"
                />
              </StaggerItem>
              <StaggerItem>
                <StatCard
                  label="Lot size"
                  value={
                    decision.lot_size == null
                      ? "—"
                      : formatNumber(num(decision.lot_size), 2)
                  }
                  hint="Risk-capped"
                />
              </StaggerItem>
            </StaggerGrid>
            )}
          </motion.section>

          {!dashQ.isError && (
          <>
          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Scale className="h-4 w-4" /> Pre-trade analysis
                </CardTitle>
              </CardHeader>
              <CardContent>
                <DeskTable
                  columns={["Factor", "Value"]}
                  rows={[
                    ["Trend", str(analysis.trend)],
                    ["Structure", str(analysis.market_structure)],
                    ["Support", analysis.support == null ? "—" : formatNumber(num(analysis.support), 5)],
                    ["Resistance", analysis.resistance == null ? "—" : formatNumber(num(analysis.resistance), 5)],
                    ["Volatility", str(analysis.volatility)],
                    ["Spread", analysis.spread == null ? "—" : formatNumber(num(analysis.spread), 5)],
                    ["Session", str(analysis.session)],
                    ["News risk", str(analysis.news_risk)],
                    ["Correlation risk", str(analysis.correlation_risk)],
                    ["Portfolio heat", str(analysis.portfolio_exposure)],
                  ]}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Multi-timeframe</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Badge tone={mtf.aligned ? "success" : "warning"}>
                  {mtf.aligned ? "Aligned" : "Not aligned → WAIT"}
                </Badge>
                <p className="text-xs text-[var(--fg-subtle)]">{str(mtf.why)}</p>
                <DeskTable
                  columns={["TF", "Trend", "Mom", "Conf"]}
                  rows={["M5", "M15", "H1", "H4", "D1"].map((tf) => {
                    const f = asRecord(frames[tf]);
                    return [
                      tf,
                      str(f.trend, "—"),
                      str(f.momentum, "—"),
                      f.confidence_pct == null
                        ? "—"
                        : `${formatNumber(num(f.confidence_pct), 0)}%`,
                    ];
                  })}
                />
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {(
              [
                ["Why it exists", explanation.why_it_exists],
                ["Why it may fail", explanation.why_it_may_fail],
                ["What invalidates it", explanation.what_invalidates_it],
                ["What would improve it", explanation.what_would_improve_it],
              ] as const
            ).map(([title, items]) => (
              <Card key={title}>
                <CardHeader>
                  <CardTitle className="text-sm">{title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="list-disc space-y-1 pl-4 text-xs text-[var(--fg-muted)]">
                    {asList(items).map(String).map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                    {!asList(items).length && <li>—</li>}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Risk gates</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <Badge tone={risk.accepted ? "success" : "danger"}>
                  {risk.accepted ? "Risk accepted" : "Risk rejected → WAIT"}
                </Badge>
                <ul className="list-disc space-y-1 pl-4 text-xs text-[var(--fg-muted)]">
                  {asList(risk.rejects).map(String).map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                  {asList(risk.warnings).map(String).map((r) => (
                    <li key={r}>⚠ {r}</li>
                  ))}
                  {!asList(risk.rejects).length && !asList(risk.warnings).length && (
                    <li>No risk rejects</li>
                  )}
                </ul>
                <p className="text-[11px] text-[var(--fg-subtle)]">
                  Score thresholds: ≥{formatNumber(num(asRecord(score.thresholds).min_score), 0)} score, ≥
                  {formatNumber(num(asRecord(score.thresholds).min_confidence_pct), 0)}% confidence
                </p>
                <p className="text-[11px] text-[var(--fg-subtle)]">
                  Live gate: {str(liveGate.reason)}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Paper performance</CardTitle>
              </CardHeader>
              <CardContent>
                {str(perf.status) === "available" ? (
                  <div className="grid gap-2 sm:grid-cols-2">
                    <StatCard
                      label="Win rate"
                      value={perf.win_rate == null ? "—" : formatPct(num(perf.win_rate, 0))}
                    />
                    <StatCard
                      label="Profit factor"
                      value={
                        perf.profit_factor == null
                          ? "—"
                          : formatNumber(num(perf.profit_factor), 2)
                      }
                    />
                    <StatCard
                      label="Sharpe"
                      value={
                        perf.sharpe_ratio == null
                          ? "—"
                          : formatNumber(num(perf.sharpe_ratio), 2)
                      }
                    />
                    <StatCard
                      label="Drawdown"
                      value={
                        perf.drawdown == null ? "—" : formatNumber(num(perf.drawdown), 2)
                      }
                    />
                    <StatCard
                      label="Expectancy"
                      value={
                        perf.expectancy == null
                          ? "—"
                          : formatNumber(num(perf.expectancy), 2)
                      }
                    />
                    <StatCard
                      label="Max consec. losses"
                      value={str(perf.max_consecutive_losses, "0")}
                    />
                  </div>
                ) : (
                  <DeskEmpty
                    icon={Scale}
                    title="Paper stats waiting"
                    description={str(perf.reason, "Record TRADE_IDEA outcomes to build edge metrics")}
                  />
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Reports — daily / weekly / monthly</CardTitle>
            </CardHeader>
            <CardContent>
              <DeskTable
                columns={["Period", "Signals", "Ideas", "Waits", "Wait ratio", "Avg score"]}
                rows={["daily", "weekly", "monthly"].map((k) => {
                  const r = asRecord(reports[k]);
                  return [
                    str(r.period, k),
                    str(r.signals, "0"),
                    str(r.trade_ideas, "0"),
                    str(r.waits, "0"),
                    r.wait_ratio == null ? "—" : formatPct(num(r.wait_ratio, 0)),
                    r.avg_score == null ? "—" : formatNumber(num(r.avg_score), 1),
                  ];
                })}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Recent paper decisions</CardTitle>
            </CardHeader>
            <CardContent>
              {recent.length ? (
                <DeskTable
                  columns={["Time", "Symbol", "Decision", "Score", "Conf"]}
                  rows={recent.slice(0, 20).map((r) => [
                    str(r.created_at).slice(0, 19),
                    str(r.symbol),
                    str(r.decision),
                    formatNumber(num(r.trade_score), 1),
                    `${formatNumber(num(r.confidence_pct), 0)}%`,
                  ])}
                />
              ) : (
                <p className="text-xs text-[var(--fg-subtle)]">No decisions recorded yet</p>
              )}
            </CardContent>
          </Card>
          </>
          )}
        </PageMotion>
      )}
    </div>
  );
}

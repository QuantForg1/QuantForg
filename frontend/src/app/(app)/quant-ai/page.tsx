"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Brain, Layers3, RefreshCw, ShieldAlert } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { PageMotion, StaggerGrid, StaggerItem } from "@/components/desk/motion";
import { SessionStrip } from "@/components/broker/session-strip";
import { quantAiApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber, formatPct } from "@/lib/utils";
import { TRADING_SYMBOL, resolveTradingSymbol } from "@/lib/trading/gold-only";

const MODULES = [
  "Market Overview",
  "Trend Analysis",
  "Momentum Analysis",
  "Volatility Analysis",
  "Support",
  "Resistance",
  "Liquidity Zones",
  "Session Analysis",
  "Multi-Timeframe Analysis",
  "Market Regime",
  "Correlation",
  "Execution Quality",
  "Portfolio Health",
  "Risk Health",
  "Trade Journal Intelligence",
] as const;

export default function QuantAiPage() {
  const [symbol, setSymbol] = useState(TRADING_SYMBOL);
  const [focus, setFocus] = useState(TRADING_SYMBOL);

  const dashQ = useQuery({
    queryKey: ["quant-ai-dashboard", focus],
    queryFn: () => quantAiApi.dashboard(focus),
    retry: false,
    refetchInterval: 45_000,
    staleTime: 12_000,
  });

  const data = asRecord(dashQ.data);
  const assistant = asRecord(data.assistant);
  const modules = asRecord(data.modules);
  const widgets = asRecord(data.widgets);
  const broker = asRecord(data.broker);
  const session = asRecord(data.session_analysis);
  const mtf = asRecord(data.multi_timeframe);
  const portfolio = asRecord(modules.portfolio_health);
  const risk = asRecord(modules.risk_health);
  const execution = asRecord(modules.execution_quality);
  const journal = asRecord(modules.trade_journal_intelligence);
  const corr = asRecord(modules.correlation);
  const why = asRecord(assistant.why);
  const reasons = asList(
    (assistant.reasons as unknown) ?? why.supporting_factors,
  ).map(String);
  const topMovers = asList(widgets.top_movers).map(asRecord);
  const strongTrends = asList(widgets.strong_trends).map(asRecord);
  const weakTrends = asList(widgets.weak_trends).map(asRecord);
  const highVol = asList(widgets.high_volatility).map(asRecord);
  const spreads = asList(widgets.spread_monitor).map(asRecord);
  const heatmap = asList(widgets.heatmap).map(asRecord);
  const events = asList(data.economic_events).map(asRecord);
  const reviews = asList(journal.reviews).map(asRecord);
  const riskFlags = asList(risk.flags).map(asRecord);
  const portMetrics = asRecord(portfolio.metrics);
  const execMetrics = asRecord(execution.metrics);
  const mtfFrames = asRecord(mtf.frames);
  const corrLabels = asList(corr.labels).map(String);
  const corrMatrix = asList(corr.matrix) as unknown[][];

  const confidencePct = num(assistant.confidence_pct, NaN);
  const confidenceLabel = Number.isFinite(confidencePct)
    ? `${formatNumber(confidencePct, 0)}%`
    : "—";

  return (
    <div className="quant-ai-desk">
      <PageHeader
        title="Quant AI"
        description="Institutional trading intelligence — explains WHY from live MT5, portfolio, risk, and execution facts. Never submits trades."
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
              onClick={() => setFocus(resolveTradingSymbol(symbol.trim()))}
            >
              Analyze
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => dashQ.refetch()}
              disabled={dashQ.isFetching}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${dashQ.isFetching ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        }
      />
      <SessionStrip className="mb-4" />

      {dashQ.isLoading ? (
        <DeskSkeleton rows={8} />
      ) : dashQ.isError ? (
        <DeskError
          message="Quant AI unavailable. Connect MT5 / authenticate, then retry. No fabricated insights."
          onRetry={() => dashQ.refetch()}
        />
      ) : (
        <PageMotion className="space-y-5">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge tone="success">advisory only</Badge>
            <Badge tone="neutral">autonomous={String(Boolean(data.autonomous_trading))}</Badge>
            <Badge tone={data.execution_enabled ? "danger" : "success"}>
              EXECUTION_ENABLED={String(Boolean(data.execution_enabled))}
            </Badge>
            <Badge tone="neutral">never_submits_orders</Badge>
            <span className="text-[var(--fg-subtle)]">
              {str(broker.status, "broker")} · {str(data.status)}
            </span>
          </div>

          {/* Assistant — WHY first */}
          <motion.section
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
            className="relative overflow-hidden rounded-xl border border-[var(--border)] bg-[linear-gradient(145deg,rgba(18,28,42,0.95),rgba(8,12,20,0.92))] p-5 shadow-[0_0_0_1px_rgba(120,160,200,0.06)]"
          >
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(70,140,200,0.12),transparent_55%)]" />
            <div className="relative flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                <Brain className="h-5 w-5 text-[var(--accent)]" />
                <div>
                  <h2 className="font-mono text-lg tracking-wide text-[var(--fg)]">
                    {str(assistant.symbol, focus)}
                  </h2>
                  <p className="text-xs text-[var(--fg-subtle)]">
                    {str(why.summary, str(assistant.reason, "Structural brief"))}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge tone={assistant.trend === "Bullish" ? "success" : assistant.trend === "Bearish" ? "danger" : "neutral"}>
                  Trend · {str(assistant.trend, "—")}
                </Badge>
                <Badge tone="neutral">Confidence · {confidenceLabel}</Badge>
                <Badge tone="neutral">Risk · {str(assistant.risk, "—")}</Badge>
              </div>
            </div>
            <div className="relative mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Momentum" value={str(assistant.momentum, "—")} />
              <StatCard label="Volatility" value={str(assistant.volatility, "—")} />
              <StatCard
                label="Suggested Stop"
                value={
                  assistant.suggested_stop == null
                    ? "—"
                    : formatNumber(num(assistant.suggested_stop), 5)
                }
                hint="Advisory only"
              />
              <StatCard
                label="Suggested TP"
                value={
                  assistant.suggested_tp == null
                    ? "—"
                    : formatNumber(num(assistant.suggested_tp), 5)
                }
                hint="Advisory only"
              />
            </div>
            <div className="relative mt-4">
              <p className="mb-2 text-[11px] uppercase tracking-[0.14em] text-[var(--fg-muted)]">
                Why
              </p>
              {reasons.length ? (
                <ul className="grid gap-1.5 sm:grid-cols-2">
                  {reasons.map((r) => (
                    <li
                      key={r}
                      className="rounded-md border border-[var(--border)]/60 bg-[var(--surface)]/40 px-3 py-2 text-sm text-[var(--fg-muted)]"
                    >
                      {r}
                    </li>
                  ))}
                </ul>
              ) : (
                <DeskEmpty
                  icon={Brain}
                  title="No reasons yet"
                  description="Insufficient real OHLC for structural WHY."
                />
              )}
            </div>
          </motion.section>

          <StaggerGrid className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StaggerItem>
              <StatCard label="Session" value={str(session.session, "—")} hint={str(session.liquidity)} />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Win rate"
                value={
                  portMetrics.win_rate == null
                    ? "n/a"
                    : formatPct(num(portMetrics.win_rate, 0))
                }
                hint={str(portfolio.status)}
              />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Execution score"
                value={
                  execution.execution_score == null
                    ? "n/a"
                    : formatNumber(num(execution.execution_score), 2)
                }
                hint={str(execution.execution_quality)}
              />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Risk health"
                value={str(risk.overall, "—")}
                hint={`${riskFlags.length} flags`}
              />
            </StaggerItem>
          </StaggerGrid>

          {/* Module strip */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Intelligence modules</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-1.5">
              {MODULES.map((m) => (
                <span
                  key={m}
                  className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1 text-[10px] uppercase tracking-wide text-[var(--fg-muted)]"
                >
                  {m}
                </span>
              ))}
            </CardContent>
          </Card>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Market dashboard</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {topMovers.length ? (
                  <DeskTable
                    columns={["Symbol", "Move %", "Trend", "Vol"]}
                    rows={topMovers.map((r) => [
                      str(r.symbol),
                      formatNumber(num(r.move_pct), 3),
                      str(r.trend),
                      str(r.volatility),
                    ])}
                  />
                ) : (
                  <p className="text-xs text-[var(--fg-subtle)]">No movers from live OHLC</p>
                )}
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <p className="mb-1 text-[11px] uppercase text-[var(--fg-muted)]">Strong trends</p>
                    {strongTrends.length ? (
                      <ul className="space-y-1 text-sm">
                        {strongTrends.map((r) => (
                          <li key={str(r.symbol)}>
                            {str(r.symbol)} · {str(r.trend)} · {formatNumber(num(r.confidence_pct), 0)}%
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-xs text-[var(--fg-subtle)]">None at ≥70% confidence</p>
                    )}
                  </div>
                  <div>
                    <p className="mb-1 text-[11px] uppercase text-[var(--fg-muted)]">Weak / neutral</p>
                    {weakTrends.length ? (
                      <ul className="space-y-1 text-sm">
                        {weakTrends.slice(0, 6).map((r) => (
                          <li key={str(r.symbol)}>
                            {str(r.symbol)} · {str(r.trend)}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-xs text-[var(--fg-subtle)]">—</p>
                    )}
                  </div>
                </div>
                <div>
                  <p className="mb-1 text-[11px] uppercase text-[var(--fg-muted)]">High volatility</p>
                  <p className="text-sm text-[var(--fg-muted)]">
                    {highVol.length
                      ? highVol.map((r) => str(r.symbol)).join(" · ")
                      : "None flagged from sample"}
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Spread · Heatmap · Events</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {spreads.length ? (
                  <DeskTable
                    columns={["Symbol", "Bid", "Ask", "Spread"]}
                    rows={spreads.map((r) => [
                      str(r.symbol),
                      formatNumber(num(r.bid), 5),
                      formatNumber(num(r.ask), 5),
                      formatNumber(num(r.spread), 5),
                    ])}
                  />
                ) : (
                  <p className="text-xs text-[var(--fg-subtle)]">No live quotes</p>
                )}
                <div className="flex flex-wrap gap-1.5">
                  {heatmap.map((h) => (
                    <span
                      key={str(h.symbol)}
                      className="rounded px-2 py-1 font-mono text-[10px]"
                      style={{
                        background:
                          h.trend === "Bullish"
                            ? "color-mix(in oklab, var(--success) 35%, transparent)"
                            : h.trend === "Bearish"
                              ? "color-mix(in oklab, var(--danger) 35%, transparent)"
                              : "var(--surface-2)",
                      }}
                    >
                      {str(h.symbol)} {formatNumber(num(h.confidence_pct), 0)}%
                    </span>
                  ))}
                </div>
                <div>
                  <p className="mb-1 text-[11px] uppercase text-[var(--fg-muted)]">Economic events</p>
                  {events.length ? (
                    <ul className="space-y-1 text-sm">
                      {events.slice(0, 6).map((e) => (
                        <li key={str(e.id || e.title)}>
                          [{str(e.impact, "n/a")}] {str(e.title)}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-[var(--fg-subtle)]">
                      No configured calendar feed — events are not invented.
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Multi-timeframe</CardTitle>
              </CardHeader>
              <CardContent>
                {str(mtf.status) === "available" ? (
                  <div className="space-y-2">
                    <Badge tone={mtf.aligned ? "success" : "warning"}>
                      {mtf.aligned ? "Aligned" : "Divergent"}
                    </Badge>
                    <DeskTable
                      columns={["TF", "Trend", "Mom", "Conf"]}
                      rows={Object.keys(mtfFrames).map((tf) => {
                        const f = asRecord(mtfFrames[tf]);
                        return [
                          tf,
                          str(f.trend),
                          str(f.momentum),
                          `${formatNumber(num(f.confidence_pct), 0)}%`,
                        ];
                      })}
                    />
                    <p className="text-xs text-[var(--fg-subtle)]">
                      {str(asRecord(mtf.why).summary)}
                    </p>
                  </div>
                ) : (
                  <DeskEmpty
                    icon={Layers3}
                    title="MTF unavailable"
                    description={str(mtf.reason)}
                  />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Portfolio AI</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {str(portfolio.status) === "available" ? (
                  <>
                    <div className="grid grid-cols-2 gap-2">
                      <StatCard
                        label="Profit factor"
                        value={
                          portMetrics.profit_factor == null
                            ? "—"
                            : formatNumber(num(portMetrics.profit_factor), 2)
                        }
                      />
                      <StatCard
                        label="Expectancy"
                        value={
                          portMetrics.expectancy == null
                            ? "—"
                            : formatNumber(num(portMetrics.expectancy), 2)
                        }
                      />
                      <StatCard
                        label="Avg RR"
                        value={
                          portMetrics.average_rr == null
                            ? "—"
                            : formatNumber(num(portMetrics.average_rr), 2)
                        }
                      />
                      <StatCard
                        label="Drawdown"
                        value={
                          portMetrics.drawdown == null
                            ? "—"
                            : formatNumber(num(portMetrics.drawdown), 2)
                        }
                      />
                    </div>
                    <p className="text-xs text-[var(--fg-subtle)]">
                      {str(asRecord(portfolio.why).summary)}
                    </p>
                    <ul className="list-disc space-y-1 pl-4 text-xs text-[var(--fg-muted)]">
                      {asList(portfolio.most_common_mistakes)
                        .map(String)
                        .map((m) => (
                          <li key={m}>{m}</li>
                        ))}
                    </ul>
                  </>
                ) : (
                  <DeskEmpty
                    icon={Layers3}
                    title="Portfolio AI waiting"
                    description={str(portfolio.reason, "No closed trades / deals yet")}
                  />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <ShieldAlert className="h-4 w-4" /> Risk AI
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {riskFlags.length ? (
                  <ul className="space-y-2">
                    {riskFlags.map((f) => (
                      <li
                        key={str(f.code) + str(f.detail)}
                        className="rounded border border-[var(--border)] px-3 py-2 text-sm"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span>{str(f.title)}</span>
                          <Badge
                            tone={
                              f.severity === "high"
                                ? "danger"
                                : f.severity === "moderate"
                                  ? "warning"
                                  : "neutral"
                            }
                          >
                            {str(f.severity)}
                          </Badge>
                        </div>
                        <p className="text-xs text-[var(--fg-subtle)]">{str(f.detail)}</p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-[var(--fg-muted)]">
                    {str(asRecord(risk.why).summary, "No elevated flags")}
                  </p>
                )}
                <p className="text-[10px] text-[var(--fg-subtle)]">
                  News risk: {str(asRecord(risk.news_risk).status)} —{" "}
                  {str(asRecord(risk.news_risk).reason)}
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Execution AI</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="mb-3 grid gap-2 sm:grid-cols-3">
                  <StatCard
                    label="Avg slippage"
                    value={
                      execMetrics.average_slippage == null
                        ? "n/a"
                        : formatNumber(num(execMetrics.average_slippage), 5)
                    }
                  />
                  <StatCard
                    label="Latency"
                    value={
                      execMetrics.broker_latency_ms == null &&
                      execMetrics.order_latency_ms_avg == null
                        ? "n/a"
                        : `${formatNumber(
                            num(
                              execMetrics.broker_latency_ms ??
                                execMetrics.order_latency_ms_avg,
                            ),
                            0,
                          )} ms`
                    }
                  />
                  <StatCard
                    label="Fill quality"
                    value={str(execMetrics.fill_quality || execution.execution_quality, "—")}
                  />
                </div>
                <ul className="space-y-1 text-xs text-[var(--fg-muted)]">
                  {asList(asRecord(execution.why).supporting_factors)
                    .map(String)
                    .map((r) => (
                      <li key={r}>• {r}</li>
                    ))}
                </ul>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Trade journal intelligence</CardTitle>
              </CardHeader>
              <CardContent>
                {reviews.length ? (
                  <DeskTable
                    columns={["Symbol", "Labels", "PnL"]}
                    rows={reviews.slice(0, 12).map((r) => [
                      str(r.symbol),
                      asList(r.labels).map(String).join(", "),
                      formatNumber(num(r.pnl), 2),
                    ])}
                  />
                ) : (
                  <p className="text-xs text-[var(--fg-subtle)]">No trade reviews — history empty</p>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Correlation</CardTitle>
            </CardHeader>
            <CardContent>
              {str(corr.status) === "available" && corrLabels.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[480px] border-collapse text-xs">
                    <thead>
                      <tr>
                        <th className="p-1 text-left text-[var(--fg-muted)]" />
                        {corrLabels.map((l) => (
                          <th key={l} className="p-1 font-mono text-[var(--fg-muted)]">
                            {l}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {corrLabels.map((row, i) => (
                        <tr key={row}>
                          <td className="p-1 font-mono text-[var(--fg-muted)]">{row}</td>
                          {asList(corrMatrix[i]).map((cell, j) => {
                            const v = typeof cell === "number" ? cell : null;
                            return (
                              <td
                                key={`${row}-${corrLabels[j]}`}
                                className="p-1 text-center font-mono"
                                style={{
                                  background:
                                    v == null
                                      ? "transparent"
                                      : v >= 0
                                        ? `color-mix(in oklab, var(--warning) ${Math.round(Math.abs(v) * 55)}%, transparent)`
                                        : `color-mix(in oklab, var(--accent) ${Math.round(Math.abs(v) * 55)}%, transparent)`,
                                }}
                              >
                                {v == null ? "—" : formatNumber(v, 2)}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <DeskEmpty
                  icon={Layers3}
                  title="Correlation unavailable"
                  description={str(corr.reason, "Need multiple symbols with real OHLC")}
                />
              )}
            </CardContent>
          </Card>
        </PageMotion>
      )}
    </div>
  );
}

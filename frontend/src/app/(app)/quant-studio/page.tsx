"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import {
  Boxes,
  FlaskConical,
  GitBranch,
  Dices,
  Brain,
  Sparkles,
  Store,
  ChartLine,
  Briefcase,
  Radio,
  Plus,
  Trash2,
  Play,
  RefreshCw,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { PageMotion } from "@/components/desk/motion";
import { SessionStrip } from "@/components/broker/session-strip";
import { LazyEquityChart } from "@/components/charts/lazy";
import { quantStudioApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, mapEquityCurve, num, str } from "@/lib/desk";
import { formatNumber, formatPct } from "@/lib/utils";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";

type ModuleId =
  | "builder"
  | "backtest"
  | "walkforward"
  | "montecarlo"
  | "review"
  | "optimizer"
  | "marketplace"
  | "analytics"
  | "portfolio"
  | "monitor";

const MODULES: { id: ModuleId; label: string; icon: typeof Boxes }[] = [
  { id: "builder", label: "Visual Builder", icon: Boxes },
  { id: "backtest", label: "Backtest Studio", icon: FlaskConical },
  { id: "walkforward", label: "Walk Forward", icon: GitBranch },
  { id: "montecarlo", label: "Monte Carlo", icon: Dices },
  { id: "review", label: "AI Review", icon: Brain },
  { id: "optimizer", label: "AI Optimizer", icon: Sparkles },
  { id: "marketplace", label: "Marketplace", icon: Store },
  { id: "analytics", label: "Analytics", icon: ChartLine },
  { id: "portfolio", label: "Portfolio Lab", icon: Briefcase },
  { id: "monitor", label: "Live Monitor", icon: Radio },
];

type StudioNode = { id: string; type: string; label: string; params: Record<string, string> };

export default function QuantStudioPage() {
  const qc = useQueryClient();
  const [module, setModule] = useState<ModuleId>("builder");
  const [symbol, setSymbol] = useState(TRADING_SYMBOL);
  const [timeframe, setTimeframe] = useState("H1");
  const [nodes, setNodes] = useState<StudioNode[]>([
    { id: "n1", type: "indicator", label: "EMA 20", params: { name: "ema", period: "20" } },
    { id: "n2", type: "session", label: "London", params: { session: "London" } },
    { id: "n3", type: "exit", label: "Exit", params: { sl_distance: "0.0020", tp_distance: "0.0040" } },
    { id: "n4", type: "execution", label: "Execution", params: { side: "buy" } },
  ]);
  const [strategyName, setStrategyName] = useState("Studio Strategy");
  const [lastRun, setLastRun] = useState<Record<string, unknown> | null>(null);
  const [wfRun, setWfRun] = useState<Record<string, unknown> | null>(null);

  const wsQ = useQuery({
    queryKey: ["quant-studio-workspace"],
    queryFn: quantStudioApi.workspace,
    retry: false,
    staleTime: 15_000,
    refetchInterval: 60_000,
  });

  const marketQ = useQuery({
    queryKey: ["quant-studio-marketplace"],
    queryFn: quantStudioApi.marketplace,
    retry: false,
    staleTime: 10_000,
  });

  const portfolioQ = useQuery({
    queryKey: ["quant-studio-portfolio-lab"],
    queryFn: quantStudioApi.portfolioLab,
    enabled: module === "portfolio",
    retry: false,
    staleTime: 12_000,
    refetchInterval: module === "portfolio" ? 45_000 : false,
  });

  const monitorQ = useQuery({
    queryKey: ["quant-studio-live-monitor"],
    queryFn: quantStudioApi.liveMonitor,
    enabled: module === "monitor",
    retry: false,
    staleTime: 8_000,
    refetchInterval: module === "monitor" ? 20_000 : false,
  });

  const graphPayload = {
    nodes: nodes.map((n) => ({ type: n.type, params: n.params, id: n.id })),
    edges: nodes.slice(0, -1).map((_, i) => ({ from: i, to: i + 1 })),
  };

  const compile = useMutation({
    mutationFn: () => quantStudioApi.compile(graphPayload),
    onSuccess: () => toast.success("Strategy graph compiled"),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Compile failed"),
  });

  const backtest = useMutation({
    mutationFn: () =>
      quantStudioApi.backtest({
        symbol,
        timeframe,
        count: 300,
        graph: graphPayload,
        assumptions: {},
      }),
    onSuccess: (data) => {
      setLastRun(asRecord(data));
      setModule("backtest");
      toast.success("Backtest Studio run complete");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Backtest failed"),
  });

  const walkforward = useMutation({
    mutationFn: () =>
      quantStudioApi.walkforward({
        symbol,
        timeframe,
        count: 400,
        in_sample_bars: 120,
        out_of_sample_bars: 40,
        step_bars: 40,
      }),
    onSuccess: (data) => {
      setWfRun(asRecord(data));
      setModule("walkforward");
      toast.success("Walk-forward complete");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Walk-forward failed"),
  });

  const saveStrategy = useMutation({
    mutationFn: () =>
      quantStudioApi.marketplaceSave({
        name: strategyName,
        graph: graphPayload,
        assumptions: asRecord(asRecord(compile.data).assumptions),
        notes: "Saved from Quant Studio",
      }),
    onSuccess: async () => {
      toast.success("Strategy saved");
      await qc.invalidateQueries({ queryKey: ["quant-studio-marketplace"] });
      await qc.invalidateQueries({ queryKey: ["quant-studio-workspace"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Save failed"),
  });

  const catalog = asList(asRecord(wsQ.data).block_catalog).map(asRecord);
  const run = asRecord(lastRun);
  const metrics = asRecord(run.metrics);
  const analytics = asRecord(run.analytics);
  const mc = asRecord(run.monte_carlo);
  const review = asRecord(run.ai_review);
  const optimizer = asRecord(run.ai_optimizer);
  const equity = mapEquityCurve(run.equity_curve);
  const trades = asList(run.trades).map(asRecord);
  const wf = asRecord(wfRun);
  const stability = asRecord(wf.stability);
  const marketItems = asList(asRecord(marketQ.data).items).map(asRecord);
  const portfolio = asRecord(portfolioQ.data);
  const monitor = asRecord(monitorQ.data);
  const corr = asRecord(portfolio.correlation);

  function addBlock(type: string, label: string) {
    setNodes((prev) => [
      ...prev,
      {
        id: `n${Date.now()}`,
        type,
        label,
        params: {},
      },
    ]);
  }

  return (
    <div className="quant-studio-desk">
      <PageHeader
        title="Quant Studio"
        description="AI-assisted research workspace — visual strategies, backtests, walk-forward, Monte Carlo, and portfolio lab. Analysis only — never submits trades."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Input
              className="h-8 w-28 font-mono text-xs"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              aria-label="Symbol"
            />
            <Input
              className="h-8 w-20 font-mono text-xs"
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value.toUpperCase())}
              aria-label="Timeframe"
            />
            <Button
              size="sm"
              onClick={() => backtest.mutate()}
              disabled={backtest.isPending}
            >
              <Play className="h-3.5 w-3.5" />
              Run Studio
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => wsQ.refetch()}
              disabled={wsQ.isFetching}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${wsQ.isFetching ? "animate-spin" : ""}`} />
            </Button>
          </div>
        }
      />
      <SessionStrip className="mb-4" />

      {wsQ.isLoading ? (
        <DeskSkeleton rows={8} />
      ) : (
        <PageMotion className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge tone="success">advisory only</Badge>
            <Badge tone="neutral">never_submits_orders</Badge>
            <Badge tone={asRecord(wsQ.data).execution_enabled ? "danger" : "success"}>
              EXECUTION_ENABLED={String(Boolean(asRecord(wsQ.data).execution_enabled))}
            </Badge>
            <span className="text-[var(--fg-subtle)]">
              v{str(asRecord(wsQ.data).version, "3.0")} ·{" "}
              {wsQ.isError ? "unavailable" : str(asRecord(wsQ.data).status, "—")}
            </span>
          </div>

          {wsQ.isError && (
            <DeskError
              message="Quant Studio workspace API unavailable — local modules still usable for builder drafts."
              onRetry={() => wsQ.refetch()}
            />
          )}

          {/* Module dock */}
          <div
            className="flex gap-1 overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)]/60 p-1.5 backdrop-blur"
            role="tablist"
            aria-label="Quant Studio modules"
          >
            {MODULES.map((m) => {
              const Icon = m.icon;
              const active = module === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => setModule(m.id)}
                  className={`flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs transition ${
                    active
                      ? "bg-[var(--surface-2)] text-[var(--fg)] shadow-sm"
                      : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)]/50"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {m.label}
                </button>
              );
            })}
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={module}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.22 }}
            >
              {module === "builder" && (
                <div className="grid gap-4 xl:grid-cols-[240px_1fr]">
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">Block palette</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-1">
                      {catalog.map((b) => (
                        <button
                          key={str(b.id)}
                          type="button"
                          className="flex w-full items-center justify-between rounded border border-[var(--border)] px-2 py-1.5 text-left text-xs hover:bg-[var(--surface-2)]"
                          onClick={() => addBlock(str(b.id), str(b.label))}
                        >
                          <span>{str(b.label)}</span>
                          <Plus className="h-3 w-3 text-[var(--fg-subtle)]" />
                        </button>
                      ))}
                      {!catalog.length && (
                        <>
                          {[
                            ["indicator", "Indicator"],
                            ["price", "Price"],
                            ["risk", "Risk"],
                            ["session", "Session"],
                            ["exit", "Exit"],
                            ["execution", "Execution"],
                            ["ai", "AI Gate"],
                          ].map(([id, label]) => (
                            <button
                              key={id}
                              type="button"
                              className="flex w-full items-center justify-between rounded border border-[var(--border)] px-2 py-1.5 text-left text-xs hover:bg-[var(--surface-2)]"
                              onClick={() => addBlock(id, label)}
                            >
                              <span>{label}</span>
                              <Plus className="h-3 w-3 text-[var(--fg-subtle)]" />
                            </button>
                          ))}
                        </>
                      )}
                    </CardContent>
                  </Card>
                  <Card className="overflow-hidden">
                    <CardHeader className="flex flex-row items-center justify-between gap-2">
                      <CardTitle className="text-sm">Visual strategy canvas</CardTitle>
                      <div className="flex gap-2">
                        <Button size="sm" variant="secondary" onClick={() => compile.mutate()}>
                          Compile
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => saveStrategy.mutate()}>
                          Save
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="mb-3 flex flex-wrap gap-2">
                        <Input
                          className="h-8 max-w-xs text-xs"
                          value={strategyName}
                          onChange={(e) => setStrategyName(e.target.value)}
                          aria-label="Strategy name"
                        />
                      </div>
                      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                        {nodes.map((n, idx) => (
                          <div
                            key={n.id}
                            className="rounded-lg border border-[var(--border)] bg-[linear-gradient(160deg,rgba(20,32,48,0.9),rgba(8,12,20,0.95))] p-3"
                          >
                            <div className="mb-2 flex items-center justify-between">
                              <Badge tone="neutral">
                                {idx + 1}. {n.label || n.type}
                              </Badge>
                              <button
                                type="button"
                                aria-label="Remove block"
                                onClick={() => setNodes((p) => p.filter((x) => x.id !== n.id))}
                              >
                                <Trash2 className="h-3.5 w-3.5 text-[var(--fg-subtle)]" />
                              </button>
                            </div>
                            <p className="font-mono text-[10px] uppercase text-[var(--fg-muted)]">
                              {n.type}
                            </p>
                          </div>
                        ))}
                      </div>
                      {compile.data && (
                        <div className="mt-4 rounded border border-[var(--border)] p-3 text-xs text-[var(--fg-muted)]">
                          <p className="mb-1 font-medium text-[var(--fg)]">Compiled assumptions</p>
                          <pre className="overflow-x-auto whitespace-pre-wrap">
                            {JSON.stringify(asRecord(asRecord(compile.data).assumptions), null, 2)}
                          </pre>
                        </div>
                      )}
                      <p className="mt-3 text-[11px] text-[var(--fg-subtle)]">
                        Shortcuts: Run Studio from header · blocks are advisory — never auto-execute.
                      </p>
                    </CardContent>
                  </Card>
                </div>
              )}

              {module === "backtest" && (
                <div className="space-y-4">
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => backtest.mutate()} disabled={backtest.isPending}>
                      {backtest.isPending ? "Running…" : "Run on live MT5 candles"}
                    </Button>
                  </div>
                  {!run.status ? (
                    <DeskEmpty
                      icon={FlaskConical}
                      title="No backtest yet"
                      description="Run Studio to simulate on broker historical candles."
                    />
                  ) : str(run.status) === "unavailable" || str(run.status) === "failed" ? (
                    <DeskError message={str(run.reason || run.error_message, "Backtest unavailable")} />
                  ) : (
                    <>
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <StatCard label="Win rate" value={metrics.win_rate == null ? "—" : `${formatNumber(num(metrics.win_rate), 1)}%`} />
                        <StatCard label="Profit factor" value={metrics.profit_factor == null ? "—" : formatNumber(num(metrics.profit_factor), 2)} />
                        <StatCard label="Sharpe" value={metrics.sharpe_ratio == null ? "—" : formatNumber(num(metrics.sharpe_ratio), 2)} />
                        <StatCard label="Sortino" value={metrics.sortino_ratio == null ? "—" : formatNumber(num(metrics.sortino_ratio), 2)} />
                        <StatCard label="Expectancy" value={metrics.expectancy == null ? "—" : formatNumber(num(metrics.expectancy), 2)} />
                        <StatCard label="Max DD %" value={metrics.max_drawdown_pct == null ? "—" : formatNumber(num(metrics.max_drawdown_pct), 2)} />
                        <StatCard label="Trades" value={str(metrics.trade_count, "0")} />
                        <StatCard label="Bars" value={str(run.bar_count, "—")} hint={str(run.data_source)} />
                      </div>
                      {equity.length > 0 && (
                        <Card>
                          <CardHeader>
                            <CardTitle className="text-sm">Equity curve</CardTitle>
                          </CardHeader>
                          <CardContent className="h-64">
                            <LazyEquityChart data={equity} />
                          </CardContent>
                        </Card>
                      )}
                      <DeskTable
                        columns={["Symbol", "Side", "PnL", "Exit"]}
                        rows={trades.slice(0, 40).map((t) => [
                          str(t.symbol),
                          str(t.side),
                          formatNumber(num(t.pnl), 2),
                          str(t.exit_reason, "—"),
                        ])}
                      />
                    </>
                  )}
                </div>
              )}

              {module === "walkforward" && (
                <div className="space-y-4">
                  <Button size="sm" onClick={() => walkforward.mutate()} disabled={walkforward.isPending}>
                    {walkforward.isPending ? "Running…" : "Run walk-forward (train / validation / OOS)"}
                  </Button>
                  {!wf.status ? (
                    <DeskEmpty icon={GitBranch} title="No walk-forward run" description="Split live candles into IS / OOS folds." />
                  ) : str(wf.status) === "unavailable" ? (
                    <DeskError message={str(wf.reason)} />
                  ) : (
                    <>
                      <div className="grid gap-3 sm:grid-cols-3">
                        <StatCard label="Stability" value={stability.stability_score == null ? "—" : formatNumber(num(stability.stability_score), 2)} />
                        <StatCard label="Mean IS PF" value={stability.mean_is_profit_factor == null ? "—" : formatNumber(num(stability.mean_is_profit_factor), 2)} />
                        <StatCard label="Mean OOS PF" value={stability.mean_oos_profit_factor == null ? "—" : formatNumber(num(stability.mean_oos_profit_factor), 2)} />
                      </div>
                      <p className="text-sm text-[var(--fg-muted)]">{str(asRecord(stability.why).summary)}</p>
                      <DeskTable
                        columns={["Fold", "IS PF", "OOS PF"]}
                        rows={asList(wf.folds).map(asRecord).map((f) => [
                          str(f.index),
                          f.is_profit_factor == null ? "—" : formatNumber(num(f.is_profit_factor), 2),
                          f.oos_profit_factor == null ? "—" : formatNumber(num(f.oos_profit_factor), 2),
                        ])}
                      />
                      <Badge tone="neutral">Promotion: {str(wf.promotion, "n/a")}</Badge>
                    </>
                  )}
                </div>
              )}

              {module === "montecarlo" && (
                <div className="space-y-4">
                  {str(mc.status) !== "available" ? (
                    <DeskEmpty
                      icon={Dices}
                      title="Monte Carlo waiting"
                      description={str(mc.reason, "Run Backtest Studio first — uses real trade PnLs only.")}
                    />
                  ) : (
                    <>
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <StatCard label="Simulations" value={str(mc.simulations)} />
                        <StatCard
                          label="P(profit)"
                          value={mc.probability_of_profit == null ? "—" : formatPct(num(mc.probability_of_profit, 0))}
                        />
                        <StatCard label="Worst case" value={formatNumber(num(mc.worst_case), 2)} />
                        <StatCard label="Best case" value={formatNumber(num(mc.best_case), 2)} />
                        <StatCard label="P05" value={formatNumber(num(asRecord(mc.confidence).p05), 2)} />
                        <StatCard label="P50" value={formatNumber(num(asRecord(mc.confidence).p50), 2)} />
                        <StatCard label="P95" value={formatNumber(num(asRecord(mc.confidence).p95), 2)} />
                        <StatCard
                          label="DD P95 %"
                          value={formatNumber(num(asRecord(mc.confidence).drawdown_p95_pct), 2)}
                        />
                      </div>
                      <p className="text-sm text-[var(--fg-muted)]">{str(asRecord(mc.why).summary)}</p>
                    </>
                  )}
                </div>
              )}

              {module === "review" && (
                <div className="grid gap-4 md:grid-cols-2">
                  {str(review.status) !== "available" ? (
                    <DeskEmpty icon={Brain} title="AI review waiting" description="Run a backtest to generate advisory review." />
                  ) : (
                    <>
                      {(
                        [
                          ["Strengths", review.strengths],
                          ["Weaknesses", review.weaknesses],
                          ["Risk", review.risk],
                          ["Market suitability", review.market_suitability],
                          ["Overfitting", review.overfitting],
                          ["Parameter sensitivity", review.parameter_sensitivity],
                        ] as const
                      ).map(([title, items]) => (
                        <Card key={title}>
                          <CardHeader>
                            <CardTitle className="text-sm">{title}</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <ul className="list-disc space-y-1 pl-4 text-sm text-[var(--fg-muted)]">
                              {asList(items).map(String).map((x) => (
                                <li key={x}>{x}</li>
                              ))}
                            </ul>
                          </CardContent>
                        </Card>
                      ))}
                    </>
                  )}
                </div>
              )}

              {module === "optimizer" && (
                <div className="space-y-3">
                  <Badge tone="warning">Suggestions only — never auto-applies</Badge>
                  {str(optimizer.status) !== "available" ? (
                    <DeskEmpty icon={Sparkles} title="Optimizer waiting" description="Run Backtest Studio for advisory SL/TP/RR suggestions." />
                  ) : (
                    <DeskTable
                      columns={["Field", "Current", "Suggested", "Reason"]}
                      rows={asList(optimizer.suggestions).map(asRecord).map((s) => [
                        str(s.field),
                        str(s.current),
                        str(s.suggested),
                        str(s.reason),
                      ])}
                    />
                  )}
                </div>
              )}

              {module === "marketplace" && (
                <div className="space-y-4">
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" onClick={() => saveStrategy.mutate()}>
                      Save / version
                    </Button>
                    <Label className="sr-only">Strategy name</Label>
                    <Input
                      className="h-8 max-w-xs text-xs"
                      value={strategyName}
                      onChange={(e) => setStrategyName(e.target.value)}
                    />
                  </div>
                  {marketItems.length ? (
                    <DeskTable
                      columns={["Name", "Version", "Published", "Favorite", "Actions"]}
                      rows={marketItems.map((item) => [
                        str(item.name),
                        str(item.latest_version),
                        String(Boolean(item.published)),
                        String(Boolean(item.favorite)),
                        <div key={str(item.id)} className="flex gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              quantStudioApi
                                .marketplaceAction({
                                  action: "publish",
                                  strategy_id: str(item.id),
                                  published: true,
                                })
                                .then(() => qc.invalidateQueries({ queryKey: ["quant-studio-marketplace"] }))
                                .then(() => toast.success("Published"))
                                .catch((e) =>
                                  toast.error(e instanceof ApiError ? e.message : "Publish failed"),
                                )
                            }
                          >
                            Publish
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              quantStudioApi
                                .marketplaceAction({
                                  action: "clone",
                                  strategy_id: str(item.id),
                                })
                                .then(() => qc.invalidateQueries({ queryKey: ["quant-studio-marketplace"] }))
                                .then(() => toast.success("Cloned"))
                                .catch((e) =>
                                  toast.error(e instanceof ApiError ? e.message : "Clone failed"),
                                )
                            }
                          >
                            Clone
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              quantStudioApi
                                .marketplaceAction({
                                  action: "favorite",
                                  strategy_id: str(item.id),
                                  favorited: true,
                                })
                                .then(() => qc.invalidateQueries({ queryKey: ["quant-studio-marketplace"] }))
                                .then(() => toast.success("Favorited"))
                                .catch((e) =>
                                  toast.error(e instanceof ApiError ? e.message : "Favorite failed"),
                                )
                            }
                          >
                            ★
                          </Button>
                        </div>,
                      ])}
                    />
                  ) : (
                    <DeskEmpty icon={Store} title="Marketplace empty" description="Save a visual strategy to version and share." />
                  )}
                </div>
              )}

              {module === "analytics" && (
                <div className="space-y-4">
                  {str(analytics.status) !== "available" ? (
                    <DeskEmpty icon={ChartLine} title="Analytics waiting" description="Run a backtest for heatmaps, calendars, and timelines." />
                  ) : (
                    <>
                      <div className="grid gap-3 sm:grid-cols-3">
                        <StatCard label="Wins" value={str(asRecord(analytics.trade_distribution).win, "0")} />
                        <StatCard label="Losses" value={str(asRecord(analytics.trade_distribution).loss, "0")} />
                        <StatCard
                          label="Mean PnL"
                          value={
                            asRecord(analytics.pnl_histogram).mean == null
                              ? "—"
                              : formatNumber(num(asRecord(analytics.pnl_histogram).mean), 2)
                          }
                        />
                      </div>
                      <DeskTable
                        columns={["Month", "Return %"]}
                        rows={asList(analytics.monthly_returns).map(asRecord).map((r) => [
                          str(r.month),
                          formatNumber(num(r.return_pct), 2),
                        ])}
                      />
                      <DeskTable
                        columns={["Date", "PnL"]}
                        rows={asList(analytics.trade_calendar)
                          .map(asRecord)
                          .slice(0, 30)
                          .map((r) => [str(r.date), formatNumber(num(r.pnl), 2)])}
                      />
                    </>
                  )}
                </div>
              )}

              {module === "portfolio" && (
                <div className="space-y-4">
                  {portfolioQ.isLoading ? (
                    <DeskSkeleton rows={4} />
                  ) : str(portfolio.status) === "unavailable" ? (
                    <DeskError message={str(portfolio.reason)} onRetry={() => portfolioQ.refetch()} />
                  ) : (
                    <>
                      <div className="grid gap-3 sm:grid-cols-4">
                        <StatCard label="Equity" value={formatNumber(num(asRecord(portfolio.account).equity), 2)} />
                        <StatCard label="Positions" value={str(asList(portfolio.exposure).length)} />
                        <StatCard
                          label="Floating"
                          value={formatNumber(num(asRecord(portfolio.risk).floating_pnl), 2)}
                        />
                        <StatCard label="Corr" value={str(corr.status, "—")} />
                      </div>
                      <div className="grid gap-4 md:grid-cols-2">
                        <Card>
                          <CardHeader>
                            <CardTitle className="text-sm">Sector allocation</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <DeskTable
                              columns={["Sector", "Weight"]}
                              rows={asList(portfolio.sector_allocation).map(asRecord).map((r) => [
                                str(r.sector),
                                formatNumber(num(r.weight), 2),
                              ])}
                            />
                          </CardContent>
                        </Card>
                        <Card>
                          <CardHeader>
                            <CardTitle className="text-sm">Currency allocation</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <DeskTable
                              columns={["Currency", "Weight"]}
                              rows={asList(portfolio.currency_allocation).map(asRecord).map((r) => [
                                str(r.currency),
                                formatNumber(num(r.weight), 2),
                              ])}
                            />
                          </CardContent>
                        </Card>
                      </div>
                      {str(corr.status) === "available" && (
                        <div className="overflow-x-auto">
                          <table className="w-full min-w-[400px] text-xs">
                            <thead>
                              <tr>
                                <th />
                                {asList(corr.labels).map(String).map((l) => (
                                  <th key={l} className="p-1 font-mono">
                                    {l}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {asList(corr.labels).map(String).map((row, i) => (
                                <tr key={row}>
                                  <td className="p-1 font-mono">{row}</td>
                                  {asList((asList(corr.matrix)[i] as unknown[]) || []).map((cell, j) => (
                                    <td key={`${row}-${j}`} className="p-1 text-center font-mono">
                                      {typeof cell === "number" ? formatNumber(cell, 2) : "—"}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {module === "monitor" && (
                <div className="space-y-4">
                  {monitorQ.isLoading ? (
                    <DeskSkeleton rows={3} />
                  ) : (
                    <>
                      <div className="grid gap-3 sm:grid-cols-3">
                        <StatCard
                          label="Open"
                          value={str(asRecord(monitor.performance).open_positions, "0")}
                        />
                        <StatCard
                          label="Floating PnL"
                          value={formatNumber(num(asRecord(monitor.performance).floating_pnl), 2)}
                        />
                        <StatCard
                          label="Latency"
                          value={
                            asRecord(monitor.broker).latency_ms == null
                              ? "—"
                              : `${formatNumber(num(asRecord(monitor.broker).latency_ms), 0)} ms`
                          }
                        />
                      </div>
                      <ul className="space-y-1 text-sm text-[var(--fg-muted)]">
                        {asList(monitor.alerts).map(String).map((a) => (
                          <li key={a}>• {a}</li>
                        ))}
                        {!asList(monitor.alerts).length && (
                          <li className="text-[var(--fg-subtle)]">No live alerts</li>
                        )}
                      </ul>
                      <DeskTable
                        columns={["Ticket", "Symbol", "Side", "Vol", "PnL"]}
                        rows={asList(monitor.positions).map(asRecord).map((p) => [
                          str(p.ticket),
                          str(p.symbol),
                          str(p.side),
                          formatNumber(num(p.volume), 2),
                          formatNumber(num(p.profit), 2),
                        ])}
                      />
                    </>
                  )}
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </PageMotion>
      )}
    </div>
  );
}

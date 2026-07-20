"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import {
  BarChart3,
  BookOpen,
  FlaskConical,
  FileText,
  Gauge,
  GitCompare,
  Layers,
  RefreshCw,
  Rocket,
  ShieldCheck,
  Sparkles,
  Waves,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { PageMotion, StaggerGrid, StaggerItem } from "@/components/desk/motion";
import { SessionStrip } from "@/components/broker/session-strip";
import { researchLabApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";
import { TRADING_SYMBOL, resolveTradingSymbol } from "@/lib/trading/gold-only";

const MODULES = [
  { id: "dashboard", label: "Dashboard", icon: Gauge },
  { id: "library", label: "Library", icon: BookOpen },
  { id: "validation", label: "Validation", icon: FlaskConical },
  { id: "compare", label: "Compare", icon: GitCompare },
  { id: "regime", label: "Regime", icon: Waves },
  { id: "params", label: "Parameters", icon: Layers },
  { id: "paper", label: "Paper", icon: BarChart3 },
  { id: "review", label: "AI Review", icon: Sparkles },
  { id: "reports", label: "Reports", icon: FileText },
  { id: "promotion", label: "Promotion", icon: Rocket },
] as const;

type ModuleId = (typeof MODULES)[number]["id"];

function metricCell(v: unknown, digits = 2) {
  if (v == null || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return formatNumber(n, digits);
}

export default function ResearchLabPage() {
  const qc = useQueryClient();
  const [symbol, setSymbol] = useState(TRADING_SYMBOL);
  const [focus, setFocus] = useState(TRADING_SYMBOL);
  const [module, setModule] = useState<ModuleId>("dashboard");
  const [strategyKey, setStrategyKey] = useState("trend_following");
  const [timeframe, setTimeframe] = useState("H1");
  const [atrPeriod, setAtrPeriod] = useState("14");
  const [emaFast, setEmaFast] = useState("20");
  const [rsiPeriod, setRsiPeriod] = useState("14");
  const [slDist, setSlDist] = useState("0.0020");
  const [tpDist, setTpDist] = useState("0.0040");
  const [lastValidation, setLastValidation] = useState<Record<string, unknown> | null>(
    null,
  );

  const dashQ = useQuery({
    queryKey: ["research-lab-dashboard", focus],
    queryFn: () => researchLabApi.dashboard(focus),
    retry: false,
    staleTime: 20_000,
    refetchInterval: 60_000,
  });

  const libraryQ = useQuery({
    queryKey: ["research-lab-library"],
    queryFn: researchLabApi.library,
    retry: false,
    staleTime: 120_000,
    enabled: module === "library" || module === "validation" || module === "promotion",
  });

  const compareQ = useQuery({
    queryKey: ["research-lab-compare"],
    queryFn: researchLabApi.compare,
    retry: false,
    staleTime: 15_000,
    enabled: module === "compare" || module === "dashboard",
  });

  const regimeQ = useQuery({
    queryKey: ["research-lab-regime", focus],
    queryFn: () => researchLabApi.regime(focus),
    retry: false,
    staleTime: 20_000,
    enabled: module === "regime",
    refetchInterval: module === "regime" ? 60_000 : false,
  });

  const paramsQ = useQuery({
    queryKey: ["research-lab-parameters"],
    queryFn: researchLabApi.parameters,
    retry: false,
    staleTime: 60_000,
    enabled: module === "params" || module === "validation",
  });

  const paperQ = useQuery({
    queryKey: ["research-lab-paper"],
    queryFn: researchLabApi.paper,
    retry: false,
    staleTime: 30_000,
    enabled: module === "paper" || module === "dashboard",
  });

  const criteriaQ = useQuery({
    queryKey: ["research-lab-criteria"],
    queryFn: researchLabApi.promotionCriteria,
    retry: false,
    staleTime: 60_000,
    enabled: module === "promotion",
  });

  const reportQ = useQuery({
    queryKey: ["research-lab-report", strategyKey],
    queryFn: () => researchLabApi.report(strategyKey),
    retry: false,
    staleTime: 15_000,
    enabled: module === "reports",
  });

  const validate = useMutation({
    mutationFn: () =>
      researchLabApi.validate({
        strategy_key: strategyKey,
        symbol: focus,
        timeframe,
        parameter_overrides: {
          atr_period: Number(atrPeriod) || 14,
          ema_fast: Number(emaFast) || 20,
          rsi_period: Number(rsiPeriod) || 14,
          stop_loss_distance: slDist,
          take_profit_distance: tpDist,
        },
      }),
    onSuccess: async (data) => {
      setLastValidation(asRecord(data));
      if (str(data.status) === "unavailable") {
        toast.message(str(data.reason, "Validation unavailable"));
      } else {
        toast.success("Validation run saved");
      }
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["research-lab-dashboard"] }),
        qc.invalidateQueries({ queryKey: ["research-lab-compare"] }),
        qc.invalidateQueries({ queryKey: ["research-lab-report"] }),
      ]);
      setModule("validation");
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Validation failed"),
  });

  const saveParams = useMutation({
    mutationFn: () =>
      researchLabApi.setParameters({
        atr_period: Number(atrPeriod) || 14,
        ema_fast: Number(emaFast) || 20,
        rsi_period: Number(rsiPeriod) || 14,
        stop_loss_distance: slDist,
        take_profit_distance: tpDist,
      }),
    onSuccess: async () => {
      toast.success("Sandbox parameters saved (production defaults unchanged)");
      await qc.invalidateQueries({ queryKey: ["research-lab-parameters"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Parameter save failed"),
  });

  const promote = useMutation({
    mutationFn: () => researchLabApi.promote({ strategy_key: strategyKey }),
    onSuccess: async (data) => {
      const eval_ = asRecord(data.evaluation);
      toast.message(
        eval_.eligible_for_decision_engine
          ? "Eligible for Decision Engine evaluation"
          : "Not eligible — criteria not met",
      );
      await qc.invalidateQueries({ queryKey: ["research-lab-dashboard"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Promotion evaluate failed"),
  });

  const dash = asRecord(dashQ.data);
  const leaders = asRecord(dash.research_dashboard);
  const best = asRecord(leaders.best);
  const worst = asRecord(leaders.worst);
  const candidate = asRecord(leaders.candidate);
  const regime = asRecord(dash.regime);
  const libraryItems = asList(asRecord(libraryQ.data).items).map(asRecord);
  const compareItems = asList(asRecord(compareQ.data).items).map(asRecord);
  const validation = lastValidation || asRecord(null);
  const valBlock = asRecord(validation.validation);
  const backtest = asRecord(valBlock.backtest);
  const walkforward = asRecord(valBlock.walkforward);
  const monte = asRecord(valBlock.monte_carlo);
  const review = asRecord(validation.ai_research_review);
  const paper = asRecord(paperQ.data || dash.paper);
  const params = asRecord(paramsQ.data);
  const report = asRecord(reportQ.data);
  const criteria = asRecord(asRecord(criteriaQ.data).criteria);

  const libraryPreview = asList(dash.library_preview).map(asRecord);

  return (
    <div className="research-lab-desk">
      <PageHeader
        title="Research Lab"
        description="Strategy research center — library, validation, comparison, regimes, and promotion eligibility. Not a trading page. Never submits orders."
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
              Focus
            </Button>
            <Button
              size="sm"
              onClick={() => validate.mutate()}
              disabled={validate.isPending}
            >
              Validate
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
        <PageMotion className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge tone="success">advisory only</Badge>
            <Badge tone="neutral">never_submits_orders</Badge>
            <Badge tone="neutral">DE gatekeeper</Badge>
            <Badge tone={dash.execution_enabled ? "danger" : "success"}>
              EXECUTION_ENABLED={String(Boolean(dash.execution_enabled))}
            </Badge>
            <span className="text-[var(--fg-subtle)]">
              v{str(dash.version, "5.0")} · {dashQ.isError ? "unavailable" : str(dash.status, "—")}
            </span>
          </div>

          {dashQ.isError && (
            <DeskError
              message="Research Lab API unavailable — no fabricated research results."
              onRetry={() => dashQ.refetch()}
            />
          )}

          <div
            className="flex gap-1 overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)]/60 p-1.5 backdrop-blur"
            role="tablist"
            aria-label="Research Lab modules"
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
              transition={{ duration: 0.18 }}
              className="space-y-4"
            >
              {module === "dashboard" && (
                <>
                  <motion.section
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="relative overflow-hidden rounded-xl border border-[var(--border)] bg-[linear-gradient(150deg,rgba(18,32,40,0.96),rgba(6,10,16,0.94))] p-5"
                  >
                    <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(70,140,120,0.12),transparent_55%)]" />
                    <div className="relative">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--fg-muted)]">
                        Research dashboard · {focus}
                      </p>
                      <h2 className="mt-1 font-mono text-xl text-[var(--fg)]">
                        Candidate · {str(candidate.name, str(candidate.strategy_key, "None"))}
                      </h2>
                      <p className="mt-1 text-sm text-[var(--fg-subtle)]">
                        Regime · {str(regime.primary, "—")} · Confidence{" "}
                        {leaders.confidence == null
                          ? "—"
                          : `${formatNumber(num(leaders.confidence), 0)}%`}
                      </p>
                    </div>
                    <StaggerGrid className="relative mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                      <StaggerItem>
                        <StatCard
                          label="Best"
                          value={str(best.name, str(best.strategy_key, "—"))}
                          hint={
                            best.sharpe_ratio == null
                              ? undefined
                              : `Sharpe ${formatNumber(num(best.sharpe_ratio), 2)}`
                          }
                        />
                      </StaggerItem>
                      <StaggerItem>
                        <StatCard
                          label="Worst"
                          value={str(worst.name, str(worst.strategy_key, "—"))}
                        />
                      </StaggerItem>
                      <StaggerItem>
                        <StatCard
                          label="Stability"
                          value={
                            leaders.stability == null
                              ? "—"
                              : formatNumber(num(leaders.stability), 2)
                          }
                        />
                      </StaggerItem>
                      <StaggerItem>
                        <StatCard
                          label="Library"
                          value={String(num(dash.library_count) || libraryPreview.length || 0)}
                        />
                      </StaggerItem>
                    </StaggerGrid>
                  </motion.section>

                  <div className="grid gap-4 xl:grid-cols-2">
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Active regime</CardTitle>
                      </CardHeader>
                      <CardContent>
                        {str(regime.status) === "unavailable" ? (
                          <DeskEmpty
                            icon={Waves}
                            title="Regime unavailable"
                            description={str(regime.reason, "Connect MT5 for live OHLC classification")}
                          />
                        ) : (
                          <DeskTable
                            columns={["Field", "Value"]}
                            rows={[
                              ["Primary", str(regime.primary)],
                              ["Regimes", asList(regime.regimes).join(", ") || "—"],
                              ["Evidence", asList(regime.evidence).slice(0, 3).join(" · ") || "—"],
                            ]}
                          />
                        )}
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Paper snapshot</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <DeskTable
                          columns={["Period", "Signals", "Sim PnL"]}
                          rows={["daily", "weekly", "monthly", "annual"].map((k) => {
                            const row = asRecord(paper[k]);
                            return [
                              k,
                              row.signals == null ? "—" : String(row.signals),
                              row.realized_sim_pnl == null
                                ? "—"
                                : formatNumber(num(row.realized_sim_pnl), 2),
                            ];
                          })}
                        />
                      </CardContent>
                    </Card>
                  </div>
                </>
              )}

              {module === "library" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Strategy library</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {libraryQ.isLoading ? (
                      <DeskSkeleton rows={4} />
                    ) : libraryItems.length === 0 ? (
                      <DeskEmpty
                        icon={BookOpen}
                        title="No strategies"
                        description="Library catalog empty"
                      />
                    ) : (
                      <DeskTable
                        columns={["Strategy", "Family", "Engine", "Best regimes"]}
                        rows={libraryItems.map((s) => [
                          str(s.name),
                          str(s.family),
                          s.engine_plugin ? "plugin" : "archetype",
                          asList(s.best_regimes).join(", "),
                        ])}
                      />
                    )}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {libraryItems.map((s) => (
                        <Button
                          key={str(s.key)}
                          size="sm"
                          variant={strategyKey === str(s.key) ? "default" : "secondary"}
                          onClick={() => setStrategyKey(str(s.key))}
                        >
                          {str(s.name)}
                        </Button>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {module === "validation" && (
                <div className="grid gap-4 xl:grid-cols-[280px_1fr]">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Validation center</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <label className="text-[11px] text-[var(--fg-muted)]">Strategy</label>
                      <Input
                        className="h-8 font-mono text-xs"
                        value={strategyKey}
                        onChange={(e) => setStrategyKey(e.target.value)}
                      />
                      <label className="text-[11px] text-[var(--fg-muted)]">Timeframe</label>
                      <Input
                        className="h-8 font-mono text-xs"
                        value={timeframe}
                        onChange={(e) => setTimeframe(e.target.value.toUpperCase())}
                      />
                      <Button
                        className="w-full"
                        size="sm"
                        onClick={() => validate.mutate()}
                        disabled={validate.isPending}
                      >
                        {validate.isPending ? "Running…" : "Run backtest · WF · MC · paper"}
                      </Button>
                      <p className="text-[11px] text-[var(--fg-subtle)]">
                        Uses historical MT5 OHLC only. Production defaults never change.
                      </p>
                    </CardContent>
                  </Card>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Backtest</CardTitle>
                      </CardHeader>
                      <CardContent>
                        {!backtest.status ? (
                          <DeskEmpty
                            icon={FlaskConical}
                            title="No run"
                            description="Start a validation"
                          />
                        ) : (
                          <DeskTable
                            columns={["Metric", "Value"]}
                            rows={[
                              ["Status", str(backtest.status)],
                              ["Win rate", metricCell(asRecord(backtest.metrics).win_rate)],
                              ["Profit factor", metricCell(asRecord(backtest.metrics).profit_factor)],
                              ["Sharpe", metricCell(asRecord(backtest.metrics).sharpe_ratio)],
                              ["Sortino", metricCell(asRecord(backtest.metrics).sortino_ratio)],
                              ["Drawdown %", metricCell(asRecord(backtest.metrics).max_drawdown_pct)],
                              ["Expectancy", metricCell(asRecord(backtest.metrics).expectancy)],
                              ["Trades", metricCell(asRecord(backtest.metrics).trade_count, 0)],
                            ]}
                          />
                        )}
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Walk-forward</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <DeskTable
                          columns={["Field", "Value"]}
                          rows={[
                            ["Status", str(walkforward.status, "—")],
                            [
                              "Stability",
                              metricCell(asRecord(walkforward.stability).stability_score),
                            ],
                            ["Folds", String(asList(walkforward.folds).length || "—")],
                          ]}
                        />
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Monte Carlo</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <DeskTable
                          columns={["Field", "Value"]}
                          rows={[
                            ["Status", str(monte.status, "—")],
                            ["Sims", monte.simulations == null ? "—" : String(monte.simulations)],
                            ["Worst", metricCell(monte.worst_case)],
                            ["Best", metricCell(monte.best_case)],
                          ]}
                        />
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Paper (side-by-side)</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <DeskTable
                          columns={["Period", "PnL"]}
                          rows={["daily", "weekly", "monthly"].map((k) => {
                            const row = asRecord(asRecord(valBlock.paper)[k] || paper[k]);
                            return [
                              k,
                              row.realized_sim_pnl == null
                                ? "—"
                                : formatNumber(num(row.realized_sim_pnl), 2),
                            ];
                          })}
                        />
                      </CardContent>
                    </Card>
                  </div>
                </div>
              )}

              {module === "compare" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Strategy comparison</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {compareQ.isLoading ? (
                      <DeskSkeleton rows={4} />
                    ) : compareItems.length === 0 ? (
                      <DeskEmpty
                        icon={GitCompare}
                        title="No research runs"
                        description="Validate strategies first — comparison uses saved research metrics only"
                      />
                    ) : (
                      <DeskTable
                        columns={[
                          "Strategy",
                          "WR",
                          "PF",
                          "Sharpe",
                          "Sortino",
                          "DD%",
                          "Exp",
                          "RR",
                          "Trades",
                        ]}
                        rows={compareItems.map((it) => [
                          str(it.name, str(it.strategy_key)),
                          metricCell(it.win_rate, 1),
                          metricCell(it.profit_factor),
                          metricCell(it.sharpe_ratio),
                          metricCell(it.sortino_ratio),
                          metricCell(it.max_drawdown_pct),
                          metricCell(it.expectancy),
                          metricCell(it.average_rr),
                          metricCell(it.trade_count, 0),
                        ])}
                      />
                    )}
                  </CardContent>
                </Card>
              )}

              {module === "regime" && (
                <div className="grid gap-4 xl:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Market regime</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {regimeQ.isLoading ? (
                        <DeskSkeleton rows={3} />
                      ) : (
                        <DeskTable
                          columns={["Field", "Value"]}
                          rows={[
                            ["Status", str(asRecord(regimeQ.data).status)],
                            ["Primary", str(asRecord(asRecord(regimeQ.data).regime).primary)],
                            [
                              "Regimes",
                              asList(asRecord(asRecord(regimeQ.data).regime).regimes).join(", ") ||
                                "—",
                            ],
                          ]}
                        />
                      )}
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Strategy regime fit</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <DeskTable
                        columns={["Strategy", "Fit", "Overlap"]}
                        rows={asList(asRecord(regimeQ.data).fits)
                          .map(asRecord)
                          .map((f) => [
                            str(f.strategy_key),
                            f.suitable ? "yes" : "no",
                            asList(f.overlap).join(", ") || "—",
                          ])}
                      />
                    </CardContent>
                  </Card>
                </div>
              )}

              {module === "params" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-sm">
                      <ShieldCheck className="h-4 w-4" /> Parameter laboratory
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-xs text-[var(--fg-subtle)]">
                      Sandbox only — production defaults remain unchanged (
                      {params.production_defaults_unchanged === false
                        ? "check failed"
                        : "confirmed"}
                      ).
                    </p>
                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                      {(
                        [
                          ["ATR", atrPeriod, setAtrPeriod],
                          ["EMA fast", emaFast, setEmaFast],
                          ["RSI", rsiPeriod, setRsiPeriod],
                          ["SL distance", slDist, setSlDist],
                          ["TP distance", tpDist, setTpDist],
                        ] as const
                      ).map(([label, val, setVal]) => (
                        <div key={label}>
                          <label className="text-[11px] text-[var(--fg-muted)]">
                            {label}
                          </label>
                          <Input
                            className="h-8 font-mono text-xs"
                            value={val}
                            onChange={(e) => setVal(e.target.value)}
                          />
                        </div>
                      ))}
                    </div>
                    <Button
                      size="sm"
                      onClick={() => saveParams.mutate()}
                      disabled={saveParams.isPending}
                    >
                      Save sandbox
                    </Button>
                  </CardContent>
                </Card>
              )}

              {module === "paper" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Paper performance</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {paperQ.isLoading ? (
                      <DeskSkeleton rows={4} />
                    ) : (
                      <DeskTable
                        columns={["Period", "Signals", "Ideas", "Waits", "Sim PnL"]}
                        rows={["daily", "weekly", "monthly", "annual"].map((k) => {
                          const row = asRecord(paper[k]);
                          return [
                            k,
                            row.signals == null ? "—" : String(row.signals),
                            row.trade_ideas == null ? "—" : String(row.trade_ideas),
                            row.waits == null ? "—" : String(row.waits),
                            row.realized_sim_pnl == null
                              ? "—"
                              : formatNumber(num(row.realized_sim_pnl), 2),
                          ];
                        })}
                      />
                    )}
                  </CardContent>
                </Card>
              )}

              {module === "review" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">AI research review</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {!review.status ? (
                      <DeskEmpty
                        icon={Sparkles}
                        title="No review yet"
                        description="Run validation to generate an advisory AI research review"
                      />
                    ) : str(review.status) === "unavailable" ? (
                      <DeskEmpty
                        icon={Sparkles}
                        title="Review unavailable"
                        description={str(review.reason, "Insufficient metrics")}
                      />
                    ) : (
                      <DeskTable
                        columns={["Topic", "Notes"]}
                        rows={[
                          ["Succeeds", asList(review.strengths).slice(0, 3).join(" · ") || "—"],
                          ["Fails", asList(review.weaknesses).slice(0, 3).join(" · ") || "—"],
                          ["Overfit", asList(review.overfitting).slice(0, 2).join(" · ") || "—"],
                          ["Suitability", asList(review.market_suitability).slice(0, 2).join(" · ") || "—"],
                          ["Risk", asList(review.risk).slice(0, 2).join(" · ") || "—"],
                        ]}
                      />
                    )}
                  </CardContent>
                </Card>
              )}

              {module === "reports" && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Research report</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {reportQ.isLoading ? (
                      <DeskSkeleton rows={4} />
                    ) : str(report.status) === "unavailable" ? (
                      <DeskEmpty
                        icon={FileText}
                        title="No report"
                        description={str(report.reason, "Validate a strategy first")}
                      />
                    ) : (
                      <>
                        <p className="mb-2 text-sm text-[var(--fg)]">{str(report.title)}</p>
                        <DeskTable
                          columns={["Section", "Summary"]}
                          rows={[
                            [
                              "Performance",
                              JSON.stringify(asRecord(asRecord(report.sections).performance)).slice(
                                0,
                                120,
                              ),
                            ],
                            [
                              "Risk",
                              JSON.stringify(asRecord(asRecord(report.sections).risk)).slice(0, 120),
                            ],
                            [
                              "Recommendations",
                              asList(asRecord(report.sections).recommendations)
                                .slice(0, 2)
                                .join(" · "),
                            ],
                          ]}
                        />
                        <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
                          {str(report.disclaimer)}
                        </p>
                      </>
                    )}
                  </CardContent>
                </Card>
              )}

              {module === "promotion" && (
                <div className="grid gap-4 xl:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Promotion criteria</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <DeskTable
                        columns={["Criterion", "Value"]}
                        rows={Object.entries(criteria).map(([k, v]) => [
                          k,
                          v == null ? "—" : String(v),
                        ])}
                      />
                      <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
                        Eligibility is advisory. Decision Engine remains the gatekeeper and is not
                        modified.
                      </p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Evaluate eligibility</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <Input
                        className="h-8 font-mono text-xs"
                        value={strategyKey}
                        onChange={(e) => setStrategyKey(e.target.value)}
                      />
                      <Button
                        size="sm"
                        onClick={() => promote.mutate()}
                        disabled={promote.isPending}
                      >
                        Evaluate for Decision Engine
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </PageMotion>
      )}
    </div>
  );
}

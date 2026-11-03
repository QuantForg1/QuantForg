"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Copy, Play, Trash2, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { strategyApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";

type Mode = "ict" | "engine";

type RuleFlags = {
  liquidity_sweep_bullish: boolean;
  liquidity_sweep_bearish: boolean;
  order_block_bullish: boolean;
  order_block_bearish: boolean;
  fvg_bullish: boolean;
  fvg_bearish: boolean;
  has_structure: boolean;
  has_liquidity: boolean;
  has_order_blocks: boolean;
  has_fvgs: boolean;
};

const defaultRules: RuleFlags = {
  liquidity_sweep_bullish: false,
  liquidity_sweep_bearish: false,
  order_block_bullish: false,
  order_block_bearish: false,
  fvg_bullish: false,
  fvg_bearish: false,
  has_structure: true,
  has_liquidity: true,
  has_order_blocks: true,
  has_fvgs: true,
};

const defaultCustomRules = JSON.stringify(
  {
    rules: [
      {
        when: { indicator: "rsi", op: "<=", value: 30 },
        action: "BUY",
        reason: "Custom RSI oversold rule",
      },
      {
        when: { indicator: "rsi", op: ">=", value: 70 },
        action: "SELL",
        reason: "Custom RSI overbought rule",
      },
    ],
    rsi_period: 14,
    sma_period: 20,
  },
  null,
  2,
);

export default function StrategyPage() {
  const qc = useQueryClient();
  const [mode, setMode] = useState<Mode>("engine");
  const [symbol, setSymbol] = useState(TRADING_SYMBOL);
  const [timeframe, setTimeframe] = useState("H1");
  const [structureBias, setStructureBias] = useState("up");
  const [rules, setRules] = useState<RuleFlags>(defaultRules);
  const [lastResult, setLastResult] = useState<Record<string, unknown> | null>(null);
  const [strategyKey, setStrategyKey] = useState("rsi");
  const [paramsJson, setParamsJson] = useState("{}");
  const [customRulesJson, setCustomRulesJson] = useState(defaultCustomRules);
  const [maxTrades, setMaxTrades] = useState("5");
  const [dailyLoss, setDailyLoss] = useState("3");
  const [maxExposure, setMaxExposure] = useState("20");
  const [configTab, setConfigTab] = useState<
    "parameters" | "logic" | "entry" | "filters" | "risk"
  >("parameters");

  const signalsQ = useQuery({
    queryKey: ["strategy-signals"],
    queryFn: strategyApi.signals,
    retry: false,
  });

  const catalogQ = useQuery({
    queryKey: ["strategy-catalog"],
    queryFn: strategyApi.catalog,
    retry: false,
  });

  const portfolioQ = useQuery({
    queryKey: ["strategy-portfolio"],
    queryFn: strategyApi.portfolio,
    retry: false,
  });

  const evaluate = useMutation({
    mutationFn: strategyApi.evaluate,
    onSuccess: async (data) => {
      setLastResult(asRecord(data));
      toast.success(`Decision: ${str(asRecord(data).decision)}`);
      await qc.invalidateQueries({ queryKey: ["strategy-signals"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Evaluate failed"),
  });

  const engineRun = useMutation({
    mutationFn: strategyApi.engineRun,
    onSuccess: (data) => {
      setLastResult(asRecord(data));
      const sig = asRecord(asRecord(data).signal);
      toast.success(`Signal: ${str(sig.action)}`);
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Engine run failed"),
  });

  const engineValidate = useMutation({
    mutationFn: strategyApi.engineValidate,
    onSuccess: (data) => {
      const r = asRecord(data);
      if (r.valid) toast.success("Params valid");
      else toast.error(`Invalid: ${asList(r.errors).join(", ")}`);
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Validation failed"),
  });

  const signals = asList(signalsQ.data).map(asRecord);
  const catalog = asList(asRecord(catalogQ.data).items).map(asRecord);

  const templates = useMemo(
    () => [
      {
        id: "ict-bull",
        name: "ICT Bullish Sweep",
        bias: "up",
        patch: {
          liquidity_sweep_bullish: true,
          order_block_bullish: true,
          fvg_bullish: true,
        },
      },
      {
        id: "ict-bear",
        name: "ICT Bearish Sweep",
        bias: "down",
        patch: {
          liquidity_sweep_bearish: true,
          order_block_bearish: true,
          fvg_bearish: true,
        },
      },
      {
        id: "range",
        name: "Range Watch",
        bias: "range",
        patch: { has_structure: true, has_liquidity: false },
      },
    ],
    [],
  );

  const selectedPlugin = catalog.find((c) => str(c.key) === strategyKey);

  const buildParams = (): Record<string, unknown> => {
    if (strategyKey === "custom_rules") {
      return JSON.parse(customRulesJson) as Record<string, unknown>;
    }
    const raw = paramsJson.trim() || "{}";
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    if (selectedPlugin && Object.keys(parsed).length === 0) {
      return asRecord(selectedPlugin.default_params);
    }
    return parsed;
  };

  const runIct = () => {
    evaluate.mutate({
      request_id: `ui-${Date.now()}`,
      symbol,
      timeframe: timeframe.toLowerCase(),
      market_open: true,
      structure_bias: structureBias,
      ...rules,
      check_risk: true,
    });
  };

  const runEngine = () => {
    let params: Record<string, unknown>;
    try {
      params = buildParams();
    } catch {
      toast.error("Invalid JSON in parameters / rules");
      return;
    }
    engineRun.mutate({
      strategy_key: strategyKey,
      symbol,
      timeframe,
      bars: [],
      use_mt5_bars: true,
      mt5_bar_count: 200,
      params,
      session: "unknown",
      market_state: "unknown",
      limits: {
        max_risk_pct: 1,
        max_trades: Number(maxTrades) || 5,
        daily_loss_pct: Number(dailyLoss) || 3,
        max_exposure_pct: Number(maxExposure) || 20,
        max_correlation: 0.8,
      },
    });
  };

  const validateEngine = () => {
    let params: Record<string, unknown>;
    try {
      params = buildParams();
    } catch {
      toast.error("Invalid JSON in parameters / rules");
      return;
    }
    engineValidate.mutate({ strategy_key: strategyKey, params });
  };

  const toggle = (key: keyof RuleFlags) =>
    setRules((r) => ({ ...r, [key]: !r[key] }));

  const signalBlock = lastResult ? asRecord(lastResult.signal) : null;
  const explanations = signalBlock
    ? asList(signalBlock.explanations).map(asRecord)
    : [];

  return (
    <div>
      <PageHeader
        title="Strategies"
        description={`Configure and evaluate modules for ${symbol}. Parameters stay advisory until risk and OMS gates pass — Evaluate never bypasses live safeguards.`}
        actions={
          <>
            <Button
              size="sm"
              variant={mode === "engine" ? "default" : "secondary"}
              onClick={() => setMode("engine")}
            >
              TA Engine
            </Button>
            <Button
              size="sm"
              variant={mode === "ict" ? "default" : "secondary"}
              onClick={() => setMode("ict")}
            >
              ICT Runtime
            </Button>
            <Button
              size="sm"
              onClick={mode === "engine" ? runEngine : runIct}
              disabled={evaluate.isPending || engineRun.isPending}
            >
              <Play className="h-3.5 w-3.5" /> Evaluate
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                void (async () => {
                  try {
                    await navigator.clipboard.writeText(
                      JSON.stringify(
                        mode === "engine"
                          ? { strategyKey, symbol, timeframe, paramsJson, customRulesJson }
                          : { symbol, timeframe, structureBias, rules },
                        null,
                        2,
                      ),
                    );
                    toast.success("Strategy snapshot copied");
                  } catch {
                    toast.error("Clipboard unavailable");
                  }
                })();
              }}
            >
              <Copy className="h-3.5 w-3.5" /> Duplicate
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setRules(defaultRules);
                setLastResult(null);
                setParamsJson("{}");
                setCustomRulesJson(defaultCustomRules);
                toast.message("Builder reset");
              }}
            >
              <Trash2 className="h-3.5 w-3.5" /> Delete
            </Button>
          </>
        }
      />

      {mode === "engine" ? (
        <div className="space-y-4">
          <section aria-labelledby="strategy-grid-heading">
            <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
              <h2 id="strategy-grid-heading" className="text-sm font-semibold">
                Strategy Catalog
              </h2>
              <p className="text-xs text-[var(--fg-muted)]">
                {catalog.length > 0
                  ? `${catalog.length} strategies loaded for ${symbol}`
                  : "Strategies load from the live catalogue"}
              </p>
            </div>
            {catalogQ.isLoading ? (
              <DeskSkeleton rows={4} />
            ) : catalogQ.isError ? (
              <DeskError
                message="Catalog unavailable."
                onRetry={() => catalogQ.refetch()}
              />
            ) : catalog.length === 0 ? (
              <DeskEmpty
                icon={Sparkles}
                title="No strategies"
                description="The strategy catalogue returned no rows."
              />
            ) : (
              <ul className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6">
                {catalog.map((c) => {
                  const key = str(c.key);
                  const selected = strategyKey === key;
                  return (
                    <li key={key}>
                      <button
                        type="button"
                        className={`flex h-full w-full flex-col rounded-[var(--radius-os)] border px-3 py-3 text-left transition ${
                          selected
                            ? "border-[var(--accent)] bg-[var(--accent-soft)] shadow-[0_0_0_1px_color-mix(in_srgb,var(--accent)_35%,transparent)]"
                            : "border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] hover:border-[var(--accent)]/40"
                        }`}
                        onClick={() => {
                          setStrategyKey(key);
                          setParamsJson(
                            JSON.stringify(asRecord(c.default_params), null, 2),
                          );
                        }}
                      >
                        <span
                          className={`mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl ${
                            selected
                              ? "bg-[var(--accent)] text-[var(--accent-fg)]"
                              : "bg-[var(--accent-soft)] text-[var(--accent)]"
                          }`}
                        >
                          <Sparkles className="h-4 w-4" aria-hidden />
                        </span>
                        <span className="text-sm font-semibold text-[var(--fg)]">
                          {str(c.name)}
                        </span>
                        <span className="mt-1 text-xs text-[var(--fg-subtle)]">
                          {str(c.category) || key}
                        </span>
                        <span className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-medium text-[var(--success)]">
                          <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" />
                          Active
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
          <Card>
            <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>
                  {str(selectedPlugin?.name) ||
                    (strategyKey === "custom_rules" ? "Rule Tree" : "Parameters")}
                </CardTitle>
                <p className="mt-1 text-xs text-[var(--fg-muted)]">
                  {str(selectedPlugin?.description) ||
                    "Select a strategy. Bars load from MT5 when connected — never fabricated."}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge tone="success">Active</Badge>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setParamsJson("{}");
                    setCustomRulesJson(defaultCustomRules);
                    toast.message("Parameters reset");
                  }}
                >
                  Reset
                </Button>
                <Button
                  className="qf-btn-hot border-0"
                  size="sm"
                  onClick={runEngine}
                  disabled={engineRun.isPending}
                >
                  Save Changes
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div
                className="flex flex-wrap gap-1 border-b border-[var(--border)] pb-2"
                role="tablist"
                aria-label="Strategy configuration"
              >
                {(
                  [
                    ["parameters", "Parameters"],
                    ["logic", "Logic & Rules"],
                    ["entry", "Entry & Exit"],
                    ["filters", "Filters"],
                    ["risk", "Risk Integration"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    aria-selected={configTab === id}
                    onClick={() => setConfigTab(id)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                      configTab === id
                        ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                        : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {configTab === "parameters" ? (
                <textarea
                  className="min-h-[220px] w-full rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] p-3 font-mono text-xs text-[var(--fg)]"
                  value={
                    strategyKey === "custom_rules" ? customRulesJson : paramsJson
                  }
                  onChange={(e) =>
                    strategyKey === "custom_rules"
                      ? setCustomRulesJson(e.target.value)
                      : setParamsJson(e.target.value)
                  }
                />
              ) : (
                <div className="min-h-[220px] rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg)]/35 p-4 text-sm text-[var(--fg-muted)]">
                  {configTab === "logic" ? (
                    <p>
                      Logic follows the selected catalog plugin and any custom rules JSON.
                      Orders still require risk and OMS approval.
                    </p>
                  ) : null}
                  {configTab === "entry" ? (
                    <p>
                      Entry and exit levels come from live evaluate / MT5 bars — never sample
                      prices. Run Evaluate to refresh.
                    </p>
                  ) : null}
                  {configTab === "filters" ? (
                    <p>
                      Symbol {symbol} · timeframe {timeframe}. Filters stay advisory until the
                      risk engine confirms.
                    </p>
                  ) : null}
                  {configTab === "risk" ? (
                    <ul className="space-y-2">
                      <li>Max trades: {maxTrades}</li>
                      <li>Daily loss %: {dailyLoss}</li>
                      <li>Max exposure %: {maxExposure}</li>
                      <li>Live path requires EXECUTION_ENABLED and owned broker session.</li>
                    </ul>
                  ) : null}
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" onClick={validateEngine}>
                  Validate
                </Button>
                <Button
                  size="sm"
                  onClick={runEngine}
                  disabled={engineRun.isPending}
                >
                  <Play className="h-3.5 w-3.5" /> Run (MT5 bars)
                </Button>
              </div>
              {signalBlock ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg-elevated)] p-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="accent">{str(signalBlock.action)}</Badge>
                    <span className="text-xs text-[var(--fg-subtle)]">
                      conf {(numish(signalBlock.confidence) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="mt-2 text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                    Explainability
                  </p>
                  <ul className="mt-1 space-y-2 text-xs text-[var(--fg-muted)]">
                    {explanations.length === 0 ? (
                      asList(signalBlock.reasons).map((r, i) => (
                        <li key={i}>• {String(r)}</li>
                      ))
                    ) : (
                      explanations.map((e, i) => (
                        <li key={i} className="rounded-md border border-[var(--border)] p-2">
                          <p className="font-medium text-[var(--fg)]">{str(e.reason)}</p>
                          <p>
                            {str(e.indicator)} · threshold {str(e.threshold)}
                            {e.value ? ` · value ${str(e.value)}` : ""}
                          </p>
                          <p className="text-[var(--fg-subtle)]">{str(e.market_context)}</p>
                        </li>
                      ))
                    )}
                  </ul>
                  {lastResult?.risk ? (
                    <p className="mt-2 text-xs text-[var(--fg-subtle)]">
                      Risk:{" "}
                      {asRecord(lastResult.risk).allowed ? "allowed" : "blocked"} ·{" "}
                      {asList(asRecord(lastResult.risk).reasons)
                        .slice(0, 2)
                        .map(String)
                        .join("; ")}
                    </p>
                  ) : null}
                </motion.div>
              ) : null}
            </CardContent>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Strategy Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex justify-between gap-3">
                  <span className="text-[var(--fg-muted)]">Type</span>
                  <span className="font-medium">
                    {str(selectedPlugin?.category) || strategyKey}
                  </span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-[var(--fg-muted)]">Market</span>
                  <span className="font-medium">{symbol}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-[var(--fg-muted)]">Timeframe</span>
                  <span className="font-medium">{timeframe}</span>
                </div>
                <p className="text-xs leading-relaxed text-[var(--fg-muted)]">
                  {str(selectedPlugin?.description) ||
                    "Strategy stays advisory until risk and OMS gates pass."}
                </p>
                <div className="grid gap-2 border-t border-[var(--border)] pt-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label>Symbol</Label>
                    <Input
                      value={symbol}
                      onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Timeframe</Label>
                    <Input
                      value={timeframe}
                      onChange={(e) => setTimeframe(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Max trades</Label>
                    <Input value={maxTrades} onChange={(e) => setMaxTrades(e.target.value)} />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Daily loss %</Label>
                    <Input value={dailyLoss} onChange={(e) => setDailyLoss(e.target.value)} />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Performance</CardTitle>
                <p className="text-xs text-[var(--fg-muted)]">
                  Live evaluate result only — never sample backtests.
                </p>
              </CardHeader>
              <CardContent>
                {signalBlock ? (
                  <dl className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <dt className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                        Last action
                      </dt>
                      <dd className="mt-1 font-semibold">{str(signalBlock.action)}</dd>
                    </div>
                    <div>
                      <dt className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                        Confidence
                      </dt>
                      <dd className="mt-1 font-semibold tabular">
                        {(numish(signalBlock.confidence) * 100).toFixed(0)}%
                      </dd>
                    </div>
                    <div className="col-span-2">
                      <dt className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                        Risk gate
                      </dt>
                      <dd className="mt-1 text-[var(--fg-muted)]">
                        {lastResult?.risk
                          ? asRecord(lastResult.risk).allowed
                            ? "Allowed"
                            : "Blocked"
                          : "—"}
                      </dd>
                    </div>
                  </dl>
                ) : (
                  <p className="text-sm text-[var(--fg-muted)]">
                    Run Evaluate to load live performance for this strategy.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Strategy Rules</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="space-y-2 text-sm">
                  {[
                    `Only trade ${symbol}`,
                    `Use timeframe ${timeframe}`,
                    `Max trades ${maxTrades}`,
                    `Daily loss ceiling ${dailyLoss}%`,
                    `Max exposure ${maxExposure}%`,
                    "Orders still pass risk and OMS gates",
                  ].map((rule, i) => (
                    <li key={rule} className="flex items-start gap-2">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--success)]" />
                      <span>
                        <span className="text-[var(--fg-subtle)]">{i + 1}. </span>
                        {rule}
                      </span>
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          </div>
          </div>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[0.85fr_1.4fr_0.95fr]">
          <Card>
            <CardHeader>
              <CardTitle>Strategy Library</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {templates.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className="w-full rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5 text-left transition hover:border-[var(--accent)]/40"
                  onClick={() => {
                    setStructureBias(t.bias);
                    setRules((r) => ({ ...r, ...t.patch }));
                  }}
                >
                  <p className="text-sm font-medium text-[var(--fg)]">{t.name}</p>
                  <p className="text-xs text-[var(--fg-subtle)]">Bias · {t.bias}</p>
                </button>
              ))}
              <div className="border-t border-[var(--border)] pt-3">
                <p className="mb-2 text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                  Recent signals
                </p>
                {signalsQ.isLoading ? (
                  <DeskSkeleton rows={2} />
                ) : signalsQ.isError ? (
                  <DeskError
                    message="Signals unavailable."
                    onRetry={() => signalsQ.refetch()}
                  />
                ) : signals.length === 0 ? (
                  <DeskEmpty
                    icon={Sparkles}
                    title="No signals yet"
                    description="Evaluate a strategy to populate the library."
                  />
                ) : (
                  <ul className="space-y-2">
                    {signals.slice(0, 8).map((s) => (
                      <li
                        key={str(s.id)}
                        className="rounded-md border border-[var(--border)] px-2.5 py-2 text-xs"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{str(s.symbol)}</span>
                          <Badge tone={s.rejected ? "danger" : "success"}>
                            {str(s.direction)}
                          </Badge>
                        </div>
                        <p className="mt-1 text-[var(--fg-subtle)]">
                          conf {(numish(s.confidence) * 100).toFixed(0)}% ·{" "}
                          {str(s.timeframe)}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Visual Rule Builder</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-2 sm:grid-cols-2">
                {(Object.keys(rules) as (keyof RuleFlags)[]).map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => toggle(key)}
                    className={`rounded-[var(--radius-os)] border px-3 py-3 text-left text-sm transition ${
                      rules[key]
                        ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--fg)]"
                        : "border-[var(--border)] bg-[var(--surface-2)] text-[var(--fg-muted)]"
                    }`}
                  >
                    <span className="block font-medium">
                      {key.replaceAll("_", " ")}
                    </span>
                    <span className="text-xs opacity-70">
                      {rules[key] ? "Armed" : "Off"}
                    </span>
                  </button>
                ))}
              </div>
              {lastResult && lastResult.decision ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="mt-4 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg-elevated)] p-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="accent">{str(lastResult.decision)}</Badge>
                    <span className="text-xs text-[var(--fg-subtle)]">
                      {str(lastResult.symbol)} · {str(lastResult.timeframe)}
                    </span>
                  </div>
                  <ul className="mt-2 space-y-1 text-xs text-[var(--fg-muted)]">
                    {asList(lastResult.reasons)
                      .slice(0, 6)
                      .map((r, i) => (
                        <li key={i}>• {String(r)}</li>
                      ))}
                  </ul>
                </motion.div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Parameters</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1.5">
                <Label>Symbol</Label>
                <Input
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Timeframe</Label>
                <Input
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Structure bias</Label>
                <Input
                  value={structureBias}
                  onChange={(e) => setStructureBias(e.target.value)}
                />
              </div>
              <Button className="w-full" onClick={runIct} disabled={evaluate.isPending}>
                Save & Evaluate
              </Button>
              <p className="text-xs text-[var(--fg-subtle)]">
                Uses existing <code>/strategy/evaluate</code> — no mock responses.
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function numish(v: unknown) {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
}

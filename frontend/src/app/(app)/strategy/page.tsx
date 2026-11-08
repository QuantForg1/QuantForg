"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Copy, Play, Trash2, Sparkles } from "lucide-react";
import { strategyCardFromRecord } from "@/components/strategies/strategy-card";
import { StrategyConfigPanel } from "@/components/strategies/strategy-config-panel";
import { StrategySidePanels } from "@/components/strategies/strategy-side-panels";
import { serializeParams } from "@/components/strategies/strategy-utils";
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
import {
  AUTONOMOUS_QUICK_SYMBOLS,
  displayTradingSymbol,
  tradingInstrumentDescription,
  TRADING_SYMBOL,
} from "@/lib/trading/gold-only";

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
  const [maxExposure] = useState("20");
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

  const onSelectStrategy = (key: string, defaultParams: Record<string, unknown>) => {
    setStrategyKey(key);
    setParamsJson(serializeParams(defaultParams));
  };

  return (
    <div>
      <PageHeader
        title="Trading Strategies"
        description={`Institutional modules for ${displayTradingSymbol(symbol)} (${tradingInstrumentDescription(symbol)}). Parameters stay advisory until Risk Center and OMS gates pass — Evaluate never bypasses live safeguards.`}
        actions={
          <>
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

      <div
        className="mb-4 flex flex-wrap items-center gap-2 rounded-[var(--radius-os)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_88%,transparent)] px-3 py-2"
        role="toolbar"
        aria-label="Strategy desk mode"
      >
        <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--fg-subtle)]">
          Desk
        </span>
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
        <span className="mx-1 hidden h-5 w-px bg-[var(--border)] sm:inline-block" aria-hidden />
        <Label htmlFor="strategy-asset" className="sr-only">
          Asset
        </Label>
        <select
          id="strategy-asset"
          className="h-8 min-w-[11rem] rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-2 text-sm text-[var(--fg)]"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
        >
          {AUTONOMOUS_QUICK_SYMBOLS.map((s) => (
            <option key={s} value={s}>
              {displayTradingSymbol(s)}
            </option>
          ))}
        </select>
      </div>

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
                {catalog.map((c) =>
                  strategyCardFromRecord(c, strategyKey, onSelectStrategy),
                )}
              </ul>
            )}
          </section>

          <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
            <StrategyConfigPanel
              title={
                str(selectedPlugin?.name) ||
                (strategyKey === "custom_rules" ? "Rule Tree" : "Parameters")
              }
              subtitle={
                str(selectedPlugin?.description) ||
                "Select a strategy. Bars load from MT5 when connected — never fabricated."
              }
              configTab={configTab}
              onConfigTab={setConfigTab}
              strategyKey={strategyKey}
              paramsJson={paramsJson}
              customRulesJson={customRulesJson}
              onParamsJson={setParamsJson}
              onCustomRulesJson={setCustomRulesJson}
              defaultParams={
                selectedPlugin ? asRecord(selectedPlugin.default_params) : undefined
              }
              symbol={symbol}
              timeframe={timeframe}
              maxTrades={maxTrades}
              dailyLoss={dailyLoss}
              maxExposure={maxExposure}
              onReset={() => {
                setParamsJson("{}");
                setCustomRulesJson(defaultCustomRules);
                toast.message("Parameters reset");
              }}
              onSave={runEngine}
              savePending={engineRun.isPending}
              onValidate={validateEngine}
              onRun={runEngine}
              runPending={engineRun.isPending}
              lastResult={lastResult}
            />
            <StrategySidePanels
              strategyKey={strategyKey}
              category={str(selectedPlugin?.category)}
              description={str(selectedPlugin?.description)}
              symbol={symbol}
              timeframe={timeframe}
              maxTrades={maxTrades}
              dailyLoss={dailyLoss}
              maxExposure={maxExposure}
              onSymbol={setSymbol}
              onTimeframe={setTimeframe}
              onMaxTrades={setMaxTrades}
              onDailyLoss={setDailyLoss}
              lastResult={lastResult}
              portfolioData={portfolioQ.data}
            />
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

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
  const [symbol, setSymbol] = useState("EURUSD");
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
        title="Strategy Builder"
        description="Deterministic strategies and ICT confluence — signals only, never autonomous trading."
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
        <div className="grid gap-4 xl:grid-cols-[0.9fr_1.35fr_1fr]">
          <Card>
            <CardHeader>
              <CardTitle>Strategy Catalog</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {catalogQ.isLoading ? (
                <DeskSkeleton rows={4} />
              ) : catalogQ.isError ? (
                <DeskError
                  message="Catalog unavailable."
                  onRetry={() => catalogQ.refetch()}
                />
              ) : (
                catalog.map((c) => (
                  <button
                    key={str(c.key)}
                    type="button"
                    className={`w-full rounded-lg border px-3 py-2.5 text-left transition ${
                      strategyKey === str(c.key)
                        ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                        : "border-[var(--border)] bg-[var(--surface-2)] hover:border-[var(--accent)]/40"
                    }`}
                    onClick={() => {
                      setStrategyKey(str(c.key));
                      setParamsJson(
                        JSON.stringify(asRecord(c.default_params), null, 2),
                      );
                    }}
                  >
                    <p className="text-sm font-medium text-[var(--fg)]">{str(c.name)}</p>
                    <p className="text-xs text-[var(--fg-subtle)]">
                      {str(c.category)} · {str(c.key)}
                    </p>
                  </button>
                ))
              )}
              <div className="border-t border-[var(--border)] pt-3">
                <p className="mb-2 text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                  Allocation
                </p>
                {portfolioQ.isLoading ? (
                  <DeskSkeleton rows={1} />
                ) : (
                  <ul className="space-y-1 text-xs text-[var(--fg-muted)]">
                    {asList(asRecord(portfolioQ.data).allocations).length === 0 ? (
                      <li>No weights set — use API PUT /strategy/portfolio/allocations</li>
                    ) : (
                      asList(asRecord(portfolioQ.data).allocations)
                        .map(asRecord)
                        .map((a, i) => (
                          <li key={i}>
                            {str(a.strategy_key)} · {String(a.weight_pct)}%
                          </li>
                        ))
                    )}
                  </ul>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>
                {strategyKey === "custom_rules" ? "Rule Tree" : "Parameters"}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-xs text-[var(--fg-subtle)]">
                {str(selectedPlugin?.description) ||
                  "Select a strategy. Bars load from MT5 when connected — never fabricated."}
              </p>
              <textarea
                className="min-h-[220px] w-full rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 font-mono text-xs text-[var(--fg)]"
                value={
                  strategyKey === "custom_rules" ? customRulesJson : paramsJson
                }
                onChange={(e) =>
                  strategyKey === "custom_rules"
                    ? setCustomRulesJson(e.target.value)
                    : setParamsJson(e.target.value)
                }
              />
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
                  className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] p-3"
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

          <Card>
            <CardHeader>
              <CardTitle>Context & Risk</CardTitle>
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
                <Label>Max trades</Label>
                <Input value={maxTrades} onChange={(e) => setMaxTrades(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Daily loss %</Label>
                <Input value={dailyLoss} onChange={(e) => setDailyLoss(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Max exposure %</Label>
                <Input
                  value={maxExposure}
                  onChange={(e) => setMaxExposure(e.target.value)}
                />
              </div>
              <p className="text-xs text-[var(--fg-subtle)]">
                Live path requires <code>EXECUTION_ENABLED=true</code>. Default is paper
                trading. Engine never submits orders.
              </p>
              <p className="text-xs text-[var(--fg-subtle)]">
                Backtest / walk-forward: reuse existing{" "}
                <code>/backtests/run</code> and <code>/walkforward/run</code>.
              </p>
            </CardContent>
          </Card>
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
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5 text-left transition hover:border-[var(--accent)]/40"
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
                    className={`rounded-lg border px-3 py-3 text-left text-sm transition ${
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
                  className="mt-4 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] p-3"
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

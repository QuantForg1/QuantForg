"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Activity, BarChart2, Binary, CandlestickChart, Layers, Shield, Sparkles, TrendingUp, Waves } from "lucide-react";
import { strategyCardFromRecord } from "@/components/strategies/strategy-card";
import { ENGINE_CATALOG } from "@/components/strategies/engine-catalog";
import { StrategyBriefPanel } from "@/components/strategies/strategy-brief-panel";
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
  displayTradingSymbol,
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

export default function StrategyPage() {
  const qc = useQueryClient();
  const [mode] = useState<Mode>("engine");
  const [symbol, setSymbol] = useState(TRADING_SYMBOL);
  const [timeframe, setTimeframe] = useState("H1");
  const [structureBias, setStructureBias] = useState("up");
  const [rules, setRules] = useState<RuleFlags>(defaultRules);
  const [lastResult, setLastResult] = useState<Record<string, unknown> | null>(null);
  const [strategyKey, setStrategyKey] = useState("rsi");
  const [catalogQuery, setCatalogQuery] = useState("");
  const [catalogCategory, setCatalogCategory] = useState("all");

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

  const signals = asList(signalsQ.data).map(asRecord);
  const serverCatalog = useMemo(
    () => asList(asRecord(catalogQ.data).items).map(asRecord),
    [catalogQ.data],
  );
  const serverKeys = useMemo(
    () => new Set(serverCatalog.map((item) => str(item.key)).filter(Boolean)),
    [serverCatalog],
  );
  const catalog = useMemo(() => {
    const byKey = new Map<string, Record<string, unknown>>();
    for (const item of ENGINE_CATALOG) {
      byKey.set(item.key, { ...item, on_server: false });
    }
    for (const item of serverCatalog) {
      const key = str(item.key);
      if (!key) continue;
      byKey.set(key, { ...item, on_server: true });
    }
    return [...byKey.values()].sort((a, b) => str(a.name).localeCompare(str(b.name)));
  }, [serverCatalog]);
  const categories = useMemo(() => {
    const names = new Set<string>();
    for (const item of catalog) {
      const category = str(item.category);
      if (category) names.add(category);
    }
    return [...names].sort((a, b) => a.localeCompare(b));
  }, [catalog]);
  const visibleCatalog = useMemo(() => {
    const query = catalogQuery.trim().toLowerCase();
    return catalog.filter((item) => {
      if (catalogCategory !== "all" && str(item.category) !== catalogCategory) return false;
      if (!query) return true;
      return [str(item.name), str(item.key), str(item.category), str(item.description)]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  }, [catalog, catalogCategory, catalogQuery]);

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

  const toggle = (key: keyof RuleFlags) =>
    setRules((r) => ({ ...r, [key]: !r[key] }));

  const onSelectStrategy = (key: string) => {
    setStrategyKey(key);
    if (window.matchMedia("(max-width: 1023px)").matches) {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      document.getElementById("strategy-detail")?.scrollIntoView({
        block: "start",
        behavior: reduce ? "auto" : "smooth",
      });
    }
  };

  return (
    <div className="qf-overview mx-auto flex w-full min-w-0 max-w-[90rem] flex-col gap-8">
      <div className="flex shrink-0 items-start gap-3">
        <span className="qf-overview-icon mt-1 hidden sm:flex" aria-hidden>
          <Layers className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
      <PageHeader
        title="Strategies"
        description="The strategy catalogue. Select a card to read how it works."
        actions={null}
      />
        </div>
      </div>

      {mode === "engine" ? (
        <div className="flex flex-col gap-8">
          <ul className="grid grid-cols-2 gap-4 md:grid-cols-3">
            {[
              {
                label: "Strategies",
                hint: catalogQ.isLoading ? "Loading" : `${catalog.length} in the library`,
                icon: Layers,
              },
              {
                label: "Categories",
                hint: catalogQ.isLoading ? "Loading" : `${categories.length} strategy types`,
                icon: Sparkles,
              },
              {
                label: "Showing",
                hint: catalogQ.isLoading ? "Loading" : `${visibleCatalog.length} after filters`,
                icon: Layers,
              },
              {
                label: "Market",
                hint: displayTradingSymbol(symbol),
                icon: Sparkles,
              },
              {
                label: "Signal",
                hint: "Intention only",
                icon: Shield,
              },
              {
                label: "Risk gate",
                hint: "Still applies",
                icon: Shield,
              },
            ].map((tile) => {
              const Icon = tile.icon;
              return (
              <li key={tile.label} className="qf-overview-card flex min-h-[6.5rem] flex-col justify-between p-4">
                <span className="qf-overview-icon qf-overview-icon-sm" aria-hidden>
                  <Icon className="h-4 w-4" />
                </span>
                <span>
                  <span className="mt-3 block text-sm font-semibold text-[var(--fg)]">{tile.label}</span>
                  <span className="mt-1 block truncate text-xs text-[var(--fg-muted)]">{tile.hint}</span>
                </span>
              </li>
              );
            })}
          </ul>
          {categories.length > 0 ? (
            <div className="flex shrink-0 gap-2 overflow-x-auto pb-1 lg:hidden" role="toolbar" aria-label="Strategy categories">
              <Button
                type="button"
                size="sm"
                variant={catalogCategory === "all" ? "default" : "secondary"}
                className="min-h-11 shrink-0"
                onClick={() => setCatalogCategory("all")}
              >
                All strategies
              </Button>
              {categories.map((category) => (
                <Button
                  key={category}
                  type="button"
                  size="sm"
                  variant={catalogCategory === category ? "default" : "secondary"}
                  className="min-h-11 shrink-0 capitalize"
                  onClick={() => setCatalogCategory(category)}
                >
                  {category.replaceAll("_", " ")}
                </Button>
              ))}
            </div>
          ) : null}
          <div className="grid items-start gap-6 lg:grid-cols-[12.5rem_minmax(16rem,1fr)_20rem]">
          <nav
            className="qf-overview-panel hidden min-h-0 flex-col gap-1 overflow-y-auto p-4 lg:sticky lg:top-4 lg:flex lg:max-h-[calc(100dvh-6rem)]"
            aria-label="Strategy categories"
          >
            <p className="px-2 pb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Categories
            </p>
            <div className="grid gap-2">
              <button
                type="button"
                className={`flex min-h-11 items-center gap-2 rounded-[var(--radius-os)] px-3 text-left text-sm ${
                  catalogCategory === "all"
                    ? "bg-[var(--accent-soft)] text-[var(--fg)] ring-1 ring-[var(--accent)]"
                    : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)]"
                }`}
                aria-pressed={catalogCategory === "all"}
                onClick={() => setCatalogCategory("all")}
              >
                <Layers className="h-4 w-4 shrink-0 text-[var(--accent)]" aria-hidden />
                All strategies
              </button>
              {categories.map((category) => {
                const Icon =
                  category === "trend"
                    ? TrendingUp
                    : category === "breakout"
                      ? BarChart2
                      : category === "momentum"
                        ? Activity
                        : category === "mean_reversion"
                          ? Binary
                          : category === "price_action"
                            ? CandlestickChart
                            : category === "volume"
                              ? Waves
                              : Sparkles;
                return (
                <button
                  key={category}
                  type="button"
                  className={`flex min-h-11 items-center gap-2 rounded-[var(--radius-os)] px-3 text-left text-sm capitalize ${
                    catalogCategory === category
                      ? "bg-[var(--accent-soft)] text-[var(--fg)] ring-1 ring-[var(--accent)]"
                      : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)]"
                  }`}
                  aria-pressed={catalogCategory === category}
                  onClick={() => setCatalogCategory(category)}
                >
                  <Icon className="h-4 w-4 shrink-0 text-[var(--accent)]" aria-hidden />
                  {category.replaceAll("_", " ")}
                </button>
                );
              })}
            </div>
          </nav>
          <section aria-labelledby="strategy-grid-heading" className="flex min-w-0 flex-col gap-4">
            <div className="shrink-0">
              <h2 id="strategy-grid-heading" className="sr-only">
                Strategy catalogue
              </h2>
              <Label htmlFor="strategy-search" className="sr-only">
                Search strategies
              </Label>
              <Input
                id="strategy-search"
                value={catalogQuery}
                onChange={(event) => setCatalogQuery(event.target.value)}
                placeholder="Search strategies"
                className="h-11 w-full"
              />
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
            ) : visibleCatalog.length === 0 ? (
              <DeskEmpty
                icon={Sparkles}
                title="No matching strategies"
                description="Nothing in the catalogue matches this search or category."
              />
            ) : (
              <ul className="grid grid-cols-1 items-stretch gap-6 sm:grid-cols-2">
                {visibleCatalog.map((c) =>
                  strategyCardFromRecord(c, strategyKey, onSelectStrategy),
                )}
              </ul>
            )}
          </section>
          <div className="min-w-0 lg:sticky lg:top-4 lg:max-h-[calc(100dvh-6rem)]">
          <StrategyBriefPanel
            strategyKey={strategyKey}
            name={str(selectedPlugin?.name)}
            category={str(selectedPlugin?.category)}
            description={str(selectedPlugin?.description)}
            market={displayTradingSymbol(symbol)}
            params={selectedPlugin ? asRecord(selectedPlugin.default_params) : {}}
            onServer={serverKeys.has(strategyKey)}
          />
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

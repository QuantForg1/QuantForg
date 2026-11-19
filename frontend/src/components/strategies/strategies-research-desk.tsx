"use client";

import { createElement, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Copy, Download, FlaskConical, Layers, Plus, Rocket, Search, Star, Upload } from "lucide-react";
import { ENGINE_CATALOG } from "@/components/strategies/engine-catalog";
import { STRATEGY_BRIEFS } from "@/components/strategies/strategy-briefs";
import { strategyIconForKey } from "@/components/strategies/strategy-icons";
import { StrategyDna } from "@/components/research/strategy-dna";
import { ConfidenceTimeline } from "@/components/research/confidence-timeline";
import { EvidenceStack } from "@/components/research/evidence-stack";
import { ResearchMemory } from "@/components/research/research-memory";
import { ResearchAiReview } from "@/components/research/ai-review";
import { PromoteGate } from "@/components/research/promote-gate";
import {
  RESEARCH_STAGES,
  loadResearchLayout,
  saveResearchLayout,
  type ResearchStage,
} from "@/components/research/layout-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { LazyEquityChart } from "@/components/charts/lazy";
import {
  backtestApi,
  researchLabApi,
  strategyApi,
  walkforwardApi,
} from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, mapEquityCurve, str } from "@/lib/desk";
import { loadBarsFromMt5Gateway } from "@/lib/mt5/bars-from-gateway";
import { displayTradingSymbol, resolveTradingSymbol, TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

type WorkspaceTab =
  | "overview"
  | "research"
  | "backtest"
  | "parameters"
  | "rules"
  | "performance"
  | "versions"
  | "risk"
  | "ai"
  | "reports";

type LibraryScope = "all" | "server" | "builtin" | "favorites";

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

const FAVORITES_KEY = "qf.strategy.favorites.v1";
const TIMEFRAME = "H1";

const TABS: { id: WorkspaceTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "research", label: "Research" },
  { id: "backtest", label: "Backtest" },
  { id: "parameters", label: "Parameters" },
  { id: "rules", label: "Rules" },
  { id: "performance", label: "Performance" },
  { id: "versions", label: "Versions" },
  { id: "risk", label: "Risk Analysis" },
  { id: "ai", label: "AI Review" },
  { id: "reports", label: "Reports" },
];

const MODES = [
  { id: "explore", label: "Explore Strategies" },
  { id: "research", label: "Research Lab" },
  { id: "backtest", label: "Backtest Lab" },
  { id: "ai", label: "AI Insights" },
  { id: "mine", label: "My Strategies" },
  { id: "reports", label: "Reports" },
] as const;

type DeskMode = (typeof MODES)[number]["id"];

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

function loadFavorites(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = JSON.parse(window.localStorage.getItem(FAVORITES_KEY) || "[]") as unknown;
    return Array.isArray(raw) ? raw.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function ownedByStrategy(row: Record<string, unknown>, key: string): boolean {
  const owner = str(row.strategy_key ?? row.strategy ?? row.key, "");
  return owner.length > 0 && owner !== "—" && owner === key;
}

function scalarRows(record: Record<string, unknown> | null): { label: string; value: string }[] {
  if (!record) return [];
  const rows: { label: string; value: string }[] = [];
  for (const [key, value] of Object.entries(record)) {
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      const text = String(value).trim();
      if (text) rows.push({ label: key.replaceAll("_", " "), value: text });
    }
  }
  return rows.slice(0, 12);
}

function tabForStage(stage: ResearchStage): WorkspaceTab {
  if (stage === "backtest" || stage === "walkforward") return "backtest";
  if (stage === "risk") return "risk";
  if (stage === "ai") return "ai";
  if (stage === "promote") return "reports";
  if (stage === "idea") return "overview";
  return "research";
}

export function StrategiesResearchDesk() {
  const qc = useQueryClient();
  const [strategyKey, setStrategyKey] = useState("rsi");
  const [catalogQuery, setCatalogQuery] = useState("");
  const [catalogCategory, setCatalogCategory] = useState("all");
  const [scope, setScope] = useState<LibraryScope>("all");
  const [sortBy, setSortBy] = useState<"recommended" | "name" | "category">("recommended");
  const [mode, setMode] = useState<DeskMode>("explore");
  const [localClone, setLocalClone] = useState<string | null>(null);
  const importRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<WorkspaceTab>("overview");
  const [stage, setStage] = useState<ResearchStage>("idea");
  const [favorites, setFavorites] = useState<string[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [promoteResult, setPromoteResult] = useState<Record<string, unknown> | null>(null);
  const [aiCollapsed, setAiCollapsed] = useState(false);
  const [rules, setRules] = useState<RuleFlags>(defaultRules);
  const symbol = TRADING_SYMBOL;

  useEffect(() => {
    const saved = loadResearchLayout();
    const fromUrl = new URLSearchParams(window.location.search).get("strategy");
    if (fromUrl) setStrategyKey(fromUrl);
    else if (saved.strategyKey) setStrategyKey(saved.strategyKey);
    setStage(saved.stage);
    setTab(tabForStage(saved.stage));
    setFavorites(loadFavorites());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    const saved = loadResearchLayout();
    saveResearchLayout({ ...saved, strategyKey, stage, symbol, aiCollapsed });
    const url = new URL(window.location.href);
    url.searchParams.set("strategy", strategyKey);
    window.history.replaceState(null, "", `${url.pathname}${url.search}`);
  }, [aiCollapsed, hydrated, stage, strategyKey, symbol]);

  const catalogQ = useQuery({
    queryKey: ["strategy-catalog"],
    queryFn: strategyApi.catalog,
    retry: false,
  });
  const libraryQ = useQuery({
    queryKey: ["research-lab-library"],
    queryFn: researchLabApi.library,
    retry: false,
    staleTime: 30_000,
  });
  const dashQ = useQuery({
    queryKey: ["research-lab-dashboard", symbol],
    queryFn: () => researchLabApi.dashboard(resolveTradingSymbol(symbol)),
    retry: false,
    staleTime: 20_000,
  });
  const compareQ = useQuery({
    queryKey: ["research-lab-compare"],
    queryFn: researchLabApi.compare,
    retry: false,
    staleTime: 30_000,
  });
  const criteriaQ = useQuery({
    queryKey: ["research-lab-criteria"],
    queryFn: researchLabApi.promotionCriteria,
    retry: false,
    staleTime: 60_000,
  });
  const backtestsQ = useQuery({
    queryKey: ["backtests"],
    queryFn: backtestApi.list,
    retry: false,
    staleTime: 30_000,
  });
  const walkforwardQ = useQuery({
    queryKey: ["walkforward"],
    queryFn: walkforwardApi.list,
    retry: false,
    staleTime: 30_000,
  });
  const reportQ = useQuery({
    queryKey: ["research-lab-report", strategyKey],
    queryFn: () => researchLabApi.report(strategyKey),
    enabled: Boolean(strategyKey),
    retry: false,
  });

  const serverCatalog = useMemo(
    () => asList(asRecord(catalogQ.data).items).map(asRecord),
    [catalogQ.data],
  );
  const serverKeys = useMemo(
    () => new Set(serverCatalog.map((item) => str(item.key, "")).filter(Boolean)),
    [serverCatalog],
  );
  const catalog = useMemo(() => {
    const byKey = new Map<string, Record<string, unknown>>();
    for (const item of ENGINE_CATALOG) byKey.set(item.key, { ...item, on_server: false });
    for (const item of serverCatalog) {
      const key = str(item.key, "");
      if (key) byKey.set(key, { ...item, on_server: true });
    }
    return [...byKey.values()].sort((a, b) => str(a.name).localeCompare(str(b.name)));
  }, [serverCatalog]);
  const categories = useMemo(() => {
    const names = new Set<string>();
    for (const item of catalog) {
      const category = str(item.category, "");
      if (category) names.add(category);
    }
    return [...names].sort((a, b) => a.localeCompare(b));
  }, [catalog]);
  const visibleCatalog = useMemo(() => {
    const query = catalogQuery.trim().toLowerCase();
    return catalog.filter((item) => {
      const key = str(item.key, "");
      if (catalogCategory !== "all" && str(item.category, "") !== catalogCategory) return false;
      if (scope === "server" && item.on_server !== true) return false;
      if (scope === "builtin" && item.on_server === true) return false;
      if (scope === "favorites" && !favorites.includes(key)) return false;
      if (!query) return true;
      return [str(item.name), key, str(item.category), str(item.description)]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  }, [catalog, catalogCategory, catalogQuery, favorites, scope]);
  const libraryRows = useMemo(() => {
    const rows = [...visibleCatalog];
    rows.sort((a, b) => {
      if (sortBy === "name") return str(a.name).localeCompare(str(b.name));
      if (sortBy === "category") {
        return str(a.category).localeCompare(str(b.category)) || str(a.name).localeCompare(str(b.name));
      }
      return Number(b.on_server === true) - Number(a.on_server === true) || str(a.name).localeCompare(str(b.name));
    });
    return rows;
  }, [sortBy, visibleCatalog]);

  useEffect(() => {
    if (!hydrated || catalog.length === 0) return;
    const exists = catalog.some((item) => str(item.key, "") === strategyKey);
    if (exists) return;
    const first = libraryRows[0] ?? catalog.find((item) => item.on_server === true) ?? catalog[0];
    const key = str(first?.key, "");
    if (key) setStrategyKey(key);
  }, [catalog, hydrated, libraryRows, strategyKey]);

  useEffect(() => {
    if (!strategyKey) return;
    document.querySelector(`[data-strategy-key="${strategyKey}"]`)?.scrollIntoView({ block: "nearest" });
  }, [strategyKey, libraryRows]);

  const libraryItems = useMemo(() => asList(asRecord(libraryQ.data).items).map(asRecord), [libraryQ.data]);
  const compareItems = useMemo(() => asList(asRecord(compareQ.data).items).map(asRecord), [compareQ.data]);
  const backtests = useMemo(() => {
    const raw = backtestsQ.data;
    return asList(asRecord(raw).items ?? asRecord(raw).backtests ?? raw).map(asRecord);
  }, [backtestsQ.data]);
  const walkforwards = useMemo(() => {
    const raw = walkforwardQ.data;
    return asList(asRecord(raw).items ?? asRecord(raw).results ?? raw).map(asRecord);
  }, [walkforwardQ.data]);

  const selected = catalog.find((item) => str(item.key, "") === strategyKey) ?? null;
  const onServer = serverKeys.has(strategyKey);
  const libraryItem = libraryItems.find((item) => str(item.strategy_key ?? item.key, "") === strategyKey) ?? null;
  const catalogItem = serverCatalog.find((item) => str(item.key, "") === strategyKey) ?? selected;
  const matchedBacktest = backtests.find((row) => ownedByStrategy(row, strategyKey)) ?? null;
  const matchedWalk = walkforwards.find((row) => ownedByStrategy(row, strategyKey)) ?? null;
  const dash = dashQ.data ? asRecord(dashQ.data) : null;
  const paper = dash ? asRecord(dash.paper) : null;
  const regime = dash ? asRecord(dash.regime) : null;
  const criteria = asRecord(asRecord(criteriaQ.data).criteria);
  const curve = mapEquityCurve(matchedBacktest?.equity_curve);
  const brief = STRATEGY_BRIEFS[strategyKey];
  const verified = selected != null && (selected.verified === true || str(selected.status, "").toLowerCase() === "verified");

  const engineRun = useMutation({ mutationFn: strategyApi.engineRun });
  const evaluate = useMutation({
    mutationFn: strategyApi.evaluate,
    onSuccess: (data) => toast.success(`Decision: ${str(asRecord(data).decision)}`),
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Evaluate failed"),
  });
  const validateMut = useMutation({
    mutationFn: () => researchLabApi.validate({ strategy_key: strategyKey, symbol: resolveTradingSymbol(symbol) }),
    onSuccess: (data) => {
      setValidation(asRecord(data));
      setStage("ai");
      setTab("ai");
      toast.success("Validation complete");
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Validate failed"),
  });
  const promoteMut = useMutation({
    mutationFn: () => researchLabApi.promote({ strategy_key: strategyKey }),
    onSuccess: (data) => {
      setPromoteResult(asRecord(data));
      setStage("promote");
      setTab("reports");
      toast.success("Promotion evaluated");
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Promote evaluate failed"),
  });
  const backtestRun = useMutation({
    mutationFn: backtestApi.run,
    onSuccess: async () => {
      toast.success("Backtest completed");
      await qc.invalidateQueries({ queryKey: ["backtests"] });
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Backtest failed"),
  });
  const walkRun = useMutation({
    mutationFn: walkforwardApi.run,
    onSuccess: async () => {
      toast.success("Walk-forward run finished");
      await qc.invalidateQueries({ queryKey: ["walkforward"] });
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Walk-forward failed"),
  });

  const selectStrategy = (key: string) => {
    setStrategyKey(key);
    engineRun.reset();
    setTab("overview");
    setStage("idea");
  };

  const toggleFavorite = (key: string) => {
    setFavorites((current) => {
      const next = current.includes(key) ? current.filter((item) => item !== key) : [...current, key];
      window.localStorage.setItem(FAVORITES_KEY, JSON.stringify(next));
      return next;
    });
  };

  const runIntention = () => {
    if (!onServer || !selected) return;
    engineRun.mutate({
      strategy_key: strategyKey,
      symbol,
      timeframe: TIMEFRAME,
      bars: [],
      use_mt5_bars: true,
      mt5_bar_count: 200,
      params: asRecord(selected.default_params),
      session: "unknown",
      market_state: "unknown",
    });
  };

  const runBacktest = async () => {
    try {
      const bars = await loadBarsFromMt5Gateway(symbol, "M15", 200);
      if (!bars.length) {
        toast.error("No MT5 candles for this symbol — connect gateway and retry.");
        return;
      }
      backtestRun.mutate({
        request_id: `bt-${Date.now()}`,
        symbol,
        timeframe: "m15",
        initial_balance: "10000",
        bars,
        strategy_key: strategyKey,
        auto_analysis: true,
      });
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Unable to load MT5 candles");
    }
  };

  const runWalkForward = async () => {
    try {
      const bars = await loadBarsFromMt5Gateway(symbol, "M15", 240);
      if (!bars.length) {
        toast.error("No MT5 candles for this symbol — connect gateway and retry.");
        return;
      }
      walkRun.mutate({
        request_id: `wf-${Date.now()}`,
        symbol,
        timeframe: "m15",
        bars,
        strategy_key: strategyKey,
        in_sample_bars: 40,
        out_of_sample_bars: 20,
        step_bars: 20,
        optimize_params: true,
      });
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Unable to load MT5 candles");
    }
  };

  const onStage = useCallback((next: ResearchStage) => {
    setStage(next);
    setTab(tabForStage(next));
  }, []);

  const openMode = (next: DeskMode) => {
    setMode(next);
    if (next === "explore") {
      setScope("all");
      setTab("overview");
    } else if (next === "research") setTab("research");
    else if (next === "backtest") setTab("backtest");
    else if (next === "ai") setTab("ai");
    else if (next === "mine") {
      setScope("server");
      setTab("overview");
    } else setTab("reports");
  };

  const readImport = async (file: File) => {
    try {
      const parsed = JSON.parse(await file.text()) as Record<string, unknown>;
      const key = str(parsed.strategy_key ?? parsed.key, "");
      if (!key || !catalog.some((item) => str(item.key, "") === key)) {
        toast.error("That file does not match a strategy in the catalogue.");
        return;
      }
      selectStrategy(key);
      toast.success("Opened the matching catalogue strategy. The file was not uploaded.");
    } catch {
      toast.error("Could not read that strategy file.");
    }
  };

  const signal = asRecord(asRecord(engineRun.data).signal);
  const intention = engineRun.isSuccess ? str(signal.action, "") : "";
  const serverCount = catalog.filter((item) => item.on_server === true).length;
  const params = asRecord(selected?.default_params);
  const eligible = Boolean(
    promoteResult &&
      (promoteResult.eligible_for_decision_engine || promoteResult.eligible || promoteResult.passed),
  );
  const evidenceCount = backtests.length + walkforwards.length + compareItems.length;

  return (
    <div className="qf-sr-desk flex h-full min-h-0 w-full flex-col overflow-hidden">
      <header className="shrink-0 border-b border-[var(--border)] px-3 py-3 sm:px-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <span className="qf-overview-icon hidden sm:flex" aria-hidden>
              <FlaskConical className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <h1 className="text-xl font-semibold tracking-tight text-[var(--fg)] sm:text-2xl">Strategies &amp; Research</h1>
              <p className="mt-0.5 max-w-3xl text-sm text-[var(--fg-muted)]">
                Discover, research, validate, and backtest strategies in one place. Nothing here places an order or activates live trading.
              </p>
            </div>
          </div>
          <div className="flex shrink-0 flex-nowrap items-center gap-2">
            <Button type="button" variant="secondary" className="h-10 whitespace-nowrap px-3" onClick={() => { setTab("rules"); setMode("explore"); }}>
              Strategy Builder
            </Button>
            <Button type="button" variant="secondary" className="h-10 whitespace-nowrap px-3" onClick={() => importRef.current?.click()}>
              <Upload className="mr-1.5 h-4 w-4" aria-hidden />
              Import Strategy
            </Button>
            <input
              ref={importRef}
              type="file"
              accept="application/json,.json"
              className="sr-only"
              aria-label="Import strategy file"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) void readImport(file);
              }}
            />
            <Button
              type="button"
              className="h-10 whitespace-nowrap px-3.5"
              onClick={() => {
                if (catalog.some((item) => str(item.key, "") === "custom_rules")) selectStrategy("custom_rules");
                setTab("rules");
                setMode("explore");
              }}
            >
              <Plus className="mr-1.5 h-4 w-4" aria-hidden />
              Create Strategy
            </Button>
          </div>
        </div>
        <div className="mt-3 flex gap-2 overflow-x-auto" role="tablist" aria-label="Strategies and research modes">
          {MODES.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={mode === item.id}
              className={cn(
                "min-h-11 shrink-0 rounded-full px-3 text-xs font-semibold",
                mode === item.id ? "bg-[var(--accent)] text-[var(--accent-fg)]" : "bg-[var(--surface-2)] text-[var(--fg-muted)]",
              )}
              onClick={() => openMode(item.id)}
            >
              {item.label}
              {item.id === "mine" ? ` ${serverCount}` : ""}
            </button>
          ))}
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 grid-rows-[minmax(14rem,38vh)_minmax(0,1fr)] xl:grid-cols-[22rem_minmax(0,1fr)] xl:grid-rows-1">
        <section className="flex min-h-0 min-w-0 flex-col border-b border-[var(--border)] xl:border-b-0 xl:border-r" aria-label="Strategy library">
          <div className="shrink-0 space-y-3 p-3">
            <div>
              <h2 className="text-sm font-semibold text-[var(--fg)]">Strategy Library</h2>
              <p className="text-xs text-[var(--fg-muted)]">Catalogue strategies. {libraryRows.length} shown.</p>
            </div>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]" aria-hidden />
              <Input
                value={catalogQuery}
                onChange={(event) => setCatalogQuery(event.target.value)}
                placeholder="Search strategies..."
                aria-label="Search strategies"
                className="h-11 pl-9"
              />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <select className="h-11 min-w-0 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] px-2 text-xs text-[var(--fg)]" aria-label="All Markets" value={displayTradingSymbol(symbol)} onChange={() => undefined}>
                <option>{displayTradingSymbol(symbol)}</option>
              </select>
              <select className="h-11 min-w-0 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] px-2 text-xs text-[var(--fg)]" aria-label="All Types" value={catalogCategory} onChange={(event) => setCatalogCategory(event.target.value)}>
                <option value="all">All Types</option>
                {categories.map((category) => (
                  <option key={category} value={category}>{category.replaceAll("_", " ")}</option>
                ))}
              </select>
              <select className="h-11 min-w-0 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] px-2 text-xs text-[var(--fg)]" aria-label="Sort" value={sortBy} onChange={(event) => setSortBy(event.target.value as "recommended" | "name" | "category")}>
                <option value="recommended">Recommended</option>
                <option value="name">Name</option>
                <option value="category">Type</option>
              </select>
            </div>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-3">
            {catalogQ.isLoading ? <DeskSkeleton rows={4} /> : null}
            {catalogQ.isError ? <DeskError message="Catalog unavailable." onRetry={() => catalogQ.refetch()} /> : null}
            {!catalogQ.isLoading && !catalogQ.isError && libraryRows.length === 0 ? (
              <DeskEmpty icon={Layers} title="No matching strategies" description="Nothing in the catalogue matches this search or filter." />
            ) : null}
            <ul className="grid grid-cols-1 gap-2 pb-3">
              {libraryRows.map((item) => {
                const key = str(item.key, "");
                const active = key === strategyKey;
                const icon = strategyIconForKey(key);
                return (
                  <li key={key} className="h-[4.75rem] min-w-0">
                    <button
                      type="button"
                      data-strategy-key={key}
                      aria-pressed={active}
                      className={cn(
                        "flex h-[4.75rem] w-full items-center gap-3 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-3 text-left transition duration-200 hover:border-[var(--accent)]",
                        active && "border-[var(--accent)] bg-[var(--accent-soft)]",
                      )}
                      onClick={() => selectStrategy(key)}
                    >
                      <span className="qf-overview-icon qf-overview-icon-sm shrink-0" aria-hidden>
                        {createElement(icon, { className: "h-4 w-4" })}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold text-[var(--fg)]">{str(item.name, key)}</span>
                        <span className="mt-1 flex gap-1 overflow-hidden whitespace-nowrap">
                          <Tag>{displayTradingSymbol(symbol)}</Tag>
                          <Tag>{str(item.category, "type").replaceAll("_", " ")}</Tag>
                          <Tag>{TIMEFRAME}</Tag>
                        </span>
                      </span>
                      <span className={cn(
                        "shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.08em]",
                        item.on_server === true ? "bg-[var(--accent-soft)] text-[var(--accent)]" : "bg-[var(--surface-2)] text-[var(--fg-muted)]",
                      )}>
                        {item.on_server === true ? "Active" : "Built-in"}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
          <div className="shrink-0 border-t border-[var(--border)] p-3">
            <Button
              type="button"
              variant="secondary"
              className="min-h-11 w-full"
              onClick={() => {
                if (catalog.some((item) => str(item.key, "") === "custom_rules")) selectStrategy("custom_rules");
                setTab("rules");
              }}
            >
              <Plus className="mr-1.5 h-4 w-4" aria-hidden />
              Create Custom Strategy
            </Button>
          </div>
        </section>

        <section id="strategy-detail" className="flex min-h-0 min-w-0 flex-col" aria-live="polite">
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3 sm:p-4">
          <article className="qf-overview-card grid min-h-[11rem] gap-4 p-4 sm:grid-cols-[7.5rem_minmax(0,1fr)] sm:p-5">
            <div className="flex h-full min-h-[7.5rem] items-center justify-center rounded-[var(--radius-os)] border border-[color-mix(in_srgb,var(--accent)_35%,var(--border))] bg-[var(--accent-soft)]">
              <span className="qf-overview-icon" aria-hidden>
                {createElement(strategyIconForKey(strategyKey), { className: "h-6 w-6" })}
              </span>
            </div>
            <div className="flex min-w-0 flex-col gap-3">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
                    Research Mode{verified ? " · Verified" : ""}
                  </p>
                  <h2 className="mt-1 text-xl font-semibold tracking-tight text-[var(--fg)]">{str(selected?.name, strategyKey)}</h2>
                  <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-[var(--fg-muted)]">
                    {str(selected?.description, "No description was returned for this strategy.")}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <Button type="button" variant="secondary" className="min-h-11" aria-pressed={favorites.includes(strategyKey)} onClick={() => toggleFavorite(strategyKey)}>
                    <Star className="mr-1.5 h-4 w-4" aria-hidden />
                    Favorite
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    className="min-h-11"
                    onClick={() => {
                      setLocalClone(strategyKey);
                      setTab("versions");
                      toast.success("Parameters copied on this page. Nothing was saved or sent.");
                    }}
                  >
                    <Copy className="mr-1.5 h-4 w-4" aria-hidden />
                    Clone
                  </Button>
                  <Button type="button" variant="secondary" className="min-h-11" disabled={!onServer || engineRun.isPending} onClick={runIntention}>
                    {engineRun.isPending ? "Evaluating…" : "Evaluate intention"}
                  </Button>
                  <Button type="button" className="min-h-11" disabled={!strategyKey || promoteMut.isPending} onClick={() => promoteMut.mutate()}>
                    <Rocket className="mr-1.5 h-4 w-4" aria-hidden />
                    {promoteMut.isPending ? "Checking…" : "Deploy to Robot"}
                  </Button>
                </div>
              </div>
              <p className="text-xs text-[var(--fg-muted)]">
                {displayTradingSymbol(symbol)} · {TIMEFRAME}. Deploy to Robot checks eligibility and does not activate live trading. Evaluate intention does not place an order.
              </p>
            </div>
          </article>

          <div className="flex gap-1 overflow-x-auto border-b border-[var(--border)]" role="tablist" aria-label="Strategy workspace">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={tab === item.id}
                className={cn(
                  "min-h-11 shrink-0 px-3 text-xs font-semibold",
                  tab === item.id ? "border-b-2 border-[var(--accent)] text-[var(--accent)]" : "text-[var(--fg-muted)]",
                )}
                onClick={() => setTab(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>

          {tab === "overview" || tab === "performance" ? (
            <div className="grid gap-3">
              {tab === "overview" ? (
                <>
                  <div className="grid grid-cols-1 items-stretch gap-3 xl:grid-cols-3">
                    <AlignCard title="Equity Curve (Backtest)">
                      {curve.length > 0 ? (
                        <LazyEquityChart data={curve} emptyLabel="No equity curve stored for this strategy." />
                      ) : (
                        <p className="text-sm leading-relaxed text-[var(--fg-muted)]">Not available. A curve appears when a saved backtest for this strategy includes one.</p>
                      )}
                    </AlignCard>
                    <AlignCard title="Research Workflow">
                      <ol className="flex h-full items-center gap-1 overflow-x-auto">
                        {RESEARCH_STAGES.map((item, index) => (
                          <li key={item.id} className="flex min-w-[4.25rem] flex-1 items-center gap-1">
                            <button
                              type="button"
                              aria-current={stage === item.id ? "step" : undefined}
                              className="flex w-full flex-col items-center gap-1"
                              onClick={() => onStage(item.id)}
                            >
                              <span className={cn(
                                "grid h-8 w-8 place-items-center rounded-full border text-[11px] font-semibold",
                                stage === item.id ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--accent-fg)]" : "border-[var(--border)] text-[var(--fg-muted)]",
                              )}>
                                {item.hotkey}
                              </span>
                              <span className="w-full truncate text-center text-[10px] font-medium text-[var(--fg-muted)]">{item.label}</span>
                            </button>
                            {index < RESEARCH_STAGES.length - 1 ? <span className="mb-4 h-px w-3 shrink-0 bg-[var(--border)]" aria-hidden /> : null}
                          </li>
                        ))}
                      </ol>
                    </AlignCard>
                    <AlignCard
                      title="AI Review"
                      action={<span className="rounded-full bg-[var(--accent-soft)] px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--accent)]">{validation ? "From server" : "Pending"}</span>}
                    >
                      <ResearchAiReview validation={validation} collapsed={false} onToggle={() => setTab("ai")} className="border-0 bg-transparent px-0 py-0" />
                      <Button type="button" variant="secondary" className="mt-3 min-h-11 w-full" disabled={!strategyKey || validateMut.isPending} onClick={() => validateMut.mutate()}>
                        {validateMut.isPending ? "Validating…" : "Validate"}
                      </Button>
                    </AlignCard>
                  </div>
                  <div className="grid grid-cols-1 items-stretch gap-3 xl:grid-cols-3">
                    <AlignCard title="Strategy Info">
                      <div className="grid gap-2">
                        <Row label="Type" value={str(selected?.category, "Not available").replaceAll("_", " ")} />
                        <Row label="Timeframe" value={TIMEFRAME} />
                        <Row label="Market" value={displayTradingSymbol(symbol)} />
                        <Row label="Risk per Trade" value={paramText(params, /risk|stop/i)} />
                        <Row label="Max Open Positions" value={paramText(params, /position|concurrent/i)} />
                        <Row label="Status" value={verified ? "Verified" : onServer ? "On server" : "Built-in"} />
                      </div>
                    </AlignCard>
                    <AlignCard title={`Evidence Stack (${evidenceCount})`}>
                      <EvidenceStack backtests={backtests} walkforwards={walkforwards} compareItems={compareItems} libraryItems={libraryItems} selectedId={strategyKey} onSelect={selectStrategy} className="h-auto border-0 bg-transparent p-0 shadow-none" />
                    </AlignCard>
                    <AlignCard title="Confidence Timeline">
                      <ConfidenceTimeline validation={validation} walkforwardItem={matchedWalk} backtestItem={matchedBacktest} strategyPresent={Boolean(strategyKey)} hasEvidence={evidenceCount > 0} className="h-auto border-0 bg-transparent p-0 shadow-none" />
                    </AlignCard>
                  </div>
                </>
              ) : (
                <article className="qf-overview-card min-h-[16rem] p-4">
                  <h3 className="text-sm font-semibold text-[var(--fg)]">Equity Curve (Backtest)</h3>
                  {curve.length > 0 ? <LazyEquityChart data={curve} emptyLabel="No equity curve stored for this strategy." /> : <p className="mt-4 text-sm text-[var(--fg-muted)]">Not available.</p>}
                </article>
              )}
            </div>
          ) : null}

          {tab === "research" ? (
            <div className="grid grid-cols-1 items-stretch gap-3 lg:grid-cols-2">
              <StrategyDna catalogItem={catalogItem} libraryItem={libraryItem} strategyKey={strategyKey} className="h-[18rem] overflow-hidden" />
              <ResearchMemory dashboard={dash} paper={paper && Object.keys(paper).length ? paper : null} regime={regime && Object.keys(regime).length ? regime : null} className="h-[18rem] overflow-hidden" />
              <ConfidenceTimeline validation={validation} walkforwardItem={matchedWalk} backtestItem={matchedBacktest} strategyPresent={Boolean(strategyKey)} hasEvidence={evidenceCount > 0} className="h-[18rem] overflow-hidden" />
              <EvidenceStack backtests={backtests} walkforwards={walkforwards} compareItems={compareItems} libraryItems={libraryItems} selectedId={strategyKey} onSelect={selectStrategy} className="h-[18rem] overflow-hidden" />
            </div>
          ) : null}

          {tab === "backtest" ? (
            <div className="grid gap-3">
              <div className="grid auto-rows-fr grid-cols-1 items-stretch gap-3 sm:grid-cols-2">
                <InfoCard title="Backtest">
                  <p className="text-sm leading-relaxed text-[var(--fg-muted)]">Runs the existing backtest service on gateway candles. It does not place an order.</p>
                  <Button type="button" className="mt-auto min-h-11" disabled={backtestRun.isPending} onClick={() => void runBacktest()}>
                    {backtestRun.isPending ? "Running backtest…" : "Run backtest"}
                  </Button>
                </InfoCard>
                <InfoCard title="Walk forward">
                  <p className="text-sm leading-relaxed text-[var(--fg-muted)]">Runs the existing walk-forward service. Results appear here only after the service stores them.</p>
                  <Button type="button" variant="secondary" className="mt-auto min-h-11" disabled={walkRun.isPending} onClick={() => void runWalkForward()}>
                    {walkRun.isPending ? "Running walk-forward…" : "Run walk forward"}
                  </Button>
                </InfoCard>
              </div>
              {curve.length > 0 ? (
                <article className="qf-overview-card min-h-[16rem] p-4">
                  <h3 className="text-sm font-semibold text-[var(--fg)]">Equity curve</h3>
                  <LazyEquityChart data={curve} emptyLabel="No equity curve stored for this strategy." />
                </article>
              ) : (
                <DeskEmpty icon={FlaskConical} title="No equity curve for this strategy" description="A curve appears when a saved backtest for this strategy includes one." />
              )}
              <EvidenceStack backtests={backtests} walkforwards={walkforwards} compareItems={compareItems} libraryItems={libraryItems} selectedId={strategyKey} onSelect={selectStrategy} className="min-h-[18rem]" />
            </div>
          ) : null}

          {tab === "parameters" ? (
            <InfoCard title="Parameters">
              {Object.keys(asRecord(selected?.default_params)).length === 0 ? (
                <p className="text-sm text-[var(--fg-muted)]">This strategy returned no parameters.</p>
              ) : (
                <dl className="grid gap-2">
                  {Object.entries(asRecord(selected?.default_params)).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between gap-3 border-b border-[var(--border)] py-2 text-sm">
                      <dt className="text-[var(--fg-muted)]">{key.replaceAll("_", " ")}</dt>
                      <dd className="font-mono text-[var(--fg)]">{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              )}
              <p className="mt-auto pt-3 text-xs text-[var(--fg-muted)]">Catalogue defaults. Changing them here does not send an order.</p>
            </InfoCard>
          ) : null}

          {tab === "rules" ? (
            <div className="grid gap-3">
              <div className="grid auto-rows-fr grid-cols-1 items-stretch gap-3 sm:grid-cols-2">
                {(Object.keys(rules) as (keyof RuleFlags)[]).map((key) => (
                  <button
                    key={key}
                    type="button"
                    aria-pressed={rules[key]}
                    className={cn(
                      "flex min-h-[5.5rem] flex-col justify-between rounded-[var(--radius-os)] border p-3 text-left",
                      rules[key] ? "border-[var(--accent)] bg-[var(--accent-soft)]" : "border-[var(--border)] bg-[var(--surface)]",
                    )}
                    onClick={() => setRules((current) => ({ ...current, [key]: !current[key] }))}
                  >
                    <span className="text-sm font-medium capitalize text-[var(--fg)]">{key.replaceAll("_", " ")}</span>
                    <span className="text-xs text-[var(--fg-muted)]">{rules[key] ? "Armed" : "Off"}</span>
                  </button>
                ))}
              </div>
              <Button
                type="button"
                className="min-h-11 w-full sm:w-auto"
                disabled={evaluate.isPending}
                onClick={() => evaluate.mutate({
                  request_id: `ui-${Date.now()}`,
                  symbol,
                  timeframe: TIMEFRAME.toLowerCase(),
                  market_open: true,
                  structure_bias: "up",
                  ...rules,
                  check_risk: true,
                })}
              >
                {evaluate.isPending ? "Checking rules…" : "Save & evaluate rules"}
              </Button>
              <p className="text-xs text-[var(--fg-muted)]">Uses the existing strategy evaluation service. The result is an intention, not an order.</p>
            </div>
          ) : null}

          {tab === "risk" ? (
            <InfoCard title="Risk analysis">
              {scalarRows(validation).filter((row) => /risk|drawdown|stop|exposure|loss/i.test(row.label)).length === 0 ? (
                <p className="text-sm leading-relaxed text-[var(--fg-muted)]">Risk figures appear after Validate returns them. This desk does not calculate or change risk limits.</p>
              ) : (
                <dl className="grid gap-2">
                  {scalarRows(validation).filter((row) => /risk|drawdown|stop|exposure|loss/i.test(row.label)).map((row) => (
                    <div key={row.label} className="flex justify-between gap-3 text-sm">
                      <dt className="capitalize text-[var(--fg-muted)]">{row.label}</dt>
                      <dd className="text-right text-[var(--fg)]">{row.value}</dd>
                    </div>
                  ))}
                </dl>
              )}
              <p className="mt-auto pt-3 text-xs text-[var(--fg-muted)]">Server risk gates stay authoritative. Open Robot &amp; Risk to review account limits.</p>
            </InfoCard>
          ) : null}

          {tab === "ai" ? (
            <div className="grid gap-3">
              <ResearchAiReview validation={validation} collapsed={aiCollapsed} onToggle={() => setAiCollapsed((value) => !value)} />
              <Button type="button" className="min-h-11 w-full sm:w-auto" disabled={!strategyKey || validateMut.isPending} onClick={() => validateMut.mutate()}>
                {validateMut.isPending ? "Validating…" : "Validate"}
              </Button>
            </div>
          ) : null}

          {tab === "versions" ? (
            <InfoCard title="Versions">
              <p className="text-sm text-[var(--fg-muted)]">The catalogue did not return saved versions for this strategy.</p>
              {localClone ? <p className="text-sm text-[var(--fg)]">Local clone of {localClone} parameters is open on this page only. It was not saved.</p> : null}
              {brief?.concept ? <p className="text-sm leading-relaxed text-[var(--fg)]">{brief.concept}</p> : null}
              {intention ? <p className="text-sm font-semibold text-[var(--fg)]">Latest intention: {intention}. This does not place an order.</p> : null}
            </InfoCard>
          ) : null}

          {tab === "reports" ? (
            <div className="grid auto-rows-fr grid-cols-1 items-stretch gap-3 lg:grid-cols-2">
              <InfoCard title="Research report">
                {reportQ.isLoading ? <DeskSkeleton rows={3} /> : null}
                {reportQ.isError ? <DeskError message="Report unavailable." onRetry={() => reportQ.refetch()} /> : null}
                {!reportQ.isLoading && !reportQ.isError && scalarRows(asRecord(reportQ.data)).length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">No saved report fields for this strategy.</p>
                ) : null}
                <dl className="grid gap-2">
                  {scalarRows(asRecord(reportQ.data)).map((row) => (
                    <div key={row.label} className="flex justify-between gap-3 text-sm">
                      <dt className="capitalize text-[var(--fg-muted)]">{row.label}</dt>
                      <dd className="max-w-[60%] truncate text-right text-[var(--fg)]">{row.value}</dd>
                    </div>
                  ))}
                </dl>
              </InfoCard>
              <PromoteGate
                criteria={Object.keys(criteria).length ? criteria : null}
                promoteResult={promoteResult}
                strategyKey={strategyKey}
                onEvaluate={() => promoteMut.mutate()}
                evaluating={promoteMut.isPending}
                className="min-h-[18rem]"
              />
            </div>
          ) : null}
          </div>
          <footer className="flex shrink-0 flex-col gap-3 border-t border-[var(--border)] bg-[var(--surface)] px-3 py-3 pb-[max(0.75rem,var(--shell-mobile-content-pad-bottom))] sm:flex-row sm:items-center sm:justify-between lg:pb-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-[var(--fg)]">Promote to Active Strategy</p>
              <p className="text-xs text-[var(--fg-muted)]">Eligibility review only. This does not activate live trading.</p>
            </div>
            <p className={cn("text-sm font-semibold", eligible ? "text-[var(--success)]" : "text-[var(--fg-muted)]")}>
              {promoteResult ? (eligible ? "Ready for promotion" : "Not ready for promotion") : "Not checked"}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" className="min-h-11" disabled={!strategyKey || promoteMut.isPending} onClick={() => promoteMut.mutate()}>
                <Rocket className="mr-1.5 h-4 w-4" aria-hidden />
                {promoteMut.isPending ? "Checking…" : "Promote Strategy"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                className="min-h-11"
                onClick={() => {
                  const payload = reportQ.data ?? { strategy_key: strategyKey, status: "No saved report fields" };
                  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
                  const url = URL.createObjectURL(blob);
                  const link = document.createElement("a");
                  link.href = url;
                  link.download = `${strategyKey || "strategy"}-research-report.json`;
                  link.click();
                  URL.revokeObjectURL(url);
                }}
              >
                <Download className="mr-1.5 h-4 w-4" aria-hidden />
                Export Report
              </Button>
            </div>
          </footer>
        </section>
      </div>
    </div>
  );
}

function AlignCard({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <article className="qf-overview-card flex h-[16rem] min-w-0 flex-col overflow-hidden p-4">
      <header className="mb-3 flex h-6 shrink-0 items-center justify-between gap-2">
        <h3 className="truncate text-sm font-semibold text-[var(--fg)]">{title}</h3>
        {action}
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </article>
  );
}

function InfoCard({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <article className={cn("qf-overview-card flex h-[12.5rem] min-w-0 flex-col gap-3 overflow-hidden p-4", className)}>
      <h3 className="shrink-0 text-sm font-semibold text-[var(--fg)]">{title}</h3>
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">{children}</div>
    </article>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-[var(--fg-muted)]">{label}</span>
      <span className="text-right font-medium text-[var(--fg)]">{value}</span>
    </div>
  );
}

function Tag({ children }: { children: ReactNode }) {
  return <span className="rounded-full bg-[var(--surface-2)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--fg-muted)]">{children}</span>;
}

function paramText(params: Record<string, unknown>, pattern: RegExp): string {
  const hit = Object.entries(params).find(([key]) => pattern.test(key));
  return hit ? String(hit[1]) : "Not available";
}

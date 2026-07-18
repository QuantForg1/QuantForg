"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Keyboard, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { SessionBar } from "@/components/broker/session-bar";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { PromotionPipeline } from "@/components/research/promotion-pipeline";
import { StrategyDna } from "@/components/research/strategy-dna";
import { ConfidenceTimeline } from "@/components/research/confidence-timeline";
import { EvidenceStack } from "@/components/research/evidence-stack";
import { ResearchMemory } from "@/components/research/research-memory";
import { ResearchAiReview } from "@/components/research/ai-review";
import { PromoteGate } from "@/components/research/promote-gate";
import {
  DEFAULT_RESEARCH_LAYOUT,
  RESEARCH_STAGES,
  loadResearchLayout,
  saveResearchLayout,
  type ResearchLayoutState,
  type ResearchStage,
} from "@/components/research/layout-store";
import {
  backtestApi,
  researchLabApi,
  strategyApi,
  walkforwardApi,
} from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function isTypingTarget(el: EventTarget | null) {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    el.isContentEditable
  );
}

const SHORTCUTS = [
  { keys: "1–8", action: "Pipeline stages" },
  { keys: "V", action: "Validate selected strategy" },
  { keys: "P", action: "Promotion evaluate" },
  { keys: "A", action: "Toggle AI Review" },
  { keys: "R", action: "Refresh" },
  { keys: "?", action: "Help" },
  { keys: "⌘3", action: "Research desk" },
];

/**
 * Research OS — Idea → … → Promote workflow.
 * Advisory only. Never submits orders. Never fabricates metrics.
 */
export function ResearchShell() {
  const [layout, setLayout] = useState<ResearchLayoutState>(DEFAULT_RESEARCH_LAYOUT);
  const [hydrated, setHydrated] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [promoteResult, setPromoteResult] = useState<Record<string, unknown> | null>(
    null,
  );

  useEffect(() => {
    setLayout(loadResearchLayout());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveResearchLayout(layout);
  }, [layout, hydrated]);

  const patch = useCallback((partial: Partial<ResearchLayoutState>) => {
    setLayout((prev) => ({ ...prev, ...partial }));
  }, []);

  const dashQ = useQuery({
    queryKey: ["research-lab-dashboard", layout.symbol],
    queryFn: () => researchLabApi.dashboard(layout.symbol || "EURUSD"),
    retry: false,
    staleTime: 20_000,
  });

  const libraryQ = useQuery({
    queryKey: ["research-lab-library"],
    queryFn: researchLabApi.library,
    retry: false,
    staleTime: 30_000,
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

  const catalogQ = useQuery({
    queryKey: ["strategy-catalog"],
    queryFn: strategyApi.catalog,
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

  const libraryItems = useMemo(
    () => asList(asRecord(libraryQ.data).items).map(asRecord),
    [libraryQ.data],
  );
  const compareItems = useMemo(
    () => asList(asRecord(compareQ.data).items).map(asRecord),
    [compareQ.data],
  );
  const catalogItems = useMemo(() => {
    const raw = catalogQ.data;
    const list = asList(
      asRecord(raw).strategies ?? asRecord(raw).items ?? raw,
    ).map(asRecord);
    return list;
  }, [catalogQ.data]);

  const backtests = useMemo(() => {
    const raw = backtestsQ.data;
    return asList(asRecord(raw).items ?? asRecord(raw).backtests ?? raw).map(
      asRecord,
    );
  }, [backtestsQ.data]);

  const walkforwards = useMemo(() => {
    const raw = walkforwardQ.data;
    return asList(asRecord(raw).items ?? asRecord(raw).results ?? raw).map(
      asRecord,
    );
  }, [walkforwardQ.data]);

  const strategyKey = layout.strategyKey;
  const libraryItem =
    libraryItems.find(
      (i) => str(i.strategy_key ?? i.key) === strategyKey,
    ) ?? null;
  const catalogItem =
    catalogItems.find(
      (i) => str(i.strategy_key ?? i.key ?? i.id) === strategyKey,
    ) ?? null;

  const dash = dashQ.data ? asRecord(dashQ.data) : null;
  const paper = dash ? asRecord(dash.paper) : null;
  const regime = dash ? asRecord(dash.regime) : null;
  const criteria = asRecord(asRecord(criteriaQ.data).criteria);

  const latestBacktest = backtests[0] ?? null;
  const latestWf = walkforwards[0] ?? null;

  const validateMut = useMutation({
    mutationFn: () =>
      researchLabApi.validate({
        strategy_key: strategyKey,
        symbol: layout.symbol || "EURUSD",
      }),
    onSuccess: (data) => {
      setValidation(asRecord(data));
      patch({ stage: "ai" });
      toast.success("Validation complete");
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Validate failed"),
  });

  const promoteMut = useMutation({
    mutationFn: () => researchLabApi.promote({ strategy_key: strategyKey }),
    onSuccess: (data) => {
      setPromoteResult(asRecord(data));
      patch({ stage: "promote" });
      toast.success("Promotion evaluated");
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Promote evaluate failed"),
  });

  const refreshAll = useCallback(() => {
    void dashQ.refetch();
    void libraryQ.refetch();
    void compareQ.refetch();
    void criteriaQ.refetch();
    void catalogQ.refetch();
    void backtestsQ.refetch();
    void walkforwardQ.refetch();
  }, [
    dashQ,
    libraryQ,
    compareQ,
    criteriaQ,
    catalogQ,
    backtestsQ,
    walkforwardQ,
  ]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setHelpOpen(false);
        return;
      }
      if (isTypingTarget(e.target)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const stage = RESEARCH_STAGES.find((s) => s.hotkey === e.key);
      if (stage) {
        e.preventDefault();
        patch({ stage: stage.id });
        return;
      }
      const k = e.key.toLowerCase();
      if (k === "v") {
        e.preventDefault();
        if (strategyKey) validateMut.mutate();
        return;
      }
      if (k === "p") {
        e.preventDefault();
        if (strategyKey) promoteMut.mutate();
        return;
      }
      if (k === "a") {
        e.preventDefault();
        patch({ aiCollapsed: !layout.aiCollapsed });
        return;
      }
      if (k === "r") {
        e.preventDefault();
        refreshAll();
        return;
      }
      if (e.key === "?" || (e.shiftKey && e.key === "/")) {
        e.preventDefault();
        setHelpOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [
    layout.aiCollapsed,
    patch,
    promoteMut,
    refreshAll,
    strategyKey,
    validateMut,
  ]);

  // Seed strategy from dashboard candidate when empty
  useEffect(() => {
    if (layout.strategyKey || !dash) return;
    const leaders = asRecord(dash.research_dashboard);
    const candidate = asRecord(leaders.candidate);
    const key = str(candidate.strategy_key);
    if (key) patch({ strategyKey: key });
  }, [dash, layout.strategyKey, patch]);

  const loading = dashQ.isLoading && libraryQ.isLoading;
  const stage: ResearchStage = layout.stage;

  return (
    <div
      className="flex h-full min-h-0 flex-col overflow-hidden bg-[var(--bg)]"
      role="application"
      aria-label="QuantForg Research"
    >
      <header className="shrink-0">
        <div className="flex h-9 items-center justify-between gap-2 border-b border-[var(--border)] px-3">
          <div className="flex min-w-0 items-center gap-2">
            <h1 className="text-xs font-semibold tracking-tight text-[var(--fg)]">
              Research
            </h1>
            <span className="qf-caption hidden sm:inline">
              Idea → Promote · advisory only
            </span>
            <Input
              className="h-7 w-24 font-mono text-[11px]"
              value={layout.symbol}
              onChange={(e) =>
                patch({ symbol: e.target.value.toUpperCase().slice(0, 16) })
              }
              aria-label="Focus symbol"
            />
            <select
              className="h-7 max-w-[10rem] truncate rounded border border-[var(--border)] bg-[var(--surface)] px-1.5 text-[11px]"
              value={strategyKey}
              onChange={(e) => patch({ strategyKey: e.target.value })}
              aria-label="Strategy"
            >
              <option value="">Select strategy…</option>
              {libraryItems.map((i) => {
                const k = str(i.strategy_key ?? i.key);
                return (
                  <option key={`lib-${k}`} value={k}>
                    {str(i.name, k)}
                  </option>
                );
              })}
              {catalogItems.map((i) => {
                const k = str(i.strategy_key ?? i.key ?? i.id);
                if (!k || libraryItems.some((l) => str(l.strategy_key) === k)) {
                  return null;
                }
                return (
                  <option key={`cat-${k}`} value={k}>
                    {str(i.name, k)}
                  </option>
                );
              })}
            </select>
          </div>
          <div className="flex items-center gap-0.5">
            <Button
              size="sm"
              className="h-7 text-[11px]"
              disabled={!strategyKey || validateMut.isPending}
              onClick={() => validateMut.mutate()}
            >
              Validate
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 px-0"
              aria-label="Refresh research"
              onClick={refreshAll}
            >
              <RefreshCw
                className={cn(
                  "h-3.5 w-3.5",
                  dashQ.isFetching && "animate-spin",
                )}
              />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 px-0"
              aria-label="Keyboard shortcuts"
              onClick={() => setHelpOpen(true)}
            >
              <Keyboard className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <SessionBar />
        <PromotionPipeline
          stage={stage}
          onStageChange={(s) => patch({ stage: s })}
        />
        <ResearchAiReview
          validation={validation}
          collapsed={layout.aiCollapsed}
          onToggle={() => patch({ aiCollapsed: !layout.aiCollapsed })}
        />
      </header>

      <div className="min-h-0 flex-1 overflow-hidden p-2 sm:p-3">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <DeskSkeleton rows={6} />
          </div>
        ) : dashQ.isError && libraryQ.isError && backtestsQ.isError ? (
          <div className="flex h-full items-center justify-center p-4">
            <DeskError
              message="Research APIs unavailable — no fabricated research results."
              onRetry={refreshAll}
            />
          </div>
        ) : (
          <div className="grid h-full min-h-0 gap-2 lg:grid-cols-2 xl:grid-cols-3">
            <StrategyDna
              catalogItem={catalogItem}
              libraryItem={libraryItem}
              strategyKey={strategyKey}
              className={cn(stage === "idea" && "ring-1 ring-[var(--accent)]")}
            />
            <ConfidenceTimeline
              validation={validation}
              walkforwardItem={latestWf}
              backtestItem={latestBacktest}
              strategyPresent={Boolean(strategyKey)}
              hasEvidence={backtests.length + walkforwards.length + compareItems.length > 0}
              className={cn(
                (stage === "observe" ||
                  stage === "validate" ||
                  stage === "backtest" ||
                  stage === "walkforward" ||
                  stage === "risk") &&
                  "ring-1 ring-[var(--accent)]",
              )}
            />
            <EvidenceStack
              backtests={backtests}
              walkforwards={walkforwards}
              compareItems={compareItems}
              libraryItems={libraryItems}
              selectedId={strategyKey}
              onSelect={(k) => patch({ strategyKey: k, stage: "observe" })}
              className={cn(stage === "observe" && "ring-1 ring-[var(--accent)]")}
            />
            <ResearchMemory
              dashboard={dash}
              paper={paper && Object.keys(paper).length ? paper : null}
              regime={regime && Object.keys(regime).length ? regime : null}
              className={cn(stage === "observe" && "ring-1 ring-[var(--accent)]")}
            />
            <PromoteGate
              criteria={Object.keys(criteria).length ? criteria : null}
              promoteResult={promoteResult}
              strategyKey={strategyKey}
              onEvaluate={() => promoteMut.mutate()}
              evaluating={promoteMut.isPending}
              className={cn(
                "lg:col-span-2 xl:col-span-1",
                stage === "promote" && "ring-1 ring-[var(--accent)]",
              )}
            />
          </div>
        )}
      </div>

      <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
        <DialogContent className="max-w-md">
          <DialogTitle>Research shortcuts</DialogTitle>
          <ul className="mt-3 space-y-2">
            {SHORTCUTS.map((row) => (
              <li
                key={row.keys}
                className="flex items-baseline justify-between gap-4 text-sm"
              >
                <kbd className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-1.5 py-0.5 font-mono text-[11px]">
                  {row.keys}
                </kbd>
                <span className="text-[var(--fg-muted)]">{row.action}</span>
              </li>
            ))}
          </ul>
        </DialogContent>
      </Dialog>
    </div>
  );
}

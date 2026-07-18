"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Keyboard, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { SessionBar } from "@/components/broker/session-bar";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { DecisionPulse } from "@/components/counsel/decision-pulse";
import { ContextLens } from "@/components/counsel/context-lens";
import { RecommendationCard } from "@/components/counsel/recommendation-card";
import { PortfolioImpact } from "@/components/counsel/portfolio-impact";
import { DecisionTimeline } from "@/components/counsel/decision-timeline";
import { LearningMemory } from "@/components/counsel/learning-memory";
import { SilenceProtocol } from "@/components/counsel/silence-protocol";
import { parseDecisionRecommendation } from "@/components/counsel/recommendation-model";
import {
  DEFAULT_COUNSEL_LAYOUT,
  loadCounselLayout,
  saveCounselLayout,
  type CounselFocus,
  type CounselLayoutState,
} from "@/components/counsel/layout-store";
import {
  decisionEngineApi,
  intelligenceApi,
  quantAiApi,
} from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
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
  { keys: "1–7", action: "Focus panels" },
  { keys: "E", action: "Evaluate (paper)" },
  { keys: "S", action: "Toggle Silence Protocol" },
  { keys: "R", action: "Refresh" },
  { keys: "?", action: "Help" },
  { keys: "⌘4", action: "Counsel desk" },
];

const FOCUS_KEYS: Record<string, CounselFocus> = {
  "1": "pulse",
  "2": "context",
  "3": "recommendation",
  "4": "impact",
  "5": "timeline",
  "6": "memory",
  "7": "silence",
};

/**
 * Counsel OS — Decision Operating System.
 * Not a chatbot. Never submits orders. Terminal is the only execution surface.
 */
export function CounselShell() {
  const session = useTradingSession();
  const qc = useQueryClient();
  const [layout, setLayout] = useState<CounselLayoutState>(DEFAULT_COUNSEL_LAYOUT);
  const [hydrated, setHydrated] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    setLayout(loadCounselLayout());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveCounselLayout(layout);
  }, [layout, hydrated]);

  const patch = useCallback((partial: Partial<CounselLayoutState>) => {
    setLayout((prev) => ({ ...prev, ...partial }));
  }, []);

  const focusSymbol = layout.symbol || "EURUSD";

  const dashQ = useQuery({
    queryKey: ["decision-engine-dashboard", focusSymbol],
    queryFn: () => decisionEngineApi.dashboard(focusSymbol),
    retry: false,
    staleTime: 10_000,
    refetchInterval: 45_000,
  });

  const quantQ = useQuery({
    queryKey: ["quant-ai-dashboard", focusSymbol],
    queryFn: () => quantAiApi.dashboard(focusSymbol),
    retry: false,
    staleTime: 12_000,
    refetchInterval: 45_000,
  });

  const contextQ = useQuery({
    queryKey: ["intelligence-market-context", focusSymbol],
    queryFn: () => intelligenceApi.marketContext("FX", focusSymbol),
    retry: false,
    staleTime: 60_000,
  });

  const evaluate = useMutation({
    mutationFn: () =>
      decisionEngineApi.evaluate({
        symbol: focusSymbol,
        mode: "paper",
        force_refresh: true,
      }),
    onSuccess: async () => {
      toast.success("Decision re-evaluated (paper · advisory)");
      await qc.invalidateQueries({
        queryKey: ["decision-engine-dashboard", focusSymbol],
      });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Evaluate failed"),
  });

  const decisionRoot = dashQ.data ? asRecord(dashQ.data) : null;
  const recommendation = useMemo(
    () => parseDecisionRecommendation(decisionRoot, focusSymbol),
    [decisionRoot, focusSymbol],
  );

  const paper = asRecord(decisionRoot?.paper);
  const paperRecent = useMemo(
    () => asList(paper.recent).map(asRecord),
    [paper.recent],
  );
  const paperPerf = Object.keys(asRecord(paper.performance)).length
    ? asRecord(paper.performance)
    : null;
  const reports = decisionRoot?.reports
    ? asRecord(decisionRoot.reports)
    : null;

  const quant = quantQ.data ? asRecord(quantQ.data) : null;
  const assistant = quant ? asRecord(quant.assistant) : null;
  const modules = quant ? asRecord(quant.modules) : null;
  const sessionAnalysis = quant
    ? asRecord(quant.session_analysis)
    : null;

  const marketContext = contextQ.data ? asRecord(contextQ.data) : null;

  const equity = num(session.equity);
  const freeMargin = num(session.freeMargin);
  const floating =
    session.positions.reduce((s, p) => s + num(p.profit, 0), 0) ||
    num(session.profit);

  const refreshAll = useCallback(() => {
    void dashQ.refetch();
    void quantQ.refetch();
    void contextQ.refetch();
  }, [dashQ, quantQ, contextQ]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setHelpOpen(false);
        return;
      }
      if (isTypingTarget(e.target)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (FOCUS_KEYS[e.key]) {
        e.preventDefault();
        patch({ focus: FOCUS_KEYS[e.key] });
        return;
      }
      const k = e.key.toLowerCase();
      if (k === "e") {
        e.preventDefault();
        evaluate.mutate();
        return;
      }
      if (k === "s") {
        e.preventDefault();
        patch({ silenceExpanded: !layout.silenceExpanded });
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
  }, [evaluate, layout.silenceExpanded, patch, refreshAll]);

  const loading = dashQ.isLoading && quantQ.isLoading;
  const focus = layout.focus;

  return (
    <div
      className="flex h-full min-h-0 flex-col overflow-hidden bg-[var(--bg)]"
      role="application"
      aria-label="QuantForg Counsel"
    >
      <header className="shrink-0">
        <div className="flex h-9 items-center justify-between gap-2 border-b border-[var(--border)] px-3">
          <div className="flex min-w-0 items-center gap-2">
            <h1 className="text-xs font-semibold tracking-tight text-[var(--fg)]">
              Counsel
            </h1>
            <span className="qf-caption hidden sm:inline">
              Decision OS · never executes
            </span>
            <Input
              className="h-7 w-24 font-mono text-[11px]"
              value={layout.symbol}
              onChange={(e) =>
                patch({ symbol: e.target.value.toUpperCase().slice(0, 16) })
              }
              aria-label="Focus symbol"
            />
          </div>
          <div className="flex items-center gap-0.5">
            <Button
              size="sm"
              className="h-7 text-[11px]"
              disabled={evaluate.isPending}
              onClick={() => evaluate.mutate()}
            >
              {evaluate.isPending ? "Evaluating…" : "Evaluate"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 px-0"
              aria-label="Refresh counsel"
              onClick={refreshAll}
            >
              <RefreshCw
                className={cn("h-3.5 w-3.5", dashQ.isFetching && "animate-spin")}
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
        <SilenceProtocol
          recommendation={recommendation}
          apiError={dashQ.isError}
          expanded={layout.silenceExpanded}
          onToggle={() =>
            patch({ silenceExpanded: !layout.silenceExpanded })
          }
        />
      </header>

      <div className="min-h-0 flex-1 overflow-hidden p-2 sm:p-3">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <DeskSkeleton rows={6} />
          </div>
        ) : dashQ.isError && quantQ.isError ? (
          <div className="flex h-full items-center justify-center p-4">
            <DeskError
              message="Counsel APIs unavailable — stance remains WAIT. No fabricated decisions."
              onRetry={refreshAll}
            />
          </div>
        ) : (
          <div className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)_minmax(0,1fr)] gap-2">
            <DecisionPulse
              recommendation={recommendation}
              focused={focus === "pulse"}
            />
            <div className="grid min-h-0 gap-2 lg:grid-cols-2 xl:grid-cols-3">
              <RecommendationCard
                recommendation={recommendation}
                focused={focus === "recommendation"}
              />
              <ContextLens
                decisionRoot={decisionRoot}
                marketContext={marketContext}
                quantAssistant={
                  assistant && Object.keys(assistant).length ? assistant : null
                }
                focused={focus === "context"}
              />
              <PortfolioImpact
                equity={equity}
                freeMargin={freeMargin}
                floating={floating}
                positionCount={session.positions.length}
                quantModules={
                  modules && Object.keys(modules).length ? modules : null
                }
                focused={focus === "impact"}
              />
            </div>
            <div className="grid min-h-0 gap-2 lg:grid-cols-2">
              <DecisionTimeline
                paperRecent={paperRecent}
                reports={reports}
                focused={focus === "timeline"}
              />
              <LearningMemory
                paperPerformance={paperPerf}
                sessionAnalysis={
                  sessionAnalysis && Object.keys(sessionAnalysis).length
                    ? sessionAnalysis
                    : null
                }
                focused={focus === "memory"}
              />
            </div>
          </div>
        )}
      </div>

      <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
        <DialogContent className="max-w-md">
          <DialogTitle>Counsel shortcuts</DialogTitle>
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

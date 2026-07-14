"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConnectionBar } from "@/components/execution/connection-bar";
import { RealtimeConnectionBadge, RealtimeMeta } from "@/components/realtime/connection-badge";
import { WorkspaceLeftRail } from "@/components/workspace/left-rail";
import { WorkspaceRightRail } from "@/components/workspace/right-rail";
import { WorkspaceBottomPanel } from "@/components/workspace/bottom-panel";
import { WorkspaceChart } from "@/components/workspace/chart-panel";
import { SplitHandle, useResizeSplit } from "@/components/workspace/splitters";
import {
  DEFAULT_LAYOUT,
  PRESET_LAYOUTS,
  WORKSPACE_SYMBOL_KEY,
  loadWorkspaceLayout,
  saveWorkspaceLayout,
  type WorkspaceLayoutState,
  type WorkspacePresetId,
} from "@/components/workspace/layout-store";
import type { OrderTicketHandle } from "@/components/execution/order-ticket";
import { useExecutionStream, useNotificationsStream, useActivityStream } from "@/hooks/realtime";
import { mt5Api } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";

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

export function WorkspaceShell() {
  const [layout, setLayout] = useState<WorkspaceLayoutState>(DEFAULT_LAYOUT);
  const [symbol, setSymbol] = useState("EURUSD");
  const [hydrated, setHydrated] = useState(false);
  const ticketRef = useRef<OrderTicketHandle | null>(null);

  useEffect(() => {
    const stored = loadWorkspaceLayout();
    setLayout(stored);
    try {
      const sym = localStorage.getItem(WORKSPACE_SYMBOL_KEY);
      if (sym) setSymbol(sym);
    } catch {
      /* ignore */
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveWorkspaceLayout(layout);
  }, [layout, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(WORKSPACE_SYMBOL_KEY, symbol);
    } catch {
      /* ignore */
    }
  }, [symbol, hydrated]);

  // Narrow viewports: collapse side rails so the chart remains usable.
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1023px)");
    const apply = () => {
      if (mq.matches) {
        setLayout((prev) => ({
          ...prev,
          leftCollapsed: true,
          rightCollapsed: true,
          bottomCollapsed: prev.bottomCollapsed,
        }));
      }
    };
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  const realtime = useExecutionStream(symbol);
  useNotificationsStream();
  useActivityStream();

  const statusQ = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    retry: false,
  });
  const tickQ = useQuery({
    queryKey: ["mt5-tick", symbol],
    queryFn: () => mt5Api.tick(symbol),
    retry: false,
    enabled: Boolean(statusQ.data?.connected) && Boolean(symbol),
  });
  const symbolsQ = useQuery({
    queryKey: ["mt5-symbols", "", 0],
    queryFn: () => mt5Api.symbols({ limit: 100, offset: 0, include_quotes: false }),
    retry: false,
    enabled: Boolean(statusQ.data?.connected),
    staleTime: 45_000,
  });

  const connected = Boolean(statusQ.data?.connected);
  const tick = asRecord(tickQ.data);
  const fromSymbols = asList(symbolsQ.data)
    .map(asRecord)
    .find((s) => str(s.code) === symbol);
  const bid = num(tick.bid, num(asRecord(fromSymbols).bid));
  const ask = num(tick.ask, num(asRecord(fromSymbols).ask));
  const lastPrice =
    Number.isFinite(bid) && Number.isFinite(ask)
      ? (bid + ask) / 2
      : Number.isFinite(num(tick.last))
        ? num(tick.last)
        : undefined;

  const patchLayout = useCallback((partial: Partial<WorkspaceLayoutState>) => {
    setLayout((prev) => ({ ...prev, ...partial }));
  }, []);

  const applyPreset = useCallback((preset: WorkspacePresetId) => {
    setLayout((prev) => ({ ...prev, ...PRESET_LAYOUTS[preset] }));
  }, []);

  const onLeftDelta = useCallback((d: number) => {
    setLayout((prev) => ({
      ...prev,
      leftWidth: Math.min(420, Math.max(200, prev.leftWidth + d)),
    }));
  }, []);
  const onRightDelta = useCallback((d: number) => {
    setLayout((prev) => ({
      ...prev,
      rightWidth: Math.min(480, Math.max(280, prev.rightWidth - d)),
    }));
  }, []);
  const onBottomDelta = useCallback((d: number) => {
    setLayout((prev) => ({
      ...prev,
      bottomHeight: Math.min(420, Math.max(120, prev.bottomHeight - d)),
    }));
  }, []);

  const leftSplit = useResizeSplit(onLeftDelta);
  const rightSplit = useResizeSplit(onRightDelta);
  const bottomSplit = useResizeSplit(onBottomDelta);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        ticketRef.current?.cancelDialog();
        if (layout.chartFullscreen) {
          patchLayout({ chartFullscreen: false });
        }
        return;
      }
      if (isTypingTarget(e.target)) return;
      if (e.key.toLowerCase() === "b" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        ticketRef.current?.buy();
      }
      if (e.key.toLowerCase() === "s" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        ticketRef.current?.sell();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [layout.chartFullscreen, patchLayout]);

  const showLeft = !layout.leftCollapsed && !layout.chartFullscreen;
  const showRight = !layout.rightCollapsed && !layout.chartFullscreen;
  const showBottom = !layout.bottomCollapsed && !layout.chartFullscreen;

  return (
    <div className="flex h-full min-h-0 flex-col bg-[var(--bg)]" role="application" aria-label="Advanced trading workspace">
      <div className="shrink-0 border-b border-[var(--border)] px-3 py-2">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-sm font-semibold tracking-tight text-[var(--fg)]">
              Advanced Trading Workspace
            </h1>
            <RealtimeMeta status={realtime} />
          </div>
          <div className="flex items-center gap-1.5">
            <RealtimeConnectionBadge status={realtime} />
            <Button
              size="sm"
              variant="ghost"
              className="h-8"
              aria-label={layout.leftCollapsed ? "Expand left panel" : "Collapse left panel"}
              onClick={() => patchLayout({ leftCollapsed: !layout.leftCollapsed })}
            >
              {layout.leftCollapsed ? (
                <PanelLeftOpen className="h-4 w-4" />
              ) : (
                <PanelLeftClose className="h-4 w-4" />
              )}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-8"
              aria-label={layout.rightCollapsed ? "Expand right panel" : "Collapse right panel"}
              onClick={() => patchLayout({ rightCollapsed: !layout.rightCollapsed })}
            >
              {layout.rightCollapsed ? (
                <PanelRightOpen className="h-4 w-4" />
              ) : (
                <PanelRightClose className="h-4 w-4" />
              )}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              className="h-8 text-xs"
              onClick={() => patchLayout({ bottomCollapsed: !layout.bottomCollapsed })}
            >
              {layout.bottomCollapsed ? "Show bottom" : "Hide bottom"}
            </Button>
          </div>
        </div>
        <ConnectionBar
          connected={connected}
          server={statusQ.data?.server}
          login={statusQ.data?.login}
          latencyMs={realtime.latencyMs ?? statusQ.data?.latency_ms}
          tradingEnabled={connected}
        />
      </div>

      <div className="flex min-h-0 flex-1">
        {showLeft ? (
          <>
            <div style={{ width: layout.leftWidth }} className="min-h-0 shrink-0">
              <WorkspaceLeftRail
                connected={connected}
                selected={symbol}
                onSelect={setSymbol}
                preset={layout.preset}
                onPresetChange={applyPreset}
              />
            </div>
            <SplitHandle
              orientation="vertical"
              label="Resize left panel"
              onStartDrag={leftSplit.start("x")}
              onStep={onLeftDelta}
            />
          </>
        ) : null}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">
            <WorkspaceChart
              symbol={symbol}
              connected={connected}
              timeframe={layout.timeframe}
              onTimeframeChange={(timeframe) => patchLayout({ timeframe })}
              chartType={layout.chartType}
              onChartTypeChange={(chartType) => patchLayout({ chartType })}
              showVolume={layout.showVolume}
              onShowVolumeChange={(showVolume) => patchLayout({ showVolume })}
              fullscreen={layout.chartFullscreen}
              onFullscreenChange={(chartFullscreen) => patchLayout({ chartFullscreen })}
              lastPrice={lastPrice}
            />
          </div>

          {showBottom ? (
            <>
              <SplitHandle
                orientation="horizontal"
                label="Resize bottom panel"
                onStartDrag={bottomSplit.start("y")}
                onStep={onBottomDelta}
              />
              <div style={{ height: layout.bottomHeight }} className="min-h-0 shrink-0">
                <WorkspaceBottomPanel
                  tab={layout.bottomTab}
                  onTabChange={(bottomTab) => patchLayout({ bottomTab })}
                />
              </div>
            </>
          ) : null}
        </div>

        {showRight ? (
          <>
            <SplitHandle
              orientation="vertical"
              label="Resize right panel"
              onStartDrag={rightSplit.start("x")}
              onStep={(d) => onRightDelta(-d)}
            />
            <div style={{ width: layout.rightWidth }} className="min-h-0 shrink-0">
              <WorkspaceRightRail
                symbol={symbol}
                onSymbolChange={setSymbol}
                connected={connected}
                bid={Number.isFinite(bid) ? bid : undefined}
                ask={Number.isFinite(ask) ? ask : undefined}
                ticketRef={ticketRef}
              />
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

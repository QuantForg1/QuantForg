"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConnectionBar } from "@/components/execution/connection-bar";
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
import { useTradingSession } from "@/providers/trading-session-provider";
import { mt5Api } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { TRADING_SYMBOL, resolveTradingSymbol } from "@/lib/trading/gold-only";

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

export function WorkspaceShell({
  captureHotkeys = true,
}: {
  /** Buy/Sell letter keys stay off when this terminal sits above another desk. */
  captureHotkeys?: boolean;
}) {
  const [layout, setLayout] = useState<WorkspaceLayoutState>(DEFAULT_LAYOUT);
  const [symbol, setSymbol] = useState(TRADING_SYMBOL);
  const [hydrated, setHydrated] = useState(false);
  const [narrow, setNarrow] = useState(true);
  const frameRef = useRef<HTMLDivElement>(null);
  const ticketRef = useRef<OrderTicketHandle | null>(null);

  useEffect(() => {
    const stored = loadWorkspaceLayout();
    setLayout(stored);
    try {
      const sym = localStorage.getItem(WORKSPACE_SYMBOL_KEY);
      setSymbol(resolveTradingSymbol(sym));
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

  useEffect(() => {
    const el = frameRef.current;
    if (!el) return;
    const apply = () => setNarrow(el.clientWidth < 1100);
    apply();
    const observer = new ResizeObserver(apply);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const realtime = useExecutionStream(symbol);
  useNotificationsStream();
  useActivityStream();
  const session = useTradingSession();
  const connected = session.connected;

  const tickQ = useQuery({
    queryKey: ["research-tick", symbol],
    queryFn: () => mt5Api.researchTick(symbol),
    retry: 1,
    enabled: Boolean(symbol),
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
  const symbolsQ = useQuery({
    queryKey: ["mt5-symbols", "", 0],
    queryFn: () => mt5Api.symbols({ limit: 100, offset: 0, include_quotes: false }),
    retry: false,
    enabled: connected,
    staleTime: 45_000,
  });

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
    if (!captureHotkeys) return;
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
  }, [captureHotkeys, layout.chartFullscreen, patchLayout]);

  const showLeft = (narrow || !layout.leftCollapsed) && !layout.chartFullscreen;
  const showRight = (narrow || !layout.rightCollapsed) && !layout.chartFullscreen;
  const showBottom = (narrow || !layout.bottomCollapsed) && !layout.chartFullscreen;

  return (
    <div
      ref={frameRef}
      className="flex h-auto min-h-0 flex-col bg-[var(--bg)] lg:h-full"
      role="application"
      aria-label="Institutional trading terminal"
    >
      <header className="shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-1.5">
          <h1 className="text-xs font-semibold tracking-tight text-[var(--fg)] sm:text-sm">
            Trading Terminal
          </h1>
          <div className="flex max-w-full flex-wrap items-center justify-end gap-1">
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 px-0"
              data-compact
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
              className="h-7 w-7 px-0"
              data-compact
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
              className="h-7 text-xs"
              data-compact
              onClick={() => patchLayout({ bottomCollapsed: !layout.bottomCollapsed })}
            >
              {layout.bottomCollapsed ? "Show book" : "Hide book"}
            </Button>
          </div>
        </div>
        <ConnectionBar
          compact
          connected={connected}
          server={session.server}
          login={session.login}
          latencyMs={realtime.latencyMs ?? session.latencyMs}
          tradingEnabled={connected}
          realtime={realtime}
        />
      </header>

      <div className={narrow ? "flex min-h-0 flex-col" : "flex min-h-0 flex-1"}>
        {showLeft ? (
          <>
            <div
              style={narrow ? undefined : { width: layout.leftWidth }}
              className={narrow ? "h-72 w-full shrink-0 border-b border-[var(--border)]" : "min-h-0 shrink-0"}
            >
              <WorkspaceLeftRail
                connected={connected}
                selected={symbol}
                onSelect={setSymbol}
                preset={layout.preset}
                onPresetChange={applyPreset}
                latencyMs={session.latencyMs}
              />
            </div>
            {narrow ? null : (
              <SplitHandle
                orientation="vertical"
                label="Resize left panel"
                onStartDrag={leftSplit.start("x")}
                onStep={onLeftDelta}
              />
            )}
          </>
        ) : null}

        <div className={narrow ? "flex min-h-[520px] min-w-0 flex-col" : "flex min-h-0 min-w-0 flex-1 flex-col"}>
          <div className={narrow ? "h-[360px] shrink-0" : "min-h-0 flex-1"}>
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
              {narrow ? null : (
                <SplitHandle
                  orientation="horizontal"
                  label="Resize bottom panel"
                  onStartDrag={bottomSplit.start("y")}
                  onStep={onBottomDelta}
                />
              )}
              <div
                style={narrow ? undefined : { height: layout.bottomHeight }}
                className={narrow ? "h-80 shrink-0 border-t border-[var(--border)]" : "min-h-0 shrink-0"}
              >
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
            {narrow ? null : (
              <SplitHandle
                orientation="vertical"
                label="Resize right panel"
                onStartDrag={rightSplit.start("x")}
                onStep={(d) => onRightDelta(-d)}
              />
            )}
            <div
              style={narrow ? undefined : { width: layout.rightWidth }}
              className={narrow ? "w-full shrink-0 border-t border-[var(--border)]" : "min-h-0 shrink-0"}
            >
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

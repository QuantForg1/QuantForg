"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Keyboard,
  PanelRightClose,
  PanelRightOpen,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { WorkspaceChart } from "@/components/workspace/chart-panel";
import { SplitHandle, useResizeSplit } from "@/components/workspace/splitters";
import { TerminalSessionBar } from "@/components/terminal/session-bar";
import { TerminalCounselStrip } from "@/components/terminal/counsel-strip";
import { TerminalRightRail } from "@/components/terminal/right-rail";
import { TerminalBlotter } from "@/components/terminal/blotter";
import {
  DEFAULT_TERMINAL_LAYOUT,
  TERMINAL_SYMBOL_KEY,
  loadTerminalLayout,
  saveTerminalLayout,
  type TerminalLayoutState,
  type TerminalBlotterTab,
} from "@/components/terminal/layout-store";
import type { OrderTicketHandle } from "@/components/execution/order-ticket";
import { useExecutionStream } from "@/hooks/realtime";
import { useTradingSession } from "@/providers/trading-session-provider";
import { mt5Api } from "@/lib/api/endpoints";
import { asRecord, num } from "@/lib/desk";
import { TRADING_SYMBOL, resolveTradingSymbol } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";
import { pushRecentSymbol } from "@/lib/workspace/nav-memory";

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

const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: "B / S", action: "Buy / Sell (confirm)" },
  { keys: "1–3", action: "Blotter tabs" },
  { keys: "]", action: "Toggle order ticket" },
  { keys: "\\", action: "Toggle blotter" },
  { keys: "C", action: "Toggle AI decision" },
  { keys: "F", action: "Chart fullscreen" },
  { keys: "Esc", action: "Cancel / close sheets" },
  { keys: "?", action: "This help" },
  { keys: "⌘1–6", action: "Workspace jump" },
];

/**
 * QuantForg Terminal V3 — flagship trading surface.
 * Chart · Order Ticket · AI Decision · Positions / Orders / Executions.
 * No monitoring, analytics, gateway, or duplicated stats.
 */
export function TerminalShell() {
  const searchParams = useSearchParams();
  const [layout, setLayout] = useState<TerminalLayoutState>(DEFAULT_TERMINAL_LAYOUT);
  const [symbol, setSymbol] = useState(TRADING_SYMBOL);
  const [hydrated, setHydrated] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const ticketRef = useRef<OrderTicketHandle | null>(null);
  const layoutRef = useRef(layout);

  useEffect(() => {
    layoutRef.current = layout;
  }, [layout]);

  useEffect(() => {
    const stored = loadTerminalLayout();
    setLayout(stored);
    try {
      const fromUrl = searchParams.get("symbol")?.trim();
      const fromLs = localStorage.getItem(TERMINAL_SYMBOL_KEY);
      setSymbol(resolveTradingSymbol(fromUrl || fromLs));
    } catch {
      /* ignore */
    }
    setHydrated(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- hydrate once
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveTerminalLayout(layout);
  }, [layout, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(TERMINAL_SYMBOL_KEY, symbol);
    } catch {
      /* ignore */
    }
    pushRecentSymbol(symbol);
  }, [symbol, hydrated]);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1023px)");
    const apply = () => {
      setIsMobile(mq.matches);
      if (mq.matches) {
        setLayout((prev) => ({
          ...prev,
          rightCollapsed: true,
        }));
      }
    };
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  const realtime = useExecutionStream(symbol);
  const session = useTradingSession();
  const connected = session.connected;

  const tickQ = useQuery({
    queryKey: ["mt5-tick", symbol],
    queryFn: () => mt5Api.tick(symbol),
    retry: false,
    enabled: connected && Boolean(symbol),
    staleTime: 2_500,
    refetchInterval: false,
  });

  const tick = asRecord(tickQ.data);
  const bid = num(tick.bid);
  const ask = num(tick.ask);
  const tickTimeMs = (() => {
    const raw = tick.timestamp ?? tick.time ?? tick.updated_at;
    if (typeof raw === "number" && Number.isFinite(raw)) {
      return raw < 1e12 ? raw * 1000 : raw;
    }
    if (typeof raw === "string" && raw.trim()) {
      const parsed = Date.parse(raw);
      return Number.isFinite(parsed) ? parsed : tickQ.dataUpdatedAt;
    }
    return tickQ.dataUpdatedAt || null;
  })();
  const lastPrice = useMemo(() => {
    if (Number.isFinite(bid) && Number.isFinite(ask)) return (bid + ask) / 2;
    const last = num(tick.last);
    return Number.isFinite(last) ? last : undefined;
  }, [bid, ask, tick.last]);

  const patchLayout = useCallback((partial: Partial<TerminalLayoutState>) => {
    setLayout((prev) => ({ ...prev, ...partial }));
  }, []);

  const onRightDelta = useCallback((d: number) => {
    setLayout((prev) => ({
      ...prev,
      rightWidth: Math.min(380, Math.max(280, prev.rightWidth - d)),
    }));
  }, []);
  const onBottomDelta = useCallback((d: number) => {
    setLayout((prev) => ({
      ...prev,
      bottomHeight: Math.min(280, Math.max(120, prev.bottomHeight - d)),
    }));
  }, []);

  const rightSplit = useResizeSplit(onRightDelta);
  const bottomSplit = useResizeSplit(onBottomDelta);

  const setBlotterTab = useCallback(
    (bottomTab: TerminalBlotterTab) => {
      patchLayout({ bottomTab, bottomCollapsed: false });
    },
    [patchLayout],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const current = layoutRef.current;
      if (e.key === "Escape") {
        ticketRef.current?.cancelDialog();
        if (current.chartFullscreen) patchLayout({ chartFullscreen: false });
        if (current.mobileTicketOpen) patchLayout({ mobileTicketOpen: false });
        setHelpOpen(false);
        return;
      }
      if (isTypingTarget(e.target)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      const k = e.key.toLowerCase();
      if (k === "b") {
        e.preventDefault();
        ticketRef.current?.buy();
        return;
      }
      if (k === "s") {
        e.preventDefault();
        ticketRef.current?.sell();
        return;
      }
      if (k === "1") {
        e.preventDefault();
        setBlotterTab("positions");
        return;
      }
      if (k === "2") {
        e.preventDefault();
        setBlotterTab("orders");
        return;
      }
      if (k === "3") {
        e.preventDefault();
        setBlotterTab("executions");
        return;
      }
      if (e.key === "]") {
        e.preventDefault();
        if (isMobile) {
          patchLayout({ mobileTicketOpen: !current.mobileTicketOpen });
        } else {
          patchLayout({ rightCollapsed: !current.rightCollapsed });
        }
        return;
      }
      if (e.key === "\\") {
        e.preventDefault();
        patchLayout({ bottomCollapsed: !current.bottomCollapsed });
        return;
      }
      if (k === "c") {
        e.preventDefault();
        patchLayout({ counselCollapsed: !current.counselCollapsed });
        return;
      }
      if (k === "f") {
        e.preventDefault();
        patchLayout({ chartFullscreen: !current.chartFullscreen });
        return;
      }
      if (e.key === "?" || (e.shiftKey && e.key === "/")) {
        e.preventDefault();
        setHelpOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [patchLayout, setBlotterTab, isMobile]);

  const showRight =
    !isMobile && !layout.rightCollapsed && !layout.chartFullscreen;
  const showBottom = !layout.bottomCollapsed && !layout.chartFullscreen;
  const showCounsel = !layout.chartFullscreen;

  const bidOk = Number.isFinite(bid) ? bid : undefined;
  const askOk = Number.isFinite(ask) ? ask : undefined;

  return (
    <div
      className="relative flex h-full min-h-0 flex-col overflow-hidden bg-[var(--bg)]"
      role="application"
      aria-label="QuantForg Terminal"
    >
      <header className="shrink-0">
        <div className="flex h-7 items-center justify-between gap-2 border-b border-[var(--border)]/70 px-2">
          <h1 className="shrink-0 text-[11px] font-semibold tracking-tight text-[var(--fg)]">
            Terminal
          </h1>
          <div className="flex items-center gap-0.5">
            {!isMobile ? (
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 px-0"
                aria-label={
                  layout.rightCollapsed ? "Expand ticket" : "Collapse ticket"
                }
                onClick={() =>
                  patchLayout({ rightCollapsed: !layout.rightCollapsed })
                }
              >
                {layout.rightCollapsed ? (
                  <PanelRightOpen className="h-4 w-4" />
                ) : (
                  <PanelRightClose className="h-4 w-4" />
                )}
              </Button>
            ) : null}
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-[11px]"
              onClick={() =>
                patchLayout({ bottomCollapsed: !layout.bottomCollapsed })
              }
            >
              {layout.bottomCollapsed ? "Blotter" : "Hide"}
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
        <TerminalSessionBar
          symbol={symbol}
          bid={bidOk}
          ask={askOk}
          realtime={realtime}
        />
        {showCounsel ? (
          <TerminalCounselStrip
            symbol={symbol}
            bid={bidOk}
            ask={askOk}
            collapsed={layout.counselCollapsed}
            onToggle={() =>
              patchLayout({ counselCollapsed: !layout.counselCollapsed })
            }
          />
        ) : null}
      </header>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div className="min-h-0 flex-1 overflow-hidden">
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
              onFullscreenChange={(chartFullscreen) =>
                patchLayout({ chartFullscreen })
              }
              lastPrice={lastPrice}
            />
          </div>

          {showBottom ? (
            <>
              <SplitHandle
                orientation="horizontal"
                label="Resize blotter"
                onStartDrag={bottomSplit.start("y")}
                onStep={onBottomDelta}
              />
              <div
                style={{ height: layout.bottomHeight }}
                className="min-h-0 shrink-0 overflow-hidden"
              >
                <TerminalBlotter
                  tab={layout.bottomTab}
                  onTabChange={setBlotterTab}
                />
              </div>
            </>
          ) : null}
        </div>

        {showRight ? (
          <>
            <SplitHandle
              orientation="vertical"
              label="Resize ticket"
              onStartDrag={rightSplit.start("x")}
              onStep={(d) => onRightDelta(-d)}
            />
            <div
              style={{ width: layout.rightWidth }}
              className="min-h-0 shrink-0 overflow-hidden"
            >
              <TerminalRightRail
                symbol={symbol}
                onSymbolChange={setSymbol}
                connected={connected}
                bid={bidOk}
                ask={askOk}
                tickTimeMs={tickTimeMs}
                ticketRef={ticketRef}
              />
            </div>
          </>
        ) : null}
      </div>

      {/* Mobile: floating Buy/Sell + ticket sheet */}
      {isMobile && !layout.chartFullscreen ? (
        <>
          <div
            className="pointer-events-none absolute inset-x-0 bottom-[4.75rem] z-20 flex justify-center gap-3 px-4"
            style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
          >
            <Button
              className="pointer-events-auto h-12 min-w-[7.5rem] flex-1 max-w-[10rem] text-base font-semibold shadow-[var(--shadow-elevated)]"
              disabled={!connected}
              onClick={() => {
                patchLayout({ mobileTicketOpen: true });
                window.setTimeout(() => ticketRef.current?.buy(), 60);
              }}
            >
              BUY
            </Button>
            <Button
              variant="danger"
              className="pointer-events-auto h-12 min-w-[7.5rem] flex-1 max-w-[10rem] text-base font-semibold shadow-[var(--shadow-elevated)]"
              disabled={!connected}
              onClick={() => {
                patchLayout({ mobileTicketOpen: true });
                window.setTimeout(() => ticketRef.current?.sell(), 60);
              }}
            >
              SELL
            </Button>
          </div>

          <div
            className={cn(
              "absolute inset-x-0 bottom-0 z-30 transition-transform duration-[var(--duration-os)] ease-[var(--ease-os)]",
              layout.mobileTicketOpen
                ? "translate-y-0"
                : "pointer-events-none translate-y-full",
            )}
            role="dialog"
            aria-modal="true"
            aria-label="Order ticket"
            aria-hidden={!layout.mobileTicketOpen}
          >
            <div
              className="mx-auto max-h-[78dvh] overflow-hidden rounded-t-2xl border border-b-0 border-[var(--border)] bg-[var(--bg-elevated)] shadow-2xl"
            >
              <div className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
                <p className="text-sm font-semibold">Order Ticket</p>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 px-0"
                  aria-label="Close ticket"
                  onClick={() => patchLayout({ mobileTicketOpen: false })}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="max-h-[calc(78dvh-2.75rem)] overflow-y-auto">
                <TerminalRightRail
                  symbol={symbol}
                  onSymbolChange={setSymbol}
                  connected={connected}
                  bid={bidOk}
                  ask={askOk}
                  tickTimeMs={tickTimeMs}
                  ticketRef={ticketRef}
                />
              </div>
            </div>
          </div>
          {layout.mobileTicketOpen ? (
            <button
              type="button"
              className="absolute inset-0 z-[25] bg-black/40"
              aria-label="Dismiss order ticket"
              onClick={() => patchLayout({ mobileTicketOpen: false })}
            />
          ) : null}
        </>
      ) : null}

      <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
        <DialogContent className="max-w-md">
          <DialogTitle>Terminal shortcuts</DialogTitle>
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
